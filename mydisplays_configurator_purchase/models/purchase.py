from odoo import api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    cfg_session_id = fields.Many2one(
        comodel_name='product.config.session',
        ondelete="restrict",
        string="Session",
        help="Configuration Session"
    )
    custom_value_ids = fields.One2many(
        comodel_name="product.config.session.custom.value",
        inverse_name="cfg_session_id",
        related="cfg_session_id.custom_value_ids",
        string="Custom Values",
    )
