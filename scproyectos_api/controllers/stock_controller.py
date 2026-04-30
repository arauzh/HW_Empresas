# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from odoo.tools import float_round


class stockAPI(http.Controller):

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

    @http.route('/api/ingresosdeproductos', type='http', auth='none', methods=['GET'], csrf=False)
    def getIngregosDeProductos(self, **kwargs):
        
        user = self._authenticate()

        if not user:
            return request.make_json_response({
                'success': False,
                'message': 'Unauthorized'
            }, headers=[('Content-Type', 'application/json')], status=401)
        
        fecha_inicial = kwargs.get('fecha_inicial')
        fecha_final = kwargs.get('fecha_final')

        if not fecha_inicial or not fecha_final:
            return request.make_json_response({
                'success': False,
                'message': 'Debe enviar fecha_inicial y fecha_final en formato YYYY-MM-DD.'
            }, status=400)

        try:
            fecha_ini = datetime.strptime(fecha_inicial, '%Y-%m-%d')
            fecha_fin = datetime.strptime(fecha_final, '%Y-%m-%d')
        except ValueError:
            return request.make_json_response({
                'success': False,
                'message': 'Formato inválido. Use fecha_inicial y fecha_final en YYYY-MM-DD y product_id numérico.'
            }, status=400)
            
        fecha_ini_str = fecha_ini.strftime('%Y-%m-%d 06:00:00')
        
        fecha_fin_str = (fecha_fin + timedelta(days=1)).strftime('%Y-%m-%d 05:59:59')
        
        domain = [
            ('state', '=', 'done'),
            ('picking_id.date_done', '>=', fecha_ini_str),
            ('picking_id.date_done', '<=', fecha_fin_str),
            ('location_id.usage', 'in', ['supplier']),
            ("product_id.type", "=", "product"),
        ]

        moves = request.env['stock.move'].sudo().search(
            domain,
            order='id'
        )
        data = []
        total_quantity = 0.0
        total_cost = 0.0

        for move in moves:
            qty = move.quantity or 0.0
            uom = move.product_uom
            uom_rounding = uom.rounding if uom else 0.01

            valuation_layers = request.env['stock.valuation.layer'].sudo().search([
                ('stock_move_id', '=', move.id)
            ])

            line_cost = abs(sum(valuation_layers.mapped('value')))
            unit_cost = line_cost / qty if qty else 0.0

            quantity = float_round(
                qty,
                precision_rounding=uom_rounding
            )

            analytic_result = []
            if move.analytic_distribution:
                id_string = list(move.analytic_distribution.keys())[0]
                analytic_ids = [int(id) for id in id_string.split(',')]
                accounts = request.env['account.analytic.account'].sudo().browse(analytic_ids)
                if accounts:
                    for account in accounts:
                        analytic_result.append({'id': account.id,'name': account.name})

            data.append({
                'move_id': move.id,
                'picking_id': move.picking_id.id if move.picking_id else False,
                'picking_name': move.picking_id.name if move.picking_id else False,
                'date_done': move.picking_id.date_done.isoformat() if move.picking_id and move.picking_id.date_done else False,

                'company_id': move.company_id.id if move.company_id else False,
                'company_name': move.company_id.name if move.company_id else False,
                
                'product_id': move.product_id.id if move.product_id else False,
                'product_code': move.product_id.default_code if move.product_id else '',
                'product_name': move.product_id.name if move.product_id else '',
                'analytic_distribution': analytic_result,
                'quantity': quantity,
                'unit_cost': round(unit_cost, 2),
                'total_cost': round(line_cost, 2),
            })

            total_quantity += qty
            total_cost += line_cost

        return request.make_json_response({
            'success': True,
            'fecha_inicial': fecha_inicial,
            'fecha_final': fecha_final,
            'count': len(data),
            'data': data,
        }, status=200)