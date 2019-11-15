import json
import pprint

from odoo import api, fields, models, _
from odoo.tools.safe_eval import test_python_expr
from odoo.exceptions import ValidationError

DEFAULT_PYTHON_CODE = """# Available variables:
#  - config: Current configuration expressed as a json object
#       config['attr_json_name'] holds cached data for the selected value
#       config['changed_field'] hold the name of the field changed by the user
#
#  - session: Object to store final computed values
#      session['prices'] holds a dictionary of all related prices:
#      session['prices'][attribute_json_name] = X
#
#      session['weights'] holds a dictionary of all related weights:
#      session['weights'][attribute_json_name] = X
#
#      session['bom'] holds a dictionary of al related prodcuts for the bom:
#      session['bom'][attribute_json_name] = {
#          'product_id': related_product_id,
#          'product_qty': 1
#      }
#
#      session['warning'] contents will pop-up in the frontend (used in
#      conjuction with config['changed_field'] to pop up message only once)
#
\n\n\n\n
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
            "product_id.lst_price",
            "product_id.standard_price",
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
        """Fetch configuration data related to templates and store them as
        json in config_cache serialized field"""
        for product_tmpl in self.filtered(lambda x: x.config_ok):
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

    @api.model
    def default_get(self, default_fields):
        """If we create new product template then only
        configurable products have field default_config_ok=True.
        """
        res = super(ProductTemplate, self).default_get(default_fields)
        default_config_ok = res.get('config_ok', False)
        if default_config_ok:
            res['config_qty_ok'] = default_config_ok
        return res

    @api.multi
    def toggle_config(self):
        super(ProductTemplate, self).toggle_config()
        for record in self:
            record2 = record.with_context(check_constraint=False)
            record2.config_qty_ok = record2.config_ok
            record.onchange_config_qty()

    @api.onchange('config_qty_ok')
    def onchange_config_qty(self):
        """Add / remove quantity attribute line to product
        template when boolean button
        is checked"""
        qty_attribute = self.env.ref(
            'mydisplays_configurator.quantity_attribute'
        )
        qty_line = self.attribute_line_ids.filtered(
            lambda l: l.attribute_id.id == qty_attribute.id
        )
        if self.config_qty_ok and not qty_line:
            attribute_line_obj = self.env['product.template.attribute.line']
            qty_line = attribute_line_obj.new({
                'attribute_id': qty_attribute.id,
                'custom': True
            })
            self.attribute_line_ids |= qty_line
        elif not self.config_qty_ok and qty_line:
            self.attribute_line_ids -= qty_line

    @api.constrains('config_qty_ok', 'attribute_line_ids')
    def check_qty_attr_line(self):
        """Ensure the quantity attribute line is added if config_qty_ok
        field is True"""
        qty_attribute = self.env.ref(
            'mydisplays_configurator.quantity_attribute'
        )
        for product_tmpl in self.filtered(lambda tmpl: tmpl.config_ok):
            if not product_tmpl.env.context.get('check_constraint', True):
                continue
            qty_line = product_tmpl.attribute_line_ids.filtered(
                lambda l: l.attribute_id.id == qty_attribute.id and l.custom)
            if product_tmpl.config_qty_ok and not qty_line:
                raise ValidationError(_(
                    "No quantity attribute line has been found on template "
                    "'%s'. Please toggle or turn off the config quantity "
                    "boolean field." % product_tmpl.name)
                )
            elif not product_tmpl.config_qty_ok and qty_line:
                raise ValidationError(_(
                    "Quantity attribute line present in template with config "
                    "quantity set to False. Please turn on config quantity or "
                    "remove the quantity attribute line")
                )

    @api.multi
    @api.depends('config_cache')
    def _compute_config_cache_debug(self):
        for template in self:
            template.config_cache_debug = pprint.pformat(template.config_cache)

    config_qty_ok = fields.Boolean(
        string="Config Quantity",
        help="Allow setting quantity in the configuration form",
    )
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
        compute='_compute_config_cache_debug',
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

    def get_product_templates_with_session(self, config_session_map={}):
        tmpls_to_update = self.env['product.template']
        if not config_session_map:
            return tmpls_to_update
        configurable_tmpls = self.filtered(lambda p: p.config_ok)
        for cfg_tmpl in configurable_tmpls:
            if cfg_tmpl.id not in config_session_map.keys():
                continue
            tmpls_to_update += cfg_tmpl
        return tmpls_to_update

    def _compute_weight(self):
        session_map = self.env.context.get('product_template_sessions', {})
        configurable_tmpls = self.get_product_templates_with_session(
            session_map.copy()
        )
        standard_templates = self - configurable_tmpls

        for cfg_tmpl in configurable_tmpls:
            product_session = self.env['product.config.session'].browse(
                session_map.get(cfg_tmpl.id)
            )
            if not product_session.exists():
                standard_templates += cfg_tmpl
                continue
            cfg_tmpl.weight = product_session.get_session_weight() or 0
        super(ProductProduct, standard_templates)._compute_weight()

    @api.multi
    def _compute_template_price(self):
        session_map = self.env.context.get('product_template_sessions', {})
        configurable_tmpls = self.get_product_templates_with_session(
            session_map.copy()
        )
        standard_templates = self - configurable_tmpls
        for cfg_tmpl in configurable_tmpls:
            product_session = self.env['product.config.session'].browse(
                session_map.get(cfg_tmpl.id)
            )
            if not product_session.exists():
                standard_templates += cfg_tmpl
                continue
            cfg_tmpl.weight = product_session.get_session_price() or 0
        super(ProductProduct, standard_templates)._compute_weight()


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_products_with_session(self, config_session_map={}):
        products_to_update = self.env['product.product']
        if not config_session_map:
            return products_to_update
        configurable_products = self.filtered(lambda p: p.config_ok)
        for cfg_product in configurable_products:
            if cfg_product.id not in config_session_map.keys():
                continue
            products_to_update += cfg_product
        return products_to_update

    def _compute_product_weight(self):
        session_map = self.env.context.get('product_sessions', {})
        configurable_products = self.get_products_with_session(session_map.copy())
        standard_products = self - configurable_products

        for cfg_product in configurable_products:
            product_session = self.env['product.config.session'].browse(
                session_map.get(cfg_product.id)
            )
            if not product_session.exists():
                standard_products += cfg_product
                continue
            cfg_product.weight = product_session.get_session_weight() or 0
        super(ProductProduct, standard_products)._compute_product_weight()

    def _compute_product_price(self):
        session_map = self.env.context.get('product_sessions', {})
        configurable_products = self.get_products_with_session(session_map.copy())
        standard_products = self - configurable_products

        for cfg_product in configurable_products:
            product_session = self.env['product.config.session'].browse(
                session_map.get(cfg_product.id)
            )
            if not product_session.exists():
                standard_products += cfg_product
                continue
            cfg_product.price = product_session.get_session_price() or 0
         super(ProductProduct, standard_products)._compute_product_price()
