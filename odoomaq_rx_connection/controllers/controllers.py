# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request, Response
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)


class OdoomaqRxConnection(http.Controller):
    
    @http.route('/api/connect/odoomaq', auth='my_api_key')
    def index(self, **kw):
        return "Hello, world"

    @http.route('/api/connect/purchase_order', type='json', auth='my_api_key', methods=['POST'], csrf=False)
    def create_purchase_order(self, **payload):
        '''Recibe JSON con cabecera y líneas, crea, confirma y bloquea la orden.'''
        try:            
            # payload = json.loads(request.httprequest.data)
            # _logger.info(payload)
            # Cabecera de la orden
            vendor_name   = payload.get('vendor_name')
            vendor_nit    = payload.get('vendor_nit')
            VenIsCompa    = payload.get('vendor_is_company')
            vendor_ref    = payload.get('vendor_ref')
            currency_code = payload.get('currency')
            company_name  = payload.get('company')
            date_planned  = payload.get('expected_date')  # YYYY-MM-DD
            date_order    = payload.get('date_order')   # YYYY-MM-DD
            priority      = payload.get('priority')
            origin        = payload.get('origin')
            payment_term  = payload.get('payment_term')
            terms         = payload.get('terms')

            # Buscar o crear proveedor
            Partner = request.env['res.partner'].sudo()
            partner = Partner.search([('vat', '=', vendor_nit)], limit=1)
            if not partner:
                partner = Partner.create({
                    'name': vendor_name,
                    'vat': vendor_nit,
                    'is_company': VenIsCompa,
                })

            # Buscar compañía
            Company = request.env['res.company'].sudo()
            company = Company.search([('name', '=', company_name)], limit=1)
            if not company:
                _logger.info(company)
                return {'error': _(f'Company {company_name} not found')}

            # Moneda
            Currency = request.env['res.currency'].sudo()
            currency = Currency.search([('name', '=', currency_code)], limit=1)
            if not currency:
                return {'error': _(f'Currency  {currency_code} not found')}

            # Crear orden de compra
            Purchase = request.env['purchase.order'].sudo().with_company(company.id)
            payment_term_obj = request.env['account.payment.term'].sudo().search([('name','=',payment_term)], limit=1)
            order_vals = {
                'partner_id': partner.id,
                'partner_ref': vendor_ref,
                'currency_id': currency.id,
                'company_id': company.id,
                'date_planned': date_order,
                'date_order': date_order,
                'priority': priority,
                'origin': origin,
                'payment_term_id': payment_term_obj.id if payment_term_obj else False,
                'notes': terms,
                'user_id': 1,
            }
            purchase = Purchase.create(order_vals)

            # Detalles de líneas
            lines = payload.get('lines', [])
            for line in lines:
                product_code = line.get('product')
                qty          = float(line.get('quantity', 0))
                desc         = line.get('description')
                price        = float(line.get('price', 0))
                discount     = float(line.get('discount', 0))
                # Impuestos
                tax_list = []
                for tax_name in line.get('taxes', []):
                    tax = request.env['account.tax'].sudo().search([('name','=',tax_name)], limit=1)
                    if tax:
                        tax_list.append(tax.id)
                # Producto
                product = request.env['product.product'].sudo().search([('default_code','=',product_code)], limit=1)

                purchase.write({
                    'order_line': [(0, 0, {
                        'product_id': product.id if product else False,
                        'name': desc or (product.name if product else ''),
                        'product_qty': qty,
                        'price_unit': price,
                        'discount': discount,
                        'taxes_id': [(6, 0, tax_list)],
                    })]
                })

            # Confirmar orden
            purchase.button_confirm()
            # Bloquea orden
            purchase.button_done()
            
            # Retornar éxito, ID y nombre de la orden
            return {
                'success': True,
                'order_id': purchase.id,
                'order_name': purchase.name,
            }

        except Exception as e:
            _logger.info(payload)
            _logger.exception(_('Error creating purchase order'))
            return Response(str(e), status=500)

