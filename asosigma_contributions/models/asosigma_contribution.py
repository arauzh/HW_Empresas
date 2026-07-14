from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AsosigmaContributionBatch(models.Model):
    _name = 'asosigma.contribution.batch'
    _description = 'Lote de Aportaciones ASOSIGMA'

    name = fields.Char(string='Referencia', required=True, copy=False, readonly=True, default=lambda self: _('Nuevo'))
    date_start = fields.Date(string='Fecha Inicio', required=True)
    date_end = fields.Date(string='Fecha Fin', required=True)
    line_ids = fields.One2many('asosigma.contribution.line', 'batch_id', string='Líneas de Aportación')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('asosigma.contribution.batch') or _('Nuevo')
        return super().create(vals_list)

    def action_consult(self):
        self.ensure_one()
        self.line_ids.unlink()
        payslip_lines = self.env['hr.payslip.line'].sudo().search([
            ('slip_id.date_from', '>=', self.date_start),
            ('slip_id.date_to', '<=', self.date_end),
            ('slip_id.state', 'in', ['done', 'paid']), # ver que estado se van a querer
            ('code', 'in', ['AHORASOSIGMA', 'AHEXASOSIGMA'])
        ])

        if not payslip_lines:
            raise UserError(_("No se encontraron retenciones con esos códigos en el rango de fechas indicado."))

        grouped_data = {}
        for line in payslip_lines:
            employee = line.employee_id
            company = line.slip_id.company_id
            code = line.code

            key = (employee.id, code, company.id)

            if key not in grouped_data:
                partner = employee.address_home_id
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
                    'amount': 0.0,
                }

            grouped_data[key]['amount'] += line.total

        self.env['asosigma.contribution.line'].create(list(grouped_data.values()))


class AsosigmaContributionLine(models.Model):
    _name = 'asosigma.contribution.line'
    _description = 'Detalle de Aportación ASOSIGMA'

    batch_id = fields.Many2one('asosigma.contribution.batch', string='Lote', ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Empleado')
    identification_id = fields.Char(string='Identificación')
    is_member = fields.Boolean(string='¿Es Asociado?')
    code = fields.Char(string='Código')
    concept = fields.Char(string='Concepto')
    company_id = fields.Many2one('res.company', string='Empresa')
    amount = fields.Float(string='Total Acumulado')