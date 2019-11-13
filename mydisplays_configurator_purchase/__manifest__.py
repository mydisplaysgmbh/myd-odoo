{
    'name': "Mydisplays Product Configurator Purchase",
    'summary': """
        Mydisplay configuration interface module for Purchase
    """,
    'author': "Pledra",
    'website': "http://www.pledra.com",
    'category': 'Generic Modules/Base',
    'license': 'Other proprietary',
    'version': '12.0.1.0.0',
    'depends': [
        'mydisplays_configurator',
        'product_configurator_purchase',
        'mydisplays_configurator_stock',
    ],
    'data': [
        'views/purchase_view.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
}
