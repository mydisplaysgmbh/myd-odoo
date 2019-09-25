from odoo import api, fields, models, _
import pprint

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
        custom_val_id = self.get_custom_value_id()
        for attr_val in self.value_ids - custom_val_id:
            val_id = str(attr_val.id)
            json_val = tmpl_config_cache["attr_vals"].get(val_id, {})
            attr_id = json_val.get("attribute_id")
            attr_json_name = tmpl_config_cache["attr_json_map"][str(attr_id)]
            config[attr_json_name] = tmpl_config_cache["attr_vals"][val_id]

        # Add custom value_ids to config dict using human readable json name
        custom_val_id = self.get_custom_value_id()
        for attr_id, vals in self.json_config.items():
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
            session.json_vals_debug = pprint.pformat(eval_context["session"])

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
                raise UserError(_("Please provide valid integer value"))
        elif custom_type in ["float"]:
            try:
                return float(val)
            except Exception:
                raise UserError(_("Please provide valid float value"))
        else:
            return val

    @api.multi
    def get_configuration_session_json_dictionary(
        self, vals, product_tmpl_id=None
    ):
        """Store product.config.session data in serialized computed field
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
        cfg_session_json = self.json_config
        if not cfg_session_json:
            cfg_session_json = {}
        for attribute_id in attrs:
            if not attrs[attribute_id].get("custom", False):
                continue
            field_name = "%s%s" % (field_prefix, attribute_id)
            custom_field = "%s%s" % (custom_field_prefix, attribute_id)
            if field_name not in vals and custom_field not in vals:
                continue
            if field_name in vals:
                # custom value changed with standard one
                value = vals.get(field_name, False)
                if (
                    value != custom_val_id.id
                    and attribute_id in cfg_session_json
                ):
                    cfg_session_json.pop(attribute_id)
            if custom_field in vals:
                custom_val = vals.get(custom_field, False)
                if not custom_val and attribute_id in cfg_session_json:
                    # If value removed
                    cfg_session_json.pop(attribute_id)
                else:
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
        return cfg_session_json

    @api.multi
    def update_session_configuration_value(self, vals, product_tmpl_id=None):
        """storing data as JSON from the session
        and update the values accordingly"""
        super(ProductConfigSession, self).update_session_configuration_value(
            vals=vals, product_tmpl_id=product_tmpl_id
        )
        cfg_session_json = self.get_configuration_session_json_dictionary(
            vals=vals, product_tmpl_id=product_tmpl_id
        )
        self.json_config = cfg_session_json
        self.json_config_text = pprint.pformat(cfg_session_json)

    def set_default_cfg_session_json_dictionary(self, custom_value_ids=None):
        """update json field while reconfigure product"""
        if custom_value_ids == None:
            custom_value_ids = self.custom_value_ids
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
        self.json_config = cfg_session_json
        self.json_config_text = pprint.pformat(cfg_session_json)

    @api.model
    def search_variant(
        self, value_ids=None, custom_vals=None, product_tmpl_id=None
    ):
        """ Searches product.variants with given value_ids and custom values
            given in the custom_vals dict

            :param value_ids: list of product.attribute.values ids
            :param custom_vals: dict {product.attribute.id: custom_value}

            :returns: product.product recordset of products matching domain
        """
        if value_ids is None:
            value_ids = self.value_ids.ids

        # START CUSTOMIZATION
        custom_value_id = self.get_custom_value_id()
        value_ids = [
            value for value in value_ids if value != custom_value_id.id
        ]
        # if custom_vals is None:
        #     custom_vals = self._get_custom_vals_dict()
        # END CUSTOMIZATION

        if not product_tmpl_id:
            session_template = self.product_tmpl_id
            if not session_template:
                raise ValidationError(
                    _(
                        "Cannot conduct search on an empty config session without "
                        "product_tmpl_id kwarg"
                    )
                )
            product_tmpl_id = self.product_tmpl_id.id
        # START CUSTOMIZATION
        domain = self.get_variant_search_domain(
            product_tmpl_id=product_tmpl_id,
            value_ids=value_ids,
            custom_vals={},
        )
        # OLD CODE
        # domain = self.get_variant_search_domain(
        #     product_tmpl_id=product_tmpl_id,
        #     value_ids=value_ids,
        #     custom_vals=custom_vals
        # )
        # END CUSTOMIZATION
        products = self.env["product.product"].search(domain)

        # At this point, we might have found products with all of the passed
        # in values, but it might have more attributes!  These are NOT
        # matches
        more_attrs = products.filtered(
            lambda p: len(p.attribute_value_ids) != len(value_ids)
            or len(p.value_custom_ids) != len(custom_vals)
        )
        products -= more_attrs
        return products

    @api.model
    def get_variant_vals(self, value_ids=None, custom_vals=None, **kwargs):
        """ Prevent to save custom values on variants
         """
        self.ensure_one()

        if value_ids is None:
            value_ids = self.value_ids.ids

        # START CUSTOMIZATION
        custom_value_id = self.get_custom_value_id()
        value_ids = [
            value for value in value_ids if value != custom_value_id.id
        ]
        # if custom_vals is None:
        #     custom_vals = self._get_custom_vals_dict()
        # END CUSTOMIZATION

        image = self.get_config_image(value_ids)
        vals = {
            "product_tmpl_id": self.product_tmpl_id.id,
            "attribute_value_ids": [(6, 0, value_ids)],
            "taxes_id": [(6, 0, self.product_tmpl_id.taxes_id.ids)],
            "image": image,
        }

        # START CUSTOMIZATION
        # if custom_vals:
        #     vals.update({
        #         'value_custom_ids': self.encode_custom_values(custom_vals)
        #     })
        # END CUSTOMIZATION
        return vals

    @api.multi
    def create_get_variant(self, value_ids=None, custom_vals=None):
        """ Prevent to save custom values on variants"""
        if value_ids is None:
            value_ids = self.value_ids.ids

        # START CUSTOMIZATION
        # if custom_vals is None:
        #     custom_vals = self._get_custom_vals_dict()
        # END CUSTOMIZATION

        try:
            self.validate_configuration()
        except ValidationError as ex:
            raise ValidationError(ex)
        except Exception:
            raise ValidationError(_("Invalid Configuration"))

        # START CUSTOMIZATION
        duplicates = self.search_variant(value_ids=value_ids, custom_vals={})
        # OLD CODE
        # duplicates = self.search_variant(
        #     value_ids=value_ids, custom_vals=custom_vals)
        # END CUSTOMIZATION

        # At the moment, I don't have enough confidence with my understanding
        # of binary attributes, so will leave these as not matching...
        # In theory, they should just work, if they are set to "non search"
        # in custom field def!
        # TODO: Check the logic with binary attributes

        # START CUSTOMIZATION
        # if custom_vals:
        #     value_custom_ids = self.encode_custom_values(custom_vals)
        #     if any('attachment_ids' in cv[2] for cv in value_custom_ids):
        #         duplicates = False
        # END CUSTOMIZATION

        if duplicates:
            self.action_confirm()
            return duplicates[:1]

        # START CUSTOMIZATION
        vals = self.get_variant_vals(value_ids)
        # OLD CODE
        # vals = self.get_variant_vals(value_ids, custom_vals)
        # END CUSTOMIZATION

        product_obj = (
            self.env["product.product"]
            .sudo()
            .with_context(mail_create_nolog=True)
        )
        variant = product_obj.sudo().create(vals)

        variant.message_post(
            body=_("Product created via configuration wizard"),
            author_id=self.env.user.partner_id.id,
        )
        self.action_confirm()
        return variant