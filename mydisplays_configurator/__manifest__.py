{
    'name': "Mydisplays Product Configurator",
    'summary': """
        Product configurator adaptation for mydisplays products and workflow
    """,
    'description': """
        Product configurator adaptation for mydisplays products and workflow
    """,
    'author': "Pledra",
    'website': "http://www.pledra.com",
    'category': 'Generic Modules/Base',
    'version': '0.1',
    'depends': [
        'base_sparse_field',
        'sale',
        'mrp',
        'product_configurator',
        'website_product_configurator',
    ],
    'data': [
        'views/sale_order_view.xml',
        'views/product_attribute_view.xml',
        'views/product_config_view.xml',
        'views/product_view.xml',
    ],
    'demo': [
        'demo/uom_demo.xml',
        'demo/product_template_demo.xml',
        'demo/product_demo.xml',
        'demo/product_attribute_demo.xml',
        'demo/product_attribute_value_demo.xml',
        'demo/product_attribute_line_demo.xml',
        'demo/product_template_attribute_value_demo.xml',
        'demo/product_config_domain_demo.xml',
        'demo/product_config_domain_line_demo.xml',
    ],
}
