# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """Add new fields to display service products"""
    _inherit = 'res.config.settings'

    interest_product_id = fields.Many2one('product.product',
                                          string="Interest Product",
                                          config_parameter="advanced_loan_management.interest_product_id",
                                          check_company=True,
                                          help="Product For Interest "
                                               "To Create Invoice Lines")
    repayment_product_id = fields.Many2one('product.product',
                                           string="Repayment Product",
                                           config_parameter="advanced_loan_management.repayment_product_id",
                                           check_company=True,
                                           help="Product For Repayment "
                                                "To Create Invoice Lines")
    disbursement_account_id = fields.Many2one('account.account',
                                           string="Disbursement account",
                                           config_parameter="advanced_loan_management.disbursement_account_id",
                                           domain="[('account_type', '=', 'liability_current'),('company_id', '=', company_id)]",
                                           check_company=True,
                                           help="Loan management disburse accounts")
    repayment_account_id = fields.Many2one('account.account',
                                           string="Repayment accounts",
                                           config_parameter="advanced_loan_management.repayment_account_id",
                                           domain="[('account_type', '=', 'asset_cash'),('company_id', '=', company_id)]",
                                           check_company=True,
                                           help="Loan payment account")
