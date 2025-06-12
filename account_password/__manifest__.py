# -*- coding: utf-8 -*-
{
    'name': "HW account_password",
    
    'license': 'LGPL-3',
    
    'summary': "Supplier payment passwords",

    'description': """
Supplier payment passwords
    """,

    'author': "HW Constructor",
    'website': "https://www.hw.com.gt",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Customizations',
    'version': '17.0.0.2',

    # any module necessary for this one to work correctly
    'depends': ['base','account'],

    # always loaded
    'data': [
        'security/account_security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'Report/password_receipt.xml',
        'Report/ir_actions_report.xml',
    ],
}

