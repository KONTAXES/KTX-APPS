# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ktx_pl_igss_laboral = fields.Float(
        related="company_id.ktx_pl_igss_laboral", readonly=False)
    ktx_pl_igss_patronal = fields.Float(
        related="company_id.ktx_pl_igss_patronal", readonly=False)
    ktx_pl_irtra = fields.Float(
        related="company_id.ktx_pl_irtra", readonly=False)
    ktx_pl_intecap = fields.Float(
        related="company_id.ktx_pl_intecap", readonly=False)
    ktx_pl_bonificacion_incentivo = fields.Float(
        related="company_id.ktx_pl_bonificacion_incentivo", readonly=False)

    ktx_pl_isr_deduccion_fija = fields.Float(
        related="company_id.ktx_pl_isr_deduccion_fija", readonly=False)
    ktx_pl_isr_tramo1_limite = fields.Float(
        related="company_id.ktx_pl_isr_tramo1_limite", readonly=False)
    ktx_pl_isr_tramo1_tasa = fields.Float(
        related="company_id.ktx_pl_isr_tramo1_tasa", readonly=False)
    ktx_pl_isr_tramo2_tasa = fields.Float(
        related="company_id.ktx_pl_isr_tramo2_tasa", readonly=False)
    ktx_pl_isr_tramo2_cuota_fija = fields.Float(
        related="company_id.ktx_pl_isr_tramo2_cuota_fija", readonly=False)

    ktx_pl_provision_frecuencia = fields.Selection(
        related="company_id.ktx_pl_provision_frecuencia", readonly=False)
    ktx_pl_prov_indemnizacion = fields.Float(
        related="company_id.ktx_pl_prov_indemnizacion", readonly=False)
    ktx_pl_prov_aguinaldo = fields.Float(
        related="company_id.ktx_pl_prov_aguinaldo", readonly=False)
    ktx_pl_prov_bono14 = fields.Float(
        related="company_id.ktx_pl_prov_bono14", readonly=False)
    ktx_pl_prov_vacaciones = fields.Float(
        related="company_id.ktx_pl_prov_vacaciones", readonly=False)

    ktx_pl_account_gasto_sueldo_id = fields.Many2one(
        related="company_id.ktx_pl_account_gasto_sueldo_id", readonly=False)
    ktx_pl_account_gasto_bonificacion_id = fields.Many2one(
        related="company_id.ktx_pl_account_gasto_bonificacion_id", readonly=False)
    ktx_pl_account_gasto_patronal_id = fields.Many2one(
        related="company_id.ktx_pl_account_gasto_patronal_id", readonly=False)
    ktx_pl_account_gasto_prestaciones_id = fields.Many2one(
        related="company_id.ktx_pl_account_gasto_prestaciones_id", readonly=False)
    ktx_pl_account_pagar_sueldos_id = fields.Many2one(
        related="company_id.ktx_pl_account_pagar_sueldos_id", readonly=False)
    ktx_pl_account_igss_pagar_id = fields.Many2one(
        related="company_id.ktx_pl_account_igss_pagar_id", readonly=False)
    ktx_pl_account_isr_pagar_id = fields.Many2one(
        related="company_id.ktx_pl_account_isr_pagar_id", readonly=False)
    ktx_pl_account_judicial_pagar_id = fields.Many2one(
        related="company_id.ktx_pl_account_judicial_pagar_id", readonly=False)
    ktx_pl_account_otros_desc_id = fields.Many2one(
        related="company_id.ktx_pl_account_otros_desc_id", readonly=False)
    ktx_pl_account_anticipos_id = fields.Many2one(
        related="company_id.ktx_pl_account_anticipos_id", readonly=False)
    ktx_pl_account_prov_indemnizacion_id = fields.Many2one(
        related="company_id.ktx_pl_account_prov_indemnizacion_id", readonly=False)
    ktx_pl_account_prov_aguinaldo_id = fields.Many2one(
        related="company_id.ktx_pl_account_prov_aguinaldo_id", readonly=False)
    ktx_pl_account_prov_bono14_id = fields.Many2one(
        related="company_id.ktx_pl_account_prov_bono14_id", readonly=False)
    ktx_pl_account_prov_vacaciones_id = fields.Many2one(
        related="company_id.ktx_pl_account_prov_vacaciones_id", readonly=False)
    ktx_pl_journal_id = fields.Many2one(
        related="company_id.ktx_pl_journal_id", readonly=False)

    ktx_pl_contador_nombre = fields.Char(
        related="company_id.ktx_pl_contador_nombre", readonly=False)
    ktx_pl_contador_registro = fields.Char(
        related="company_id.ktx_pl_contador_registro", readonly=False)
