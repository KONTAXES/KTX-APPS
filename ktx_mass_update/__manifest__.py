# -*- coding: utf-8 -*-
{
    "name": "Asignación Masiva",
    "version": "19.0.1.2.0",
    "category": "Accounting/Accounting",
    "summary": "Actualiza masivamente cuentas, impuestos, fechas y CxP/CxC en facturas desde una sola ventana",
    "description": "Actualizacion masiva de cuentas contables, impuestos, fecha contable/de factura y cuentas CxP/CxC en facturas desde un unico wizard.",
    "author": "KONTAXES",
    "website": "https://www.kontaxes.com",
    "license": "OPL-1",
    "price": 0.0,
    "currency": "USD",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "views/mass_update_wizard_view.xml",
        "views/mass_update_action.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
    "images": [
        "static/description/banner.gif",
        "static/description/banner.png",
    ],
    "web_icon": "ktx_mass_update,static/description/icon.png",
}
