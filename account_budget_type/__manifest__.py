# -*- coding: utf-8 -*-
{
    'name': "Account budget type",

    'summary': "Agrega que tipo de posición presupuestaria es",

    'description': """
Agrega que tipo de posición presupuestaria es
    """,

    'license': 'LGPL-3',

    'author': "HW Constructor",
    'website': 'https://www.hw.com.gt',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Customizations',
    'version': '17.0.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account', 'account_budget'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/account_budget_type_data.xml',
        'views/account_budget_post.xml',
    ],
}

