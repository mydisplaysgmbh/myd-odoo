from odoo import fields, models


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

    def _merge_in_existing_line(self, product_id, product_qty, product_uom, location_id, name, origin, values):
        res = super(PurchaseOrderLine, self)._merge_in_existing_line(
            product_id=product_id, product_qty=product_qty, product_uom=product_uom,
            location_id=location_id, name=name, origin=origin, values=values)
        if not values.get('cfg_session_id'):
            return res
        return False