import json
import pprint

from odoo import api, fields, models, _
from odoo.tools.safe_eval import test_python_expr
from odoo.exceptions import ValidationError

DEFAULT_PYTHON_CODE = """# Available variables:
#  - config: Current configuration expressed as json
#  - session: Object to store computed values on\n\n\n\n
"""


class ProductTemplate(models.Model):
    _inherit = "product.template"

    """Store product.template configuration data in a serialized computed field
    in an attempt to reduce latency and read/write cycles for an efficient
    configuration process

        {
            'attr_json_map': {
                'id_1': 'length',
                'id_2': 'width'
            },
            'attrs': {
                'attr_id_1': {
                    'name': attribute.name,
                    'custom': attribute.val_custom,
                    'custom_type': attribute.custom_type,
                    'required': attribute.required,
                }
            }
            'attr_vals': {
                'val_id_1': {
                    'attribute_id': attribute.id,
                    'custom_type': 'float',
                    'price_extra': 'number'
                    'product_id': product_id,
                    'price': 'product_price',
                    'weight': 'product_weight'
                        }
                    }
                }
                }
            }
        }

    """

    def get_attr_val_json_tree(self):
        """Data to include inside json tree from attribute_value onward"""
        return [
            "json_context",
            "product_id",
            "product_id.price",
            "product_id.weight",
        ]

    def get_config_dependencies(self):
        """Return fields used in computing the config cache"""
        constraints = [
            "attribute_line_ids",
            "attribute_line_ids.value_ids",
            "attribute_line_ids.attribute_id",
            "attribute_line_ids.attribute_id.json_name",
            "attribute_line_ids.attribute_id.val_custom",
            "attribute_line_ids.attribute_id.custom_type",
            "product_template_value_ids",
            "product_template_value_ids.product_attribute_value_id",
            "product_template_value_ids.attribute_id",
            "product_template_value_ids.price_extra",
        ]
        attr_val_prefix = "attribute_line_ids.attribute_id.value_ids.%s"
        attr_val_constraints = self.get_attr_val_json_tree()
        attr_val_constraints = [
            attr_val_prefix % cst for cst in attr_val_constraints
        ]
        constraints += attr_val_constraints
        return constraints

    @api.multi
    @api.depends(get_config_dependencies)
    def _get_config_data(self):
        for product_tmpl in self.filtered(lambda x: x.config_ok):
            """Fetch configuration data related to templates and store them as
            json in config_cache serialized field"""
            attr_lines = product_tmpl.attribute_line_ids
            attrs = attr_lines.mapped("attribute_id")
            json_tree = {
                # Map attribute ids to their respective json name
                "attrs": {},
                "attr_vals": {},
                "attr_json_map": {
                    '%s' % (a.id): a.json_name for a in attrs if a.json_name
                },
            }

            tmpl_attr_val_obj = self.env["product.template.attribute.value"]

            # Get tmpl attr val objects with weight or price extra
            product_tmpl_attr_vals = tmpl_attr_val_obj.search_read(
                [("product_tmpl_id", "=", product_tmpl.id)],
                ["price_extra", "weight_extra", "product_attribute_value_id"],
            )

            attr_vals_extra = {
                v["product_attribute_value_id"][0]: {
                    "price_extra": v["price_extra"],
                    "weight_extra": v["weight_extra"],
                }
                for v in product_tmpl_attr_vals
            }

            for line in attr_lines:
                attr = line.attribute_id
                json_tree["attrs"]['%s' % (attr.id)] = {
                    "required": line.required,
                    "multi": line.multi,
                    "custom": line.custom,
                    "custom_type": attr.custom_type,
                    "name": attr.name
                }
                for attr_val in line.value_ids:
                    val_tree = json_tree["attr_vals"][
                        '%s' % (attr_val.id)
                    ] = {}
                    val_tree.update(
                        {
                            "attribute_id": attr.id,
                            "product_id": 0,
                            "price": 0,
                            "weight": 0,
                        }
                    )

                    # Load extra info from attribute value or related product
                    # if we decide to change approach (or both?)
                    if attr_val.json_context:
                        val_tree.update(json.loads(attr_val.json_context))

                    # Product info
                    product = attr_val.product_id
                    if product:
                        pricelist = (
                            self.env.user.partner_id.property_product_pricelist
                        )
                        val_tree["product_id"] = product.id
                        val_tree["price"] = product.with_context(
                            pricelist=pricelist.id
                        ).price
                        val_tree["weight"] = product.weight
                    else:
                        val_tree["price"] = attr_vals_extra.get(
                            attr_val.id, {}
                        ).get("price_extra", 0)
                        val_tree["weight"] = attr_vals_extra.get(
                            attr_val.id, {}
                        ).get("weight_extra", 0)
            product_tmpl.config_cache = json_tree
            product_tmpl.config_cache_debug = pprint.pformat(json_tree)

    config_cache = fields.Serialized(
        name="Cached configuration data",
        compute="_get_config_data",
        readonly=True,
        store=True,
        help="Store data used for configuration in json format for quick "
        "access and low latency",
    )
    config_cache_debug = fields.Text(
        name='Cached config data (debug)',
        compute='_get_config_data',
        readonly=True,
    )
    computed_vals_formula = fields.Text(
        string="Computed values function",
        default=DEFAULT_PYTHON_CODE,
        help="Write Python code that will compute extra values on the "
        "configuration JSON values field. Some variables are ",
    )
    product_template_value_ids = fields.One2many(
        comodel_name="product.template.attribute.value",
        inverse_name="product_tmpl_id",
        string="Price Extra Lines"
    )

    @api.constrains("computed_vals_formula")
    def _check_python_code(self):
        for tmpl in self.sudo().filtered("computed_vals_formula"):
            msg = test_python_expr(
                expr=tmpl.computed_vals_formula.strip(), mode="exec"
            )
            if msg:
                raise ValidationError(msg)

    def _check_visible_attribute_line(self):
        invisible_attr = self.attribute_line_ids.filtered(
            lambda x: x.invisible
        ).mapped("attribute_id")
        domain_attr = self.config_line_ids.mapped(
            "domain_id.domain_line_ids.attribute_id"
        )
        invalid_attr = domain_attr & invisible_attr
        return invalid_attr

    @api.constrains("config_line_ids", "attribute_line_ids")
    def _check_config_line_ids(self):
        for tmpl in self.filtered(lambda x: x.config_line_ids):
            invalid_attr = tmpl._check_visible_attribute_line()
            if not invalid_attr:
                continue
            attrs_name = "\n".join(list(invalid_attr.mapped("name")))
            raise ValidationError(
                _("Invisible attribute lines are not allowed in configuration "
                  "restrictions:\n" + attrs_name
                  )
            )
