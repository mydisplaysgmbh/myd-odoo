from odoo import http
from odoo.http import request
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.website_product_configurator.controllers.main import\
    ProductConfigWebsiteSale
from odoo.addons.website_product_configurator.controllers.main import\
    get_pricelist



class MydisplaysConfigWebsiteSale(ProductConfigWebsiteSale):


    @http.route()
    def save_configuration(self, form_values, current_step=False,
                           next_step=False):
        res = super(MydisplaysConfigWebsiteSale, self).save_configuration(
            form_values=form_values, current_step=current_step, next_step=next_step)
        if res:
            redirect_url = res.get('redirect_url', False)
            config_session = request.env['product.config.session'].browse(res.get('config_session'))
            product = request.env['product.product'].browse(res.get('product_id'))
            if redirect_url:
                redirect_url = "/website_product_configurator/open_product"
                redirect_url += '/%s' % (slug(config_session))
                redirect_url += '/%s' % (slug(product))
                res.update({'redirect_url': redirect_url})
                return res
        return {}

    @http.route(
        '/website_product_configurator/open_product/'
        '<model("product.config.session"):config_session_id>/'
        '<model("product.product"):product_id>',
        type='http', auth="public", website=True)
    def config_session(self, product_id, config_session_id, **post):
        """Render product page of product_id"""
        product_tmpl_id = product_id.product_tmpl_id

        custom_vals = sorted(
            product_id.value_custom_ids,
            key=lambda obj: obj.attribute_id.sequence
        )
        vals = sorted(
            product_id.attribute_value_ids,
            key=lambda obj: obj.attribute_id.sequence
        )
        pricelist = get_pricelist()
        if request.session['product_config_session'].get(product_tmpl_id.id):
            product_config_session = request.session['product_config_session']
            del product_config_session[product_tmpl_id.id]
            request.session['product_config_session'] = product_config_session
        values = {
            'product_id': product_id,
            'product_tmpl': product_tmpl_id,
            'config_session': config_session_id,
            'pricelist': pricelist,
            'custom_vals': custom_vals,
            'vals': vals,
        }
        return request.render(
            "website_product_configurator.cfg_product_variant", values)
