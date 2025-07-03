# -*- coding: utf-8 -*-
from odoo import http
from odoo import models, fields, api
from odoo.http import request, Response


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _auth_method_my_api_key(cls):
        """
        Autenticación por API Key personalizada via header 'Authorization: <api_key>'.
        Descarga el API Key y delega en el método _check_credentials de res.users.apikeys.
        """
        api_key = request.httprequest.headers.get("Authorization")
        if not api_key:
            raise BadRequest(_("Authorization header with API key missing"))
        # Validar credenciales en modelo apikeys
        user_id = request.env["res.users.apikeys"]._check_credentials(
            scope="rpc", key=api_key
        )
        if not user_id:
            raise BadRequest(_("API key invalid"))

        # Actualizar el entorno de request con el usuario autenticado
        request.update_env(user_id)
