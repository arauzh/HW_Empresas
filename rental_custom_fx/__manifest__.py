# -*- coding: utf-8 -*-
{
    'name': "Rental Custom FX",

    'summary': "Custom exchange rates for Renting (USD↔Q)",

    'description': """
Custom exchange rates for Renting (USD↔Q)
    """,

    'license': 'LGPL-3',
    
    'author': 'HW Constructor',
    'website': 'https://www.hw.com.gt',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Customizations',
    'version': '17.0.0.0',

    # any module necessary for this one to work correctly
    'depends': ['sale_renting'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/rental_exchange_rate_views.xml',
        'views/sale_order_views.xml',
    ],
}

