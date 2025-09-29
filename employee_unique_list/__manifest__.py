{
    "name": "Employee Unique List",
    "version": "17.0.0.0.1",
    "summary": "Lista de empleados únicos por identification_id con deducciones",
    "author": "HW",
    'license': 'LGPL-3',
    'website': 'https://www.hw.com.gt',
    "category": "Human Resources",
    "depends": ["hr", "hr_payroll", "account"],
    "data": [
        'security/employee_unique_security.xml',
        "security/ir.model.access.csv",
        "views/employee_unique_views.xml",
    ],
    "installable": True,
    "application": False,
}
