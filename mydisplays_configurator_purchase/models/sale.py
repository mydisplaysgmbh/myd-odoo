from odoo import models, api


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.multi
    def _purchase_service_prepare_line_values(
        self, purchase_order, quantity=False
    ):
        res = super(SaleOrderLine, self)._purchase_service_prepare_line_values(
            purchase_order=purchase_order, quantity=quantity
        )
        if self.cfg_session_id:
            res.update({'cfg_session_id': self.cfg_session_id.id})
        return res
