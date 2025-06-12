# -*- coding: utf-8 -*-
# from odoo import http


# class AccountPassword(http.Controller):
#     @http.route('/account_password/account_password', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/account_password/account_password/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('account_password.listing', {
#             'root': '/account_password/account_password',
#             'objects': http.request.env['account_password.account_password'].search([]),
#         })

#     @http.route('/account_password/account_password/objects/<model("account_password.account_password"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('account_password.object', {
#             'object': obj
#         })

