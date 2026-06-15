# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ── Régimen IVA ─────────────────────────────────────────────────────────
    ktx_iva_regime = fields.Selection([
        ('pequeno', 'Pequeño Contribuyente'),
        ('general', 'Régimen General del IVA'),
    ], string='Régimen IVA', default='general')

    # ── Régimen ISR (aplicable si iva_regime == 'general') ──────────────────
    ktx_isr_regime = fields.Selection([
        ('opcional',    'Opcional Simplificado s/ Ingresos de Actividades Lucrativas'),
        ('utilidades',  'Sobre Utilidades de Actividades Lucrativas'),
    ], string='Régimen ISR')

    # ── Opciones adicionales (solo si isr_regime == 'utilidades') ───────────
    ktx_apply_iso = fields.Boolean(string='Aplica ISO')
    ktx_apply_inventory = fields.Boolean(string='Reporte de Inventarios')
    ktx_acreditacion = fields.Selection([
        ('mensual',     'Mensual'),
        ('trimestral',  'Trimestral'),
        ('anual',       'Anual'),
    ], string='Forma de Acreditación ISR')

    # ── Cuentas contables por tipo de impuesto ───────────────────────────────
    ktx_iva_sale_account_id = fields.Many2one(
        'account.account', string='Cuenta IVA Ventas',
        domain="[('company_ids', 'in', [id])]",
    )
    ktx_iva_purchase_account_id = fields.Many2one(
        'account.account', string='Cuenta IVA Compras',
        domain="[('company_ids', 'in', [id])]",
    )
    ktx_iva_ret_account_id = fields.Many2one(
        'account.account', string='Cuenta IVA Retenciones',
        domain="[('company_ids', 'in', [id])]",
    )
    ktx_iva_rem_account_id = fields.Many2one(
        'account.account', string='Cuenta IVA Remanente',
        domain="[('company_ids', 'in', [id])]",
    )
    ktx_iva_exencion_account_id = fields.Many2one(
        'account.account', string='Cuenta IVA Exenciones',
        domain="[('company_ids', 'in', [id])]",
        help='Cuenta para registrar IVA conforme constancias de exención recibidas. '
             'La suma de los cargos al debe durante el período se agrega como crédito fiscal.',
    )
    ktx_isr_account_id = fields.Many2one(
        'account.account', string='Cuenta ISR por Pagar',
        domain="[('company_ids', 'in', [id])]",
    )
    ktx_isr_ret_account_id = fields.Many2one(
        'account.account', string='Cuenta Retenciones ISR',
        domain="[('company_ids', 'in', [id])]",
    )
    ktx_isr_trim_account_id = fields.Many2one(
        'account.account', string='Cuenta ISR Trimestral',
        domain="[('company_ids', 'in', [id])]",
        help='Cuenta para registrar el ISR Trimestral (régimen sobre utilidades). '
             'Su saldo determina el ISR acumulado del trimestre anterior.',
    )
    ktx_iso_trim_account_id = fields.Many2one(
        'account.account', string='Cuenta ISO Trimestral',
        domain="[('company_ids', 'in', [id])]",
        help='Cuenta para registrar el ISO Trimestral. Su saldo determina el ISO a acreditar.',
    )

    # ── Impuestos de combustibles (para la sección de compras del IVA) ────────
    ktx_fuel_tax_ids = fields.Many2many(
        'account.tax', 'ktx_company_fuel_tax_rel', 'company_id', 'tax_id',
        string='Impuestos de Combustibles',
        help='Impuestos que identifican las compras de combustibles. Las facturas '
             'con cualquiera de estos impuestos se reportan en la sección de '
             'combustibles de la declaración de IVA.',
    )

    # ── Contador y Representante Legal ──────────────────────────────────────
    ktx_contador_id  = fields.Many2one('res.partner', string='Contador / Perito Contador')
    ktx_contador_reg = fields.Char(string='No. Registro SAT del Contador')
    ktx_rep_legal_id = fields.Many2one('res.partner', string='Representante Legal')

    # ── Categorías SAT por impuesto (para configuración en Ajustes) ─────────
    ktx_satgt_tax_config_ids = fields.One2many(
        'ktx.satgt.tax.config', 'company_id',
        string='Categorías SAT por Impuesto',
    )

    # ── Impuestos adicionales por actividad RTU ──────────────────────────────
    ktx_extra_tax_ids = fields.One2many(
        'ktx.satgt.extra.tax', 'company_id',
        string='Impuestos Adicionales RTU',
    )

    # ── Resumen de impuestos aplicables (HTML computado) ─────────────────────
    ktx_fiscal_summary_html = fields.Html(
        compute='_compute_fiscal_summary_html', sanitize=False,
    )

    @api.depends(
        'ktx_iva_regime', 'ktx_isr_regime',
        'ktx_apply_iso', 'ktx_apply_inventory', 'ktx_acreditacion',
        'ktx_extra_tax_ids',
    )
    def _compute_fiscal_summary_html(self):
        for company in self:
            company.ktx_fiscal_summary_html = company._build_fiscal_summary()

    def _build_fiscal_summary(self):
        regime_labels = dict(self._fields['ktx_iva_regime'].selection)
        isr_labels = dict(self._fields['ktx_isr_regime'].selection)
        iva_label = regime_labels.get(self.ktx_iva_regime, '—')
        rows = [
            ('IVA', iva_label),
        ]
        if self.ktx_iva_regime == 'general':
            isr_label = isr_labels.get(self.ktx_isr_regime, 'No configurado')
            rows.append(('ISR', isr_label))
            if self.ktx_isr_regime == 'utilidades':
                if self.ktx_apply_iso:
                    rows.append(('ISO', 'Aplica — 1% trimestral sobre activos/ingresos'))
                if self.ktx_apply_inventory:
                    rows.append(('Inventarios', 'Reporte anual requerido'))
                if self.ktx_acreditacion:
                    acred_labels = dict(self._fields['ktx_acreditacion'].selection)
                    rows.append(('Acreditación ISR', acred_labels.get(self.ktx_acreditacion, '')))
        for extra in self.ktx_extra_tax_ids:
            rows.append((extra.name, extra.tax_id.name if extra.tax_id else ''))

        html = (
            "<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
            "<thead><tr style='background:#f0f9ff;'>"
            "<th style='padding:6px 10px;text-align:left;border:1px solid #d4e9f3;color:#0369a1;'>Impuesto</th>"
            "<th style='padding:6px 10px;text-align:left;border:1px solid #d4e9f3;color:#0369a1;'>Régimen / Detalle</th>"
            "</tr></thead><tbody>"
        )
        for i, (label, value) in enumerate(rows):
            bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            html += (
                f"<tr style='background:{bg};'>"
                f"<td style='padding:5px 10px;border:1px solid #e2e8f0;font-weight:600;'>{label}</td>"
                f"<td style='padding:5px 10px;border:1px solid #e2e8f0;color:#374151;'>{value}</td>"
                "</tr>"
            )
        html += "</tbody></table>"
        return html


class KtxSatgtExtraTax(models.Model):
    _name = 'ktx.satgt.extra.tax'
    _description = 'Impuesto Adicional RTU por Empresa'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Descripción', required=True)
    tax_id = fields.Many2one('account.tax', string='Impuesto')
    account_id = fields.Many2one('account.account', string='Cuenta Contable')
