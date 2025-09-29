from odoo import models, fields, api
from odoo.exceptions import UserError


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    slip_number = fields.Char(
        related='slip_id.number',
        string='Número de Recibo',
        store=True
    )
    payslip_run_name = fields.Char(
        related='slip_id.payslip_run_id.name',
        string='Lote',
        store=True
    )
    amount = fields.Monetary("Importe", currency_field="currency_id")
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        help="Producto específico para esta deducción. Se usará para pre-asignar en el asistente de facturación."
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="No. de Factura",
        readonly=True,
        help="Factura generada a partir de esta deducción."
    )
    is_invoiced = fields.Boolean(
        string="Ya facturada?",
        compute="_compute_is_invoiced",
        store=True
    )

    @api.depends("invoice_id", "invoice_id.state")
    def _compute_is_invoiced(self):
        for rec in self:
            rec.is_invoiced = bool(rec.invoice_id and rec.invoice_id.state not in ("cancel"))

    def action_create_supplier_invoice_wizard(self):
        # Bloquear que pueda crear si ya esta facturada
        invoiced = self.filtered(lambda l: l.is_invoiced)
        if invoiced:
            raise UserError(
                f"Las siguientes deducciones ya fueron facturadas y no pueden volver a facturarse:\n- " +
                "\n- ".join(invoiced.mapped("name"))
            )
        return {
            'name': "Crear Factura de Proveedor",
            'type': 'ir.actions.act_window',
            'res_model': 'create.supplier.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
        }


class EmployeeUnique(models.Model):
    _name = "employee.unique"
    _description = "Empleado Único por Documento"
    _auto = False

    name = fields.Char("Nombre")
    identification_id = fields.Char("Número de Identificación")
    registration_number = fields.Char("Número de Registro")
    work_email = fields.Char("Correo")
    company_id = fields.Many2one("res.company", "Compañía")

    deduction_lines = fields.Many2many(
        "hr.payslip.line",
        compute="_compute_deduction_lines",
        string="Deducciones",
    )

    def _compute_deduction_lines(self):
        for record in self:
            if not record.identification_id:
                record.deduction_lines = False
                continue
            employees = self.env["hr.employee"].search([("identification_id", "=", record.identification_id)])
            payslips = self.env["hr.payslip"].search([("employee_id", "in", employees.ids)])
            deductions = self.env["hr.payslip.line"].search([
                ("slip_id", "in", payslips.ids),
                ("name", "ilike", "ASOSIGMA"),
            ])
            record.deduction_lines = deductions

    def action_open_deductions(self):
        self.ensure_one()
        return {
            'name': f'Deducciones de {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.line',
            'views': [(self.env.ref('employee_unique_list.view_hr_payslip_line_tree_deductions_grouped').id, 'tree')],
            'domain': [('id', 'in', self.deduction_lines.ids)],
            'context': dict(self.env.context),
        }

    def init(self):
        self.env.cr.execute("""
            DROP VIEW IF EXISTS employee_unique CASCADE;
            CREATE OR REPLACE VIEW employee_unique AS (
                SELECT
                    MIN(e.id) AS id,
                    MAX(e.name)::varchar AS name,
                    e.identification_id,
                    MAX(e.work_email)::varchar AS work_email,
                    MAX(e.company_id) AS company_id,
                    MAX(e.registration_number)::varchar AS registration_number
                FROM hr_employee e
                JOIN hr_payslip p ON p.employee_id = e.id
                JOIN hr_payslip_line l ON l.slip_id = p.id
                JOIN hr_salary_rule_category c ON c.id = l.category_id
                WHERE e.identification_id IS NOT NULL
                  AND l.name ILIKE 'ASOSIGMA'
                GROUP BY e.identification_id
            )
        """)


class CreateSupplierInvoiceWizard(models.TransientModel):
    _name = "create.supplier.invoice.wizard"
    _description = "Asistente para Crear Factura de Proveedor desde Deducciones"

    supplier_id = fields.Many2one("res.partner", string="Proveedor", required=True)
    wizard_line_ids = fields.One2many(
        "create.supplier.invoice.wizard.line",
        "wizard_id",
        string="Deducciones a Facturar"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        deduction_ids = self.env.context.get('active_ids', [])
        if deduction_ids:
            lines = []
            deductions = self.env['hr.payslip.line'].browse(deduction_ids)
            for deduction in deductions:
                if deduction.is_invoiced:
                    raise UserError(f"La deducción '{deduction.name}' ya fue facturada.")
                lines.append((0, 0, {
                    'deduction_id': deduction.id,
                    'product_id': deduction.product_id.id or False,
                }))
            res['wizard_line_ids'] = lines
        return res

    def action_create_invoice(self):
        self.ensure_one()
        if not self.wizard_line_ids:
            raise UserError("No hay deducciones seleccionadas para crear la factura.")

        invoice_lines = []
        deductions_to_link = []
        for line in self.wizard_line_ids:
            if not line.product_id:
                raise UserError(f"Debe seleccionar un producto para la deducción del empleado '{line.employee_name}'.")

            product = line.product_id
            deduction = line.deduction_id

            if deduction.is_invoiced:
                raise UserError(f"La deducción '{deduction.name}' ya fue facturada.")

            account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
            if not account:
                raise UserError(f"El producto '{product.name}' no tiene definida una cuenta de gastos.")

            line_vals = {
                'product_id': product.id,
                'name': f"{deduction.name} - {line.employee_name}",
                'quantity': 1,
                'price_unit': line.amount,
                'account_id': account.id,
            }
            invoice_lines.append((0, 0, line_vals))
            deductions_to_link.append(deduction)

        invoice_vals = {
            'partner_id': self.supplier_id.id,
            'move_type': 'in_invoice',
            'invoice_line_ids': invoice_lines,
        }
        invoice = self.env['account.move'].create(invoice_vals)

        # Vincular cada deduccion con una factura
        for deduction in deductions_to_link:
            deduction.invoice_id = invoice.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CreateSupplierInvoiceWizardLine(models.TransientModel):
    _name = "create.supplier.invoice.wizard.line"
    _description = "Línea del Asistente para Crear Factura de Proveedor"

    wizard_id = fields.Many2one("create.supplier.invoice.wizard", string="Asistente", required=True, ondelete="cascade")
    deduction_id = fields.Many2one("hr.payslip.line", string="Deducción Original", required=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    employee_name = fields.Char(related="deduction_id.employee_id.name", string="Empleado", readonly=True)
    name = fields.Char(related="deduction_id.name", string="Descripción", readonly=True)
    amount = fields.Monetary(related="deduction_id.amount", string="Importe", readonly=True)
    currency_id = fields.Many2one(related="deduction_id.currency_id", readonly=True)
