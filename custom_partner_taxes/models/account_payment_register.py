from odoo import fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    posicion_presupuestaria_id = fields.Many2one(
        "account.budget.post",
        string="Posición Presupuestaria"
    )

    def _create_payment_vals_from_wizard(self, batch_result):

        vals = super()._create_payment_vals_from_wizard(batch_result)

        vals['posicion_presupuestaria_id'] = self.posicion_presupuestaria_id.id

        return vals