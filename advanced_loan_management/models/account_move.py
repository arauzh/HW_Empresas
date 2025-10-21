# -*- coding: utf-8 -*-

from odoo import models


class AccountMove(models.Model):
    """Alter loan repayment line state on draft and cancel button click"""
    _inherit = 'account.move'

    def button_draft(self):
        """Change repayment record state to 'invoiced'
        while reset to draft the invoice"""
        res = super().button_draft()
        loan_line_ids = self.env['repayment.line'].search([
            ('name', 'ilike', self.payment_reference)])
        if loan_line_ids:
            loan_line_ids.update({
                'state': 'invoiced',
                'invoice': True
            })
        return res

    def button_cancel(self):
        """Change repayment record state to 'unpaid'
        while cancelling the invoice"""
        res = super().button_cancel()
        for record in self:
            loan_line_ids = self.env['repayment.line'].search([
                ('name', 'ilike', record.payment_reference)])
            if loan_line_ids:
                loan_line_ids.update({
                    'state': 'unpaid',
                    'invoice': False
                })
        return res
