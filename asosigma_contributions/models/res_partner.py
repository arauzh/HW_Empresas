from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_asosigma_member = fields.Boolean(
        string='Es asociado ASOSIGMA',
        default=False
    )