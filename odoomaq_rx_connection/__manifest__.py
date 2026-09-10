# -*- coding: utf-8 -*-
{
    'name': "HW Odoomaq RX Connection",

    'summary': "Module to receive information from Odoo Machinery",

    'description': """
Module to receive information from Odoo Machinery and place it in the administrative system.
    """,

    'license': 'LGPL-3',
    
    'author': 'HW Constructor',
    'website': 'https://www.hw.com.gt',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Customizations',

    'version': '17.0.0.3',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'purchase'
    ],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/purchase_order.xml',
        # 'views/templates.xml',
    ],
    'installable': True,
    'application': False
}

