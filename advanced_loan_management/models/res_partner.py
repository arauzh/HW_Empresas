# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    """Add new tab to display partner's loan count"""
    _inherit = "res.partner"

    def _compute_partner_loans(self):
        """This compute the loan amount and total loans count of a partner."""
        self.loan_count = self.env['loan.request'].search_count(
            [('partner_id', '=', self.id),
             ('state', 'in', ('disbursed', 'closed'))])

    loan_count = fields.Integer(string="Loan Count",
                                compute='_compute_partner_loans',
                                help="Displays numbers of loans "
                                     "ongoing and closed by the employee")

    def action_view_loans(self):
        """Returns loan records of current employee"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Loans',
            'view_mode': 'tree',
            'res_model': 'loan.request',
            'domain': [('partner_id', '=', self.id)],
            'context': "{'create': False}"
        }
