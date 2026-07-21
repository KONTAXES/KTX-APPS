# -*- coding: utf-8 -*-
{
    "name": "Planilla Empleados GT",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": (
        "Planilla de sueldos Guatemala: asistencias, IGSS, ISR, Bono 14, "
        "aguinaldo, vacaciones, liquidaciones, partidas contables y recibos"
    ),
    "description": (
        "Gestión completa de planilla de empleados para Guatemala. "
        "Asistencias con calendario, cálculo de sueldos con bonificación incentivo "
        "(Decreto 78-89), IGSS laboral y patronal, IRTRA, INTECAP, ISR en relación de "
        "dependencia (Decreto 10-2012), provisiones de prestaciones laborales, "
        "Bono 14 (Decreto 42-92), aguinaldo (Decreto 76-78), vacaciones, "
        "liquidación de prestaciones laborales con finiquito (Código de Trabajo), "
        "partidas contables por empleado, pagos con cheque o transferencia, "
        "recibos de nómina con firma y reportes en PDF y Excel según formatos "
        "de SAT y Ministerio de Trabajo."
    ),
    "author": "KONTAXES",
    "website": "https://www.kontaxes.com",
    "license": "OPL-1",
    "price": 0.0,
    "currency": "USD",
    "depends": [
        "hr",
        "account",
        "mail",
        "ktx_check_print",
        "ktx_expense_management",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/paperformat_data.xml",
        "data/mail_template_data.xml",
        "views/res_config_settings_views.xml",
        "views/res_partner_views.xml",
        "views/hr_employee_views.xml",
        "views/asistencia_views.xml",
        "views/asistencia_masiva_wizard_views.xml",
        "views/planilla_views.xml",
        "views/planilla_linea_views.xml",
        "views/liquidacion_views.xml",
        "views/planilla_pago_wizard_views.xml",
        "views/enviar_recibo_wizard_views.xml",
        "views/account_payment_views.xml",
        "report/report_planilla.xml",
        "report/report_recibo_nomina.xml",
        "report/report_liquidacion.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "application": True,
    "installable": True,
    "auto_install": False,
    "images": [
        "static/description/banner.png",
    ],
    "web_icon": "ktx_planilla_empleados_gt,static/description/icon.png",
}
