# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ApprovalRequest(models.Model):
    _name = 'approval.budget'
    _description = 'Approval budget'
    _check_company_auto = True
    _order = "sequence, id"
    
    sequence = fields.Integer(default=10, index=True)
    name = fields.Char('Description')
    approval_request_id = fields.Many2one('approval.request', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', store=True, index=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    analytic_plan_id = fields.Many2one('account.analytic.plan', 'Analytic Plan', related='analytic_account_id.plan_id', readonly=True)
    general_budget_id = fields.Many2one('account.budget.post', 'Budgetary Position')
    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    planned_amount = fields.Monetary(
        'Planned Amount', required=True, default=0.0,
        help="Amount you plan to earn/spend. Record a positive amount if it is a revenue and a negative amount if it is a cost.")
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False)
    # Campo para mostrar el subtotal de la sección
    planned_subtotal = fields.Monetary(
        string='Planned subtotal',
        currency_field='currency_id',
        store=False,
    )
    executed_amount = fields.Monetary(
        'Executed amount', required=True, default=0.0,
        help="Amount executed. Record a positive amount if it is income and a negative amount if it is a cost.")
    executed_subtotal = fields.Monetary(
        string='Executed subtotal',
        currency_field='currency_id',
        store=False,
    )
    observation = fields.Text('Observation')

    @api.onchange('approval_request_id')
    def _onchange_approval_request_id(self):
        """ 
        Al crear la línea, trae las fechas del padre si existen.
        """
        for record in self:
            if record.approval_request_id:
                # Validamos que el padre tenga las fechas llenas
                if not record.approval_request_id.date_start or not record.approval_request_id.date_end:
                    raise UserError(_("Before adding budget lines, you must define the 'From' and 'To' dates in the approval request."))
                
                # Asignamos los valores
                record.date_from = record.date_from or record.approval_request_id.date_start
                record.date_to = record.date_to or record.approval_request_id.date_end