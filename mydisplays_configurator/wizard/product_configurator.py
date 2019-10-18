from odoo import models, fields, tools, api, _
import pprint
from lxml import etree
from odoo.osv import orm
from odoo.exceptions import UserError


class ProductConfigurator(models.TransientModel):
    _inherit = "product.configurator"

    def _get_dynamic_fields(self, values):
        dynamic_vals = {}
        product_configurator_obj = self.env["product.configurator"]
        field_prefix = product_configurator_obj._prefixes.get("field_prefix")
        custom_field_prefix = product_configurator_obj._prefixes.get(
            "custom_field_prefix"
        )
        for attr, value in values.items():
            if not attr.startswith(field_prefix) and not attr.startswith(
                custom_field_prefix
            ):
                continue
            dynamic_vals[attr] = value
        return dynamic_vals

    @api.multi
    def onchange(self, values, field_name, field_onchange):
        res = super(ProductConfigurator, self).onchange(
            values=values, field_name=field_name, field_onchange=field_onchange
        )
        config_session_id = self.env["product.config.session"].browse(
            values.get("config_session_id", [])
        )
        if not config_session_id:
            config_session_id = self.config_session_id
        vals = self._get_dynamic_fields(values)
        cfg_session_json = config_session_id.get_config_session_json(vals=vals)
        value_ids = res.get('value', {}).get('value_ids', {})
        if value_ids:
            cfg_session_json['value_ids'] = value_ids[0][2]
        config_session_id.json_config = cfg_session_json
        config_session_id.json_config_text = pprint.pformat(cfg_session_json)
        if not res.get("value"):
            res["value"] = {}
        json_session_vals = config_session_id.json_vals
        res["value"]["price"] = json_session_vals.get("price", 0)
        res["value"]["weight"] = json_session_vals.get("weight", 0)
        return res

    @api.model
    def add_dynamic_fields(self, res, dynamic_fields, wiz):
        """ Create the configuration view using the dynamically generated
            fields in fields_get()
        """

        field_prefix = self._prefixes.get("field_prefix")
        custom_field_prefix = self._prefixes.get("custom_field_prefix")

        try:
            # Search for view container hook and add dynamic view and fields
            xml_view = etree.fromstring(res["arch"])
            xml_static_form = xml_view.xpath("//group[@name='static_form']")[0]
            xml_dynamic_form = etree.Element(
                "group", colspan="2", name="dynamic_form"
            )
            xml_parent = xml_static_form.getparent()
            xml_parent.insert(
                xml_parent.index(xml_static_form) + 1, xml_dynamic_form
            )
            xml_dynamic_form = xml_view.xpath("//group[@name='dynamic_form']")[
                0
            ]
        except Exception:
            raise UserError(
                _(
                    "There was a problem rendering the view "
                    "(dynamic_form not found)"
                )
            )

        # Get all dynamic fields inserted via fields_get method
        attr_lines = wiz.product_tmpl_id.attribute_line_ids.sorted()

        # Loop over the dynamic fields and add them to the view one by one
        for attr_line in attr_lines:

            attribute_id = attr_line.attribute_id.id
            field_name = field_prefix + str(attribute_id)
            custom_field = custom_field_prefix + str(attribute_id)

            # Check if the attribute line has been added to the db fields
            if field_name not in dynamic_fields:
                continue

            config_steps = wiz.product_tmpl_id.config_step_line_ids.filtered(
                lambda x: attr_line in x.attribute_line_ids
            )

            # attrs property for dynamic fields
            attrs = {"readonly": ["|"], "required": [], "invisible": ["|"]}

            if config_steps:
                cfg_step_ids = [str(id) for id in config_steps.ids]
                attrs["invisible"].append(("state", "not in", cfg_step_ids))
                attrs["readonly"].append(("state", "not in", cfg_step_ids))

                # If attribute is required make it so only in the proper step
                if attr_line.required:
                    attrs["required"].append(("state", "in", cfg_step_ids))
            else:
                attrs["invisible"].append(("state", "not in", ["configure"]))
                attrs["readonly"].append(("state", "not in", ["configure"]))

                # If attribute is required make it so only in the proper step
                if attr_line.required:
                    attrs["required"].append(("state", "in", ["configure"]))

            if attr_line.custom:
                pass
                # TODO: Implement restrictions for ranges

            config_lines = wiz.product_tmpl_id.config_line_ids
            dependencies = config_lines.filtered(
                lambda cl: cl.attribute_line_id == attr_line
            )

            # If an attribute field depends on another field from the same
            # configuration step then we must use attrs to enable/disable the
            # required and readonly depending on the value entered in the
            # dependee

            if attr_line.value_ids <= dependencies.mapped("value_ids"):
                attr_depends = {}
                domain_lines = dependencies.mapped("domain_id.domain_line_ids")
                for domain_line in domain_lines:
                    attr_id = domain_line.attribute_id.id
                    attr_field = field_prefix + str(attr_id)
                    attr_lines = wiz.product_tmpl_id.attribute_line_ids
                    # If the fields it depends on are not in the config step
                    if config_steps and str(attr_line.id) != wiz.state:
                        continue
                    if attr_field not in attr_depends:
                        attr_depends[attr_field] = set()
                    if domain_line.condition == "in":
                        attr_depends[attr_field] |= set(
                            domain_line.value_ids.ids
                        )
                    elif domain_line.condition == "not in":
                        val_ids = attr_lines.filtered(
                            lambda l: l.attribute_id.id == attr_id
                        ).value_ids
                        val_ids = val_ids - domain_line.value_ids
                        attr_depends[attr_field] |= set(val_ids.ids)

                for dependee_field, val_ids in attr_depends.items():
                    if not val_ids:
                        continue
                    attrs["readonly"].append(
                        (dependee_field, "not in", list(val_ids))
                    )
                    attrs["required"].append(
                        (dependee_field, "in", list(val_ids))
                    )

            # Create the new field in the view
            node = etree.Element(
                "field",
                name=field_name,
                on_change="onchange_attribute_value(%s, context)" % field_name,
                default_focus="1" if attr_line == attr_lines[0] else "0",
                attrs=str(attrs),
                context=str(
                    {
                        "show_attribute": False,
                        "show_price_extra": True,
                        "active_id": wiz.product_tmpl_id.id,
                    }
                ),
                options=str(
                    {
                        "no_create": True,
                        "no_create_edit": True,
                        "no_open": True,
                    }
                ),
            )

            field_type = dynamic_fields[field_name].get("type")
            if field_type == "many2many":
                node.attrib["widget"] = "many2many_tags"
            # Apply the modifiers (attrs) on the newly inserted field in the
            # arch and add it to the view
            orm.setup_modifiers(node)
            xml_dynamic_form.append(node)

            if attr_line.custom and custom_field in dynamic_fields:
                widget = ""
                config_session_obj = self.env["product.config.session"]
                custom_option_id = config_session_obj.get_custom_value_id().id

                if field_type == "many2many":
                    field_val = [(6, False, [custom_option_id])]
                else:
                    field_val = custom_option_id

                attrs["readonly"] += [(field_name, "!=", field_val)]
                attrs["invisible"] += [(field_name, "!=", field_val)]
                attrs["required"] += [(field_name, "=", field_val)]

                if config_steps:
                    attrs["required"] += [("state", "in", cfg_step_ids)]

                # TODO: Add a field2widget mapper
                if attr_line.attribute_id.custom_type == "color":
                    widget = "color"
                node = etree.Element(
                    "field",
                    name=custom_field,
                    # customization
                    on_change="onchange_attribute_value(%s, context)"
                    % custom_field,
                    # End
                    attrs=str(attrs),
                    widget=widget,
                )
                orm.setup_modifiers(node)
                xml_dynamic_form.append(node)
        return xml_view


class ProductConfiguratorSale(models.TransientModel):
    _inherit = "product.configurator.sale"

    def _get_order_line_vals(self, product_id):
        """ Link session with sale order lines"""

        line_vals = super(ProductConfiguratorSale, self)._get_order_line_vals(
            product_id=product_id
        )
        line_vals.update({"cfg_session_id": self.config_session_id.id})
        return line_vals
