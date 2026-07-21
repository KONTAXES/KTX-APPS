# -*- coding: utf-8 -*-
{
    'name': 'FEL2ODOO - FORMATO FEL GT - Apariencia KTX 6',
    'summary': 'Apariencia bold (acento fuerte) de factura para Formato FEL GT (KTX6)',
    'description': """
Apariencia adicional (KTX 6) para el modulo base ktx_fel2odoo_format.

Diseño bold en tamaño Carta: badge de documento en acento, franja fuerte,
tabla con encabezado solido y un bloque de TOTAL A PAGAR sobredimensionado.
Color de acento configurable (cfg['accent_color']) con un default esmeralda.
""",
    'author': 'KTX APPS',
    'website': "https://www.kontaxes.com",
    "price": 0.0,
    "currency": "USD",
    'category': 'Accounting/Localizations/Guatemala',
    'version': '19.0.1.1.2',
    'license': 'OPL-1',
    'countries': ['gt'],
    'depends': ['ktx_fel2odoo_format'],
    'data': [
        'report/ktx6_report.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
