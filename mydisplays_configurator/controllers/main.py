import json
from odoo import http
from odoo.http import request
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.website_product_configurator.controllers.main import\
    ProductConfigWebsiteSale
from odoo.addons.website_product_configurator.controllers.main import\
    get_pricelist
from odoo.addons.website_sale.controllers.main import WebsiteSale


class MydisplaysConfigWebsiteSale(ProductConfigWebsiteSale):

    @http.route()
    def product(self, product, category='', search='', **kwargs):
        """ Temporary workaround to allow deployment of configurator
        to live instance without disrupting views until we can adapt
        the design of the configurator to the theme"""
        if request.env.user.id in [1, 2]:
            # return WebsiteSale.product(product, category, search, **kwargs)
            return super(MydisplaysConfigWebsiteSale, self).product(
                product, category, search, **kwargs
            )
        return super(ProductConfigWebsiteSale, self).product(
            product, category, search, **kwargs
        )

    def get_render_vals(self, cfg_session):
        """Return dictionary with values required for website template
        rendering"""
        vals = super(MydisplaysConfigWebsiteSale, self).get_render_vals(
            cfg_session=cfg_session
        )
        json_session_vals = cfg_session.json_vals
        config_cache = cfg_session.product_tmpl_id.config_cache
        vals.update({
            'json_session_vals': json_session_vals or {},
            'config_cache': config_cache or {},
        })
        return vals

    @http.route()
    def onchange(self, form_values, field_name, **post):
        """Capture onchange events in the website and forward data to backend
        onchange method"""
        updates = super(MydisplaysConfigWebsiteSale, self).onchange(
            form_values=form_values,
            field_name=field_name,
            **post
        )
        values = updates.get('value')
        if not values:
            return updates
        product_configurator_obj = request.env["product.configurator"]
        dynamic_values = product_configurator_obj._get_dynamic_fields(values)
        updates['dynamic_values'] = dynamic_values
        return updates

    @http.route()
    def save_configuration(self, form_values, current_step=False,
                           next_step=False, **post):
        res = super(MydisplaysConfigWebsiteSale, self).save_configuration(
            form_values=form_values,
            current_step=current_step,
            next_step=next_step,
            **post
        )
        try:
            redirect_url = res.get('redirect_url', False)
            if not redirect_url:
                return res
            config_session = request.env['product.config.session'].browse(
                res.get('config_session'))
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
        '<model("product.config.session"):config_session>',
        type='http', auth="public", website=True)
    def config_session(self, config_session, **post):
        """Render product page of product_id"""
        if not config_session.exists():
            return request.render("website.404")
        product = config_session.product_id
        product_tmpl = config_session.product_tmpl_id
        if not product_tmpl.exists():
            return request.render("website.404")

        cfg_user_id = config_session.user_id
        user_id = request.env.user

        check_for_session = (
            product.product_tmpl_id == product_tmpl and
            cfg_user_id == user_id and
            config_session.state == 'done'
        ) and True or False

        if not check_for_session:
            return request.redirect('/shop/product/%s' % slug(product_tmpl))

        vals = sorted(
            product.attribute_value_ids,
            key=lambda obj: obj.attribute_id.sequence
        )
        custom_vals = config_session.json_config.get('custom_values', {})
        pricelist = get_pricelist()
        if request.session['product_config_session'].get(product_tmpl.id):
            product_config_session = request.session['product_config_session']
            del product_config_session[product_tmpl.id]
            request.session['product_config_session'] = product_config_session

        product_qty = config_session.get_session_qty()

        values = {
            'product_id': product,
            'product_tmpl': product_tmpl,
            'config_session': config_session,
            'pricelist': pricelist,
            'product_qty': product_qty,
            'custom_vals': custom_vals,
            'json_vals': config_session.json_vals,
            'attr_data': product_tmpl.config_cache.get('attrs', {}),
            'vals': vals,
        }

        return request.render(
            "website_product_configurator.cfg_product_variant", values
        )


class WebsiteSale(WebsiteSale):
    @http.route(
        ["/shop/cart/update"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False,
    )
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        """This route is called when adding a product to cart (no options)."""
        sale_order = request.website.sale_get_order(force_create=True)
        if sale_order.state != 'draft':
            request.session['sale_order_id'] = None
            sale_order = request.website.sale_get_order(force_create=True)

        product_custom_attribute_values = None
        if kw.get('product_custom_attribute_values'):
            product_custom_attribute_values = json.loads(
                kw.get('product_custom_attribute_values')
            )

        no_variant_attribute_values = None
        if kw.get('no_variant_attribute_values'):
            no_variant_attribute_values = json.loads(
                kw.get('no_variant_attribute_values')
            )

        if kw.get('product_qty'):
            try:
                set_qty = int(kw.get('product_qty'))
            except Exception:
                pass

        sale_order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            # Custom code
            config_session_id=kw.get('config_session_id', False)
            # End
        )
        return request.redirect("/shop/cart")
