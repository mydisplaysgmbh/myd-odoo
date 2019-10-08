{
    'name': "Mydisplays Product Configurator Stock",
    'summary': """
        Mydisplay configuration interface module for Stock
    """,
    'description': """
        Mydisplay configuration interface module for Stock
    """,
    'author': "Pledra",
    'website': "http://www.pledra.com",
    'category': 'Generic Modules/Base',
    'version': '0.1',
    'depends': [
        'mydisplays_configurator',
        'product_configurator_stock'
    ],
    'data': [
        'views/stock_picking_view.xml',
        'views/stock_move_view.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'auto_install': False,
}
