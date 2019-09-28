from odoo import fields, api, models

class SaleOrder(models.Model):
    _inherit = 'sale.order.line'

    @api.multi
    def _prepare_procurement_values(self, group_id=False):
        res = super(SaleOrder, self)._prepare_procurement_values(
            group_id=group_id)
        if res:
            res.update({'cfg_session_id': self.cfg_session_id.id})
        return res
