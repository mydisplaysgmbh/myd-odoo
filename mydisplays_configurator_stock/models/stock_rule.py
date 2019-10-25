from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_custom_move_fields(self):
        res = super(StockRule, self)._get_custom_move_fields()
        res.append('cfg_session_id')
        return res
