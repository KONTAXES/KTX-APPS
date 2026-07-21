# -*- coding: utf-8 -*-
{
    'name': 'FEL2ODOO - FORMATO FEL GT - Apariencia KTX 3',
    'summary': 'Apariencia premium de factura para Formato FEL GT (KTX3)',
    'description': """
Apariencia adicional (KTX 3) para el modulo base ktx_fel2odoo_format.

Rediseño ejecutivo/premium del formato Carta, inspirado en la factura real
de CORPOSISTEMAS y mejorado en jerarquia visual, tipografia y limpieza.
Color de acento configurable (cfg['accent_color']), con un default elegante.
""",
    'author': 'KTX APPS',
    'website': "https://www.kontaxes.com",
    "price": 0.0,
    "currency": "USD",
    'category': 'Accounting/Localizations/Guatemala',
    'version': '19.0.1.1.2',
    'license': 'OPL-1',
    'countries': ['gt'],
    # CLAVE: depende del modulo base. Asi hereda toda la logica y los datos.
    'depends': ['ktx_fel2odoo_format'],
    'data': [
        'report/ktx3_report.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
