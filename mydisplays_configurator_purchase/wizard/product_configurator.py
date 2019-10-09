from odoo import models


class ProductConfiguratorSale(models.TransientModel):
    _inherit = "product.configurator.purchase"

    def _get_order_line_vals(self, product_id):
        """ Link session with ssale order lines"""

        line_vals = super(ProductConfiguratorSale, self)._get_order_line_vals(
            product_id=product_id
        )
        line_vals.update({"cfg_session_id": self.config_session_id.id})
        return line_vals
