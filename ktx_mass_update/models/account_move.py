# -*- coding: utf-8 -*-
from odoo import models

_VENDOR_TYPES = ('in_invoice', 'in_refund', 'in_receipt')
_CUSTOMER_TYPES = ('out_invoice', 'out_refund', 'out_receipt')
_EXPENSE_TYPES = ('expense', 'expense_direct_cost', 'asset_expense')


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _ktx_mass_update_expense_income(self, expense_account=None, income_account=None):
        total = 0
        for move in self:
            if expense_account:
                lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type in _EXPENSE_TYPES
                ).exists()
                if lines:
                    lines.write({'account_id': expense_account.id})
                    total += len(lines)
            if income_account:
                lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'income'
                ).exists()
                if lines:
                    lines.write({'account_id': income_account.id})
                    total += len(lines)
        return total

    def _ktx_mass_update_taxes(self, action_type, taxes):
        total = 0
        for move in self:
            for line in move.invoice_line_ids:
                if action_type == 'replace':
                    line.tax_ids = taxes
                elif action_type == 'add':
                    line.tax_ids = line.tax_ids | taxes
                elif action_type == 'reset':
                    line.tax_ids = [(5,)]
                total += 1
        return total

    def _ktx_mass_update_dates(self, new_date=None, new_invoice_date=None):
        vals = {}
        if new_date:
            vals['date'] = new_date
        if new_invoice_date:
            vals['invoice_date'] = new_invoice_date
        if not vals or not self:
            return 0
        self.write(vals)
        return len(self)

    def _ktx_mass_update_sync_accounting_date(self):
        """Iguala, factura por factura, la fecha contable (date) a su propia
        fecha de factura (invoice_date). A diferencia de _ktx_mass_update_dates
        (que fija UNA fecha igual para todas), aqui cada documento toma SU
        PROPIA fecha de factura, no una fecha comun."""
        total = 0
        for move in self:
            if move.invoice_date and move.date != move.invoice_date:
                move.date = move.invoice_date
                total += 1
        return total

    def _ktx_mass_update_cxp_cxc(self, payable_account=None, receivable_account=None):
        total = 0
        for move in self:
            if payable_account and move.move_type in _VENDOR_TYPES:
                lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'liability_payable'
                ).exists()
                if lines:
                    lines.write({'account_id': payable_account.id})
                    total += len(lines)
            if receivable_account and move.move_type in _CUSTOMER_TYPES:
                lines = move.line_ids.filtered(
                    lambda l: l.account_id.account_type == 'asset_receivable'
                ).exists()
                if lines:
                    lines.write({'account_id': receivable_account.id})
                    total += len(lines)
        return total
