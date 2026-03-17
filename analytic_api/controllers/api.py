from odoo import http
from odoo.http import request
import json


class AnalyticAccountAPI(http.Controller):

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
        '/api/analytic-accounts',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False
    )
    def obtener_cuentas_analiticas(self, **kwargs):

        user = self._authenticate()

        if not user:
            return request.make_response(
                json.dumps({"error": "Unauthorized"}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )

        # Puedes ajustar dominio si necesitas filtrar
        domain = []

        accounts = request.env['account.analytic.account'].sudo().search(domain)

        fields_to_read = [
            "name",
            "code",
            "partner_id",
            "plan_id",
            "company_id",
        ]

        records = accounts.read(fields_to_read)

        model = request.env['account.analytic.account']
        resultado = []

        for record in records:

            new_record = {}

            for field_name, value in record.items():

                field = model._fields.get(field_name)

                # Detectar campos many2one
                if field and field.type == "many2one":

                    if value:
                        new_record[field_name] = value[0]
                        new_record[field_name.replace("_id", "_name")] = value[1]
                    else:
                        new_record[field_name] = None
                        new_record[field_name.replace("_id", "_name")] = None

                else:
                    new_record[field_name] = value

            resultado.append(new_record)

        return request.make_response(
            json.dumps(resultado, default=str),
            headers=[('Content-Type', 'application/json')],
            status=200
        )