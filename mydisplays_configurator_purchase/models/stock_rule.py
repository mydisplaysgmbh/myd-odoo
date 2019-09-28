from odoo import fields, models, api


class StockRule(models.Model):
	_inherit = 'stcok.rule'

	@api.multi
    def _prepare_purchase_order_line(self, product_id, product_qty, product_uom, values, po, partner):
    	res = super(product_id=product_id, product_qty=product_qty,
    		product_uom=product_uom, values=values, po=po, partner=partner)
    	res.update({'cfg_session_id': values.get('cfg_session_id')})
    	return res