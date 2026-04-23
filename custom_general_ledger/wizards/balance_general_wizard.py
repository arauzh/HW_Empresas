from odoo import models, fields

class BalanceGeneralWizard(models.TransientModel):
    _name = 'custom.balance.general.wizard'
    _description = 'Wizard Balance General'

    date_to = fields.Date(string='Fecha Corte', required=True)
    folio = fields.Char(string='No. Folio')

    target_move = fields.Selection([
        ('posted', 'Asientos publicados'),
        ('all', 'Todos los asientos'),
    ], default='posted', required=True)

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True
    )

    def action_print_report(self):
        data = {
            'date_to': self.date_to,
            'target_move': self.target_move,
            'company_id': self.company_id.id,
            'folio': self.folio,
        }

        return self.env.ref(
            'custom_general_ledger.action_report_balance_general'
        ).report_action(self, data=data)