from odoo import models, fields, tools, api, _


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
