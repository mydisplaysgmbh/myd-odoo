from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    """Store product.template configuration data in a serialized computed field
    in an attempt to reduce latency and read/write cycles for an efficient
    configuration process

        {
            'attr_prefix_map': {
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

    def get_attr_json_tree(self):
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
        attr_val_constraints = self.get_attr_json_tree()
        attr_val_constraints = [
             attr_val_prefix % cst for cst in attr_val_constraints
        ]
        constraints += attr_val_constraints
        return constraints
        # return ','.join(constraints)

    @api.multi
    @api.depends(get_config_dependencies)
    def _get_config_data(self):
        for product_tmpl in self:
            """Fetch configuration data related to templates and store them as
            json in config_cache serialized field"""
            json_tree = {
                'attrs': {}
            }

            for line in product_tmpl.attribute_line_ids:
                attr = line.attribute_id
                if not attr.json_name:
                    continue
                attr_tree = json_tree['attrs'][attr.json_name] = {}
                attr_tree['custom_type'] = attr.custom_type
                attr_tree['attr_vals'] = {}
                for attr_val in line.value_ids:
                    attr_tree['attr_vals'][attr_val.id] = {
                        'price_extra': 100,
                    }
            import pdb;pdb.set_trace()
            product_tmpl.config_cache = json_tree

    config_cache = fields.Serialized(
        name='Cached configuration data',
        compute='_get_config_data',
        store=True,
        help='Store data used for configuration in json format for quick '
        'access and low latency',
    )
