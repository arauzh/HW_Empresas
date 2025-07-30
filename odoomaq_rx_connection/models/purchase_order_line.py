# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import requests
import logging

_logger = logging.getLogger(__name__)

class Purchase_Order_Line(models.Model):
    _inherit = 'purchase.order.line'

    origin_order_line_id = fields.Integer(string='Origin order line ID', copy=False, default=0)