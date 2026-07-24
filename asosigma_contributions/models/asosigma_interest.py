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
    
    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    journal_id = fields.Many2one('account.journal', string='Diario Contable', domain="[('type', 'in', ['general', 'bank', 'cash'])]")
    accounting_date = fields.Date(string='Fecha Contable', default=fields.Date.context_today)
    move_id = fields.Many2one('account.move', string='Asiento Contable', readonly=True)
    move_ref = fields.Char(related='move_id.ref', string='Referencia del Asiento', readonly=True)
    debit_account_id = fields.Many2one('account.account', string='Cuenta de Cargo (Debe)')
    credit_account_id = fields.Many2one('account.account', string='Cuenta de Abono (Haber)')
    
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('consulted', 'Consultado'),
        ('calculated', 'Calculado'),
        ('confirmed', 'Confirmado'),
        ('posted', 'Asiento Publicado'),
        ('cancel', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)

    line_ids = fields.One2many('asosigma.interest.line', 'batch_id', string='Detalle de Distribución')

    @api.constrains('year', 'month', 'state')
    def _check_unique_year_month(self):
        for record in self:
            if record.state != 'cancel':
                domain = [
                    ('year', '=', record.year),
                    ('month', '=', record.month),
                    ('state', '!=', 'cancel'),
                    ('id', '!=', record.id)
                ]
                if self.search_count(domain) > 0:
                    raise UserError(_("No se puede tener más de un lote de intereses activo para el mismo Año y Mes."))

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
            
            month_dict = dict(self._fields['month'].selection)
            month_name = month_dict.get(record.month, '')
            concept_name = f"Canasta basica {month_name}-{record.year}"
            
            lines_val = []
            for account in accounts:
                total_ord = account.total_ordinary
                total_ext = account.total_extraordinary
                emp_contrib = total_ord
                total_sum = total_ord + emp_contrib + total_ext
                
                lines_val.append((0, 0, {
                    'account_id': account.id,
                    'partner_id': account.partner_id.id,
                    'total_ordinary': total_ord,
                    'employer_contribution': emp_contrib,
                    'total_extraordinary': total_ext,
                    'total_sum': total_sum,
                    'percentage': 0.0,
                    'canasta': 0.0,
                    'concept': concept_name,
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
            if not record.journal_id or not record.debit_account_id or not record.credit_account_id:
                raise UserError(_("Para confirmar el lote debe seleccionar el Diario y las Cuentas de Cargo y Abono."))
            
            total_canasta_all = sum(record.line_ids.mapped('canasta'))
            
            if total_canasta_all > 0:
                move_lines = []
                
                # Debe
                move_lines.append((0, 0, {
                    'name': f"Total Intereses {record.name}",
                    'account_id': record.debit_account_id.id,
                    'debit': total_canasta_all,
                    'credit': 0.0,
                }))
                
                # Haber
                move_lines.append((0, 0, {
                    'name': f"Total Intereses {record.name}",
                    'account_id': record.credit_account_id.id,
                    'debit': 0.0,
                    'credit': total_canasta_all,
                }))
                
                create_date_str = record.create_date.strftime('%Y-%m-%d') if record.create_date else fields.Date.context_today(record).strftime('%Y-%m-%d')
                ref_name = f"{record.name} - {create_date_str}"
                
                move_vals = {
                    'journal_id': record.journal_id.id,
                    'date': record.accounting_date,
                    'ref': ref_name,
                    'company_id': record.company_id.id,
                    'line_ids': move_lines,
                }
                move = self.env['account.move'].create(move_vals)
                record.move_id = move.id
                
            record.write({'state': 'confirmed'})
            
    def action_cancel(self):
        for record in self:
            if record.state == 'posted':
                raise UserError(_("No puede cancelar un lote cuyo asiento contable ya ha sido publicado."))
            if record.move_id:
                if record.move_id.state == 'posted':
                    record.move_id.button_draft()
                record.move_id.button_cancel()
            record.write({'state': 'cancel'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def unlink(self):
        for record in self:
            if record.state == 'posted':
                raise UserError(_("No puede borrar un lote cuyo asiento contable ya ha sido publicado."))
        return super().unlink()


class AsosigmaInterestLine(models.Model):
    _name = 'asosigma.interest.line'
    _description = 'Línea de Interés Mensual'

    batch_id = fields.Many2one('asosigma.interest.batch', string='Lote de Interés', ondelete='cascade')
    account_id = fields.Many2one('asosigma.member.account', string='Cuenta Acumulada', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Contacto Asociado', required=True)
    
    total_ordinary = fields.Float(string='Total Ordinario')
    employer_contribution = fields.Float(string='Aportaciones Patronales')
    total_extraordinary = fields.Float(string='Total Extraordinario')
    total_sum = fields.Float(string='Total (Suma)')
    
    percentage = fields.Float(string='(%) Porcentaje')
    canasta = fields.Float(string='Canasta')
    
    date = fields.Date(string='Fecha', default=fields.Date.context_today)
    concept = fields.Char(string='Concepto')
    is_manual = fields.Boolean(string='Es Manual', default=False)
    manual_reference = fields.Char(string='Secuencia Manual')
    
    reference_display = fields.Char(string='Referencia / Lote', compute='_compute_reference_display', store=True)

    @api.depends('batch_id.name', 'manual_reference', 'is_manual')
    def _compute_reference_display(self):
        for line in self:
            if line.is_manual:
                line.reference_display = line.manual_reference
            else:
                line.reference_display = line.batch_id.name if line.batch_id else ''
