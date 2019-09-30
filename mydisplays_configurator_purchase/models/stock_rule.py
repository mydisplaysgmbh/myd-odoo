from odoo import models, api


class StockRule(models.Model):
    _inherit = 'stock.rule'

    @api.model
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, values, po, supplier):
        res = super(StockRule, self)._prepare_purchase_order_line(
            product_id, product_qty, product_uom, values, po, supplier)
        res['cfg_session_id'] = values.get('cfg_session_id', False)
        return res
