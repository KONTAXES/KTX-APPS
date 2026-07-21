# -*- coding: utf-8 -*-
{
    'name': 'FEL2ODOO - FORMATO FEL GT - Apariencia KTX 4',
    'summary': 'Apariencia corporativa (ERP) de factura para Formato FEL GT (KTX4)',
    'description': """
Apariencia adicional (KTX 4) para el modulo base ktx_fel2odoo_format.

Diseño corporativo/ERP en tamaño Carta: banda de cabecera solida, cajas
Emisor/Receptor, franja de datos del documento, tabla con cuadricula y filas
alternas, y bloque de certificacion con QR. Pensado para verse mas limpio y
ordenado que formatos tipo SAP. Color de acento configurable
(cfg['accent_color']) con un default corporativo (navy).
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
        'report/ktx4_report.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
