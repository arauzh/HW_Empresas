from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AsosigmaContributionBatch(models.Model):
    _name = 'asosigma.contribution.batch'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Lote de Aportaciones ASOSIGMA'

    name = fields.Char(string='Referencia', required=True, copy=False, readonly=True, default=lambda self: _('Nuevo'), tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('posted', 'Asiento Publicado'),
        ('cancel', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)

    date_start = fields.Date(string='Fecha Inicio', required=True, tracking=True)
    date_end = fields.Date(string='Fecha Fin', required=True, tracking=True)
    
    total_ordinary = fields.Float(string='Total Ahorro Ordinario', compute='_compute_totals', store=True, tracking=True)
    total_extraordinary = fields.Float(string='Total Ahorro Extraordinario', compute='_compute_totals', store=True, tracking=True)

    company_id = fields.Many2one('res.company', string='Empresa', default=lambda self: self.env.company)
    journal_id = fields.Many2one('account.journal', string='Diario Contable', domain="[('type', 'in', ['general', 'bank', 'cash'])]")
    accounting_date = fields.Date(string='Fecha Contable', default=fields.Date.context_today)
    move_id = fields.Many2one('account.move', string='Asiento Contable', readonly=True)
    move_ref = fields.Char(related='move_id.ref', string='Referencia del Asiento', readonly=True)
    debit_account_id = fields.Many2one('account.account', string='Cuenta de Cargo (Debe)')
    ordinary_credit_account_id = fields.Many2one('account.account', string='Cuenta de Abono Ordinario (Haber)')
    extraordinary_credit_account_id = fields.Many2one('account.account', string='Cuenta de Abono Extraordinario (Haber)')

    line_ids = fields.One2many('asosigma.contribution.line', 'batch_id', string='Líneas de Aportación')
    run_ids = fields.One2many('asosigma.contribution.run', 'batch_id', string='Lotes de Planilla')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('asosigma.contribution.batch') or _('Nuevo')
        return super().create(vals_list)

    @api.depends('line_ids.amount', 'line_ids.code')
    def _compute_totals(self):
        for record in self:
            record.total_ordinary = sum(record.line_ids.filtered(lambda l: l.code == 'AHORASOSIGMA').mapped('amount'))
            record.total_extraordinary = sum(record.line_ids.filtered(lambda l: l.code == 'AHEXASOSIGMA').mapped('amount'))

    def action_consult(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("Solo puede consultar datos en estado Borrador."))

        self.line_ids.unlink()
        self.run_ids.unlink()

        payslip_lines = self.env['hr.payslip.line'].sudo().search([
            ('slip_id.date_from', '>=', self.date_start),
            ('slip_id.date_to', '<=', self.date_end),
            ('slip_id.state', 'in', ['done', 'paid']),
            ('code', 'in', ['AHORASOSIGMA', 'AHEXASOSIGMA'])
        ])

        if not payslip_lines:
            raise UserError(_("No se encontraron retenciones con esos códigos en el rango de fechas indicado."))

        grouped_data = {}
        unique_runs = set()

        for line in payslip_lines:
            employee = line.employee_id
            company = line.slip_id.company_id
            code = line.code
            
            payslip_run_name = line.slip_id.payslip_run_id.name if line.slip_id.payslip_run_id else 'Sin Lote'
            unique_runs.add(payslip_run_name)

            key = (employee.id, code, company.id, payslip_run_name)

            if key not in grouped_data:
                partner = employee.work_contact_id
                is_member = partner.is_asosigma_member if partner else False
                concept = 'Ahorro Ordinario ASOSIGMA' if code == 'AHORASOSIGMA' else 'Ahorro Extraordinario ASOSIGMA'

                grouped_data[key] = {
                    'batch_id': self.id,
                    'date': line.slip_id.date_to,
                    'employee_id': employee.id,
                    'identification_id': employee.identification_id,
                    'is_member': is_member,
                    'code': code,
                    'concept': concept,
                    'company_id': company.id,
                    'payslip_run_name': payslip_run_name,
                    'amount': 0.0,
                }
            grouped_data[key]['amount'] += line.total

        lines_to_create = [data for data in grouped_data.values() if data['amount'] > 0]
        if lines_to_create:
            self.env['asosigma.contribution.line'].create(lines_to_create)

        if unique_runs:
            runs_to_create = [{'batch_id': self.id, 'name': run_name} for run_name in unique_runs]
            self.env['asosigma.contribution.run'].create(runs_to_create)

    def action_confirm(self):
        for record in self:
            if not record.journal_id or not record.debit_account_id or not record.ordinary_credit_account_id or not record.extraordinary_credit_account_id:
                raise UserError(_("Para confirmar el lote debe seleccionar el Diario, la Cuenta de Cargo (Debe) y las Cuentas de Abono (Haber)."))

            for line in record.line_ids:
                if not line.is_member:
                    raise UserError(_("No puede confirmar el lote porque hay líneas de aportación donde el empleado no es Asociado Activo (is_member es falso)."))

                account = self.env['asosigma.member.account'].search([('employee_id', '=', line.employee_id.id)], limit=1)
                if not account:
                    account = self.env['asosigma.member.account'].create({
                        'employee_id': line.employee_id.id
                    })
                line.account_id = account.id

            move_lines = []
            
            # Línea 1: Debe (Total general)
            total_debit = record.total_ordinary + record.total_extraordinary
            if total_debit > 0:
                move_lines.append((0, 0, {
                    'name': f"Total Aportaciones {record.name}",
                    'account_id': record.debit_account_id.id,
                    'debit': total_debit,
                    'credit': 0.0,
                }))

            # Línea 2: Haber (Ahorro Ordinario)
            if record.total_ordinary > 0:
                move_lines.append((0, 0, {
                    'name': f"Ahorro Ordinario {record.name}",
                    'account_id': record.ordinary_credit_account_id.id,
                    'debit': 0.0,
                    'credit': record.total_ordinary,
                }))

            # Línea 3: Haber (Ahorro Extraordinario)
            if record.total_extraordinary > 0:
                move_lines.append((0, 0, {
                    'name': f"Ahorro Extraordinario {record.name}",
                    'account_id': record.extraordinary_credit_account_id.id,
                    'debit': 0.0,
                    'credit': record.total_extraordinary,
                }))

            if move_lines:
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


class AsosigmaMemberAccount(models.Model):
    _name = 'asosigma.member.account'
    _description = 'Saldos Acumulados ASOSIGMA'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', related='employee_id.work_contact_id', string='Contacto Asociado', store=True, readonly=True, compute_sudo=True)
    identification_id = fields.Char(related='employee_id.identification_id', string='Identificación', store=True, compute_sudo=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', string='Empresa', store=True, compute_sudo=True)

    total_ordinary = fields.Float(string='Total Ordinario', compute='_compute_totals', store=True)
    total_extraordinary = fields.Float(string='Total Extraordinario', compute='_compute_totals', store=True)
    total_accumulated = fields.Float(string='Total General', compute='_compute_totals', store=True)
    total_canasta = fields.Float(string='Total Canasta', compute='_compute_totals', store=True)

    # Ahora el dominio acepta: o está confirmado/publicado el lote, o es una línea manual.
    line_ids = fields.One2many(
        'asosigma.contribution.line', 
        'account_id', 
        string='Detalle de Aportaciones',
        domain=['|', ('batch_id.state', 'in', ['confirmed', 'posted']), ('is_manual', '=', True)]
    )
    
    interest_line_ids = fields.One2many(
        'asosigma.interest.line',
        'account_id',
        string='Detalle de Intereses',
        domain=['|', ('batch_id.state', 'in', ['confirmed', 'posted']), ('is_manual', '=', True)]
    )

    @api.depends('line_ids.amount', 'line_ids.code', 'line_ids.batch_id.state', 'line_ids.is_manual', 'interest_line_ids.canasta', 'interest_line_ids.batch_id.state')
    def _compute_totals(self):
        for record in self:
            # Filtramos para sumar solo líneas manuales o de lotes confirmados/publicados
            valid_lines = record.line_ids.filtered(lambda l: l.is_manual or (l.batch_id and l.batch_id.state in ['confirmed', 'posted']))
            
            record.total_ordinary = sum(valid_lines.filtered(lambda l: l.code == 'AHORASOSIGMA').mapped('amount'))
            record.total_extraordinary = sum(valid_lines.filtered(lambda l: l.code == 'AHEXASOSIGMA').mapped('amount'))
            record.total_accumulated = record.total_ordinary + record.total_extraordinary
            
            valid_interests = record.interest_line_ids.filtered(lambda l: l.is_manual or (l.batch_id and l.batch_id.state in ['confirmed', 'posted']))
            record.total_canasta = sum(valid_interests.mapped('canasta'))

    @api.depends('employee_id')
    def _compute_display_name(self):
        for record in self:
            employee_name = record.employee_id.sudo().name if record.employee_id else "Sin Empleado"
            record.display_name = f"Saldo: {employee_name}"

    # Acción que abre la ventana emergente para cargas manuales
    def action_add_manual_adjustment(self):
        self.ensure_one()
        return {
            'name': _('Carga y Ajuste Manual'),
            'type': 'ir.actions.act_window',
            'res_model': 'asosigma.manual.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_account_id': self.id}
        }

class AsosigmaContributionLine(models.Model):
    _name = 'asosigma.contribution.line'
    _description = 'Detalle de Aportación ASOSIGMA'
    _order = 'identification_id, payslip_run_name'
    
    batch_id = fields.Many2one('asosigma.contribution.batch', string='Lote Origen', ondelete='cascade')
    account_id = fields.Many2one('asosigma.member.account', string='Cuenta Acumulada', ondelete='cascade')
    date = fields.Date(string='Fecha', default=fields.Date.context_today)
    
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    # Vinculamos el contacto para que en el form de la línea salga el partner
    partner_id = fields.Many2one('res.partner', related='employee_id.work_contact_id', string='Contacto Asociado', store=True, compute_sudo=True)
    identification_id = fields.Char(string='Identificación')
    is_member = fields.Boolean(string='Asociado Activo')
    
    code = fields.Char(string='Código')
    concept = fields.Char(string='Concepto')
    company_id = fields.Many2one('res.company', string='Empresa')
    payslip_run_name = fields.Char(string='Lote de Nómina / Referencia')
    amount = fields.Float(string='Total')

    # Campos nuevos para gestionar la lógica manual
    is_manual = fields.Boolean(string='Es Manual', default=False)
    manual_reference = fields.Char(string='Secuencia Manual')
    
    # Este campo dinámico mostrará el nombre del Lote o la Secuencia manual
    reference_display = fields.Char(string='Referencia / Lote', compute='_compute_reference_display', store=True)

    @api.depends('batch_id.name', 'manual_reference', 'is_manual')
    def _compute_reference_display(self):
        for line in self:
            if line.is_manual:
                line.reference_display = line.manual_reference
            else:
                line.reference_display = line.batch_id.name if line.batch_id else ''

class AsosigmaManualAdjustmentWizard(models.TransientModel):
    _name = 'asosigma.manual.adjustment.wizard'
    _description = 'Asistente de Carga Manual'

    account_id = fields.Many2one('asosigma.member.account', string='Cuenta', required=True)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    type = fields.Selection([
        ('AHORASOSIGMA', 'Ahorro Ordinario ASOSIGMA'),
        ('AHEXASOSIGMA', 'Ahorro Extraordinario ASOSIGMA'),
        ('CANASTA', 'Canasta (Intereses)')
    ], string='Tipo de Ajuste', required=True, default='AHORASOSIGMA')
    amount = fields.Float(string='Monto', required=True, help="Positivo para sumar, negativo para restar.")

    def action_confirm(self):
        seq = self.env['ir.sequence'].next_by_code('asosigma.manual.adjustment') or '/'
        
        if self.type == 'CANASTA':
            self.env['asosigma.interest.line'].create({
                'account_id': self.account_id.id,
                'partner_id': self.account_id.partner_id.id,
                'total_ordinary': 0.0,
                'employer_contribution': 0.0,
                'total_extraordinary': 0.0,
                'total_sum': 0.0,
                'percentage': 0.0,
                'canasta': self.amount,
                'is_manual': True,
                'manual_reference': seq,
                'date': self.date,
                'concept': 'Ajuste Manual Canasta',
            })
        else:
            concept = 'Ahorro Ordinario ASOSIGMA' if self.type == 'AHORASOSIGMA' else 'Ahorro Extraordinario ASOSIGMA'
            self.env['asosigma.contribution.line'].create({
                'account_id': self.account_id.id,
                'employee_id': self.account_id.employee_id.id,
                'identification_id': self.account_id.identification_id,
                'company_id': self.account_id.company_id.id,
                'is_member': self.account_id.partner_id.is_asosigma_member,
                'code': self.type,
                'concept': concept,
                'payslip_run_name': 'Aporte manual',
                'amount': self.amount,
                'is_manual': True,
                'manual_reference': seq,
                'date': self.date,
            })


class AsosigmaContributionRun(models.Model):
    _name = 'asosigma.contribution.run'
    _description = 'Listado de Planillas Consultadas'

    batch_id = fields.Many2one('asosigma.contribution.batch', string='Lote de Consulta', ondelete='cascade')
    name = fields.Char(string='Lote de Nómina')

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        res = super().action_post()
        batches = self.env['asosigma.contribution.batch'].search([('move_id', 'in', self.ids), ('state', '=', 'confirmed')])
        batches.write({'state': 'posted'})
        
        interest_batches = self.env['asosigma.interest.batch'].search([('move_id', 'in', self.ids), ('state', '=', 'confirmed')])
        interest_batches.write({'state': 'posted'})
        return res

    def button_draft(self):
        res = super().button_draft()
        batches = self.env['asosigma.contribution.batch'].search([('move_id', 'in', self.ids), ('state', '=', 'posted')])
        batches.write({'state': 'confirmed'})
        
        interest_batches = self.env['asosigma.interest.batch'].search([('move_id', 'in', self.ids), ('state', '=', 'posted')])
        interest_batches.write({'state': 'confirmed'})
        return res