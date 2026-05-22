from odoo import models, fields, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    tax_alert_message = fields.Html(
        string='Mensaje Impuestos',
        compute='_compute_tax_alert_message',
        sanitize=False
    )

    @api.depends('partner_id')
    def _compute_tax_alert_message(self):
        for rec in self:

            rec.tax_alert_message = False

            if not rec.partner_id:
                continue

            taxes = rec.partner_id.applicable_tax_ids

            if not taxes:
                continue

            tags_html = ""

            for tag in taxes:
                tags_html += f"""
                    <span style="
                        background-color:#875A7B;
                        color:white;
                        padding:4px 8px;
                        border-radius:10px;
                        margin-right:5px;
                        font-size:12px;
                    ">
                        {tag.name}
                    </span>
                """

            rec.tax_alert_message = f"""
                <div class="alert alert-warning" role="alert">
                    <strong>
                        Este proveedor tiene los siguientes impuestos aplicables:
                    </strong>
                    <br/><br/>
                    {tags_html}
                </div>
            """