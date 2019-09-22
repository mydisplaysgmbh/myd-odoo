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
        'product_configurator',
        'website_product_configurator',
    ],
    'data': [
        'views/product_attribute_view.xml',
        'views/product_config_view.xml',
        'views/product_view.xml',
    ],
    'demo': [
        'demo/product_template.xml',
        'demo/prodcut.xml',
        'demo/prodcut_attribute.xml',
        'demo/prodcut_attribute_value.xml',
        'demo/product_attribute_line.xml',
    ],
}
