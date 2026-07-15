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
        ('cancel', 'Cancelado')
    ], string='Estado', default='draft', tracking=True)

    date_start = fields.Date(string='Fecha Inicio', required=True, tracking=True)
    date_end = fields.Date(string='Fecha Fin', required=True, tracking=True)
    
    total_ordinary = fields.Float(string='Total Ahorro Ordinario', compute='_compute_totals', store=True, tracking=True)
    total_extraordinary = fields.Float(string='Total Ahorro Extraordinario', compute='_compute_totals', store=True, tracking=True)

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
            for line in record.line_ids:
                account = self.env['asosigma.member.account'].search([('employee_id', '=', line.employee_id.id)], limit=1)
                if not account:
                    account = self.env['asosigma.member.account'].create({
                        'employee_id': line.employee_id.id
                    })
                line.account_id = account.id
            record.write({'state': 'confirmed'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
        
    def action_draft(self):
        self.write({'state': 'draft'})


# --- SALDOS ACUMULADOS ---
class AsosigmaMemberAccount(models.Model):
    _name = 'asosigma.member.account'
    _description = 'Saldos Acumulados ASOSIGMA'

    employee_id = fields.Many2one('hr.employee', string='Empleado', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', related='employee_id.work_contact_id', string='Contacto Asociado', store=True, readonly=True)
    identification_id = fields.Char(related='employee_id.identification_id', string='Identificación', store=True)
    company_id = fields.Many2one('res.company', related='employee_id.company_id', string='Empresa', store=True)

    total_ordinary = fields.Float(string='Total Ordinario', compute='_compute_totals', store=True)
    total_extraordinary = fields.Float(string='Total Extraordinario', compute='_compute_totals', store=True)
    total_accumulated = fields.Float(string='Total General', compute='_compute_totals', store=True)

    line_ids = fields.One2many(
        'asosigma.contribution.line', 
        'account_id', 
        string='Detalle de Aportaciones',
        domain=[('batch_id.state', '=', 'confirmed')]
    )
    
    manual_line_ids = fields.One2many('asosigma.member.account.manual', 'account_id', string='Cargas Manuales')

    @api.depends('line_ids.amount', 'line_ids.code', 'line_ids.batch_id.state', 'manual_line_ids.amount', 'manual_line_ids.type')
    def _compute_totals(self):
        for record in self:
            valid_lines = record.line_ids.filtered(lambda l: l.batch_id.state == 'confirmed')
            ord_payslips = sum(valid_lines.filtered(lambda l: l.code == 'AHORASOSIGMA').mapped('amount'))
            ext_payslips = sum(valid_lines.filtered(lambda l: l.code == 'AHEXASOSIGMA').mapped('amount'))
            
            ord_manual = sum(record.manual_line_ids.filtered(lambda m: m.type == 'ordinary').mapped('amount'))
            ext_manual = sum(record.manual_line_ids.filtered(lambda m: m.type == 'extraordinary').mapped('amount'))
            
            record.total_ordinary = ord_payslips + ord_manual
            record.total_extraordinary = ext_payslips + ext_manual
            record.total_accumulated = record.total_ordinary + record.total_extraordinary

    @api.depends('employee_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"Saldo: {record.employee_id.name}" if record.employee_id else "Saldo Sin Empleado"


class AsosigmaMemberAccountManual(models.Model):
    _name = 'asosigma.member.account.manual'
    _description = 'Movimientos Manuales de Cuenta ASOSIGMA'

    account_id = fields.Many2one('asosigma.member.account', string='Cuenta', ondelete='cascade', required=True)
    date = fields.Date(string='Fecha', default=fields.Date.context_today, required=True)
    description = fields.Char(string='Descripción/Motivo', required=True)
    type = fields.Selection([
        ('ordinary', 'Ahorro Ordinario'),
        ('extraordinary', 'Ahorro Extraordinario')
    ], string='Tipo de Ahorro', required=True, default='ordinary')
    amount = fields.Float(string='Monto', required=True, help="Usa montos positivos para aportes y montos negativos para retiros.")


class AsosigmaContributionLine(models.Model):
    _name = 'asosigma.contribution.line'
    _description = 'Detalle de Aportación ASOSIGMA'
    _order = 'identification_id, payslip_run_name'
    
    batch_id = fields.Many2one('asosigma.contribution.batch', string='Lote de Consulta', ondelete='cascade')
    account_id = fields.Many2one('asosigma.member.account', string='Cuenta Acumulada', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    identification_id = fields.Char(string='Identificación')
    is_member = fields.Boolean(string='Asociado Activo')
    code = fields.Char(string='Código')
    concept = fields.Char(string='Concepto')
    company_id = fields.Many2one('res.company', string='Empresa')
    payslip_run_name = fields.Char(string='Lote de Nómina')
    amount = fields.Float(string='Total Acumulado')


class AsosigmaContributionRun(models.Model):
    _name = 'asosigma.contribution.run'
    _description = 'Listado de Planillas Consultadas'

    batch_id = fields.Many2one('asosigma.contribution.batch', string='Lote de Consulta', ondelete='cascade')
    name = fields.Char(string='Lote de Nómina')