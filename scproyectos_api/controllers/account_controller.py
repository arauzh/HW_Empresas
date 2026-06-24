# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from odoo.tools import float_round


class AccountAPI(http.Controller):

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

    @http.route('/api/facturas', type='http', auth='none', methods=['GET'], csrf=False)
    def getAccountMove(self, **kwargs):
        
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
                
            fecha_ini_str = fecha_ini.strftime('%Y-%m-%d')
            
            fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')
            
            accounts_anali = request.env['account.analytic.account'].sudo().search([('send_to_project', '=', True)])
            analytic_list = [account.id for account in accounts_anali]
            domain = [
                ('state', '=', 'posted'),
                ('invoice_date', '>=', fecha_ini_str),
                ('invoice_date', '<=', fecha_fin_str),
                ("invoice_line_ids.distribution_analytic_account_ids", "in", analytic_list),
            ]
            
            moves = request.env['account.move'].sudo().search(
                domain,
                order='id'
            )
            
            data = []
            for move in moves:
                
                lines = []
                for line in move.invoice_line_ids:
                    # analytic_result = []
                    # if line.analytic_distribution:
                    #     id_string = list(line.analytic_distribution.keys())[0]
                    #     analytic_ids = [int(id) for id in id_string.split(',')]
                    #     accounts = request.env['account.analytic.account'].sudo().browse(analytic_ids)
                    #     if accounts:
                    #         for account in accounts:
                    #             analytic_result.append({'id': account.id,'name': account.name})
                                
                    lines.append({
                        'product_code':line.product_id.default_code,
                        'product_name':line.product_id.name,
                        'description':line.name,
                        'analytic_distribution':line.analytic_distribution if line.analytic_distribution else [],
                        'quantity':line.quantity,
                        'price_unit':line.price_unit,
                        'discount':line.discount,
                        'taxes': [tax.name for tax in line.tax_ids],
                        })
                    
                data.append({
                    'name': move.name,
                    'partner_name': move.partner_id.name,
                    'partner_vat': move.partner_id.vat,
                    'partner_is_company': 1 if move.partner_id.is_company else 0,
                    'ref': move.ref or '',
                    'fac_serie': move.fac_serie or '',
                    'fac_numero': move.fac_numero or '',
                    'invoice_date': move.invoice_date.strftime('%Y-%m-%d') if move.invoice_date else False,
                    'date': move.date.strftime('%Y-%m-%d') if move.date else False,
                    'currency': move.currency_id.name,
                    'company_id': move.company_id.id,
                    'company_name': move.company_id.name,
                    'payment_reference': move.payment_reference  or '',
                    'invoice_payment_term_id': move.invoice_payment_term_id.name or '',
                    'journal_id': move.journal_id.name or '',
                    'narration': move.narration or '',
                    'lines': lines,
                })
                
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

    @http.route('/api/diarios', type='http', auth='none', methods=['GET'], csrf=False)
    def getJournals(self, **kwargs):

        try:

            user = self._authenticate()

            if not user:
                return request.make_json_response({
                    'success': False,
                    'message': 'Unauthorized'
                }, headers=[('Content-Type', 'application/json')], status=401)

            journals = request.env['account.journal'].sudo().search(
                [],
                order='code'
            )

            data = []

            for journal in journals:

                company = journal.company_id.sudo()
                currency = journal.currency_id.sudo() if journal.currency_id else company.currency_id.sudo()

                data.append({
                    'id': journal.id,
                    'name': journal.name,
                    'code': journal.code,
                    'type': journal.type,

                    'company_id': company.id,
                    'company_name': company.name,

                    'currency_id': currency.id if currency else False,
                    'currency_name': currency.name if currency else False,
                    'currency_symbol': currency.symbol if currency else False,

                    'active': journal.active,

                    'default_account_id': journal.default_account_id.id if journal.default_account_id else False,
                    'default_account_name': journal.default_account_id.display_name if journal.default_account_id else False,

                    'suspense_account_id': journal.suspense_account_id.id if journal.suspense_account_id else False,
                    'suspense_account_name': journal.suspense_account_id.display_name if journal.suspense_account_id else False,

                    'profit_account_id': journal.profit_account_id.id if journal.profit_account_id else False,
                    'profit_account_name': journal.profit_account_id.display_name if journal.profit_account_id else False,

                    'loss_account_id': journal.loss_account_id.id if journal.loss_account_id else False,
                    'loss_account_name': journal.loss_account_id.display_name if journal.loss_account_id else False,
                })

            return request.make_json_response({
                'success': True,
                'count': len(data),
                'data': data,
            }, status=200)

        except Exception as e:

            return request.make_json_response({
                'success': False,
                'message': str(e),
                'type': 'server_error'
            }, status=400)
    
    @http.route('/api/account_account', type='http', auth='none', methods=['GET'], csrf=False)
    def getAccountMove(self, **kwargs):
        try:
            user = self._authenticate()

            if not user:
                return request.make_json_response({
                    'success': False,
                    'message': 'Unauthorized'
                }, headers=[('Content-Type', 'application/json')], status=401)
            
            accounts = request.env['account.account'].sudo().search(
                domain=[],
                order='id'
            )
            
            data = []
            for account in accounts:
                data.append({
                    'Id': account.id,
                    'code': account.code,
                    'name': account.name,
                    'account_type': account.account_type,
                    'currency_id': account.currency_id.id if account.currency_id else False,
                    'currency_name': account.currency_id.name if account.currency_id else False,
                    'company_id': account.company_id.id if account.company_id else False,
                    'company_name': account.company_id.name if account.company_id else False,
                    'deprecated': account.deprecated,
                })
            
            return request.make_json_response({
                'success': True,
                'count': len(data),
                'data': data,
            }, status=200)
        except Exception as e:
            return request.make_json_response({
                'success': False,
                'message': str(e),   
                'type': 'server_error'
            }, status=400)