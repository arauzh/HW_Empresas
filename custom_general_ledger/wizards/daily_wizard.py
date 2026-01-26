from odoo import models, fields, api

class CustomDailyWizard(models.TransientModel):
    _name = 'custom.daily.wizard'
    _description = 'Wizard para Libro Diario (Resumido)'

    date_from = fields.Date(string='Fecha Inicio', required=True)
    date_to = fields.Date(string='Fecha Fin', required=True)
    target_move = fields.Selection([
        ('posted', 'Todos los asientos publicados'),
        ('all', 'Todos los asientos'),
    ], string='Movimientos', required=True, default='posted')
    
    folio = fields.Char(string='No. Folio', required=False)
    company_id = fields.Many2one('res.company', string='Compañía', required=True, default=lambda self: self.env.company)

    def action_print_report(self):
        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'target_move': self.target_move,
            'company_id': self.company_id.id,
            'folio': self.folio,
        }
        return self.env.ref('custom_general_ledger.action_report_custom_daily').report_action(self, data=data)