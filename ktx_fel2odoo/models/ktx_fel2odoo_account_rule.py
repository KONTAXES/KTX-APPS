# -*- coding: utf-8 -*-
"""Reglas de clasificacion de cuentas contables por palabra clave.

Mapean una palabra de la descripcion de la linea a una cuenta contable. El
destino de la regla se puede indicar de tres formas (en orden de prioridad):

1. **Cuenta concreta** (``account_id``): una cuenta especifica de la empresa.
2. **Codigo de cuenta** (``account_code``): se resuelve contra el plan de la
   empresa por codigo (exacto y luego por prefijo).
3. **Nombre de cuenta** (``account_name``): se resuelve por nombre contra el
   plan de la empresa (del tipo correcto: gasto para compras, ingreso para
   ventas). Es la forma mas PORTABLE: el modulo trae un estandar de reglas
   para Guatemala usando nombres, que funcionan en cualquier plan de cuentas
   (l10n_gt o personalizado) porque los nombres en espanol son consistentes.

Complementan la clasificacion por historial del proveedor y la asistencia por
IA (opcional). Todo configurable por empresa.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class KtxFel2odooAccountRule(models.Model):
    _name = 'ktx.fel2odoo.account.rule'
    _description = 'Regla de clasificacion de cuenta contable (FEL2Odoo)'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Empresa',
        default=lambda self: self.env.company,
        help='Vacio = aplica a todas las empresas.')
    keyword = fields.Char(
        'Palabra clave', required=True,
        help='Si aparece en la descripcion de la linea (sin distinguir '
             'mayusculas ni acentos), se asigna la cuenta indicada.')
    account_id = fields.Many2one(
        'account.account', string='Cuenta contable',
        check_company=True,
        help='Cuenta concreta (prioridad maxima). Si se deja vacia se usa el '
             'codigo o el nombre de cuenta.')
    account_code = fields.Char(
        'Codigo de cuenta',
        help='Se resuelve contra el plan de la empresa por codigo (exacto y '
             'luego por prefijo). Se usa si no hay cuenta concreta.')
    account_name = fields.Char(
        'Nombre de cuenta',
        help='Se resuelve por nombre contra el plan de la empresa, del tipo '
             'correcto (gasto en compras, ingreso en ventas). Forma portable: '
             'funciona en cualquier plan de cuentas de Guatemala.')
    operation = fields.Selection([
        ('purchase', 'Compras'),
        ('sale', 'Ventas'),
        ('both', 'Ambas'),
    ], string='Aplica a', default='purchase', required=True)

    @api.constrains('account_id', 'account_code', 'account_name')
    def _check_target(self):
        for rec in self:
            if not (rec.account_id or rec.account_code or rec.account_name):
                raise ValidationError(_(
                    'La regla "%s" debe indicar una cuenta concreta, un codigo '
                    'de cuenta o un nombre de cuenta.') % (rec.keyword or ''))
