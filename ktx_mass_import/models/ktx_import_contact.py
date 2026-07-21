# -*- coding: utf-8 -*-
from odoo import fields, models


class KtxImportContact(models.Model):
    """Contacto nuevo detectado y creado durante la prueba de importacion.

    Permite asignar la cuenta por cobrar y por pagar a cada contacto nuevo
    antes de crear las facturas. Las cuentas se guardan en las propiedades
    contables del contacto (que son company_dependent), usando el contexto
    de la empresa de la sesion para no mezclar configuraciones entre empresas.
    """
    _name = 'ktx.import.contact'
    _description = 'Contacto Nuevo de Importacion FEL'
    _order = 'id'

    session_id = fields.Many2one(
        'ktx.import.session', required=True, ondelete='cascade', index=True
    )
    company_id = fields.Many2one(
        'res.company', related='session_id.company_id', store=True
    )
    partner_id = fields.Many2one(
        'res.partner', string='Contacto', required=True, ondelete='cascade'
    )
    vat = fields.Char(related='partner_id.vat', string='NIT', readonly=True)
    account_receivable_id = fields.Many2one(
        'account.account', string='Cuenta por Cobrar',
        domain="[('account_type', '=', 'asset_receivable')]",
        help='Cuenta por cobrar a asignar a este contacto en la empresa de la sesion.'
    )
    account_payable_id = fields.Many2one(
        'account.account', string='Cuenta por Pagar',
        domain="[('account_type', '=', 'liability_payable')]",
        help='Cuenta por pagar a asignar a este contacto en la empresa de la sesion.'
    )

    def write(self, vals):
        res = super().write(vals)
        if 'account_receivable_id' in vals or 'account_payable_id' in vals:
            self._apply_accounts()
        return res

    def _apply_accounts(self):
        """Guarda las cuentas elegidas en el contacto, en el contexto de la
        empresa de la sesion (las propiedades contables son company_dependent)."""
        for rec in self:
            if not rec.partner_id:
                continue
            company = rec.company_id or rec.env.company
            partner = rec.partner_id.with_company(company)
            if rec.account_receivable_id:
                partner.property_account_receivable_id = rec.account_receivable_id.id
            if rec.account_payable_id:
                partner.property_account_payable_id = rec.account_payable_id.id
