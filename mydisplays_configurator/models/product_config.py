import pprint
import logging
import itertools

from odoo import api, fields, models, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


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
            attr_json_name = tmpl_config_cache["attr_json_map"].get(
                str(attr_id)
            )
            # TODO: Add typecast using custom_type info
            config[attr_json_name] = value

        if self.json_config.get('changed_attr'):
            config['changed_field'] = tmpl_config_cache["attr_json_map"].get(
                self.json_config.get('changed_attr')
            )

        return {
            "template": tmpl_config_cache.get("attrs", {}),
            "session": self._get_eval_context_session(),
            "config": config,
        }

    @api.model
    def _get_eval_context_session(self):
        prices = {}
        weights = {}
        bom = {}
        value_ids = [
            str(val_id) for val_id in self.json_config.get('value_ids', [])
        ]
        tmpl_config_cache = self.product_tmpl_id.config_cache
        for value_id in value_ids:
            attr_val_data = tmpl_config_cache['attr_vals'].get(value_id, {})
            attribute_id = str(attr_val_data.get('attribute_id'))
            json_name = tmpl_config_cache['attr_json_map'].get(attribute_id)
            if not json_name:
                continue
            prices[json_name] = attr_val_data.get('price')
            weights[json_name] = attr_val_data.get('weight')

            product_id = attr_val_data.get('product_id')

            if not product_id:
                continue

            bom[json_name] = {
                'product_id': product_id,
                'product_qty': 1,
                'workcenter_id': attr_val_data.get('workcenter_id'),
            }

        return {
            'prices': prices,
            'weights': weights,
            'bom': bom
        }

    @api.multi
    @api.depends("product_tmpl_id.config_cache", "json_config")
    def _compute_json_vals(self):
        for session in self.filtered(lambda s: s.state != 'done'):
            code = session.product_tmpl_id.computed_vals_formula
            eval_context = session._get_eval_context()
            safe_eval(
                code.strip(),
                eval_context,
                mode="exec",
                nocopy=True,
                locals_builtins=True,
            )

            json_vals = eval_context['session']

            config_qty = session.get_session_qty()

            json_vals['price_unit'] = sum([
                price for k, price in json_vals['prices'].items()
            ])

            json_vals['price'] = json_vals['price_unit'] * config_qty

            json_vals['weight'] = sum([
                weight for k, weight in json_vals['weights'].items()
            ]) * config_qty

            json_vals['bom'] = [
                line_data for k, line_data in json_vals['bom'].items()
            ]

            session.json_vals = json_vals

    @api.depends('json_config')
    def _get_json_vals(self):
        for session in self:
            json_value_ids = session.json_config.get('value_ids', [])
            json_custom_vals = session.json_config.get('custom_values', {})
            custom_obj = self.env['product.config.session.custom.value']
            memory_custom_objects = custom_obj
            for k, v in json_custom_vals.items():
                memory_custom_objects |= custom_obj.new({
                    'value': v.get('value'),
                    'attribute_id': int(k),
                })
            session.custom_value_ids = memory_custom_objects
            session.value_ids = json_value_ids

    def _set_json_vals(self):
        for session in self:
            json_config = session.json_config
            json_config['value_ids'] = session.value_ids.ids
            session.json_config = json_config

    @api.multi
    @api.depends("json_vals")
    def _compute_json_vals_debug(self):
        for session in self:
            session.json_vals_debug = pprint.pformat(session.json_vals)

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
        name="JSON Vals Debug",
        compute="_compute_json_vals_debug",
        readonly=True
    )
    custom_value_ids = fields.One2many(
        compute='_get_json_vals',
        # inverse='_set_json_vals',
    )
    value_ids = fields.Many2many(
        compute='_get_json_vals',
        inverse='_set_json_vals',
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

    @api.model
    def get_session_qty(self):
        """Attempt to retrieve the quantity potentially set on a configuration
        session via the modle created quantity attribute"""
        try:
            quantity_attr = self.env.ref(
                'mydisplays_configurator.quantity_attribute'
            )
            qty_custom_val = self.json_config['custom_values'].get(
                str(quantity_attr.id), {}
            )
            product_qty = int(qty_custom_val.get('value', 1))
        except Exception:
            product_qty = 1

        return product_qty

    def get_session_weight(self):
        """Return weight from JSON Values"""
        weight = None
        if self.json_vals:
            weight = self.json_vals.get('weight', None)
        if weight is not None:
            product_qty = self.get_session_qty()
            weight = weight / product_qty
        return weight

    def get_session_volume(self):
        """Return volume from JSON Values"""
        volume = None
        if self.json_vals:
            volume = self.json_vals.get('volume', None)
        if volume is not None:
            product_qty = self.get_session_qty()
            volume = volume / product_qty
        return volume

    @api.multi
    def get_config_session_json(
        self, vals, changed_field, product_tmpl_id=None
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
                value = vals.get(field_name, False)
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
        result = {
            'custom_values': cfg_session_json,
        }
        if changed_field and (
            changed_field.startswith(field_prefix) or
            changed_field.startswith(custom_field_prefix)
        ):
            result.update({
                'changed_attr': changed_field.split('-')[1],
            })
        return result

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

    @api.model
    def search_variant(
        self, value_ids=None, custom_vals=None, product_tmpl_id=None
    ):
        """ Prevent to save custom values on variant
        """
        if value_ids is None:
            value_ids = self.value_ids.ids

        # Remove custom value
        custom_value_id = self.get_custom_value_id()
        value_ids = [
            value for value in value_ids if value != custom_value_id.id
        ]
        return super(ProductConfigSession, self).search_variant(
            value_ids=value_ids,
            custom_vals={},
            product_tmpl_id=product_tmpl_id,
        )

    @api.model
    def get_variant_vals(self, value_ids=None, custom_vals=None, **kwargs):
        """ Prevent to save custom values on variants
         """
        self.ensure_one()

        if value_ids is None:
            value_ids = self.value_ids.ids

        # Remove custom value
        custom_value_id = self.get_custom_value_id()
        value_ids = [
            value for value in value_ids if value != custom_value_id.id
        ]
        return super(ProductConfigSession, self).get_variant_vals(
            value_ids=value_ids, custom_vals={}, kwargs=kwargs
        )

    @api.multi
    def create_get_variant(self, value_ids=None, custom_vals=None):
        """ Prevent to save custom values on variants"""
        return super(ProductConfigSession, self).create_get_variant(
            value_ids=value_ids, custom_vals={}
        )

    def set_bom_line_operations(self, bom_lines, operation_ids):
        if not operation_ids:
            return bom_lines
        for bom_line in bom_lines:
            workcenter_id = bom_line.get('workcenter_id')
            if 'workcenter_id' in bom_line:
                bom_line.pop('workcenter_id')
            if not workcenter_id:
                continue
            operation_id = operation_ids.filtered(
                lambda op:
                op.workcenter_id and
                op.workcenter_id.id == workcenter_id
            )
            bom_line['operation_id'] = operation_id.id
        return bom_lines

    @api.model
    def get_route_warning_message(self, val_list):
        if not val_list:
            return False
        warning_message = (
            "No matching route is found. Please create one manually."
        )
        for val in val_list:
            workcenter_ids = val.get('workcenters')
            product_id = val.get('product')
            if not product_id or not workcenter_ids:
                continue
            warning_message += "\n\nLinked workcenters: %s" % (
                ', '.join(workcenter_ids.mapped('name'))
            )
            warning_message += "\nProduct: %s" % (product_id.name)
        return warning_message

    def _create_bom_from_json(self):
        """Create a bill of material from the json custom values attached on
        the related session and link it on the sale order line
        """
        json_vals = self.json_vals
        bom_lines = json_vals.get('bom', [])

        if not bom_lines:
            return False, ''

        result = self._create_get_route()
        route = result.get('route')
        if len(route) > 1:
            _logger.info(
                "Multiple routes have been identified:"
                " Session: %s, Product: %s, Routes: %s" % (
                    self.name,
                    self.product_id.name,
                    ', '.join(route.mapped('code'))
                )
            )
            route = route[:1]
        workcenter_ids = result.get('workcenters')
        warning_message = False
        if route:
            bom_lines = self.set_bom_line_operations(
                bom_lines=bom_lines,
                operation_ids=route.operation_ids
            )

        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product_tmpl_id.id,
            'routing_id': route and route.id or False,
            'product_id': self.product_id.id,
            'bom_line_ids': [
                (0, 0, line_data) for line_data in bom_lines if line_data
            ]
        })
        if not route and workcenter_ids:
            warning_message = self.get_route_warning_message([{
                'workcenters': workcenter_ids,
                'product': self.product_id,
            }])
        return bom, warning_message

    def _create_get_route(self, workcenter_ids=None):
        """Find a route matching the operations given or create one
        if search returns empty"""

        if workcenter_ids is None and self:
            workcenter_ids = self.value_ids.mapped('workcenter_id')
        route_obj = self.env['mrp.routing']

        if not workcenter_ids:
            return {
                'route': route_obj,
                'workcenters': workcenter_ids,
            }

        # Search for a routing with an exact match on operation ids
        domain_sets = []
        for workcenter_id in workcenter_ids:
            domain = [
                ('operation_ids', '=', op_set.id)
                for op_set in workcenter_id.routing_line_ids
            ]
            domain = ((len(domain) - 1) * ['|']) + domain
            if not domain:
                continue
            domain_sets.append(domain)

        domain = ((len(domain_sets) - 1) * ['&']) + list(
            itertools.chain.from_iterable(domain_sets)
        )
        routes = route_obj.search(domain)

        # Filter out routes that do not have the same amount of operations
        operation_ids = workcenter_ids.mapped('routing_line_ids')
        routes = routes.filtered(
            lambda r: not (r.operation_ids - operation_ids)
        )

        return {
            'route': routes,
            'workcenters': workcenter_ids,
        }

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

    def get_session_price(self):
        json_vals = self.json_vals or {}
        if not json_vals:
            self._compute_json_vals()
        if json_vals.get('price_unit', None) is None:
            return 0.0
        return self.json_vals.get('price_unit')


class ProductConfigDomain(models.Model):
    _inherit = "product.config.domain"

    @api.constrains("domain_line_ids")
    def _check_domain_line_ids(self):
        check_attr_visible = self.env.context.get("check_attr_visible")
        product_tmpl_id = self.env.context.get("product_tmpl_id")
        if not check_attr_visible or not product_tmpl_id:
            return
        product_tmpl_id = self.env["product.template"].browse(product_tmpl_id)
        invisible_attr = product_tmpl_id.attribute_line_ids.filtered(
            lambda x: x.invisible
        ).mapped("attribute_id")
        domain_attr = self.mapped("domain_line_ids.attribute_id")
        invalid_attr = domain_attr & invisible_attr
        if not invalid_attr:
            return
        attrs_name = "\n".join(list(invalid_attr.mapped("name")))
        raise ValidationError(
            _("Invisible attribute lines are not allowed in configuration "
              "restrictions:\n" + attrs_name
              )
        )
