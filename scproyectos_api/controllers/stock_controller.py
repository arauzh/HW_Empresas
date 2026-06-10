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
        
        try:
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
                    'partner_id': move.picking_id.partner_id.id if move.picking_id.partner_id else False,
                    'partner_name': move.picking_id.partner_id.name if move.picking_id.partner_id else False,
                    'partner_vat': move.picking_id.partner_id.vat if move.picking_id.partner_id else False,
                    'warehouse_id': move.picking_id.picking_type_id.warehouse_id.id if move.picking_id else False,
                    'warehouse_name': move.picking_id.picking_type_id.warehouse_id.name if move.picking_id else False,
                    'date_done': move.picking_id.date_done.isoformat() if move.picking_id and move.picking_id.date_done else False,

                    'company_id': move.company_id.id if move.company_id else False,
                    'company_name': move.company_id.name if move.company_id else False,
                    
                    'location_dest_id': move.location_dest_id.id if move.location_dest_id else False,
                    'location_dest_name': move.location_dest_id.display_name if move.location_dest_id else False,
                    'product_id': move.product_id.id if move.product_id else False,
                    'product_code': move.product_id.default_code if move.product_id else '',
                    'product_name': move.product_id.name if move.product_id else '',
                    'product_type': move.product_id.detailed_type if move.product_id else '',
                    'categ_id': move.product_id.categ_id.id if move.product_id.categ_id else '',
                    'categ_name': move.product_id.categ_id.display_name if move.product_id.categ_id else '',
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
        except Exception as e:
            return request.make_json_response({
                'success': False,
                'message': str(e),
                'type': 'server_error'
            }, status=400)
        
    @http.route('/api/salidasdeproductos', type='http', auth='none', methods=['POST'], csrf=False)
    def postSalidasDeProductos(self, **kwargs):

        try:
            # 1. Autenticación
            user = self._authenticate()
            if not user:
                return request.make_json_response({
                    'success': False,
                    'message': 'Unauthorized'
                }, status=401)

            # 2. Datos del JSON y Compañía
            data = request.get_json_data()

            company_id = data.get('company_id')
            if not company_id:
                return request.make_json_response({
                    'success': False,
                    'message': 'Faltan datos: company_id'
                }, status=400)

            company = request.env['res.company'].sudo().search([
                ('id', '=', company_id)
            ], limit=1)

            if not company:
                return request.make_json_response({
                    'success': False,
                    'message': 'Compania no encontrada'
                }, status=400)

            # 3. Crear entorno con el usuario
            env = request.env(user=user)

            partner_id = data.get('partner_id', 0)
            partner_vat = data.get('partner_vat')
            partner_name = data.get('partner_name')
            partner_iscompa = data.get('partner_iscompa')
            warehouse_id = data.get('warehouse_id')
            productos = data.get('productos', [])

            if not partner_id and not partner_vat:
                return request.make_json_response({
                    'success': False,
                    'message': 'Faltan datos: No se envio ni partner_id, ni partner_vat'
                }, status=400)

            if not warehouse_id:
                return request.make_json_response({
                    'success': False,
                    'message': 'Faltan datos: warehouse_id'
                }, status=400)

            if not productos:
                return request.make_json_response({
                    'success': False,
                    'message': 'Debe enviar al menos un producto.'
                }, status=400)

            # 4. Obtener información del Partner
            partner = request.env['res.partner'].sudo().search([
                ('id', '=', partner_id)
            ], limit=1)

            if not partner:
                if not partner_vat:
                    return request.make_json_response({
                        'success': False,
                        'message': 'Faltan datos: partner_vat'
                    }, status=400)
                    
                partner = request.env['res.partner'].sudo().search([
                    ('vat', '=', partner_vat)
                ], limit=1)

                if not partner:
                    if not partner_name:
                        return request.make_json_response({
                            'success': False,
                            'message': 'Partner no encontrado y partner_name es vacío.'
                        }, status=400)

                    partner = request.env['res.partner'].sudo().create({
                        'name': partner_name,
                        'vat': partner_vat,
                        'is_company': partner_iscompa,
                    })

            # 5. Buscar almacén origen
            warehouse_origin = env['stock.warehouse'].sudo().search([
                ('id', '=', warehouse_id),
                ('company_id', '=', company_id)
            ], limit=1)

            if not warehouse_origin:
                return request.make_json_response({
                    'success': False,
                    'message': 'Almacén origen no encontrado.'
                }, status=400)

            # 6. Buscar Tipo de Operación de salida
            picking_type = env['stock.picking.type'].sudo().search([
                ('code', '=', 'outgoing'),
                ('warehouse_id', '=', warehouse_origin.id),
                ('company_id', '=', company_id)
            ], limit=1)

            if not picking_type:
                return request.make_json_response({
                    'success': False,
                    'message': 'Operación de entrega no configurada para este almacén/compañía'
                }, status=400)

            # 7. Verificar si el partner corresponde a un almacén destino
            warehouse_dest = env['stock.warehouse'].sudo().search([
                ('partner_id', '=', partner.id),
                ('company_id', '=', company_id)
            ], limit=1)

            is_inventory_transfer = bool(warehouse_dest)

            # 8. Ubicación destino de la salida
            # if picking.picking_type_id.default_location_src_id:
            #     location_id = picking.picking_type_id.default_location_src_id.id
            # elif picking.partner_id:
            #     location_id = picking.partner_id.property_stock_supplier.id
            # else:
            #     _customerloc, location_id = self.env['stock.warehouse']._get_partner_locations()
            
            # if picking_type.default_location_dest_id:
            #     location_dest_id = picking_type.default_location_dest_id.id
            # elif picking.partner_id:
            #     location_dest_id = picking.partner_id.property_stock_customer.id
            # else:
            #     location_dest_id, _supplierloc = self.env['stock.warehouse']._get_partner_locations()

            # 9. Crear salida
            picking_vals = {
                'partner_id': partner.id,
                'picking_type_id': picking_type.id,
                # 'location_id': location_id,
                # 'location_dest_id': location_dest_id,
                'origin': data.get('referencia', 'API Delivery'),
                'company_id': company_id,
            }

            picking = env['stock.picking'].create(picking_vals)

            moves = []

            for line in productos:
                product = env['product.product'].browse(line.get('product_id'))

                if not product.exists():
                    return request.make_json_response({
                        'success': False,
                        'message': 'Producto no encontrado: %s' % line.get('product_id')
                    }, status=400)

                cantidad = line.get('cantidad')

                if not cantidad or cantidad <= 0:
                    return request.make_json_response({
                        'success': False,
                        'message': 'Cantidad inválida para el producto: %s' % product.display_name
                    }, status=400)

                move_vals = {
                    'name': product.display_name or 'Salida API',
                    'picking_id': picking.id,
                    'product_id': product.id,
                    'product_uom_qty': cantidad,
                    'quantity': cantidad,
                    'product_uom': product.uom_id.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'company_id': company_id,
                }

                moves.append(move_vals)

            env['stock.move'].create(moves)

            # 10. Si es traslado de inventario, crear recepción en almacén destino
            receipt = False

            if is_inventory_transfer:
                incoming_type = env['stock.picking.type'].sudo().search([
                    ('code', '=', 'incoming'),
                    ('warehouse_id', '=', warehouse_dest.id),
                    ('company_id', '=', company_id)
                ], limit=1)

                if not incoming_type:
                    return request.make_json_response({
                        'success': False,
                        'message': 'Operación de recepción no configurada para el almacén destino.'
                    }, status=400)

                receipt_location_dest_id = (
                    incoming_type.default_location_dest_id.id
                    or warehouse_dest.lot_stock_id.id
                )

                receipt_vals = {
                    'partner_id': partner.id,
                    'picking_type_id': incoming_type.id,
                    'location_id': picking.location_dest_id.id,
                    'location_dest_id': receipt_location_dest_id,
                    'origin': picking.name,
                    'company_id': company_id,
                }

                receipt = env['stock.picking'].create(receipt_vals)

                receipt_moves = []

                for line in productos:
                    product = env['product.product'].browse(line.get('product_id'))
                    cantidad = line.get('cantidad')

                    receipt_moves.append({
                        'name': product.display_name or 'Recepción API',
                        'picking_id': receipt.id,
                        'product_id': product.id,
                        'product_uom_qty': cantidad,
                        'quantity': cantidad,
                        'product_uom': product.uom_id.id,
                        'location_id': receipt.location_id.id,
                        'location_dest_id': receipt.location_dest_id.id,
                        'company_id': company_id,
                    })

                env['stock.move'].create(receipt_moves)

            return request.make_json_response({
                'success': True,
                'is_inventory_transfer': is_inventory_transfer,
                'picking_id': picking.id,
                'name': picking.name,
                'state': picking.state,
                'receipt_id': receipt.id if receipt else False,
                'receipt_name': receipt.name if receipt else False,
                'receipt_state': receipt.state if receipt else False,
            }, status=201)

        except Exception as e:
            return request.make_json_response({
                'success': False,
                'message': str(e),
                'type': 'server_error'
            }, status=400)