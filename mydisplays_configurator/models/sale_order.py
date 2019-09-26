
from odoo import fields, models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bom_id = fields.Many2one(
        string='Bill Of Material',
        ondelete='cascade',
        domain="[('product_id', '=', product_id)]",
        comodel_name='mrp.bom'
    )
    cfg_session_id = fields.Many2one(
        comodel_name="product.config.session",
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


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def _cart_update(self, product_id=None, line_id=None,
        add_qty=0, set_qty=0, **kwargs):
        res = super(SaleOrder, self)._cart_update(
            product_id=product_id, line_id=line_id, add_qty=add_qty, set_qty=set_qty, **kwargs)
        config_session_id = kwargs.get('config_session_id')
        if config_session_id:
            config_session_id = int(config_session_id)
            order_line = self.env['sale.order.line'].browse(res.get('line_id'))
            for line in order_line:
                line.cfg_session_id = config_session_id
        return res