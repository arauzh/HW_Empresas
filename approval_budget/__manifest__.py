# -*- coding: utf-8 -*-
{
    'name': "Approval budget",

    'summary': "Additional module for budget approval",

    'description': """
Additional module for budget approval
    """,
    
    'license': 'LGPL-3',

    'author': "HW Constructor",
    'website': 'https://www.hw.com.gt',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources/Approvals',
    'version': '17.0.2.0',

    # any module necessary for this one to work correctly
    'depends': ['approvals', 'account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/approval_category_views.xml',
        'views/approval_request_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'approval_budget/static/src/js/section_wise_subtotal.js',
        ],
    },
    'installable': True,
    'auto_install': True,
}

