{
    'name': "Mydisplays Product Configurator Stock",
    'summary': """
        Mydisplay configuration interface module for Stock
    """,
    'author': "Pledra",
    'website': "http://www.pledra.com",
    'category': 'Generic Modules/Base',
    'license': 'Other proprietary',
    'version': '12.0.1.0.0',
    'depends': [
        'mydisplays_configurator',
        'product_configurator_stock',
        'sale_stock',
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
