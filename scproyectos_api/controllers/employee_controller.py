from odoo import http
from odoo.http import request
import json


class EmployeeAPI(http.Controller):

    def _authenticate(self):

        auth_header = request.httprequest.headers.get("Authorization")

        if not auth_header:
            return None

        if not auth_header.startswith("Bearer "):
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
        '/api/employees',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False
    )
    def obtener_empleados(self, **kwargs):

        user = self._authenticate()

        if not user:
            return request.make_response(
                json.dumps({"error": "Unauthorized"}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )

        domain = [
            ('active', '=', True)
        ]

        employees = request.env['hr.employee'].sudo().search(domain)

        fields_to_read = [
            "id",
            "name",
            "work_email",
            "company_id",
            "department_id",
            "job_id",
            "ref_hw"
        ]

        records = employees.read(fields_to_read)

        contract_fields = [
            "structure_type_id",
            "wage",
            "date_start",
            "date_end",
            "resource_calendar_id",
            "wage_type",
            "schedule_pay",
            "wage",
            "hourly_wage",
            "tipo_planilla_id",
            "bono_especial",
            "bono_decreto",
            "sueldo_diario",
            "bonificacion_diario",
            "analytic_account_id"
        ]

        model = request.env['hr.employee']
        resultado = []

        for record in records:

            new_record = {}

            employee = request.env['hr.employee'].browse(record['id'])

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

            contracts_data = []

            contracts = request.env['hr.contract'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'open')
            ])

            for contract in contracts:

                contract_record = contract.read(contract_fields)[0]

                new_contract = {}

                contract_model = request.env['hr.contract']

                for field_name, value in contract_record.items():

                    field = contract_model._fields.get(field_name)

                    if field and field.type == "many2one":

                        if value:
                            new_contract[field_name] = value[0]
                            new_contract[field_name.replace("_id", "_name")] = value[1]
                        else:
                            new_contract[field_name] = None
                            new_contract[field_name.replace("_id", "_name")] = None

                    else:
                        new_contract[field_name] = value

                contracts_data.append(new_contract)

            new_record["contracts"] = contracts_data

            resultado.append(new_record)

        return request.make_response(
            json.dumps(resultado, default=str),
            headers=[('Content-Type', 'application/json')],
            status=200
        )