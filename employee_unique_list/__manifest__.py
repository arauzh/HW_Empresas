{
    "name": "Employee Unique List",
    "version": "17.0.0.0.6",
    "summary": "Lista de empleados únicos por numero de identificacion personal, las deducciones de ASOSIGMA que poseean cada uno y su facturacion",
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
