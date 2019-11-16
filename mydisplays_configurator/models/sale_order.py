from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def _cart_update(self, product_id=None, line_id=None,
                     add_qty=0, set_qty=0, **kwargs):
        config_session_id = kwargs.get('config_session_id', False)
        if not config_session_id and line_id:
            order_line = self._cart_find_product_line(
                product_id, line_id, **kwargs)[:1]
            config_session_id = order_line.cfg_session_id.id

        if not config_session_id:
            return res

        config_session_id = int(config_session_id)
        product = product_id
        if not product:
            config_session = self.env['product.config.session'].browse(
                config_session_id
            )
            product = config_session.product_id.id
        session_map = {
            product: config_session_id
        }
        self = self.with_context(product_sessions=session_map)
        return super(SaleOrder, self)._cart_update(
            product_id=product_id, line_id=line_id, add_qty=add_qty,
            set_qty=set_qty, **kwargs
        )

    @api.multi
    def _website_product_id_change(self, order_id, product_id, qty=0):
        values = super(SaleOrder, self)._website_product_id_change(
            order_id=order_id, product_id=product_id, qty=qty
        )
        session_map = self.env.context.get('product_sessions', {})
        if session_map.get(product_id, False):
            values.update({'cfg_session_id': session_map.get(product_id)})
        return values

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

    @api.onchange('product_id', 'price_unit',
                  'product_uom', 'product_uom_qty', 'tax_id')
    def _onchange_discount(self):
        if self.cfg_session_id:
            self = self.with_context(
                product_sessions={self.product_id.id: self.cfg_session_id.id}
            )
        return super(SaleOrderLine, self)._onchange_discount()

    @api.multi
    def _get_display_price(self, product):
        if self.cfg_session_id:
            session_map = {self.product_id.id: self.cfg_session_id.id}
            self = self.with_context(product_sessions=session_map)
            product = product.with_context(product_sessions=session_map)
        res = super(SaleOrderLine, self)._get_display_price(
            product=product)
        return res

