# -*- coding: utf-8 -*-
{
    "name": "Reportería Fiscal SAT GT",
    "version": "19.0.1.4.0",
    "category": "Accounting/Accounting",
    "summary": (
        "Libros SAT · Declaración Sombra · IVA / ISR / ISO · "
        "Localización fiscal completa para Guatemala en Odoo 19"
    ),
    "description": (
        "Genera los Libros de Compras, Ventas, Diario y Mayor en el formato exacto que exige la "
        "SAT de Guatemala. Incluye Resumen Fiscal interactivo con cálculo de IVA (General y "
        "Pequeño Contribuyente), ISR (Opcional Simplificado y Sobre Utilidades) e ISO, y "
        "Declaración Sombra para revisar tu posición fiscal antes de ingresar al portal SAT. "
        "Diseñado específicamente para la localización de Guatemala. "
        "NOTA: versión actual cubre movimientos locales; importaciones y exportaciones "
        "estarán disponibles en próximas actualizaciones."
    ),
    "author": "KONTAXES",
    "website": "https://app.kontaxes.com",
    "license": "OPL-1",
    "price": 1.00,
    "currency": "USD",
    "depends": ["account"],
    "assets": {
        "web.assets_backend": [
            "ktx_satgt_reports/static/src/components/period_filter.js",
            "ktx_satgt_reports/static/src/components/period_filter.xml",
            "ktx_satgt_reports/static/src/components/period_filter.scss",
        ],
    },
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/res_company_views.xml",
        "views/account_account_views.xml",
        "views/account_tax_views.xml",
        "views/satgt_resumen_views.xml",
        "views/satgt_book_views.xml",
        "views/satgt_decl_views.xml",
        "views/satgt_ajustes_views.xml",
        "report/satgt_libro_compras_report.xml",
        "report/satgt_libro_ventas_report.xml",
        "report/satgt_libro_pc_report.xml",
        "report/satgt_libro_diario_report.xml",
        "report/satgt_libro_mayor_report.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "application": True,
    "installable": True,
    "auto_install": False,
    "images": [
        "static/description/banner.gif",
        "static/description/banner.png",
    ],
    "web_icon": "ktx_satgt_reports,static/description/icon.png",
}
