import json
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    json_name = fields.Char(
        name='JSON Name',
        required=True,
    )

    _sql_constraints = [('unique_attribute_json_name', 'unique(json_name)',
                         'Json name must be unique for each attribute')]


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
                raise ValidationError(
                    'Please provide a valid JSON object and be sure to use '
                    'double quotes "" for keys'
                )
