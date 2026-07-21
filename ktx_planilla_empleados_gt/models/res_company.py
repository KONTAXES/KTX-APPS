# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # ------------------------------------------------------------------
    # Tasas legales Guatemala (valores por defecto vigentes; editables
    # para absorber futuras reformas sin actualizar el módulo).
    # ------------------------------------------------------------------
    ktx_pl_igss_laboral = fields.Float(
        string="IGSS Laboral (%)",
        default=4.83,
        help="Cuota laboral IGSS retenida al trabajador (Acuerdo 1118 J.D. IGSS). "
             "Se calcula sobre salario ordinario + extraordinario + comisiones; "
             "la bonificación incentivo está exenta (Decreto 78-89).",
    )
    ktx_pl_igss_patronal = fields.Float(
        string="IGSS Patronal (%)",
        default=10.67,
        help="Cuota patronal IGSS a cargo del empleador.",
    )
    ktx_pl_irtra = fields.Float(
        string="IRTRA (%)",
        default=1.0,
        help="Cuota patronal IRTRA (Decreto 1528).",
    )
    ktx_pl_intecap = fields.Float(
        string="INTECAP (%)",
        default=1.0,
        help="Cuota patronal INTECAP (Decreto 17-72).",
    )
    ktx_pl_bonificacion_incentivo = fields.Float(
        string="Bonificación Incentivo Mensual",
        default=250.0,
        help="Bonificación incentivo mensual mínima (Decretos 78-89 y 37-2001): Q250.00. "
             "Exenta de IGSS pero afecta a ISR.",
    )

    # --- ISR relación de dependencia (Decreto 10-2012, art. 72-73) ---
    ktx_pl_isr_deduccion_fija = fields.Float(
        string="ISR: Deducción Fija Anual",
        default=48000.0,
        help="Deducción única anual sin comprobación (Q48,000, art. 72 Decreto 10-2012).",
    )
    ktx_pl_isr_tramo1_limite = fields.Float(
        string="ISR: Límite Tramo 1",
        default=300000.0,
        help="Renta imponible anual hasta la cual aplica la tasa del tramo 1 (Q300,000).",
    )
    ktx_pl_isr_tramo1_tasa = fields.Float(
        string="ISR: Tasa Tramo 1 (%)",
        default=5.0,
    )
    ktx_pl_isr_tramo2_tasa = fields.Float(
        string="ISR: Tasa Tramo 2 (%)",
        default=7.0,
        help="Tasa sobre el excedente del límite del tramo 1.",
    )
    ktx_pl_isr_tramo2_cuota_fija = fields.Float(
        string="ISR: Cuota Fija Tramo 2",
        default=15000.0,
        help="Importe fijo anual del tramo 2 (Q15,000 sobre el excedente de Q300,000).",
    )

    # --- Provisiones de prestaciones laborales ---
    ktx_pl_provision_frecuencia = fields.Selection(
        selection=[
            ("mensual", "Mensual (en cada planilla)"),
            ("ninguna", "No provisionar"),
        ],
        string="Provisión de Prestaciones",
        default="mensual",
        help="Si es mensual, cada planilla de sueldos genera la provisión de "
             "indemnización (9.72%), aguinaldo (8.33%), Bono 14 (8.33%) y "
             "vacaciones (4.17%) en la partida contable.",
    )
    ktx_pl_prov_indemnizacion = fields.Float(
        string="Provisión Indemnización (%)",
        default=9.72,
        help="Un mes por año (8.33%) más la incidencia de aguinaldo y Bono 14 "
             "sobre la indemnización (art. 82 Código de Trabajo y Decreto 76-78).",
    )
    ktx_pl_prov_aguinaldo = fields.Float(
        string="Provisión Aguinaldo (%)",
        default=8.33,
    )
    ktx_pl_prov_bono14 = fields.Float(
        string="Provisión Bono 14 (%)",
        default=8.33,
    )
    ktx_pl_prov_vacaciones = fields.Float(
        string="Provisión Vacaciones (%)",
        default=4.17,
    )

    # ------------------------------------------------------------------
    # Cuentas contables por defecto
    # ------------------------------------------------------------------
    ktx_pl_account_gasto_sueldo_id = fields.Many2one(
        "account.account",
        string="Gasto Sueldos y Salarios",
        help="Cuenta de gasto por defecto para sueldos y salarios. "
             "Puede sobreescribirse por empleado en su contacto.",
    )
    ktx_pl_account_gasto_bonificacion_id = fields.Many2one(
        "account.account",
        string="Gasto Bonificación Incentivo",
        help="Si se deja vacío se usa la cuenta de gasto de sueldos.",
    )
    ktx_pl_account_gasto_patronal_id = fields.Many2one(
        "account.account",
        string="Gasto Cuotas Patronales",
        help="Gasto de IGSS patronal, IRTRA e INTECAP. "
             "Si se deja vacío se usa la cuenta de gasto de sueldos.",
    )
    ktx_pl_account_gasto_prestaciones_id = fields.Many2one(
        "account.account",
        string="Gasto Prestaciones Laborales",
        help="Gasto de provisiones y de liquidaciones de prestaciones. "
             "Si se deja vacío se usa la cuenta de gasto de sueldos.",
    )
    ktx_pl_account_pagar_sueldos_id = fields.Many2one(
        "account.account",
        string="Por Pagar Sueldos y Salarios",
        help="Cuenta puente de sueldos por pagar; se cancela con el pago al empleado.",
    )
    ktx_pl_account_igss_pagar_id = fields.Many2one(
        "account.account",
        string="IGSS por Pagar",
        help="Cuota laboral retenida + cuotas patronales por enterar al IGSS.",
    )
    ktx_pl_account_isr_pagar_id = fields.Many2one(
        "account.account",
        string="ISR Retenido por Pagar",
    )
    ktx_pl_account_judicial_pagar_id = fields.Many2one(
        "account.account",
        string="Descuentos Judiciales por Pagar",
        help="Embargos y pensiones alimenticias ordenados por juez.",
    )
    ktx_pl_account_otros_desc_id = fields.Many2one(
        "account.account",
        string="Otros Descuentos por Pagar",
    )
    ktx_pl_account_anticipos_id = fields.Many2one(
        "account.account",
        string="Anticipos a Empleados",
        help="Cuenta de activo donde se registran los anticipos que se descuentan en planilla.",
    )
    ktx_pl_account_prov_indemnizacion_id = fields.Many2one(
        "account.account",
        string="Provisión Indemnización (Pasivo)",
    )
    ktx_pl_account_prov_aguinaldo_id = fields.Many2one(
        "account.account",
        string="Provisión Aguinaldo (Pasivo)",
    )
    ktx_pl_account_prov_bono14_id = fields.Many2one(
        "account.account",
        string="Provisión Bono 14 (Pasivo)",
    )
    ktx_pl_account_prov_vacaciones_id = fields.Many2one(
        "account.account",
        string="Provisión Vacaciones (Pasivo)",
    )

    ktx_pl_journal_id = fields.Many2one(
        "account.journal",
        string="Diario de Planilla",
        domain="[('type', '=', 'general')]",
        help="Diario donde se registran las partidas contables de planilla.",
    )

    # --- Datos para reportes ---
    ktx_pl_contador_nombre = fields.Char(
        string="Nombre del Contador",
        help="Nombre que firma la planilla impresa.",
    )
    ktx_pl_contador_registro = fields.Char(
        string="No. Registro Perito Contador",
        help="Número de registro del perito contador ante la SAT.",
    )
