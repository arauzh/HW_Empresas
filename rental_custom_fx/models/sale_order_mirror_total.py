# -*- coding: utf-8 -*-

from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = "sale.order"

    mirror_currency_id = fields.Many2one(
        "res.currency",
        string="Mirror coin (order)",
        compute="_compute_mirror_totals",
        store=True,
    )
    mirror_amount_untaxed = fields.Monetary(
        string="Base (Mirror Coin)",
        currency_field="mirror_currency_id",
        compute="_compute_mirror_totals",
        store=True,
    )
    mirror_amount_tax = fields.Monetary(
        string="Taxes (Mirror Currency)",
        currency_field="mirror_currency_id",
        compute="_compute_mirror_totals",
        store=True,
    )
    mirror_amount_total = fields.Monetary(
        string="Total (Mirror Currency)",
        currency_field="mirror_currency_id",
        compute="_compute_mirror_totals",
        store=True,
        help="Total converted to the opposite currency (USD↔Q) using Renting's custom exchange rate."
    )

    @api.depends(
        "amount_untaxed", "amount_tax", "amount_total",
        "pricelist_id.currency_id",
        "company_id",
        "date_order",
        "order_line.price_subtotal",
    )
    def _compute_mirror_totals(self):
        Currency = self.env["res.currency"]
        usd = Currency.search([("name", "=", "USD")], limit=1)
        gtq = Currency.search([("name", "in", ["GTQ", "Q"])], limit=1)

        for order in self:
            order.mirror_currency_id = False
            order.mirror_amount_untaxed = 0.0
            order.mirror_amount_tax = 0.0
            order.mirror_amount_total = 0.0
            
            if not order.is_rental_order:
                continue

            src_cur = order.pricelist_id.currency_id
            if not src_cur or not usd or not gtq:
                continue

            # Toma la tasa personalizada por fecha de pedido
            date = fields.Date.to_date(order.date_order or fields.Date.context_today(order))
            fx = self.env["rental.exchange.rate"]._get_fx_for_date(order.company_id, date)
            
            if not fx or not fx.rate_usd_to_gtq:
                return

            if src_cur == usd:
                order.mirror_currency_id = gtq
                rate = fx.rate_usd_to_gtq
                order.mirror_amount_untaxed = order.amount_untaxed * rate
                order.mirror_amount_tax = order.amount_tax * rate
                order.mirror_amount_total = order.amount_total * rate

            elif src_cur == gtq:
                order.mirror_currency_id = usd
                rate = fx.rate_gtq_to_usd or (1.0 / fx.rate_usd_to_gtq if fx.rate_usd_to_gtq else 0.0)
                order.mirror_amount_untaxed = order.amount_untaxed * rate
                order.mirror_amount_tax = order.amount_tax * rate
                order.mirror_amount_total = order.amount_total * rate

            else:
                # Otras monedas: sin conversión (puedes extenderlo si lo necesitas)
                pass

    def _prepare_confirmation_values(self):
        """ Prepare the sales order confirmation values.

        Note: self can contain multiple records.

        :return: Sales Order confirmation values
        :rtype: dict
        """
        values = super()._prepare_confirmation_values()
        
        if self.is_rental_order:
            return {
                'state': 'sale'
            }
        
        return values