from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def _cart_update(self, product_id=None, line_id=None,
                     add_qty=0, set_qty=0, **kwargs):
        res = super(SaleOrder, self)._cart_update(
            product_id=product_id, line_id=line_id, add_qty=add_qty,
            set_qty=set_qty, **kwargs)

        config_session_id = kwargs.get('config_session_id', False)
        if not config_session_id:
            return res

        config_session_id = int(config_session_id)
        config_session = self.env['product.config.session'].browse(
            config_session_id
        )
        order_line = self.env['sale.order.line'].browse(res.get('line_id'))
        for line in order_line:
            line.write({
                'cfg_session_id': config_session.id,
                'price_unit': config_session.json_vals.get('price_unit'),
            })

    @api.multi
    def action_confirm(self):
        """Create bom and write to line before confirming sale order"""
        config_order_lines = self.mapped('order_line').filtered(
            lambda l: l.config_ok and l.cfg_session_id
        )
        for so_line in config_order_lines:
            so_line.bom_id = so_line.cfg_session_id._create_bom_from_json()
        return super(SaleOrder, self).action_confirm()


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

    @api.constrains('cfg_session_id', 'product_id')
    def check_product_config_session(self):
        """Ensure there are no inconsistencies between the products and
        attached configuration sessions"""
        for line in self.filtered(lambda l: l.cfg_session_id):
            if line.product_id != line.cfg_session_id.product_id:
                raise ValidationError(_(
                    'Product on sale order line must match the product on the '
                    'related configuration session - %s' %
                    line.cfg_session_id.name)
                )
