from odoo import http
from odoo.http import request
import json
from datetime import datetime


class PayrollAPI(http.Controller):

    def _authenticate(self):

        auth_header = request.httprequest.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        api_key = auth_header.split(" ")[1]

        user_id = request.env['res.users.apikeys']._check_credentials(
            scope="rpc",
            key=api_key
        )

        if not user_id:
            return None

        return request.env['res.users'].browse(user_id)

    @http.route(
        '/api/payslips',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False
    )
    def obtener_nominas(self, **kwargs):

        user = self._authenticate()

        if not user:
            return request.make_response(
                json.dumps({"error": "Unauthorized"}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )

        env = request.env

        date_from = kwargs.get('date_from')
        date_to = kwargs.get('date_to')

        try:
            if date_from:
                datetime.strptime(date_from, "%Y-%m-%d")
            if date_to:
                datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            return request.make_response(
                json.dumps({"error": "Formato de fecha inválido. Usa YYYY-MM-DD"}),
                headers=[('Content-Type', 'application/json')],
                status=400
            )

        domain = []

        if date_from and date_to:
            domain += [
                ('date_from', '<=', date_to),
                ('date_to', '>=', date_from)
            ]

        if kwargs.get('state'):
            domain.append(('state', '=', kwargs.get('state')))

        if kwargs.get('employee_id'):
            domain.append(('employee_id', '=', int(kwargs.get('employee_id'))))

        payslip_model = env['hr.payslip'].sudo()
        line_model = env['hr.payslip.line'].sudo()

        payslips = payslip_model.search(domain)

        payslip_fields = [
            "id",
            "name",
            "number",
            "employee_id",
            "payslip_run_id",
            "date_from",
            "date_to",
            "state"
        ]

        records = payslips.read(payslip_fields)

        all_lines = line_model.search([
            ('slip_id', 'in', payslips.ids),
            ('category_id.code', 'in', ['NET', 'COMP'])
        ])

        lines_by_slip = {}

        for line in all_lines:
            lines_by_slip.setdefault(line.slip_id.id, []).append(line)

        resultado = []

        for record in records:

            new_record = {}

            payslip = payslip_model.browse(record['id'])

            model = payslip_model

            for field_name, value in record.items():

                field = model._fields.get(field_name)

                if field and field.type == "many2one":

                    if value:
                        new_record[field_name] = value[0]
                        new_record[field_name.replace("_id", "_name")] = value[1]
                    else:
                        new_record[field_name] = None
                        new_record[field_name.replace("_id", "_name")] = None

                else:
                    new_record[field_name] = value

            employee = payslip.employee_id
            new_record["employee_code"] = getattr(employee, 'ref_hw', None)

            lines_data = []

            slip_lines = lines_by_slip.get(payslip.id, [])

            for line in slip_lines:

                lines_data.append({
                    "id": line.id,
                    "name": line.name,
                    "code": line.code,
                    "category": line.category_id.name if line.category_id else None,
                    "quantity": line.quantity,
                    "rate": line.rate,
                    "amount": line.amount,
                    "total": line.total
                })

            new_record["lines"] = lines_data

            resultado.append(new_record)

        return request.make_response(
            json.dumps(resultado, default=str),
            headers=[('Content-Type', 'application/json')],
            status=200
        )