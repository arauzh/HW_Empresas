# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError

from collections import defaultdict


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'
    
    has_budget = fields.Selection(related="category_id.has_budget")
    approval_budget_ids = fields.One2many('approval.budget', 'approval_request_id', check_company=True)
    
    def unlink(self):
        self.filtered(lambda a: a.has_budget).approval_budget_ids.unlink()
        return super().unlink()