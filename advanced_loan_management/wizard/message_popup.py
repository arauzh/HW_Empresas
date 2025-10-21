# -*- coding: utf-8 -*-

from odoo import fields, models


class MessageWizard(models.TransientModel):
    """For creating alert messages"""
    _name = 'message.popup'
    _description = 'Generate Popup Message'

    message = fields.Text(string='Message', required=True, help="Alert Content")
