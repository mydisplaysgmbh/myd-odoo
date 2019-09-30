from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.multi
    def _prepare_procurement_values(self, group_id=False):
        res = super(SaleOrderLine, self)._prepare_procurement_values(
            group_id=group_id)
        res.update({'cfg_session_id': self.cfg_session_id.id})
        print("\n\n\n _prepare_procurement_values", self.cfg_session_id.id, self)
        return res

    # @api.multi
    # def _purchase_service_prepare_line_values(self, purchase_order, quantity=False):
    #     res = super(SaleOrderLine, self)._purchase_service_prepare_line_values(
    #         purchase_order=purchase_order, quantity=quantity)
    #     print("\n\n\n SaleOrderLine res", res)
    #     res.update({'cfg_session_id': self.cfg_session_id.id})
    #     return res
