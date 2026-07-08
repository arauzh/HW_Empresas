# -*- coding: utf-8 -*-

from odoo import models, fields, api


class account_budget_type(models.Model):
    _name = 'account_budget_type.account_budget_type'
    _description = 'Account budget type'

    name = fields.Char()

