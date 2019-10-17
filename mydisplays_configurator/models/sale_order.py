from odoo import fields, models, api


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
        order_line = self.env['sale.order.line'].browse(res.get('line_id'))
        for line in order_line:
            line.cfg_session_id = config_session_id
            bom_id = line._create_bom_from_json()
            line.write({
                'bom_id': bom_id,
                'price_unit': line.cfg_session_id.json_vals.get('price')
            })


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

    def _create_bom_from_json(self):
        """Create a bill of material from the json custom vallues attached on
        the related session and link it on the sale order line
        """
        json_vals = self.cfg_session_id.json_vals
        bom_lines = json_vals.get('bom', [])

        if not bom_lines:
            return None

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'product_id': self.product_id.id,
            'bom_line_ids': [(0, 0, line_data) for line_data in bom_lines]
        })

        return bom.id
