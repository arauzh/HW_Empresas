from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    applicable_tax_ids = fields.Many2many(
        'partner.tax.tag',
        'res_partner_tax_rel',
        'partner_id',
        'tax_tag_id',
        string='Impuestos Aplicables'
    )