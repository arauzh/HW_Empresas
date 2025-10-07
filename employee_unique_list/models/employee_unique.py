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
    _check_company_auto = False

    name = fields.Char("Nombre")
    unique_document = fields.Char("Documento Único")
    identification_id = fields.Char("Número de Identificación")
    cui = fields.Char("CUI")
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
            if not record.unique_document:
                record.deduction_lines = False
                continue

            # Buscamos todos los registros de empleado donde el CUI o el No. de ID coincidan
            domain = [
                '|',
                ('identification_id', '=', record.unique_document),
                ('cui', '=', record.unique_document)
            ]
            
            employees = self.env["hr.employee"].sudo().with_context(active_test=False).with_company(False).search(domain)
            
            payslips = self.env["hr.payslip"].sudo().with_company(False).search([
                ("employee_id", "in", employees.ids)
            ])
            
            deductions = self.env["hr.payslip.line"].sudo().with_company(False).search([
                ("slip_id", "in", payslips.ids),
                ("name", "ilike", "%ASOSIGMA%"),
                ("amount", ">", 0)
            ])

            record.deduction_lines = deductions

    def action_open_deductions(self):
        self.ensure_one()
        all_company_ids = self.env['res.company'].search([]).ids
        action_context = dict(self.env.context, allowed_company_ids=all_company_ids)
        domain = [('id', 'in', self.deduction_lines.ids)]
        
        return {
            'name': f'Deducciones de {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip.line',
            'views': [(self.env.ref('employee_unique_list.view_hr_payslip_line_tree_deductions_grouped').id, 'tree')],
            'domain': domain,
            'context': action_context,
        }


    def init(self):
            self.env.cr.execute("""
                DROP VIEW IF EXISTS employee_unique CASCADE;
                CREATE OR REPLACE VIEW employee_unique AS (
                    WITH latest_employee AS (
                        SELECT DISTINCT ON (COALESCE(e.identification_id, e.cui))
                            COALESCE(e.identification_id, e.cui) AS unique_document,
                            e.identification_id,
                            e.cui,
                            e.name,
                            e.work_email,
                            e.company_id,
                            e.registration_number
                        FROM hr_employee e
                        WHERE e.identification_id IS NOT NULL OR e.cui IS NOT NULL
                        ORDER BY 
                            unique_document, 
                            e.active DESC,
                            e.create_date DESC
                    ),
                    employees_with_deductions AS (
                        SELECT DISTINCT COALESCE(e.identification_id, e.cui) AS unique_document
                        FROM hr_employee e
                        JOIN hr_payslip p ON p.employee_id = e.id
                        JOIN hr_payslip_line l ON l.slip_id = p.id
                        WHERE (e.identification_id IS NOT NULL OR e.cui IS NOT NULL)
                          AND l.name ILIKE '%ASOSIGMA%'
                          AND l.amount > 0
                    )
                    SELECT
                        ROW_NUMBER() OVER() AS id,
                        le.unique_document,
                        le.identification_id,
                        le.cui,
                        le.name,
                        le.work_email,
                        le.company_id,
                        le.registration_number
                    FROM latest_employee le
                    JOIN employees_with_deductions ed ON le.unique_document = ed.unique_document
                )
            """)
            
    def open_employee_unique_view(self):
        # Que empresa es la que tiene permitido utilizar esta funcion
        ALLOWED_COMPANY_ID = 5

        current_company = self.env.company
        
        if current_company.id != ALLOWED_COMPANY_ID:
            raise UserError(
                "¡Acceso no Permitido!\n\n"
                "Esta funcionalidad solo puede ser utilizada desde la compañía 'ASOSIGMA'. "
                f"Por favor, cambia de compañía para continuar."
            )

        action = self.env['ir.actions.act_window']._for_xml_id('employee_unique_list.action_employee_unique')
        return action

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
        if not deduction_ids:
            return res

        deductions = self.env['hr.payslip.line'].browse(deduction_ids)
        
        employee = deductions.mapped('employee_id').sudo()

        if len(employee) > 1:
            raise UserError("Solo puedes crear una factura para deducciones del mismo empleado a la vez.")
        
        supplier_partner = employee.work_contact_id
        
        if not supplier_partner:
            raise UserError(
                f"El empleado '{employee.name}' no tiene un 'Contacto Laboral' asignado en su ficha.\n\n"
                f"Por favor, ve a la pestaña 'Información Laboral' de la ficha del empleado y asigna su contacto."
            )
            
        if 'supplier_id' in fields_list:
            res['supplier_id'] = supplier_partner.id


        lines = []
        for deduction in deductions:
            if deduction.is_invoiced:
                raise UserError(f"La deducción '{deduction.name}' del empleado {deduction.employee_id.name} ya fue facturada.")
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

        # Vincular deducciones con la factura creada
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