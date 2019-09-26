import json
from odoo import http
from odoo.http import request
from odoo.addons.website_product_configurator.controllers.main\
 import ProductConfigWebsiteSale
from odoo.addons.website_sale.controllers.main import WebsiteSale



def get_pricelist():
    sale_order = request.env.context.get('sale_order')
    if sale_order:
        pricelist = sale_order.pricelist_id
    else:
        partner = request.env.user.partner_id
        pricelist = partner.property_product_pricelist
    return pricelist


class MydisplayConfigWebsiteSale(ProductConfigWebsiteSale):

    @http.route(
        '/website_product_configurator/open_product/'
        '<model("product.product"):product_id>',
        type='http', auth="public", website=True)
    def cfg_session(self, product_id, **post):
        """Render product page of product_id"""
        product_tmpl_id = product_id.product_tmpl_id
        try:
            config_session_id = self.get_config_session(
                product_tmpl_id=product_tmpl_id)
        except Exception as Ex:
            return {'error': Ex}

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


class WebsiteSale(WebsiteSale):
    
    @http.route(['/shop/cart/update'], type='http', auth="public", methods=['POST'], website=True, csrf=False)
    def cart_update(self, product_id, add_qty=1, set_qty=0, **kw):
        """This route is called when adding a product to cart (no options)."""
        print("kw ",kw)
        sale_order = request.website.sale_get_order(force_create=True)
        if sale_order.state != 'draft':
            request.session['sale_order_id'] = None
            sale_order = request.website.sale_get_order(force_create=True)

        product_custom_attribute_values = None
        if kw.get('product_custom_attribute_values'):
            product_custom_attribute_values = json.loads(kw.get('product_custom_attribute_values'))

        no_variant_attribute_values = None
        if kw.get('no_variant_attribute_values'):
            no_variant_attribute_values = json.loads(kw.get('no_variant_attribute_values'))
        if kw.get('config_session_id'):
            config_session_id = kw.get('config_session_id')
        sale_order._cart_update(
            product_id=int(product_id),
            add_qty=add_qty,
            set_qty=set_qty,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_values=no_variant_attribute_values,
            config_session_id=config_session_id,
        )
        return request.redirect("/shop/cart")

    # @http.route(['/shop/cart/update_json'], type='json', auth="public", methods=['POST'], website=True, csrf=False)
    # def cart_update_json(self, product_id, line_id=None, add_qty=None, set_qty=None, display=True):
    #     res = super(WebsiteSale, self).cart_update_json(
    #         product_id=product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, display=display)
    #     print("\n\n\n res", res, )
