from odoo import api, models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_procurement_values(self):
        values = super(StockMove, self)._prepare_procurement_values()
        if self.cfg_session_id:
            values.update({"cfg_session_id": self.cfg_session_id.id})
        return values
