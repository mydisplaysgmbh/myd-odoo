from odoo import models


class ProviderGrid(models.Model):
    _inherit = 'delivery.carrier'

    def _get_price_available(self, order):
        self.ensure_one()
        session_map = {}
        for line in order.order_line:
            if not line.cfg_session_id or not line.product_id.config_ok:
                continue
            session_map[line.product_id.id] = line.cfg_session_id.id
        order = order.with_context(product_sessions=session_map)
        return super(ProviderGrid, self)._get_price_available(order=order)
