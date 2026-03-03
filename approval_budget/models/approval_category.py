# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

CATEGORY_SELECTION = [
    ('required', 'Required'),
    ('optional', 'Optional'),
    ('no', 'None')]

class ApprovalCategory(models.Model):
    _inherit = 'approval.category'
    
    has_budget = fields.Selection(CATEGORY_SELECTION, string="Has budget", default="no", required=True)
    
    @api.onchange('has_budget')
    def _onchange_has_budget(self):
        for record in self:
            if record.has_budget != "no":
                record.has_period = "required"
    
    @api.constrains('has_budget', 'has_period')
    def _check_budget_period_consistency(self):
        """
        Validación de seguridad al guardar:
        Si el presupuesto está activo, el periodo NO puede ser 'no' ni 'optional'.
        """
        for record in self:
            if record.has_budget in ['optional', 'required']:
                if record.has_period != 'required':
                    raise ValidationError(_(
                        "Configuration error: If budgeting is enabled (as optional or required), the Period field MUST be set to 'Required'."
                    ))