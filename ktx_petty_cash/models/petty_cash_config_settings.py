# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    petty_cash_transit_account_id = fields.Many2one(
        "account.account",
        string="Cuenta Transitoria de Reposición",
        config_parameter="ktx_petty_cash.transit_account_id",
        help="Cuenta transitoria (debe tener 'Permitir conciliación' activo) usada como puente "
             "entre el banco y la caja chica al agregar fondos.",
    )
    petty_cash_default_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de Caja Chica por Defecto",
        config_parameter="ktx_petty_cash.default_account_id",
        help="Cuenta contable utilizada por defecto para los fondos de caja chica.",
    )
    petty_cash_default_journal_id = fields.Many2one(
        "account.journal",
        string="Diario por Defecto",
        config_parameter="ktx_petty_cash.default_journal_id",
        domain="[('type', 'in', ['general', 'cash', 'bank'])]",
        help="Diario contable utilizado por defecto para los asientos de caja chica.",
    )
    petty_cash_require_authorizer = fields.Boolean(
        string="Requerir Autorizador",
        config_parameter="ktx_petty_cash.require_authorizer",
        help="Si está activo, cada fondo de caja chica debe tener un autorizador asignado.",
    )
    petty_cash_auto_reconcile = fields.Boolean(
        string="Reconciliar automáticamente con facturas",
        config_parameter="ktx_petty_cash.auto_reconcile",
        default=True,
        help="Reconcilia automáticamente el asiento contable con la factura de origen.",
    )
    petty_cash_multi_company = fields.Boolean(
        string="Vista Multiempresa",
        config_parameter="ktx_petty_cash.multi_company",
        help=(
            "Si está activo, muestra fondos, movimientos y gastos por reembolsar "
            "de todas las compañías del usuario al mismo tiempo. "
            "Si no está activo, cada compañía ve únicamente su propia información."
        ),
    )
