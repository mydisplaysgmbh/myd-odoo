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
