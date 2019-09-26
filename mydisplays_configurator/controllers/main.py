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
        vals["cfg_session_price"] = json_session_vals.get("price", 0)
        vals["cfg_session_weight"] = json_session_vals.get("weight", 0)
        return vals
