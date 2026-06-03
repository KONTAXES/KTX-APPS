# -*- coding: utf-8 -*-
{
    "name": "Asignación Masiva",
    "version": "19.0.1.0.5",
    "category": "Accounting/Accounting",
    "summary": "Actualiza masivamente cuentas, impuestos y CxP/CxC en facturas desde una sola ventana",
    "description": "Actualizacion masiva de cuentas contables, impuestos y cuentas CxP/CxC en facturas desde un unico wizard.",
    "author": "KONTAXES",
    "website": "https://app.kontaxes.com",
    "license": "OPL-1",
    "price": 10.00,
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
