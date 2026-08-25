# -*- coding: utf-8 -*-
{
    'name': "Purchase analytical reception",

    'summary': """
    Agrega que al confirmar la compra y crear la recepción se creen la líneas de recepción con la misma que la compra.
    """,

    'description': """
Agrega que al confirmar la compra y crear la recepción se creen la líneas de recepción con la misma que la compra.
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
    'depends': ['base','purchase_stock'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        # 'views/views.xml',
        # 'views/templates.xml',
    ],
}

