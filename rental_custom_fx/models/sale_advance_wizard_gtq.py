# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.fields import Command

class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    # -------- Helpers básicos --------
    def _get_gtq_currency(self):
        gtq = self.env['res.currency'].search([('name', 'in', ['GTQ', 'Q'])], limit=1)
        if not gtq:
            raise UserError(_("The GTQ/Q coin was not found in the coin catalog."))
        return gtq

    def _get_usd_currency(self):
        usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        if not usd:
            raise UserError(_("USD currency was not found in the currency catalog."))
        return usd

    @staticmethod
    def _order_is_rental(order):
        """Detecta SO de Alquiler (línea real con is_rental o product.rent_ok)."""
        for l in order.order_line:
            if getattr(l, "display_type", False):
                continue
            if getattr(l, "is_rental", False):
                return True
            if hasattr(l.product_id, "rent_ok") and l.product_id.rent_ok:
                return True
        return False

    def _usd_to_gtq_rate_for(self, order, date_ref):
        """Toma TU tasa personalizada de rental.exchange.rate para la fecha dada."""
        fx = self.env['rental.exchange.rate']._get_fx_for_date(order.company_id, date_ref)
        if not fx or not fx.rate_usd_to_gtq:
            raise UserError(_("There is no valid USD→Q exchange rate for the order %s.") % (order.name,))
        return fx.rate_usd_to_gtq

    def _recompute_invoice_after_changes(self, move):
        """Refresca importes/impuestos en Odoo 17 (sin _recompute_dynamic_lines)."""
        try:
            move._onchange_currency()
        except Exception:
            pass
        try:
            for inv_line in move.invoice_line_ids.filtered(lambda l: not l.display_type):
                inv_line._onchange_price_subtotal()
        except Exception:
            pass
        try:
            move.invoice_line_ids._onchange_mark_recompute_taxes()
        except Exception:
            pass
        cm = move.with_context(check_move_validity=False)
        if hasattr(cm, "_recompute_tax_lines"):
            cm._recompute_tax_lines()
        if hasattr(cm, "_recompute_payment_terms_lines"):
            cm._recompute_payment_terms_lines()

    def _post_convert_moves_to_gtq(self, moves, sale_orders):
        """Después de crear la(s) factura(s): impone GTQ y convierte price_unit desde el valor que trae la factura."""
        if not moves:
            return
        gtq = self._get_gtq_currency()
        usd = self._get_usd_currency()

        # sale_orders viene del wizard; ayuda a resolver anticipos sin sale_line_ids
        orders_hint = sale_orders

        for move in moves:
            # Orden(es) de venta vinculadas a las líneas; si no hay, usamos las del wizard.
            orders = move.invoice_line_ids.mapped('sale_line_ids.order_id')
            if not orders and orders_hint:
                orders = orders_hint

            # ¿Alguna SO es de alquiler?
            if not any(self._order_is_rental(o) for o in orders):
                continue

            # Forzar moneda de la factura a GTQ
            if move.currency_id != gtq:
                move.currency_id = gtq

            # Para cada línea de producto, tomar el price_unit ACTUAL de la factura y sustituirlo por su conversión:
            for inv_line in move.invoice_line_ids:
                # if inv_line.display_type:
                #     print("Llega # 9")
                #     continue

                # Tomar una SO de referencia: si la línea viene de venta, usar esa; si no, usar el primer pedido del wizard
                sol = inv_line.sale_line_ids[:1]
                order = sol.order_id if sol else (orders[:1] if orders else False)
                if not order:
                    continue

                # Si la SO estaba en GTQ, no convertimos esta línea
                if order.pricelist_id.currency_id == gtq:
                    continue

                # Solo contemplamos USD→GTQ
                if order.pricelist_id.currency_id != usd:
                    # Si quieres, cámbialo a 'continue' para ignorar otras monedas sin error
                    raise UserError(_("The Renting policy only contemplates USD↔GTQ. "
                                      "The order %s is in %s.")
                                    % (order.name, order.pricelist_id.currency_id.display_name))

                # Tasa por fecha de la SO (si prefieres por fecha de factura: usa move.invoice_date)
                date_ref = fields.Date.to_date(order.date_order or fields.Date.context_today(self))
                rate = self._usd_to_gtq_rate_for(order, date_ref)

                # BASE = el price_unit que YA tiene la factura (tal como quedó). Lo convertimos a Q.
                base_price = inv_line.price_unit or 0.0
                inv_line.price_unit = base_price * rate

            # Recalcular totales/impuestos
            # self._recompute_invoice_after_changes(move)

            # Traza en chatter
            move.message_post(body=_("Renting: GTQ currency imposed and price_unit converted from invoice values ​​(USD→Q)."))

    # -------- Override compacto solicitado --------
    def _create_invoices(self, sale_orders):
        """
        1) Ejecuta el flujo core para crear la(s) factura(s).
        2) Al final, fuerza moneda GTQ y CONVIERTE price_unit DESDE EL VALOR DE LA FACTURA
           usando la tasa personalizada, solo si proviene de Renting.
        """
        moves = super()._create_invoices(sale_orders)
        # En Odoo, un único registro también es un recordset; esto funciona en ambos casos.
        self._post_convert_moves_to_gtq(moves, sale_orders)
        return moves
