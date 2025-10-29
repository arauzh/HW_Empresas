# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math


class LoanRequest(models.Model):
    """Can create new loan requests and manage records"""
    _name = 'loan.request'
    _inherit = ['mail.thread']
    _description = 'Loan Request'
    _order = 'id desc, name desc'

    name = fields.Char(string='Loan Reference', readonly=True,
                       copy=False, help="Sequence number for loan requests",
                       default=lambda self: 'New')
    company_id = fields.Many2one('res.company', string='Company',
                                 readonly=True,
                                 help="Company Name",
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  required=True, help="Currency",
                                  default=lambda self: self.env.user.company_id.
                                  currency_id)
    loan_type_id = fields.Many2one('loan.type', string='Loan Type',
                                   required=True, help="Can choose different "
                                                       "loan types suitable")
    loan_amount = fields.Float(string="Loan Amount",
                               help="Total loan amount", )
    processing_fee = fields.Float(string="Processing Fee",
                                    help="Amount For Initializing The Loan")
    disbursal_amount = fields.Float(string="Disbursal Amount",
                                    compute='_compute_disbursal_amount',
                                    help="Total loan amount "
                                         "available to disburse")
    tenure = fields.Integer(string="Tenure", default=1,
                            help="Installment period")
    interest_rate = fields.Float(string="Interest Rate", help="Interest percentage", default=1)
    rate_fee = fields.Float(string="Fee rate", compute='_compute_rate_fee', digits=(16, 10), store=True,
                            help="Percentage rate of quota")
    periodic_payment = fields.Float(string="Periodic payment", compute='_compute_rate_fee', digits=(16, 8), store=True,
                            help="Periodic payment")
    date = fields.Date(string="First payment date", default=fields.Date.today(), 
                       required=True, help="First payment date")
    disbursal_date = fields.Date(string="Disbursal date", default=fields.Date.today(), 
                       required=True, help="Disbursal date")
    partner_id = fields.Many2one('res.partner', string="Partner",
                                 required=True,
                                 help="Partner")
    guarantor_partner_id = fields.Many2many('res.partner',
                                          relation="m2m_guarantor_partner_rel",
                                          column1="partners_ids",
                                          string="Guarantor")
    repayment_lines_partner_ids = fields.One2many('repayment.line.partner',
                                          'loan_id',
                                          string="Partner loan line", index=True,
                                          help="Partner loan repayments")
    repayment_lines_ids = fields.One2many('repayment.line',
                                          'loan_id',
                                          string="Loan Line", index=True,
                                          help="Repayment lines")
    documents_ids = fields.Many2many('loan.documents',
                                     string="Proofs",
                                     help="Documents as proof")
    img_attachment_ids = fields.Many2many('ir.attachment',
                                          relation="m2m_ir_identity_card_rel",
                                          column1="documents_ids",
                                          string="Images",
                                          help="Image proofs")
    journal_id = fields.Many2one('account.journal',
                                 string="Journal",
                                 help="Journal types",
                                 domain="[('type', '=', 'purchase'),"
                                        "('company_id', '=', company_id)]",
                                 )
    debit_account_id = fields.Many2one('account.account',
                                       string="Debit account",
                                       help="Choose account for "
                                            "disbursement debit")
    credit_account_id = fields.Many2one('account.account',
                                        string="Credit account",
                                        help="Choose account for "
                                             "disbursement credit")
    reject_reason = fields.Text(string="Reason", help="Displays "
                                                      "rejected reason")
    request = fields.Boolean(string="Request",
                             help="For monitoring the record")
    state = fields.Selection(string='State',
                             selection=[('draft', 'Draft'), ('confirmed', 'Confirmed'),
                                    ('waiting', 'Waiting For Approval'),
                                    ('approved', 'Approved'), ('disbursed', 'Disbursed'),
                                    ('rejected', 'Rejected'), ('closed', 'Closed')],
                                    copy=False, tracking=True, default='draft', help="Loan request states")
    payment_frequency = fields.Selection(string='Payment frequency',
                             selection=[('biweekly', 'Biweekly'), ('fortnightly', 'Fortnightly'),
                                    ('monthly', 'Monthly')],
                                    copy=False, tracking=True, default='fortnightly', help="Payment frequency, used for the frequency of installments")

    @api.model_create_multi
    def create(self, vals):
        """create  auto sequence for the loan request records"""
        loan_count = self.env['loan.request'].search(
            [('partner_id', '=', vals['partner_id']),
             ('state', 'not in', ('draft', 'rejected', 'closed'))])
        if loan_count:
            for rec in loan_count:
                if rec.state != 'closed':
                    raise UserError(
                        _('The partner has already an ongoing loan.'))
        else:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'increment_loan_ref')
            res = super().create(vals)
            return res

    @api.onchange('loan_type_id')
    def _onchange_loan_type_id(self):
        """Changing field values based on the chosen loan type"""
        type_id = self.loan_type_id
        self.loan_amount = type_id.loan_amount
        self.processing_fee = type_id.processing_fee
        self.disbursal_amount = type_id.disbursal_amount
        self.tenure = type_id.tenure
        self.interest_rate = type_id.interest_rate
        self.documents_ids = type_id.documents_ids

    def action_loan_request(self):
        """Changes the state to confirmed and send confirmation mail"""
        self.write({'state': "confirmed"})
        partner = self.partner_id
        loan_no = self.name
        subject = 'Loan Confirmation'
        message = (f"Dear {partner.name},<br/> This is a confirmation mail "
                   f"for your loan{loan_no}. We have submitted your loan "
                   f"for approval.")
        outgoing_mail = self.company_id.email
        mail_values = {
            'subject': subject,
            'email_from': outgoing_mail,
            'author_id': self.env.user.partner_id.id,
            'email_to': partner.email,
            'body_html': message,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

    def action_request_for_loan(self):
        """Change the state to waiting for approval"""
        if self.request:
            self.write({'state': "waiting"})
        else:
            message_id = self.env['message.popup'].create(
                {'message': _("Compute the repayments before requesting")})
            return {
                'name': _('Repayment'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'message.popup',
                'res_id': message_id.id,
                'target': 'new'
            }

    def action_loan_approved(self):
        """Change to Approved state"""
        self.write({'state': "approved"})

    def action_disburse_loan(self):
        """Disbursing the loan to customer and creating journal
         entry for the disbursement"""
        self.write({'state': "disbursed"})
        for loan in self:
            amount = loan.disbursal_amount
            loan_name = loan.partner_id.name
            reference = loan.name
            journal_id = loan.journal_id.id
            debit_account_id = loan.debit_account_id.id
            credit_account_id = loan.credit_account_id.id
            date_now = loan.disbursal_date
            debit_vals = {
                'name': loan_name,
                'account_id': debit_account_id,
                'journal_id': journal_id,
                'date': date_now,
                'debit': amount > 0.0 and amount or 0.0,
                'credit': amount < 0.0 and -amount or 0.0,
            }
            credit_vals = {
                'name': loan_name,
                'account_id': credit_account_id,
                'journal_id': journal_id,
                'date': date_now,
                'debit': amount < 0.0 and -amount or 0.0,
                'credit': amount > 0.0 and amount or 0.0,
            }
            vals = {
                'name': f'DIS / {reference}',
                'narration': reference,
                'ref': reference,
                'journal_id': journal_id,
                'date': date_now,
                'line_ids': [(0, 0, debit_vals), (0, 0, credit_vals)]
            }
            move = self.env['account.move'].create(vals)
            # move.action_post()
        return True

    def action_close_loan(self):
        """Closing the loan"""
        demo = []
        for check in self.repayment_lines_ids:
            if check.state == 'unpaid':
                demo.append(check)
        if len(demo) >= 1:
            message_id = self.env['message.popup'].create(
                {'message': _("Pending Repayments")})
            return {
                'name': _('Repayment'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'message.popup',
                'res_id': message_id.id,
                'target': 'new'
            }
        self.write({'state': "closed"})

    def action_loan_rejected(self):
        """You can add reject reasons here"""
        return {'type': 'ir.actions.act_window',
                'name': 'Loan Rejection',
                'res_model': 'reject.reason',
                'target': 'new',
                'view_mode': 'form',
                'context': {'default_loan': self.name}
                }

    def _compute_repayment_partner(self):
        for loan in self:
            loan.repayment_lines_partner_ids.unlink()
            date_start = datetime.strptime(str(loan.date),'%Y-%m-%d')
            amount = loan.loan_amount
            # interest = amount * loan.interest_rate
            # capital_amount = loan.periodic_payment - interest
            # total_amount = interest + capital_amount
            partner = loan.partner_id
            for rand_num in range(1, loan.tenure + 1):
                interest = amount * loan.rate_fee
                capital_amount = loan.periodic_payment - interest
                self.env['repayment.line.partner'].create({
                    'name': f"{loan.name}/{rand_num}",
                    'partner_id': partner.id,
                    'date': date_start,
                    'amount': capital_amount,
                    'interest_amount': interest,
                    'total_amount': interest + capital_amount,
                    'outstanding_capital': amount - capital_amount,
                    'loan_id': loan.id})
                amount -= capital_amount
                
                if self.payment_frequency == 'biweekly':
                    date_start += relativedelta(days=15)
                elif self.payment_frequency == 'fortnightly':
                    date_start += relativedelta(days=14)
                else:
                    date_start += relativedelta(months=1)
        return True            

    def action_compute_repayment(self):
        """This automatically create the installment the employee need to pay to
        company based on payment start date and the no of installments.
            """
        self.request = True
        for loan in self:
            loan.repayment_lines_ids.unlink()
            self._compute_repayment_partner()
            date_start = datetime.strptime(str(loan.date),'%Y-%m-%d')
            amount_init = loan.loan_amount
            amount = amount_init / loan.tenure
            # interest = loan.loan_amount * loan.interest_rate
            interest = sum(self.env['repayment.line.partner'].search([('loan_id', '=', loan.id)]).mapped('interest_amount'))
            # print(interest)
            interest_amount = interest / loan.tenure
            total_amount = amount + interest_amount
            partner = self.partner_id
            for rand_num in range(1, loan.tenure + 1):
                self.env['repayment.line'].create({
                    'name': f"{loan.name}/{rand_num}",
                    'partner_id': partner.id,
                    'date': date_start,
                    'amount': amount,
                    'capital_balance': amount_init - amount,
                    'interest_amount': interest_amount,
                    'total_amount': total_amount,
                    # 'interest_account_id': self.env.ref('advanced_loan_management.'
                    #                                     'loan_management_'
                    #                                     'inrst_accounts').id,
                    # 'interest_account_id': self.env['ir.config_parameter'].sudo().get_param('advanced_loan_management.interest_account_id').id,
                    'interest_account_id': self.company_id.interest_account_id.id,
                    # 'repayment_account_id': self.env.ref('advanced_loan_management.'
                    #                                      'demo_'
                    #                                      'loan_accounts').id,
                    # 'repayment_account_id': self.env['ir.config_parameter'].sudo().get_param('advanced_loan_management.repayment_account_id').id,
                    'repayment_account_id': self.company_id.repayment_account_id.id,
                    'loan_id': loan.id})
                amount_init -= amount
                if self.payment_frequency == 'biweekly':
                    date_start += relativedelta(days=15)
                elif self.payment_frequency == 'fortnightly':
                    date_start += relativedelta(days=14)
                else:
                    date_start += relativedelta(months=1)
                    
        return True
    
    @api.depends('loan_amount','processing_fee')
    def _compute_disbursal_amount(self):
        """Calculating amount for disbursing"""
        self.disbursal_amount = self.loan_amount - self.processing_fee
    
    @api.depends('loan_amount','interest_rate','tenure')
    def _compute_rate_fee(self):
        """Calculating rate_fee"""
        rate_fee = self.interest_rate/24
        if self.tenure != 0:
            periodic_payment = ((self.loan_amount * rate_fee)/(1-math.pow((1 + rate_fee),(-self.tenure))))
            self.rate_fee = rate_fee
            self.periodic_payment = periodic_payment
        else:
            self.rate_fee = 0
            self.periodic_payment = 0