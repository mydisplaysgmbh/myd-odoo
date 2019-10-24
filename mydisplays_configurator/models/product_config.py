import pprint

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError


class ProductConfigSessionCustomValue(models.Model):
    _inherit = "product.config.session.custom.value"

    @api.multi
    @api.depends("attribute_id", "attribute_id.uom_id")
    def _compute_val_name(self):
        for attr_val_custom in self:
            uom = attr_val_custom.attribute_id.uom_id.name
            attr_val_custom.name = "%s%s" % (attr_val_custom.value, uom or "")

    name = fields.Char(
        string="Name", readonly=True, compute="_compute_val_name", store=True
    )


class ProductConfigSession(models.Model):
    _inherit = "product.config.session"

    @api.model
    def _get_eval_context(self):
        """ Evaluatioe context to pass to safe_eval """
        tmpl_config_cache = self.product_tmpl_id.config_cache or {}

        # Configuration data (attr vals and custom vals) using json name
        config = {}
        # Add selected value_ids to config dict using human readable json name
        custom_val = self.get_custom_value_id()

        json_value_ids = list(
            set(self.json_config.get('value_ids') or []) - set([custom_val.id])
        )

        for attr_val in json_value_ids:
            val_id = str(attr_val)
            json_val = tmpl_config_cache["attr_vals"].get(val_id, {})
            attr_id = json_val.get("attribute_id")
            attr_json_name = tmpl_config_cache["attr_json_map"][str(attr_id)]
            config[attr_json_name] = tmpl_config_cache["attr_vals"][val_id]

        # Add custom value_ids to config dict using human readable json name
        for attr_id, vals in self.json_config.get('custom_values', {}).items():
            if not vals.get("value", False):
                continue
            value = vals.get("value")
            attr_json_name = tmpl_config_cache["attr_json_map"][str(attr_id)]
            # TODO: Add typecast using custom_type info
            config[attr_json_name] = value
        return {
            "template": tmpl_config_cache.get("attrs", {}),
            "session": {"price": 0, "weight": 0, "quantity": 0, "bom": []},
            "config": config,
        }

    @api.multi
    @api.depends("product_tmpl_id.config_cache", "json_config")
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
            session.json_vals_debug = pprint.pformat(eval_context["session"])

    @api.depends('json_config')
    def _get_json_value_ids(self):
        for session in self:
            json_value_ids = session.json_config.get('value_ids', [])
            session.value_ids = json_value_ids

    def _set_json_value_ids(self):
        for session in self:
            json_config = session.json_config
            json_config['value_ids'] = session.value_ids.ids
            session.json_config = json_config

    json_config = fields.Serialized(
        name="JSON Config", help="Json representation of all custom values"
    )
    json_config_text = fields.Text()
    json_vals = fields.Serialized(
        name="JSON Vals",
        help="Final version of aggregated custom values and computed values",
        compute="_compute_json_vals",
        store=True,
    )
    json_vals_debug = fields.Text(
        name="JSON Vals Debug", compute="_compute_json_vals", readonly=True
    )
    value_ids = fields.Many2many(
        compute='_get_json_value_ids',
        inverse='_set_json_value_ids',
    )

    @api.model
    def get_parsed_custom_value(self, val, custom_type="char"):
        """Parse and return type casted value for custom fields
        :val(string): custom value
        :custom_type(string): type of custom field"""
        if not custom_type:
            custom_type = "char"
        if custom_type in ["int"]:
            try:
                return int(val)
            except Exception:
                raise UserError(_("Please provide a valid integer value"))
        elif custom_type in ["float"]:
            try:
                return float(val)
            except Exception:
                raise UserError(_("Please provide a valid float value"))
        else:
            return val

    @api.multi
    def get_config_session_json(
        self, vals, product_tmpl_id=None
    ):
        """Get product.config.session data in a serialized computed field
            {
                'attrs': {
                    attr_1_id: {
                        'value': custom - value,  # (sanitized and typecasted),
                    }
                }
            }

        """
        self.ensure_one()
        if not product_tmpl_id:
            product_tmpl_id = self.product_tmpl_id
        tmpl_config_cache = product_tmpl_id.config_cache
        attrs = tmpl_config_cache.get("attrs", {})
        product_configurator_obj = self.env["product.configurator"]
        field_prefix = product_configurator_obj._prefixes.get("field_prefix")
        custom_field_prefix = product_configurator_obj._prefixes.get(
            "custom_field_prefix"
        )
        custom_val_id = self.get_custom_value_id()
        cfg_session_json = self.json_config.get('custom_values', {})
        if not cfg_session_json:
            cfg_session_json = {}
        for attribute_id in attrs:
            if not attrs[attribute_id].get("custom", False):
                continue
            field_name = "%s%s" % (field_prefix, attribute_id)
            custom_field = "%s%s" % (custom_field_prefix, attribute_id)
            if field_name not in vals and custom_field not in vals:
                continue
            custom_flag = True
            if field_name in vals:
                # custom value changed with standard one
                value = vals.get(field_name, False)
                if (
                    value != custom_val_id.id
                    and attribute_id in cfg_session_json
                ):
                    cfg_session_json.pop(attribute_id)
                custom_flag = (value == custom_val_id.id)
            if custom_field in vals and custom_flag:
                custom_val = vals.get(custom_field, False)
                if not custom_val and attribute_id in cfg_session_json:
                    # If value removed
                    cfg_session_json.pop(attribute_id)
                elif custom_val:
                    attr_dict = {}
                    custom_val = vals.get(custom_field, False)
                    custom_type = attrs.get(attribute_id, {}).get(
                        "custom_type", "char"
                    )
                    custom_val = self.get_parsed_custom_value(
                        val=custom_val, custom_type=custom_type
                    )
                    attr_dict["value"] = custom_val
                    cfg_session_json[attribute_id] = attr_dict
        return {'custom_values': cfg_session_json}

    @api.multi
    def update_session_config_vals(self, vals, product_tmpl_id=None):
        """storing data as JSON from the session
        and update the values accordingly"""
        super(ProductConfigSession, self).update_session_configuration_value(
            vals=vals, product_tmpl_id=product_tmpl_id
        )
        cfg_session_json = self.get_config_session_json(
            vals=vals, product_tmpl_id=product_tmpl_id
        )
        self.json_config = cfg_session_json
        self.json_config_text = pprint.pformat(cfg_session_json)

    def set_default_config_json(self, value_ids=None, custom_value_ids=None):
        """update json field while reconfigure product"""
        if custom_value_ids is None:
            custom_value_ids = self.custom_value_ids
        if value_ids is None:
            value_ids = self.value_ids
        cfg_session_json = {}
        for custom_val_id in custom_value_ids:
            attribute_id = "%s" % (custom_val_id.attribute_id.id)
            attr_dict = cfg_session_json[attribute_id] = {}
            custom_val = False
            if custom_val_id.value:
                custom_type = custom_val_id.attribute_id.custom_type
                custom_val = self.get_parsed_custom_value(
                    val=custom_val_id.value, custom_type=custom_type
                )
            elif custom_val_id.attachment_ids:
                vals = custom_val_id.attachment_ids.mapped("datas")
                if len(vals) == 1:
                    custom_val = vals[0]
                else:
                    custom_val = vals
            if custom_val:
                attr_dict["value"] = custom_val

        cfg_session_json = {
            'custom_values': cfg_session_json,
            'value_ids': value_ids.ids
        }
        self.json_config = cfg_session_json
        self.json_config_text = pprint.pformat(cfg_session_json)

    @api.multi
    @api.depends("json_vals")
    def _compute_cfg_weight(self):
        for cfg_session in self:
            cfg_session.weight = cfg_session.json_vals.get('weight', 0)

    @api.multi
    @api.depends("json_vals")
    def _compute_cfg_price(self):
        for session in self:
            session.price = session.json_vals.get('price', 0)
