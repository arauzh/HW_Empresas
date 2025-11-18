# -*- coding: utf-8 -*-

from odoo import fields, models

class ResCompany(models.Model):
    _inherit = ["res.company"]
    
    interest_product_id = fields.Many2one('product.product',
                                             string="Interest Product",
                                             check_company=True,
                                             help="Product For Interest "
                                                  "To Create Invoice Lines")
    repayment_product_id = fields.Many2one('product.product',
                                             string="Repayment Product",
                                             check_company=True,
                                             help="Product For Repayment "
                                                  "To Create Invoice Lines")
    interest_account_id = fields.Many2one('account.account',
                                             string="Interest account",
                                             # domain="[('account_type', '=', 'liability_current')]",
                                             check_company=True,
                                             help="Loan management interest accounts")
    disbursement_account_id = fields.Many2one('account.account',
                                             string="Disbursement account",
                                             # domain="[('account_type', '=', 'liability_current')]",
                                             check_company=True,
                                             help="Loan management disburse accounts")
    repayment_account_id = fields.Many2one('account.account',
                                             string="Repayment accounts",
                                             # domain="[('account_type', '=', 'asset_cash')]",
                                             check_company=True,
                                             help="Loan payment account")


class ResConfigSettings(models.TransientModel):
    """Add new fields to display service products"""
    _inherit = 'res.config.settings'

    interest_product_id = fields.Many2one('product.product',                                          
                                             related='company_id.interest_product_id',
                                             string="Interest Product",
                                             # config_parameter="advanced_loan_management.interest_product_id",
                                             check_company=True, readonly=False,
                                             help="Product For Interest "
                                                  "To Create Invoice Lines")
    repayment_product_id = fields.Many2one('product.product',
                                             related='company_id.repayment_product_id',
                                             string="Repayment Product",
                                             # config_parameter="advanced_loan_management.repayment_product_id",
                                             check_company=True, readonly=False,
                                             help="Product For Repayment "
                                                  "To Create Invoice Lines")
    interest_account_id = fields.Many2one('account.account',
                                             related='company_id.interest_account_id',
                                             string="Interest account",
                                             # config_parameter="advanced_loan_management.interest_account_id",
                                             # domain="[('account_type', '=', 'liability_current'),('company_id', '=', company_id)]",
                                             domain="[('company_id', '=', company_id)]",
                                             check_company=True, readonly=False,
                                             help="Loan management interest accounts")
    disbursement_account_id = fields.Many2one('account.account',
                                             related='company_id.disbursement_account_id',
                                             string="Disbursement account",
                                             # config_parameter="advanced_loan_management.disbursement_account_id",
                                             # domain="[('account_type', '=', 'liability_current'),('company_id', '=', company_id)]",
                                             domain="[('company_id', '=', company_id)]",
                                             check_company=True, readonly=False,
                                             help="Loan management disburse accounts")
    repayment_account_id = fields.Many2one('account.account',
                                             related='company_id.repayment_account_id',
                                             string="Repayment accounts",
                                             # config_parameter="advanced_loan_management.repayment_account_id",
                                             # domain="[('account_type', '=', 'asset_cash'),('company_id', '=', company_id)]",
                                             domain="[('company_id', '=', company_id)]",
                                             check_company=True, readonly=False,
                                             help="Loan payment account")
