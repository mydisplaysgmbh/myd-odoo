from odoo import http
from odoo.http import request
from odoo.addons.website_product_configurator.controllers.main import (
    ProductConfigWebsiteSale as WebsiteSale,
)


class ProductConfigWebsiteSale(WebsiteSale):
    def get_render_vals(self, cfg_session):
        """Return dictionary with values required for website template
        rendering"""
        vals = super(ProductConfigWebsiteSale, self).get_render_vals(
            cfg_session=cfg_session
        )
        json_session_vals = cfg_session.json_vals
        if json_session_vals:
            vals.update({'json_session_vals': json_session_vals})
        return vals
