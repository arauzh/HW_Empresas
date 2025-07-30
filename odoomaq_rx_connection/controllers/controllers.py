# -*- coding: utf-8 -*-
import json
from odoo import http, _
from odoo.http import request, Response
from datetime import datetime
import logging
from werkzeug.exceptions import BadRequest

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

            lang = request.env.user.lang
            
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
                return BadRequest(_(f"Company {company_name} not found"))

            # Moneda
            Currency = request.env['res.currency'].sudo().with_context(lang=lang)
            currency = Currency.search([('name', '=', currency_code)], limit=1)
            if not currency:
                return BadRequest(_(f"Currency {currency_code} not found"))

            # Crear orden de compra
            Purchase = request.env['purchase.order'].sudo().with_company(company.id)
            payment_term_obj = request.env['account.payment.term'].sudo().with_context(lang=lang).with_company(company.id).search([('name','=',payment_term)], limit=1)
            if not payment_term_obj:
                return BadRequest(_(f"Payment term {payment_term} not found"))
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
                ori_line_id  = line.get('origin_order_line_id')
                # Impuestos
                tax_list = []
                for tax_name in line.get('taxes', []):
                    tax = request.env['account.tax'].sudo().with_context(lang=lang).with_company(company.id).search([('name','=',tax_name)], limit=1)
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
                        'origin_order_line_id': ori_line_id,
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
            # return Response(str(e), status=500)
            return BadRequest(_(f"Error creating purchase order: {e}"))


    @http.route('/api/payroll/latest', type='json', auth='my_api_key', methods=['GET'], csrf=False)
    def get_latest_payslip_gross(self, **kwargs):
        try:
            Payslip = request.env['hr.payslip'].sudo()

            # 1) Recuperar todas las planillas ordenadas por empleado y fecha de inicio descendente
            slips = Payslip.search(
                [],
                order='employee_id asc, date_from desc'
            )

            data = []
            seen_employees = set()
            for slip in slips:
                emp_id = slip.employee_id.id
                # 2) Sólo procesar la primera planilla que aparezca para cada empleado
                if emp_id in seen_employees:
                    continue
                seen_employees.add(emp_id)

                # 3) Calcular salario bruto de esa planilla
                gross_amount = sum(
                    slip.line_ids
                        .filtered(lambda l: l.salary_rule_id.category_id.code == 'GROSS')
                        .mapped('amount')
                )
                
                # 4) Calcular total de horas trabajadas en esa planilla
                worked_hours = sum(slip.worked_days_line_ids.mapped('number_of_hours'))
                
                data.append({
                    'employee_id':   emp_id,
                    'registration_number':  slip.employee_id.registration_number,
                    'employee_name': slip.employee_id.name,
                    'payslip_name':  slip.name,
                    'date_from':     slip.date_from.isoformat(),
                    'gross_salary':  float(gross_amount),
                    'worked_hours':  float(worked_hours),
                })

            # print(data)
            if not data:
                return {'error': 'No se encontraron planillas'}

            return {'data': data}
            # return data

        except Exception as e:
            # Registrar error en logs de Odoo
            _logger.error('Error al obtener salarios brutos de la última planilla: %s', e, exc_info=True)
            # Responder con JSON de error
            return Response(str(e), status=500)
        
    @http.route('/api/connect/account_invoice', type='json', auth='my_api_key', methods=['POST'], csrf=False)
    def create_account_invoice(self, **payload):
        try:
            inv_vals = {
                'partner_name':             payload.get('partner_name'),
                'partner_vat':              payload.get('partner_vat'),
                'partner_is_compa':         payload.get('partner_is_company'),
                'ref':                      payload.get('ref'),
                'fac_serie':                payload.get('fac_serie'),
                'fac_numero':               payload.get('fac_numero'),
                'invoice_date':             payload.get('invoice_date'),
                'date':                     payload.get('date'),
                'currency':                 payload.get('currency'),
                'company':                  payload.get('company'),
                'payment_reference':        payload.get('payment_reference'),
                'invoice_payment_term_id':  payload.get('invoice_payment_term_id'),
                'journal_id':               payload.get('journal_id'),
                'x_studio_fact_odoomaq':    payload.get('x_studio_fact_odoomaq'),
                'narration':                payload.get('narration'),
                'lines':                    payload.get('lines', []),
            }
            # print(inv_vals)

            # Buscar compañía
            Company = request.env['res.company'].sudo()
            company = Company.search([('name', '=', inv_vals['company'])], limit=1)
            if not company:
                _logger.info(company)
                return BadRequest(_(f"Company {inv_vals['company']} not found"))
            
            # Partner
            partner = request.env['res.partner'].sudo().search([('vat','=',inv_vals['partner_vat'])], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create({'name': inv_vals['partner_name'], 'vat': inv_vals['partner_vat'], 'is_company': inv_vals['partner_is_compa']})
                
            # Currency
            currency = request.env['res.currency'].sudo().search([('name','=',inv_vals['currency'])], limit=1)
            if not currency:
                return BadRequest(_(f"Currency {inv_vals['currency']} not found"))
            
            # Invoice
            lang = request.env.user.lang
            Invoice = request.env['account.move'].sudo().with_company(company.id)
            origin = ','.join({str(ln.get('purchase_order_id')) for ln in inv_vals['lines'] if ln.get('purchase_order_id')})
            payment_term_obj = request.env['account.payment.term'].sudo().with_context(lang=lang).with_company(company.id).search([('name','=',inv_vals['invoice_payment_term_id'])], limit=1)
            # print(payment_term_obj)
            if not payment_term_obj:
                return BadRequest(_(f"Payment term {inv_vals['invoice_payment_term_id']} not found"))
            journal_obj = request.env['account.journal'].sudo().with_context(lang=lang).with_company(company.id).search([('name','=',inv_vals['journal_id'])], limit=1)
            # print(journal_obj)
            if not journal_obj:
                return BadRequest(_(f"Journal {inv_vals['journal_id']} not found"))
            
            inv_dict = {
                'move_type':                'in_invoice',
                'name':                     '/',
                'partner_id':               partner.id,
                'ref':                      inv_vals['ref'],
                'fac_serie':                inv_vals['fac_serie'],
                'fac_numero':               inv_vals['fac_numero'],
                'invoice_date':             inv_vals['invoice_date'],
                'date':                     inv_vals['date'],
                'payment_reference':        inv_vals['payment_reference'],
                'invoice_payment_term_id':  payment_term_obj.id if payment_term_obj else False,
                'currency_id':              currency.id,
                'journal_id':               journal_obj.id if journal_obj else False,
                'x_studio_fact_odoomaq':    inv_vals['x_studio_fact_odoomaq'],
                'invoice_origin':           origin,
                'invoice_line_ids':         [],
            }
            # invoice = Invoice.create()
            
            # Lines
            for ln in inv_vals['lines']:
                #Se busca la linea de orden de compra
                purchase_order_line_obj = request.env['purchase.order.line'].sudo().with_company(company.id).search([('order_id.name','=',ln.get('purchase_order_id')),('origin_order_line_id','=',ln.get('origin_order_line_id'))], limit=1)
                
                # Se crea la linea con relación a una orden de compra si los campos purchase_order_id y origin_order_line_id 
                # si traian datos y la linea de la orden de compra fue encontrada.
                if purchase_order_line_obj.order_id:
                    if purchase_order_line_obj.order_id.invoice_status != 'to invoice':
                        continue
                    
                    line_vals = purchase_order_line_obj._prepare_account_move_line()
                    
                    line_vals["name"] = ln.get('description', '')
                    line_vals["quantity"] = float(ln.get('quantity', 0))
                    line_vals["price_unit"] = float(ln.get('price', 0))
                    line_vals["discount"] = float(ln.get('discount', 0))
                    tax_ids = request.env['account.tax'].sudo().with_context(lang=lang).with_company(company.id).search([('name', 'in', ln.get('taxes', []))]).ids
                    line_vals["tax_ids"] = [(6, 0, tax_ids)]
                    
                    inv_dict['invoice_line_ids'].append((0, 0, line_vals))
                    
                else:
                    # Se crea la linea sin relación a una orden de compra si los campos purchase_order_id y origin_order_line_id no traen datos
                    prod = request.env['product.product'].sudo().search([('default_code', '=', ln.get('product'))], limit=1)
                    tax_ids = request.env['account.tax'].sudo().with_context(lang=lang).with_company(company.id).search([('name', 'in', ln.get('taxes', []))]).ids
                    inv_dict['invoice_line_ids'].append((0, 0, {
                        'product_id': prod.id if prod else False,
                        'name': ln.get('description', ''),
                        'quantity': float(ln.get('quantity', 0)),
                        'price_unit': float(ln.get('price', 0)),
                        'discount': float(ln.get('discount', 0)),
                        'tax_ids': [(6, 0, tax_ids)],
                    }))
            
            #Se crea la factura con los datos de inv_dict
            invoice = Invoice.create(inv_dict)
            
            if not invoice:
                return BadRequest(_(f"An unidentified error occurred while creating an invoice."))
                
            return {'success': True, 'invoice_id': invoice.id, 'invoice_name': invoice.name,}
        
        except Exception as e:
            _logger.info(payload)
            _logger.exception(_('Error creating invoice'))
            # return Response(str(e), status=500)
            return BadRequest(_(f"Error creating invoice: {e}"))