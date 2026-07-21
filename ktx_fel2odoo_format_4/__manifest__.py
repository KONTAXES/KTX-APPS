# -*- coding: utf-8 -*-
{
    'name': 'FEL2ODOO - FORMATO FEL GT - Apariencia KTX 5',
    'summary': 'Apariencia minimalista de factura para Formato FEL GT (KTX5)',
    'description': """
Apariencia adicional (KTX 5) para el modulo base ktx_fel2odoo_format.

Diseño minimalista en tamaño Carta: mucho aire, tipografia protagonista,
lineas finas (hairlines) en lugar de cajas y total destacado por escala.
Color de acento configurable (cfg['accent_color']) con un default tinta.
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
        'report/ktx5_report.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
