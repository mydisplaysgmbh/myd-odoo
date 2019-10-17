import json
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    json_name = fields.Char(
        name='JSON Name',
        required=True,
    )
    is_website_visible = fields.Boolean(
        string="Website",
        default=True,
        help="Set in order to make attribute visible on "
        "website(work only for configurable products)",
    )

    _sql_constraints = [('unique_attribute_json_name', 'unique(json_name)',
                         'Json name must be unique for each attribute')]

    @api.onchange("is_website_visible")
    def _onchange_display_attribute(self):
        for attr_id in self:
            if attr_id.is_website_visible:
                return
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

    is_website_visible = fields.Boolean(
        string="Website",
        default=True,
        help="Set in order to make attribute visible on "
        "website(work only for configurable products)",
    )

    @api.onchange("attribute_id")
    def onchange_attribute(self):
        res = super(ProductAttributeLine, self).onchange_attribute()
        self.is_website_visible = self.attribute_id.is_website_visible
        return res

    @api.onchange("is_website_visible")
    def _onchange_display_attribute(self):
        for attr_line in self:
            if attr_line.is_website_visible:
                return
            attr_line.required = False

    @api.multi
    @api.constrains("is_website_visible")
    def _check_default_values(self):
        for template in self.mapped("product_tmpl_id"):
            if not template.attribute_line_ids.filtered(
                lambda l: l.is_website_visible
            ):
                raise ValidationError(
                    _("Please set at least one attribute visible on website.")
                )


class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

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
