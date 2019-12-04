from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    route_warning = fields.Text(
        string="Warning", copy=False,
        compute="_compute_route_warning"
    )

    def _compute_route_warning(self, warning_message=None):
        for sale_order in self:
            if warning_message:
                sale_order.route_warning = warning_message
                continue

            message_list = []
            wrong_route_lines = self.env['sale.order.line']
            lines_without_route = self.env['sale.order.line']
            for line in sale_order.order_line:
                cfg_session_id = line.cfg_session_id
                if not line.product_id.config_ok or not cfg_session_id:
                    continue
                result = cfg_session_id._create_get_route()
                routes = result.get('route')
                workcenter_ids = result.get('workcenters')
                if not workcenter_ids:
                    continue
                if routes:
                    if line.bom_id and not line.bom_id.routing_id:
                        lines_without_route += line
                        continue
                    if (line.bom_id and
                            line.bom_id.routing_id.id not in routes.ids):
                        wrong_route_lines += line
                        continue
                    continue
                message_list.append({
                    'workcenters': workcenter_ids,
                    'product': line.product_id,
                })
            session_obj = self.env['product.config.session']
            warning_message = ''
            if message_list:
                warning_message = session_obj.get_route_warning_message(
                    message_list
                )
            if lines_without_route:
                warning_message += warning_message and '\n\n' or ''
                warning_message += (
                    "Following products do not have routes on linked bom. "
                    "Please set manually.\nProducts : %s" % (
                        ', '.join(lines_without_route.mapped("product_id.name"))
                    )
                )
            if wrong_route_lines:
                warning_message += warning_message and '\n\n' or ''
                warning_message += (
                    "Bill of material linked to following products "
                    "have wrong route according to the configuration on it's "
                    "attribute values.\nProducts : %s" % (
                        ', '.join(wrong_route_lines.mapped("product_id.name"))
                    )
                )
            sale_order.route_warning = warning_message or False

    @api.multi
    def _cart_update(self, product_id=None, line_id=None,
                     add_qty=0, set_qty=0, **kwargs):
        config_session_id = kwargs.get('config_session_id', False)
        if not config_session_id and line_id:
            order_line = self._cart_find_product_line(
                product_id, line_id, **kwargs)[:1]
            config_session_id = order_line.cfg_session_id.id

        if config_session_id:
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
    def _cart_find_product_line(self, product_id=None, line_id=None, **kwargs):
        """Include Config session in search.
        """
        order_line = super(SaleOrder, self)._cart_find_product_line(
            product_id=product_id,
            line_id=line_id,
            **kwargs
        )
        # Onchange quantity in cart
        if line_id:
            return order_line

        config_session_id = kwargs.get('config_session_id', False)
        if not config_session_id:
            session_map = self.env.context.get('product_sessions', {})
            config_session_id = session_map.get(product_id, False)
        if not config_session_id:
            return order_line

        order_line = order_line.filtered(
            lambda p: p.cfg_session_id.id == int(config_session_id)
        )
        return order_line

    @api.multi
    def action_confirm(self):
        """Create bom and write to line before confirming sale order"""
        config_order_lines = self.mapped('order_line').filtered(
            lambda l: l.config_ok and l.cfg_session_id
        )
        for so_line in config_order_lines:
            bom_id, warning_message = (
                so_line.cfg_session_id._create_bom_from_json()
            )
            so_line.bom_id = bom_id
            if warning_message:
                warning_message += self.route_warning or ''
                self.route_warning = warning_message
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
