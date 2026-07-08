# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

# ---------------------------------------------------------
# Budgets
# ---------------------------------------------------------
class AccountBudgetPost(models.Model):
    _inherit = "account.budget.post"
    
    account_budget_type_id = fields.Many2one('account_budget_type.account_budget_type', string='Budget item type')