# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    mirror_price_unit = fields.Monetary(
        string="Price Unit. (Mirror coin)",
        currency_field="mirror_currency_id",
        compute="_compute_mirror_prices",
        help="Unit price converted to the opposite currency (USD↔Q) using custom exchange rate."
    )
    mirror_price_subtotal = fields.Monetary(
        string="Subtotal (Mirror Currency)",
        currency_field="mirror_currency_id",
        compute="_compute_mirror_prices",
        help="Subtotal converted to opposite currency (USD↔Q) using custom exchange rate."
    )
    mirror_currency_id = fields.Many2one(
        "res.currency",
        string="Mirror coin",
        compute="_compute_mirror_prices",
        store=False,
    )

    @api.depends(
        "price_unit",
        "price_subtotal",
        "order_id.pricelist_id.currency_id",
        "order_id.company_id",
        "order_id.date_order",
        "product_uom_qty",
        "discount",
        "tax_id"
    )
    def _compute_mirror_prices(self):
        Currency = self.env["res.currency"]
        usd = Currency.search([("name", "=", "USD")], limit=1)
        gtq = Currency.search([("name", "in", ["GTQ", "Q"])], limit=1)  # en GT hay GTQ

        for line in self:
            line.mirror_price_unit = 0.0
            line.mirror_price_subtotal = 0.0
            line.mirror_currency_id = False
            
            if not line.order_id.is_rental_order:
                continue

            if not line.order_id or not line.order_id.pricelist_id.currency_id or not usd or not gtq:
                continue

            src_cur = line.order_id.pricelist_id.currency_id
            company = line.order_id.company_id
            date = fields.Date.to_date(line.order_id.date_order or fields.Date.context_today(line))
            fx = self.env["rental.exchange.rate"]._get_fx_for_date(company, date)

            # Solo convertimos si la moneda origen es USD o GTQ
            if src_cur == usd:
                # USD → GTQ
                line.mirror_currency_id = gtq
                rate = fx.rate_usd_to_gtq
                line.mirror_price_unit = line.price_unit * rate
                # Para el subtotal, usamos line.price_subtotal ya con impuestos excluidos en moneda origen
                line.mirror_price_subtotal = line.price_subtotal * rate

            elif src_cur == gtq:
                # GTQ → USD
                line.mirror_currency_id = usd
                rate = fx.rate_gtq_to_usd or (1.0 / fx.rate_usd_to_gtq if fx.rate_usd_to_gtq else 0.0)
                line.mirror_price_unit = line.price_unit * rate
                line.mirror_price_subtotal = line.price_subtotal * rate

            else:
                # Si la lista es otra moneda, no mostramos conversión (o podrías extenderlo si lo necesitas).
                line.mirror_currency_id = False
                line.mirror_price_unit = 0.0
                line.mirror_price_subtotal = 0.0
