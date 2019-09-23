from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    @api.model
    def _get_eval_context(self):
        """ Evaluatioe context to pass to safe_eval """
        tmpl_config_cache = self.product_tmpl_id.config_cache or {}

        # Configuration data (attr vals and custom vals) using json name
        config = {}
        # Add selected value_ids to config dict using human readable json name
        for attr_val in self.value_ids:
            val_id = str(attr_val.id)
            json_val = tmpl_config_cache["attr_vals"].get(val_id, {})
            attr_id = json_val.get("attribute_id")
            attr_json_name = tmpl_config_cache["attr_json_map"][str(attr_id)]
            config[attr_json_name] = tmpl_config_cache["attr_vals"][val_id]

        # Add custom value_ids to config dict using human readable json name
        for attr_val_id, val in self.json_config:
            val_id = str(attr_val.id)
            json_val = tmpl_config_cache["attr_vals"].get(val_id, {})
            attr_id = json_val.get("attribute_id")
            attr_json_name = tmpl_config_cache["attr_json_map"][str(attr_id)]
            # TODO: Add typecast using custom_type info
            config[attr_json_name] = val

        return {
            "template": tmpl_config_cache.get("attrs", {}),
            "session": {},
            "config": config,
        }

    @api.multi
    @api.depends("product_tmpl_id.config_cache", "json_config", "value_ids")
    def _compute_json_vals(self):
        # for session in self:
        #     code = session.product_tmpl_id.computed_vals_formula
        #     eval_context = session._get_eval_context()
        #     safe_eval(
        #         code.strip(), eval_context, mode="exec",
        #         nocopy=True, locals_builtins=True
        #     )
        #     session.json_vals = eval_context['session']
        pass

    json_config = fields.Serialized(
        name="JSON Config", help="Json representation of all custom values"
    )
    json_vals = fields.Serialized(
        name="JSON Vals",
        help="Final version of aggregated custom values and computed values",
        compute="_compute_json_vals",
        store=True,
    )

    def get_parsed_custom_value(self, val, type="char"):
        if custom_type in ["int"]:
            try:
                return int(val)
            except Exception:
                raise UserError(_("Please provide valid integer value"))
        elif custom_type in ["float"]:
            try:
                return float(val)
            except Exception:
                raise UserError(_("Please provide valid float value"))
        elif custom_type in [
            "text",
            "char",
            "color",
            "binary",
            "date",
            "datetime",
        ]:
            return val

    def get_configuration_session_json_dictionary(self, vals, product_tmpl_id):
        if not product_tmpl_id:
            product_tmpl_id = self.product_tmpl_id
        tmpl_config_cache = product_tmpl_id.config_cache
        product_configurator_obj = self.env["product.configurator"]
        field_prefix = product_configurator_obj._prefixes.get("field_prefix")
        custom_field_prefix = product_configurator_obj._prefixes.get(
            "custom_field_prefix"
        )
        custom_val_id = self.get_custom_value_id()
        cfg_session_json = {}
        attr_dict = cfg_session_json["attrs"] = {}
        for attr_line in product_tmpl_id.attribute_line_ids:
            attribute_id = attr_line.attribute_id
            attr_prefix = tmpl_config_cache.get("attr_json_map", {}).get(
                "%s" % (attribute_id)
            )
            attr_dict[attr_prefix] = {}
            field_name = "%s%s" % (field_prefix, attribute_id)
            custom_field = "%s%s" % (custom_field_prefix, attribute_id)
            value = vals.get(field_name, False)
            if not value:
                continue
            if value == custom_val_id.id:
                value = vals.get(custom_field, False)
                custom_type = attribute_id.custom_type or "char"
                custom_val = self.get_parsed_custom_value(
                    val=value, type=custom_type
                )
                attr_dict[attr_prefix]["value"] = custom_val
            else:
                attr_dict[attr_prefix].update({""})

    @api.multi
    def update_session_configuration_value(self, vals, product_tmpl_id=None):
        super(ProductConfigSession, self).update_session_configuration_value(
            vals=vals, product_tmpl_id=product_tmpl_id
        )
        self.get_configuration_session_json_dictionary(
            vals=vals, product_tmpl_id=product_tmpl_id
        )
        print(
            "vals ",
            vals,
        )


# %Y-%m-%d %Y-%m-%d %H:%M:%S
# vals  {'__attribute-5': 7, '__custom-5': '09/23/2019 19:54:58', '__attribute-6': 7, '__custom-6': '09/23/2019', '__attribute-7': False, '__custom-7': False, '__attribute-8': False, '__custom-8': False, '__attribute-9': False, '__custom-9': False, '__attribute-10': False, '__custom-10': False, '__attribute-11': False, '__custom-11': False, '__attribute-12': [[6, False, []]], '__custom-12': False}
# vals  {'__attribute-2': 3, '__attribute-10': 7, '__custom-10': 'sfsfw', '__attribute-12': 7, '__custom-12': 'sdfwsfwef', 'value_ids': [[6, False, [3, 7, 7]]]}
# {'__attribute-2': 3, '__attribute-10': 7, '__custom-10': 'ytiuyiuyi', '__attribute-12': 7, '__custom-12': 'oy8768y', 'value_ids': [[6, False, [3, 7, 7]]]}


# cfg_session_json = {
#     attrs: {
#         attr_prefix: {
#             'value': custom - value,  # (sanitized and typecasted),
#             # (when standard option and attr_val_id is selected, cannot be both custom and value_id)
#             'value_id': attr_val_id,
#             'product': {  # ( related product data if any) {
#                 'id': attr_val.product_id.id,
#                 'price': attr_val.product_id.price,
#                 'weight': attr_val.product_id.weight
#             }
#         }
#     },
# }
