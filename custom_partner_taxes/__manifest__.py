{
    'name': 'Partner Applicable Taxes',
    'version': '17.0.0.0',
    'summary': 'Agregar impuestos aplicables en contactos',
    'description': """
Campo de etiquetas para impuestos aplicables
en el formulario de contactos.
""",
    'author': 'HW Constructor',
    'category': 'Customizations',
    'license': 'LGPL-3',
    'depends': ['contacts', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/partner_tax_tag_views.xml',
        'views/res_partner_views.xml',
        'views/account_payment_views.xml',
        'views/account_payment_register_views.xml',
    ],
    'installable': True,
    'application': False,
}