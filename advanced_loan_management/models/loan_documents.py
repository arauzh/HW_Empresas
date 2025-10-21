# -*- coding: utf-8 -*-

from odoo import fields, models


class LoanDocuments(models.Model):
    """Documents required to approve loan, eg:-Aadhar, Pan"""
    _name = 'loan.documents'
    _description = 'Loan Documents'
    _rec_name = 'loan_proofs'

    loan_proofs = fields.Char(string="Proofs", help="Document name "
                                                    "for identification")
    company_id = fields.Many2one('res.company', string='Company',
                                 readonly=True,
                                 help="Company Name",
                                 default=lambda self:
                                 self.env.company)
