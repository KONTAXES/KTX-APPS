# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    ktx_non_deductible = fields.Boolean(
        string='Gasto No Deducible ISR',
        default=False,
        help='Activado: esta cuenta se incluye como gasto no deducible en el cálculo de ISR Sobre Utilidades.',
    )
    ktx_isr_exento = fields.Boolean(
        string='Ingreso Exento ISR',
        default=False,
        help='Activado: los ingresos de esta cuenta se consideran exentos del ISR '
             '(se restan de la base imponible en la Declaración Sombra ISR Mensual).',
    )
