from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval


class ProductConfigSession(models.Model):
    _inherit = 'product.config.session'

    @api.model
    def _get_eval_context(self):
        """ Evaluatioe context to pass to safe_eval """
        tmpl_config_cache = self.product_tmpl_id.config_cache or {}

        # Configuration data (attr vals and custom vals) using json name
        config = {}

        # Add selected value_ids to config dict using human readable json name
        for attr_val in self.value_ids:
            val_id = str(attr_val.id)
            json_val = tmpl_config_cache['attr_vals'].get(val_id, {})
            attr_id = json_val.get('attribute_id')
            attr_json_name = tmpl_config_cache['attr_json_map'][str(attr_id)]
            config[attr_json_name] = tmpl_config_cache['attr_vals'][val_id]

        # Add custom value_ids to config dict using human readable json name
        for attr_val_id, val in self.json_config:
            val_id = str(attr_val.id)
            json_val = tmpl_config_cache['attr_vals'].get(val_id, {})
            attr_id = json_val.get('attribute_id')
            attr_json_name = tmpl_config_cache['attr_json_map'][str(attr_id)]
            # TODO: Add typecast using custom_type info
            config[attr_json_name] = val

        return {
            'template': tmpl_config_cache.get('attrs', {}),
            'session': {
                'price': 0,
                'weight': 0,
                'quantity': 0,
                'bom': [],
            },
            'config': config,
        }

    @api.multi
    @api.depends('product_tmpl_id.config_cache', 'json_config', 'value_ids')
    def _compute_json_vals(self):
        for session in self:
            code = session.product_tmpl_id.computed_vals_formula
            eval_context = session._get_eval_context()
            safe_eval(
                code.strip(), eval_context, mode="exec",
                nocopy=True, locals_builtins=True
            )
            session.json_vals = eval_context['session']

    json_config = fields.Serialized(
        name='JSON Config',
        help='Json representation of all custom values'
    )
    json_vals = fields.Serialized(
        name='JSON Vals',
        help='Final version of aggregated custom values and computed values',
        compute='_compute_json_vals',
        store=True
    )

    @api.multi
    def get_session_vals(self, product_tmpl_id, parent_id=None, user_id=None):
        res = super(ProductConfigSession, self).get_session_vals(
            product_tmpl_id=product_tmpl_id, parent_id=None, user_id=None)
        product_tmpl_id = res.get('product_tmpl_id', False)
        product_tmpl = self.env['product.template'].browse(int(product_tmpl_id))
        attr_line = product_tmpl.attribute_line_ids
        for line in attr_line:
            if len(line.value_ids) == 1:
                res.update({'value_ids': [(6, 0, line.value_ids)]})
        return res