# -*- coding: utf-8 -*-
{
    'name': 'Importacion Masiva XML-SAT FEL',
    'summary': 'Importa cientos de DTE XML FEL de la SAT Guatemala a Odoo en minutos',
    'description': '''
Importacion Masiva XML-SAT FEL (Guatemala)
==========================================

Convierte cientos de Documentos Tributarios Electronicos (DTE) en formato XML
de la SAT Guatemala (FEL) en facturas de Odoo perfectas, en minutos y sin digitar.

Funcionalidades:
- Carga masiva de archivos XML FEL sin limite (Windows, Mac y Linux)
- Deteccion automatica de documentos vigentes y anulados (los anulados no se importan)
- Omite automaticamente documentos CAIS y CIVA
- Validacion automatica: duplicados, NIT receptor/emisor y compatibilidad
- Mapeo de impuestos por linea segun catalogo SAT (NombreCorto + CodigoUG),
  incluyendo IVA, IDP y TASA MUNICIPAL, con configuracion independiente por empresa
- Soporte completo de frases SAT (12 tipos, 80+ escenarios) con retenciones
  ISR e IVA configurables por empresa
- Calculo de descuentos exacto (monto convertido a porcentaje preciso)
- Totales exactos incluyendo retenciones ISR e IVA
- Creacion automatica de contactos nuevos con asignacion de cuentas por cobrar/pagar
- Correlativo unico por sesion de importacion (IMP/AAAA/MM/0001)
- Historial en vista Kanban/Lista con filtros por NIT, serie, autorizacion y estado
- Normalizacion de texto en espanol (tildes y enies correctas)
- Multiempresa: catalogo compartido, asignacion contable independiente por empresa
    ''',
    'author': 'Kontaxes',
    'website': 'https://www.kontaxes.com',
    'category': 'Accounting/Localizations/Guatemala',
    'version': '19.0.3.0.2',
    'license': 'OPL-1',
    'price': 20.00,
    'currency': 'USD',
    'depends': ['base', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'security/ktx_security.xml',
        'data/ir_sequence_data.xml',
        'data/ktx_frases_data.xml',
        'data/ktx_tax_mapping_data.xml',
        'views/ktx_import_session_views.xml',
        'views/ktx_import_document_views.xml',
        'views/ktx_tax_mapping_views.xml',
        'views/ktx_phrase_config_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'images': [
        'static/description/banner.gif',
        'static/description/banner.png',
    ],
    'web_icon': 'ktx_mass_import,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
