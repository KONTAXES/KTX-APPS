# -*- coding: utf-8 -*-
{
    'name': 'FEL2ODOO - AUTOMATE FEL GT - IMPORTACION MASIVA DE XML',
    'summary': 'Automatiza las facturas de compras y ventas FEL de la SAT Guatemala: '
               'descarga por API o carga masiva de XML, con impuestos y contabilizacion',
    'description': '''
FEL2ODOO - AUTOMATE FEL GT - IMPORTACION MASIVA DE XML
======================================================

Automatiza el ingreso de **facturas de compras y ventas** (DTE FEL) de la SAT
de Guatemala hacia Odoo. Dos modos en un solo modulo:

1. **Automatico por API** (proveedor intermediario apifelcore.com): consulta y
   descarga por periodos, crea las facturas y (opcional) las confirma.
2. **Carga masiva de XML manual**: sube muchos XML a la vez, con asignacion
   automatica de impuestos por linea segun el catalogo SAT.

Ademas, permite **EMITIR** (certificar ante la SAT) facturas de venta
normales directamente desde Odoo, con el mismo proveedor. Se configura por
DIARIO de ventas (establecimiento, tipo de documento, manual o automatica
al confirmar); restringida a gestores contables, DESACTIVADA por defecto.
Anular una factura emitida (con motivo) tambien se puede hacer con el
flujo estandar de Odoo: restablecer a borrador y Cancelar.

Enfocado SOLO en facturas de compras y ventas (no exportaciones, importaciones
ni retenciones como documento aparte).

Que hace
--------
- Autenticacion segura con doble token (plataforma via /login + token de
  Agencia Virtual en el cuerpo). Los secretos nunca se muestran ni se registran.
- Solo descarga los XML **pendientes** (compara por numero de autorizacion) para
  ahorrar llamadas API; control de cuota mensual con corte automatico.
- Sincronizacion automatica (cron) activable solo con la conexion probada, con
  frecuencia configurable (6h/12h/diaria/semanal/mensual).
- Creacion de facturas con mapeo de impuestos por linea (IVA, IDP, Tasa
  Municipal, etc.), frases SAT con retenciones ISR/IVA, descuentos y contactos.
- Clasificacion opcional de cuentas contables (por descripcion e historial del
  proveedor) y asistencia por IA opcional (modulo de IA aparte, con su API key
  por cliente). Ambas DESACTIVADAS por defecto.
- Confirmacion automatica opcional (DESACTIVADA por defecto).
- Interfaz de solo lectura para agentes de IA/integraciones (``ai_status``).
- Bitacora con diagnostico por corrida.

Seguridad
---------
Modulo que consume APIs de terceros con capas de proteccion: credenciales
tratadas como secretos, sin inyeccion de datos externos como codigo, acceso por
grupos contables, y la automatica bloqueada hasta verificar la conexion.

----
Propiedad de **KTX APPS** — NIT 93823509.
Contenido generado con ayuda de IA, con estricta planificacion y gestion de KTX.
    ''',
    'author': 'KTX APPS',
    'website': "https://www.kontaxes.com",
    'category': 'Accounting/Localizations/Guatemala',
    'version': '19.0.35.1.0',
    'license': 'OPL-1',
    'countries': ['gt'],
    # LANZAMIENTO 2026: GRATIS (50% OFF sobre el precio normal de 200 USD).
    # Al terminar el lanzamiento, subir 'price' a 200.00.
    'price': 0.0,
    'currency': 'USD',
    'depends': [
        'base',
        'account',
        'mail',
        'ktx_mass_import',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/ktx_fel2odoo_security.xml',
        'data/ir_cron_data.xml',
        'data/account_rule_data.xml',
        'views/ktx_fel2odoo_config_views.xml',
        'views/ktx_fel2odoo_account_rule_views.xml',
        'views/ktx_fel2odoo_log_views.xml',
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/res_partner_views.xml',
        'wizard/ktx_fel2odoo_test_wizard_views.xml',
        'wizard/ktx_fel2odoo_cancel_wizard_views.xml',
        'wizard/ktx_fel2odoo_nit_wizard_views.xml',
        'views/menus.xml',
    ],
    'images': [
        'static/description/banner.gif',
        'static/description/banner.png',
    ],
    'web_icon': 'ktx_fel2odoo,static/description/icon.png',
    'installable': True,
    'application': True,
    'auto_install': False,
}
