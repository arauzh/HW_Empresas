# -*- coding: utf-8 -*-

from odoo import models

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_stock_moves(self, picking):
        # Obtener los valores base que genera Odoo
        res = super(PurchaseOrderLine, self)._prepare_stock_moves(picking)
        
        # Mapear la distribución analítica a cada línea de stock.move generada
        for re in res:
            if self.analytic_distribution:
                re['analytic_distribution'] = self.analytic_distribution
                
        return res