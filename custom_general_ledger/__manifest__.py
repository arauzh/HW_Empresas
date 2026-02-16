{
    'name': 'Reporte Libro Mayor, Diario Personalizado',
    'version': '17.0.0.1',
    'category': 'Accounting/Reporting',
    'summary': 'Reporte de Libro Mayor y Diario con estructura personalizada',
    'author': 'HW Constructor',
    "website": "https://www.hw.com.gt",
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/ledger_wizard_view.xml',
        'views/daily_wizard_view.xml',
        'reports/report_general_ledger.xml',
        'reports/report_daily_journal.xml',
    ],
    'installable': True,
    'application': False,
    "license": "LGPL-3",
}