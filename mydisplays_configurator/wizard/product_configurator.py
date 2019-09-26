from odoo import models, api


class ProductConfigurator(models.TransientModel):
    _inherit = "product.configurator"

    @api.model
    def create(self, vals):
        wizard = super(ProductConfigurator, self).create(vals)
        if wizard.custom_value_ids:
            wizard.config_session_id.set_default_cfg_session_json_dictionary(
                wizard.custom_value_ids
            )
        return wizard


class ProductConfiguratorSale(models.TransientModel):
    _inherit = "product.configurator.sale"

    def _get_order_line_vals(self, product_id):
        """ Link session with ssale order lines"""

        line_vals = super(ProductConfiguratorSale, self)._get_order_line_vals(
            product_id=product_id
        )
        line_vals.update({"cfg_session_id": self.config_session_id.id})
        return line_vals
