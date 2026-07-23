from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AsosigmaInterestBatch(models.Model):
    _name = 'asosigma.interest.batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Lote de Intereses Mensuales ASOSIGMA'

    name = fields.Char(string='Referencia', required=True, copy=False, readonly=True, default=lambda self: _('Nuevo'), tracking=True)
    
    year = fields.Selection([
        (str(y), str(y)) for y in range(2020, 2040)
    ], string='Año', required=True, tracking=True, default=lambda self: str(fields.Date.today().year))
    
    month = fields.Selection([
        ('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'),
        ('04', 'Abril'), ('05', 'Mayo'), ('06', 'Junio'),
        ('07', 'Julio'), ('08', 'Agosto'), ('09', 'Septiembre'),
        ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre')
    ], string='Mes', required=True, tracking=True)
    
    total_interest = fields.Float(string='Interés Total', required=True, tracking=True)
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('consulted', 'Consultado'),
        ('calculated', 'Calculado'),
        ('confirmed', 'Confirmado')
    ], string='Estado', default='draft', tracking=True)

    line_ids = fields.One2many('asosigma.interest.line', 'batch_id', string='Detalle de Distribución')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                year = vals.get('year', str(fields.Date.today().year))
                month = vals.get('month', '00')
                seq = self.env['ir.sequence'].next_by_code('asosigma.interest.batch.sequence') or '0000'
                vals['name'] = f"INT/{year}/{month}/{seq}"
        return super().create(vals_list)
        
    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if ('year' in vals or 'month' in vals) and record.name and record.name.startswith('INT/'):
                parts = record.name.split('/')
                if len(parts) == 4:
                    seq = parts[3]
                    record.name = f"INT/{record.year}/{record.month}/{seq}"
        return res

    def action_consult(self):
        for record in self:
            if record.state not in ('draft', 'consulted'):
                raise UserError(_("Solo se puede consultar en estado Borrador o Consultado."))
            
            record.line_ids.unlink()

            accounts = self.env['asosigma.member.account'].search([])
            
            if not accounts:
                raise UserError(_("No se encontraron contactos en Saldos Acumulados."))
            
            lines_val = []
            for account in accounts:
                total_ord = account.total_ordinary
                total_ext = account.total_extraordinary
                emp_contrib = total_ord
                total_sum = total_ord + emp_contrib + total_ext
                
                lines_val.append((0, 0, {
                    'partner_id': account.partner_id.id,
                    'total_ordinary': total_ord,
                    'employer_contribution': emp_contrib,
                    'total_extraordinary': total_ext,
                    'total_sum': total_sum,
                    'percentage': 0.0,
                    'canasta': 0.0,
                }))
            
            if lines_val:
                record.write({'line_ids': lines_val})
                
                global_sum = sum(record.line_ids.mapped('total_sum'))
                if global_sum > 0:
                    for line in record.line_ids:
                        line.percentage = (line.total_sum * 100.0) / global_sum
                else:
                    for line in record.line_ids:
                        line.percentage = 0.0
            
            record.write({'state': 'consulted'})

    def action_calculate(self):
        for record in self:
            if record.state not in ('consulted', 'calculated'):
                raise UserError(_("Primero debe Consultar los saldos para poder calcular."))
            if record.total_interest <= 0:
                raise UserError(_("El Interés Total debe ser mayor a cero para calcular la canasta."))

            for line in record.line_ids:
                line.canasta = (line.percentage * record.total_interest) / 100.0
            
            record.write({'state': 'calculated'})

    def action_confirm(self):
        for record in self:
            if record.state != 'calculated':
                raise UserError(_("Debe calcular los intereses antes de confirmar."))
            record.write({'state': 'confirmed'})
            
    def action_draft(self):
        self.write({'state': 'draft'})


class AsosigmaInterestLine(models.Model):
    _name = 'asosigma.interest.line'
    _description = 'Línea de Interés Mensual'

    batch_id = fields.Many2one('asosigma.interest.batch', string='Lote de Interés', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Contacto Asociado', required=True)
    
    total_ordinary = fields.Float(string='Total Ordinario')
    employer_contribution = fields.Float(string='Aportaciones Patronales')
    total_extraordinary = fields.Float(string='Total Extraordinario')
    total_sum = fields.Float(string='Total (Suma)')
    
    percentage = fields.Float(string='(%) Porcentaje')
    canasta = fields.Float(string='Canasta')
