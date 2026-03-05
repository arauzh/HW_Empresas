# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError

from collections import defaultdict


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'
    
    has_budget = fields.Selection(related="category_id.has_budget")
    approval_budget_ids = fields.One2many('approval.budget', 'approval_request_id', check_company=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    planned_total = fields.Monetary('Planned total', default=0.0)
    total_executed = fields.Monetary('Total executed', default=0.0)
    
    def unlink(self):
        self.filtered(lambda a: a.has_budget).approval_budget_ids.unlink()
        return super().unlink()
    
    @api.onchange(
    'approval_budget_ids',
    'approval_budget_ids.planned_amount',
    'approval_budget_ids.display_type'
    )
    def _onchange_budget_total(self):
        for req in self:
            totalp = 0.0
            totalE = 0.0
            for line in req.approval_budget_ids:
                if not line.display_type:
                    totalp += (line.planned_amount or 0.0)
                    totalE += (line.executed_amount or 0.0)
            req.planned_total = totalp
            req.total_executed = totalE