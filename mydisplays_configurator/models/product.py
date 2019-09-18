from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    """Store product.template configuration data in a serialized computed field
    in an attempt to reduce latency and read/write cycles for an efficient
    configuration process

        {
            'attr_json_name_map': {
                'id_1': 'length',
                'id_2': 'width'
            },

            'attrs': {
                'attr_prefix': {
                    'attr_vals': {
                        'custom_type': 'float',
                        'val_id_1': {
                            'price_extra': 'number'
                            'product': {
                                'id': 'product_id',
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
            # ?? 'price_extra',
            'product_id',
            'product_id.price',
            'product_id.weight',
        ]

    def get_config_dependencies(self):
        """Return fields used in computing the config cache"""
        constraints = [
            'attribute_line_ids',
            'attribute_line_ids.value_ids',
            'attribute_line_ids.attribute_id',
            'attribute_line_ids.attribute_id.json_name',
            'attribute_line_ids.attribute_id.custom_type',
        ]
        attr_val_prefix = 'attribute_line_ids.attribute_id.value_ids.%s'
        attr_val_constraints = self.get_attr_val_json_tree()
        attr_val_constraints = [
             attr_val_prefix % cst for cst in attr_val_constraints
        ]
        constraints += attr_val_constraints
        return constraints
        # return ','.join(constraints)

    @api.multi
    @api.depends(get_config_dependencies)
    def _get_config_data(self):
        for product_tmpl in self.filtered(lambda x: x.config_ok):
            """Fetch configuration data related to templates and store them as
            json in config_cache serialized field"""
            attr_lines = product_tmpl.attribute_line_ids
            attrs = attr_lines.mapped('attribute_id')
            json_tree = {
                'attr_json_name_map': {
                    a.id: a.json_name for a in attrs if a.json_name
                },
                'attrs': {}
            }

            tmpl_attr_val_obj = self.env['product.template.attribute.value']

            # Get tmpl attr val objects with weight or price extra
            product_tmpl_attr_vals = tmpl_attr_val_obj.search_read([
                ('product_tmpl_id', '=', product_tmpl.id)],
                ['price_extra', 'weight_extra', 'product_attribute_value_id']
            )

            attr_vals_extra = {
                v['product_attribute_value_id'][0]: {
                    'price_extra': v['price_extra'],
                    'weight_extra': v['weight_extra']
                } for v in product_tmpl_attr_vals
            }

            for line in attr_lines:
                attr = line.attribute_id
                if attr.id not in json_tree['attr_json_name_map']:
                    continue
                attr_tree = json_tree['attrs'][attr.json_name] = {}
                attr_tree['custom'] = attr.val_custom
                attr_tree['custom_type'] = attr.custom_type
                attr_tree['attr_vals'] = {}

                for attr_val in line.value_ids:
                    attr_tree['attr_vals'][attr_val.id] = {
                        'price': 0,
                        'weight': 0,
                    }

                    attr_val_tree = attr_tree['attr_vals'][attr_val.id]

                    # Product info
                    product = attr_val.product_id
                    if product:
                        attr_val_tree['price'] = product.price
                        attr_val_tree['weight'] = product.weight
                    else:
                        attr_val_tree['price'] = attr_vals_extra.get(
                            'price_extra', 0
                        )
                        attr_val_tree['weight'] = attr_vals_extra.get(
                            'weight_extra', 0
                        )
            product_tmpl.config_cache = json_tree

    config_cache = fields.Serialized(
        name='Cached configuration data',
        compute='_get_config_data',
        store=True,
        help='Store data used for configuration in json format for quick '
        'access and low latency',
    )
