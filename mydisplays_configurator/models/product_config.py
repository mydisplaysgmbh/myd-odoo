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
            "session": {"price": 0, "weight": 0, "quantity": 0, "bom": []},
            "config": config,
        }

    @api.multi
    @api.depends("product_tmpl_id.config_cache", "json_config", "value_ids")
    def _compute_json_vals(self):
        for session in self:
            code = session.product_tmpl_id.computed_vals_formula
            eval_context = session._get_eval_context()
            safe_eval(
                code.strip(),
                eval_context,
                mode="exec",
                nocopy=True,
                locals_builtins=True,
            )
            session.json_vals = eval_context["session"]

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
        """Store product.config.session data in serialized computed field
            {
                'attrs': {
                    attr_1_JSON_name: {
                        'value': custom - value,  # (sanitized and typecasted),
                        # (when standard option and attr_val_id is selected,
                        # cannot be both custom and value_id)
                        'value_id': attr_val_id,
                        'product': attr_val.product_id.id,
                        'price': attr_val.product_id.price,
                        'weight': attr_val.product_id.weight,
                        'quantity': product_quantity (computed value)
                    }
                }
            }

        """
        if not product_tmpl_id:
            product_tmpl_id = self.product_tmpl_id
        tmpl_config_cache = product_tmpl_id.config_cache
        attr_json_map = tmpl_config_cache.get("attr_json_map", {})
        attrs = tmpl_config_cache.get("attrs", {})
        attr_vals = tmpl_config_cache.get("attr_vals", {})
        product_configurator_obj = self.env["product.configurator"]
        field_prefix = product_configurator_obj._prefixes.get("field_prefix")
        custom_field_prefix = product_configurator_obj._prefixes.get(
            "custom_field_prefix"
        )
        custom_val_id = self.get_custom_value_id()
        cfg_session_json = {}
        cfg_session_json["attrs"] = {}
        for attribute_id in attrs:
            attr_prefix = attr_json_map.get(attribute_id, attribute_id)
            attr_dict = cfg_session_json["attrs"][attr_prefix] = {}
            field_name = "%s%s" % (field_prefix, attribute_id)
            custom_field = "%s%s" % (custom_field_prefix, attribute_id)
            value = vals.get(field_name, False)
            if not value:
                continue
            if value == custom_val_id.id:
                value = vals.get(custom_field, False)
                custom_type = attrs.get(attribute_id, {}).get(
                    "custom_type", "char"
                )
                custom_val = self.get_parsed_custom_value(
                    val=value, type=custom_type
                )
                attr_dict["value"] = custom_val
            else:
                attr_dict["value_id"] = value
                value_tree = attr_vals.get("%s" % (value), {})
                attr_dict["price"] = value_tree.get("price", 0)
                attr_dict["weight"] = value_tree.get("weight", 0)
                product_id = value_tree.get("product_id", 0)
                if product_id:
                    attr_dict["product"] = product_id
        return cfg_session_json


    @api.multi
    def update_session_configuration_value(self, vals, product_tmpl_id=None):
        super(ProductConfigSession, self).update_session_configuration_value(
            vals=vals, product_tmpl_id=product_tmpl_id
        )
        cfg_session_json = self.get_configuration_session_json_dictionary(
            vals=vals, product_tmpl_id=product_tmpl_id
        )
        self.json_config = cfg_session_json
