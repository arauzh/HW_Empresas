from odoo import models, fields


class PartnerTaxTag(models.Model):
    _name = 'partner.tax.tag'
    _description = 'Etiquetas de Impuestos Aplicables'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre',
        required=True
    )

    active = fields.Boolean(
        default=True
    )

    color = fields.Integer(
        string='Color'
    )