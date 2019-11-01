import json
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    json_name = fields.Char(
        name='JSON Name',
        required=True,
    )
    invisible = fields.Boolean(
        string="Invisible",
        help="Set in order to make attribute invisible in the configuration "
        "interface",
    )

    _sql_constraints = [('unique_attribute_json_name', 'unique(json_name)',
                         'Json name must be unique for each attribute')]

    @api.onchange("invisible")
    def _onchange_display_attribute(self):
        """Remove required attribute from line due to limited support for
        autofilling empty values"""
        for attr_id in self.filtered(lambda x: x.invisible):
            attr_id.required = False

    @api.model_create_multi
    def create(self, vals_list):
        for attr_vals in vals_list:
            if 'json_name' not in attr_vals:
                json_name = attr_vals.get('name').replace(" ", "_")
                attr_vals['json_name'] = json_name
        res = super(ProductAttribute, self).create(vals_list=vals_list)
        return res

    @api.multi
    def copy(self, default=None):

        if not default:
            default = {}

        default.update({
            'json_name': self.json_name + '_copy'
        })

        return super(ProductAttribute, self).copy(default=default)


class ProductAttributeLine(models.Model):
    _inherit = "product.template.attribute.line"

    invisible = fields.Boolean(
        string="Invisible",
        help="Set in order to make attribute invisible in the configuration "
        "interface",
    )

    @api.onchange("attribute_id")
    def onchange_attribute(self):
        res = super(ProductAttributeLine, self).onchange_attribute()
        self.invisible = self.attribute_id.invisible
        return res

    @api.onchange("invisible")
    def _onchange_display_attribute(self):
        """Remove required attribute from line due to limited support for
        autofilling empty values"""
        for attr_id in self.filtered(lambda x: x.invisible):
            attr_id.required = False


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    @api.onchange('product_id')
    def onchange_product(self):
        if not self.product_id:
            self.operation_id = None

    operation_id = fields.Many2one(
        comodel_name='mrp.routing.workcenter',
        string='Operation / Workcenter',
    )
    json_context = fields.Text(
        string='Json Context',
        default='{}',
        help="JSON dictionary to provide data to formula fields * Warning: "
        "values added here will overwrite any cached fields from the template"
    )

    @api.constrains('json_context')
    def _check_json_context(self):
        for attr_val in self.sudo().filtered('json_context'):
            try:
                json.loads(attr_val.json_context.strip())
            except Exception:
                raise ValidationError(_(
                    'Please provide a valid JSON object and be sure to use '
                    'double quotes "" for keys and delete trailing commas'
                ))

    @api.multi
    def name_get(self):
        res = super(ProductAttributeValue, self).name_get()
        if not self._context.get('show_price_extra'):
            return res
        product_tmpl_id = self.env.context.get('active_id', False)
        product_tmpl = self.env['product.template'].browse(
            int(product_tmpl_id)
        )
        tmpl_config_cache = product_tmpl.config_cache or {}
        res_prices = []

        for attr_val in res:
            attr_vals = tmpl_config_cache.get('attr_vals', {})
            json_vals = attr_vals.get(str(attr_val[0]), {})
            price_extra = json_vals.get('price')
            if price_extra:
                val_id = self.env['product.attribute.value'].browse(
                    attr_val[0]
                )
                attr_val = (
                    val_id.id, '%s ( +%s )' % (val_id.name, price_extra)
                )
            res_prices.append(attr_val)
        return res_prices

    def get_attr_value_name(self, product_tmpl, pricelist_id):
        self = self.with_context({
            'show_price_extra': False,
            'active_id': product_tmpl.id,
            'show_attribute': False,
        })

        res = self.name_get()
        product_tmpl_id = self.env.context.get('active_id', False)
        product_tmpl = self.env['product.template'].browse(
            int(product_tmpl_id)
        )
        tmpl_config_cache = product_tmpl.config_cache or {}
        res_prices = []

        for attr_val in res:
            attr_vals = tmpl_config_cache.get('attr_vals', {})
            json_vals = attr_vals.get(str(attr_val[0]), {})
            price_extra = json_vals.get('price')
            if price_extra:
                val_id = self.env['product.attribute.value'].browse(
                    attr_val[0]
                )
                attr_val = (
                    val_id.id, '%s ( +%s )' % (val_id.name, price_extra)
                )
            res_prices.append(attr_val)
        return res_prices
