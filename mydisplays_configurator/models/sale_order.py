from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    route_warning = fields.Text(
        string="Warning", copy=False,
        compute="_compute_route_warning"
    )
    bom_route_warning = fields.Text(
        string="BOM Route Warning", copy=False,
        compute="_compute_bom_route_warning"
    )

    def _compute_bom_route_warning(self):
        for sale_order in self:
            if sale_order.state in ['draft', 'sent']:
                continue
            order_line = sale_order.order_line
            lines_without_route = order_line.mapped('bom_id').filtered(
                lambda bom: not bom.routeing_id
            )
            if lines_without_route:
                sale_order.bom_route_warning = (
                    "Following products do not have routes on linked bom. "
                    "Please set manually.\nProducts : %s" % (
                        ', '.join(lines_without_route.mapped("name"))
                    )
                )
            else:
                sale_order.bom_route_warning = False

    def _compute_route_warning(self, warning_message=None):
        for sale_order in self:
            if warning_message:
                sale_order.route_warning = warning_message
                continue

            message_list = []
            for line in sale_order.order_line:
                cfg_session_id = line.cfg_session_id
                if not line.product_id.config_ok or not cfg_session_id:
                    continue
                result = cfg_session_id._create_get_route()
                route = result.get('route')
                workcenter_ids = result.get('workcenters')
                if route or not workcenter_ids:
                    continue
                message_list.append({
                    'workcenters': workcenter_ids,
                    'product': line.product_id,
                })
            session_obj = self.env['product.config.session']
            warning_message = session_obj.get_route_warning_message(
                message_list)
            sale_order.route_warning = warning_message

    @api.multi
    def _cart_update(self, product_id=None, line_id=None,
                     add_qty=0, set_qty=0, **kwargs):
        res = super(SaleOrder, self)._cart_update(
            product_id=product_id, line_id=line_id, add_qty=add_qty,
            set_qty=set_qty, **kwargs)

        config_session_id = kwargs.get('config_session_id', False)
        if not config_session_id and line_id:
            order_line = self._cart_find_product_line(
                product_id, line_id, **kwargs)[:1]
            config_session_id = order_line.cfg_session_id.id

        if not config_session_id:
            return res

        config_session_id = int(config_session_id)
        config_session = self.env['product.config.session'].browse(
            config_session_id
        )
        order_line = self.env['sale.order.line'].browse(res.get('line_id'))
        order_line.write({
            'cfg_session_id': config_session.id,
            'price_unit': config_session.get_session_price() or 0.0,
        })
        return res

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
