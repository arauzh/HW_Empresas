# -*- coding: utf-8 -*-

{
    'name': 'Loan Management',
    
    'license': 'LGPL-3',
    
    'summary': 'Helps You To Manage Loan Requests/Disbursement/'
               'Repayments/Amortization Operations',
               
    'description': 'Module Allows To Create different types of loans,'
                   'Manage Loan Requests And Amortization Operations Simply,'
                   'Create Invoices For Each Repayment Amounts',
                   
    'author': "HW Constructor",
    'website': 'https://www.hw.com.gt',
    
    'category': 'Accounting',
    'version': '17.0.3.2',
    
    'depends': ['base',
                'mail', 
                'account'
                ],
    
    'data': [
        'security/loan_management_groups.xml',
        'security/loan_management_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/loan_type_views.xml',
        'views/loan_request_views.xml',
        'views/repayment_lines_views.xml',
        'views/loan_documents_views.xml',
        'views/res_config_settings_views.xml',
        'views/loan_management_menus.xml',
        'views/res_partner_views.xml',
        'wizard/message_popup_views.xml',
        'wizard/reject_reason_views.xml',
        'report/loan_management_reports.xml',
        'report/loan_report_templates.xml',
        'report/loan_report_templates2.xml',
    ],
    
    'demo': ['data/loan_journal_data.xml'],
    
    'installable': True,    
    'auto_install': False,    
    'application': True,
}
