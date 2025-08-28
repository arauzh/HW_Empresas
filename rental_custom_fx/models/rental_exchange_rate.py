# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class RentalExchangeRate(models.Model):
    _name = "rental.exchange.rate"
    _description = "Custom exchange rate for Renting (USD↔Q)"
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char("Description", compute="_compute_name", store=True)
    date = fields.Date("Date", required=True, default=fields.Date.context_today)
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, default=lambda self: self.env.company
    )
    # Tasa = cuántos Q cuesta 1 USD
    rate_usd_to_gtq = fields.Float("USD→Q rate", required=True, digits=(16, 6))
    rate_gtq_to_usd = fields.Float("Q→USD Rate", compute="_compute_inverse", store=True, digits=(16, 6))

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("uniq_company_date", "unique(company_id, date)", _("There is already a rate for that date and company.")),
        ("positive_rate", "CHECK(rate_usd_to_gtq > 0)", _("The USD→Q rate must be greater than 0.")),
    ]

    @api.depends("date", "company_id")
    def _compute_name(self):
        for r in self:
            r.name = f"{r.company_id.name or ''} - {r.date or ''}"

    @api.depends("rate_usd_to_gtq")
    def _compute_inverse(self):
        for r in self:
            r.rate_gtq_to_usd = r.rate_usd_to_gtq and (1.0 / r.rate_usd_to_gtq) or 0.0

    @api.model
    def _get_fx_for_date(self, company, date):
        """Obtiene la última tasa <= fecha. Si no hay para esa fecha, toma la más reciente anterior."""
        self = self.sudo()
        rec = self.search(
            [("company_id", "=", company.id), ("date", "<=", date), ("active", "=", True)],
            order="date desc, id desc",
            limit=1,
        )
        if not rec:
            # fallback: la más reciente activa aunque sea posterior
            rec = self.search(
                [("company_id", "=", company.id), ("active", "=", True)],
                order="date desc, id desc",
                limit=1,
            )
        if not rec:
            raise UserError(_("There is no custom exchange rate for the company %s.") % company.name)
        return rec
