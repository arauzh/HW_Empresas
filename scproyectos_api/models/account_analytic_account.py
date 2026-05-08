# -*- coding: utf-8 -*-

from odoo import api, fields, models

class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"
    
    send_to_project = fields.Boolean(
        string='Enviar a proyecto',
        help='Al estar activado se tomará esta cuenta analítica en la validación del api de factura que serán enviadas a OdooProyectos.', default=False
    )