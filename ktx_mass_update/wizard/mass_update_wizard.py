# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_VENDOR_TYPES = ('in_invoice', 'in_refund', 'in_receipt')
_CUSTOMER_TYPES = ('out_invoice', 'out_refund', 'out_receipt')


class KtxMassUpdateWizard(models.TransientModel):
    _name = 'ktx.mass.update.wizard'
    _description = 'Asignación Masiva de Facturas'

    move_ids = fields.Many2many(
        'account.move',
        string='Facturas seleccionadas',
        readonly=True,
    )

    # ── Pestaña 2: Gasto / Venta ──────────────────────────────────────────────
    expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Gasto',
        domain=[
            ('account_type', 'in', ['expense', 'expense_direct_cost', 'asset_expense']),
            ('active', '=', True),
        ],
    )
    income_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de Ingreso',
        domain=[('account_type', '=', 'income'), ('active', '=', True)],
    )

    # ── Pestaña 3: Impuestos ──────────────────────────────────────────────────
    tax_action_type = fields.Selection(
        [
            ('replace', 'Reemplazar impuestos'),
            ('add', 'Agregar impuestos'),
            ('reset', 'Eliminar impuestos'),
        ],
        string='Acción',
        default='replace',
        required=True,
    )
    vendor_tax_ids = fields.Many2many(
        'account.tax',
        'ktx_mass_upd_purchase_rel',
        'wizard_id', 'tax_id',
        string='Impuestos de compra',
        domain=[('type_tax_use', '=', 'purchase')],
    )
    customer_tax_ids = fields.Many2many(
        'account.tax',
        'ktx_mass_upd_sale_rel',
        'wizard_id', 'tax_id',
        string='Impuestos de venta',
        domain=[('type_tax_use', '=', 'sale')],
    )

    # ── Pestaña 4: Fecha ──────────────────────────────────────────────────────
    new_date = fields.Date(
        string='Nueva fecha contable',
        help='Se aplica al campo Fecha (fecha contable) de los documentos en '
             'borrador seleccionados.',
    )
    new_invoice_date = fields.Date(
        string='Nueva fecha de factura',
        help='Se aplica al campo Fecha de factura de los documentos en '
             'borrador seleccionados.',
    )

    # ── Pestaña 5: CxC / CxP ─────────────────────────────────────────────────
    account_payable_id = fields.Many2one(
        'account.account',
        string='Nueva cuenta CxP',
        domain=[('account_type', '=', 'liability_payable'), ('active', '=', True)],
        help='Se aplica a facturas y notas de proveedor en borrador.',
    )
    account_receivable_id = fields.Many2one(
        'account.account',
        string='Nueva cuenta CxC',
        domain=[('account_type', '=', 'asset_receivable'), ('active', '=', True)],
        help='Se aplica a facturas y notas de cliente en borrador.',
    )
    update_partner_account = fields.Boolean(
        string='Asignar cuenta al proveedor/cliente',
        default=False,
        help=(
            'Si está activo, también actualiza la cuenta CxP/CxC en la pestaña '
            'Contabilidad de cada contacto involucrado.'
        ),
    )

    # ── Resultado de la última acción ─────────────────────────────────────────
    result_message = fields.Char(string='Resultado', readonly=True)

    # ── Campos de resumen (solo vista) ────────────────────────────────────────
    has_vendor = fields.Boolean(compute='_compute_doc_summary', store=False)
    has_customer = fields.Boolean(compute='_compute_doc_summary', store=False)
    vendor_count = fields.Integer(compute='_compute_doc_summary', store=False)
    customer_count = fields.Integer(compute='_compute_doc_summary', store=False)
    draft_count = fields.Integer(compute='_compute_doc_summary', store=False)
    non_draft_count = fields.Integer(compute='_compute_doc_summary', store=False)
    has_reconciled = fields.Boolean(compute='_compute_doc_summary', store=False)
    reconciled_count = fields.Integer(compute='_compute_doc_summary', store=False)

    @api.depends('move_ids')
    def _compute_doc_summary(self):
        for wiz in self:
            vendors = wiz.move_ids.filtered(lambda m: m.move_type in _VENDOR_TYPES)
            customers = wiz.move_ids.filtered(lambda m: m.move_type in _CUSTOMER_TYPES)
            drafts = wiz.move_ids.filtered(lambda m: m.state == 'draft')
            reconciled = wiz.move_ids.filtered(
                lambda m: any(l.reconciled for l in m.line_ids)
            )
            wiz.has_vendor = bool(vendors)
            wiz.has_customer = bool(customers)
            wiz.vendor_count = len(vendors)
            wiz.customer_count = len(customers)
            wiz.draft_count = len(drafts)
            wiz.non_draft_count = len(wiz.move_ids) - len(drafts)
            wiz.has_reconciled = bool(reconciled)
            wiz.reconciled_count = len(reconciled)

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids')
        if self.env.context.get('active_model') == 'account.move' and active_ids:
            res['move_ids'] = [(6, 0, active_ids)]
        return res

    # ── Acciones ──────────────────────────────────────────────────────────────

    def action_reset_to_draft(self):
        if not self.move_ids:
            raise UserError(_('No hay documentos seleccionados.'))
        count = 0
        for move in self.move_ids:
            if move.state in ('posted', 'cancel'):
                move.button_draft()
                count += 1
        if not count:
            raise UserError(_('No hay documentos que puedan restablecerse a borrador.'))
        return self._notify_and_close(
            _('Se restablecieron %s documento(s) a borrador.') % count
        )

    def action_apply_accounts(self):
        if not self.expense_account_id and not self.income_account_id:
            raise UserError(_('Seleccione al menos una cuenta de gasto o ingreso.'))
        drafts = self.move_ids.filtered(lambda m: m.state == 'draft')
        if not drafts:
            raise UserError(_('No hay documentos en borrador para modificar.'))
        total_lines = total_moves = 0
        for move in drafts:
            updated = move._ktx_mass_update_expense_income(
                expense_account=self.expense_account_id or None,
                income_account=self.income_account_id or None,
            )
            if updated:
                total_lines += updated
                total_moves += 1
        if not total_lines:
            raise UserError(_('No se encontraron líneas de gasto/ingreso para modificar.'))
        return self._notify_and_close(
            _('Se actualizaron %s cuentas en %s facturas.') % (total_lines, total_moves)
        )

    def action_apply_taxes(self):
        drafts = self.move_ids.filtered(lambda m: m.state == 'draft')
        if not drafts:
            raise UserError(_('No hay documentos en borrador para modificar.'))
        if (self.tax_action_type != 'reset'
                and not self.vendor_tax_ids
                and not self.customer_tax_ids):
            raise UserError(_('Seleccione al menos un impuesto para aplicar.'))
        total_lines = total_moves = 0
        for move in drafts:
            taxes = (
                self.vendor_tax_ids if move.move_type in _VENDOR_TYPES
                else self.customer_tax_ids
            )
            updated = move._ktx_mass_update_taxes(
                action_type=self.tax_action_type,
                taxes=taxes,
            )
            if updated:
                total_lines += updated
                total_moves += 1
        if not total_lines:
            raise UserError(_('No se encontraron líneas de factura para modificar.'))
        return self._notify_and_close(
            _('Se actualizaron impuestos en %s líneas de %s facturas.') % (total_lines, total_moves)
        )

    def action_apply_dates(self):
        if not self.new_date and not self.new_invoice_date:
            raise UserError(_('Seleccione al menos una fecha para aplicar.'))
        drafts = self.move_ids.filtered(lambda m: m.state == 'draft')
        if not drafts:
            raise UserError(_('No hay documentos en borrador para modificar.'))
        updated = drafts._ktx_mass_update_dates(
            new_date=self.new_date or None,
            new_invoice_date=self.new_invoice_date or None,
        )
        if not updated:
            raise UserError(_('No se actualizó ninguna fecha.'))
        return self._notify_and_close(
            _('Se actualizó la fecha en %s documento(s).') % updated
        )

    def action_sync_accounting_date(self):
        drafts = self.move_ids.filtered(lambda m: m.state == 'draft')
        if not drafts:
            raise UserError(_('No hay documentos en borrador para modificar.'))
        updated = drafts._ktx_mass_update_sync_accounting_date()
        if not updated:
            raise UserError(_(
                'No hay nada que igualar: ya coinciden, o los documentos no '
                'tienen fecha de factura.'
            ))
        return self._notify_and_close(
            _('Se igualó la fecha contable a la fecha de factura en %s documento(s).') % updated
        )

    def action_apply_cxp_cxc(self):
        if not self.account_payable_id and not self.account_receivable_id:
            raise UserError(_('Seleccione al menos una cuenta CxP o CxC.'))
        drafts = self.move_ids.filtered(lambda m: m.state == 'draft')
        if not drafts:
            raise UserError(_('No hay documentos en borrador para modificar.'))
        total_lines = total_moves = 0
        for move in drafts:
            updated = move._ktx_mass_update_cxp_cxc(
                payable_account=self.account_payable_id or None,
                receivable_account=self.account_receivable_id or None,
            )
            if updated:
                total_lines += updated
                total_moves += 1
        if not total_lines:
            raise UserError(_('No se actualizó ninguna línea CxP/CxC.'))
        partners_updated = 0
        if self.update_partner_account:
            partners_updated = self._update_partner_accounts()
        msg = _('Se actualizaron %s cuentas en %s facturas.') % (total_lines, total_moves)
        if partners_updated:
            msg += _(' Se actualizó la cuenta en %s contacto(s).') % partners_updated
        return self._notify_and_close(msg)

    def action_confirm_moves(self):
        if not self.move_ids:
            raise UserError(_('No hay documentos seleccionados.'))
        drafts = self.move_ids.filtered(lambda m: m.state == 'draft')
        if not drafts:
            raise UserError(_('No hay documentos en borrador para confirmar.'))
        count = 0
        for move in drafts:
            move.action_post()
            count += 1
        return self._notify_and_close(
            _('Se confirmaron %s documento(s).') % count
        )

    def _update_partner_accounts(self):
        updated = set()
        for move in self.move_ids.filtered(lambda m: m.state == 'draft'):
            partner = move.partner_id.commercial_partner_id
            if not partner:
                continue
            if self.account_payable_id and move.move_type in _VENDOR_TYPES:
                if partner.property_account_payable_id != self.account_payable_id:
                    partner.property_account_payable_id = self.account_payable_id
                    updated.add(partner.id)
            if self.account_receivable_id and move.move_type in _CUSTOMER_TYPES:
                if partner.property_account_receivable_id != self.account_receivable_id:
                    partner.property_account_receivable_id = self.account_receivable_id
                    updated.add(partner.id)
        return len(updated)

    def _notify_and_close(self, message):
        self.result_message = message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Proceso completado'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': self._name,
                    'res_id': self.id,
                    'view_mode': 'form',
                    'views': [(False, 'form')],
                    'target': 'new',
                },
            },
        }
