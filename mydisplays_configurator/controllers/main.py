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
                           next_step=False, **post):
        res = super(MydisplaysConfigWebsiteSale, self).save_configuration(
            form_values=form_values, current_step=current_step,
            next_step=next_step, post=post)
        try:
            redirect_url = res.get('redirect_url', False)
            if not redirect_url:
                return res
            config_session = request.env['product.config.session'].browse(
                res.get('config_session'))
            product = request.env['product.product'].browse(
                res.get('product_id'))
            if redirect_url:
                redirect_url = "/website_product_configurator/configuration"
                redirect_url += '/%s' % (slug(config_session))
                res.update({'redirect_url': redirect_url})
                return res
        except Exception as Ex:
            return {'error': Ex}
        return {}

    @http.route(
        '/website_product_configurator/configuration/'
        '<model("product.config.session"):config_session_id>',
        type='http', auth="public", website=True)
    def config_session(self, config_session_id, **post):
        """Render product page of product_id"""
        if not config_session_id.exists():
            return request.render("website.404")
        product_id = config_session_id.product_id
        product_tmpl_id = config_session_id.product_tmpl_id
        if not product_tmpl_id.exists():
            return request.render("website.404")

        cfg_user_id = config_session_id.user_id
        user_id = request.env.user

        check_for_session = (
            product_id.product_tmpl_id == product_tmpl_id and
            cfg_user_id == user_id and
            config_session_id.state == 'done'
        ) and True or False

        if not check_for_session:
            return request.redirect('/shop/product/%s' % slug(product_tmpl_id))

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
            'custom_vals': config_session_id.json_config,
            'json_vals': config_session_id.json_vals,
            'attr_data': product_tmpl_id.config_cache.get('attrs', {}),
            'vals': vals,
        }
        return request.render(
            "website_product_configurator.cfg_product_variant", values)
