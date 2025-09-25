from odoo import fields, models

class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # Campo relacionado al número de recibo de nómina
    slip_number = fields.Char(related='slip_id.number', string='Número de Recibo', store=True)

    # Campo relacionado al lote de nómina
    payslip_run_name = fields.Char(related='slip_id.payslip_run_id.name', string='Lote', store=True)
    
    amount = fields.Monetary("Importe", currency_field="currency_id")


class EmployeeUnique(models.Model):
    _name = "employee.unique"
    _description = "Empleado Único por Documento"
    _auto = False  # Esto es por que vamos a usar una vista SQL

    # Campos que mapean columnas de la vista
    name = fields.Char("Nombre")
    identification_id = fields.Char("Número de Identificación")
    registration_number = fields.Char("Número de Registro")
    work_email = fields.Char("Correo")
    company_id = fields.Many2one("res.company", "Compañía")

    # Campo computado para traer deducciones
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

            employees = self.env["hr.employee"].search([
                ("identification_id", "=", record.identification_id)
            ])
            payslips = self.env["hr.payslip"].search([
                ("employee_id", "in", employees.ids)
            ])
            # Solo deducciones "Provident Fund" con importe > 0
            deductions = self.env["hr.payslip.line"].search([
                ("slip_id", "in", payslips.ids),
                ("category_id.code", "=", "DED"),
                ("name", "ilike", "asosigma"),
                ("amount", ">", 0)
            ])
            record.deduction_lines = deductions

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
                  AND c.code = 'DED'
                  AND l.name ILIKE 'asosigma'
                  AND l.amount > 0
                GROUP BY e.identification_id
            )
        """)
