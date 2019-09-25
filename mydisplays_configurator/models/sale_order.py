
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    bom_id = fields.Many2one(
        string='Bill Of Material',
        ondelete='cascade',
        domain="[('product_id', '=', product_id)]",
        comodel_name='mrp.bom'
    )
