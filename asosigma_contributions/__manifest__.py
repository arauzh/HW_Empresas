{
    'name': 'ASOSIGMA Contributions',
    'version': '17.0.0.0',
    'category': 'Accounting',
    'summary': 'Gestión de aportaciones y ahorros ASOSIGMA',
    'author': 'ASOSIGMA',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'contacts',
        'hr_payroll',
    ],
    'data': [
        'views/res_partner_views.xml',
        'views/asosigma_contribution_views.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True,
    'application': True,
}