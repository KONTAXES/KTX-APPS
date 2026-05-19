<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <!-- Acción del reporte PDF -->
    <record id="action_report_ktx_settlement" model="ir.actions.report">
        <field name="name">Liquidación</field>
        <field name="model">ktx.settlement</field>
        <field name="report_type">qweb-pdf</field>
        <field name="report_name">ktx_expense_management.report_ktx_settlement</field>
        <field name="report_file">ktx_expense_management.report_ktx_settlement</field>
        <field name="binding_model_id" ref="model_ktx_settlement"/>
        <field name="binding_type">report</field>
        <field name="paperformat_id" ref="base.paperformat_euro"/>
    </record>

    <!-- Template principal -->
    <template id="report_ktx_settlement">
        <t t-call="web.html_container">
            <t t-foreach="docs" t-as="doc">
                <t t-call="web.external_layout">
                    <div class="page">
                        <t t-set="state_label_map" t-value="{'draft': 'Borrador', 'confirmed': 'Confirmado', 'approved': 'Aprobado', 'posted': 'Publicado', 'paid': 'Pagado', 'rejected': 'Rechazado', 'cancelled': 'Cancelado'}"/>
                        <t t-set="state_color_map" t-value="{'draft': '#6c757d', 'confirmed': '#0d6efd', 'approved': '#fd7e14', 'posted': '#0dcaf0', 'paid': '#198754', 'rejected': '#dc3545', 'cancelled': '#6c757d'}"/>
                        <t t-set="state_bg" t-value="state_color_map.get(doc.state, '#6c757d')"/>
                        <t t-set="state_label" t-value="state_label_map.get(doc.state, doc.state)"/>

                        <!-- Encabezado con cintillo de estado -->
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px;">
                            <div>
                                <div style="font-size:11px; color:#888; margin-bottom:2px; letter-spacing:0.5px;">LIQUIDACIÓN DE GASTOS</div>
                                <h2 style="margin:0; color:#007B7F; font-size:20px;" t-esc="doc.name"/>
                                <h3 t-if="doc.description" style="margin:4px 0 0 0; font-weight:normal; font-size:14px; color:#444;">
                                    <t t-esc="doc.description"/>
                                </h3>
                            </div>
                            <div>
                                <span t-attf-style="background-color:#{state_bg}; color:white; padding:6px 18px; border-radius:4px; font-size:14px; font-weight:bold; display:inline-block;">
                                    <t t-esc="state_label"/>
                                </span>
                            </div>
                        </div>

                        <!-- Info general -->
                        <table style="width:100%; border-collapse:collapse; margin-bottom:16px; font-size:11px;">
                            <tr>
                                <td style="width:18%; font-weight:bold; padding:4px 8px; background:#f0f0f0; border:1px solid #ddd;">Referencia</td>
                                <td style="width:32%; padding:4px 8px; border:1px solid #ddd;" t-esc="doc.name"/>
                                <td style="width:18%; font-weight:bold; padding:4px 8px; background:#f0f0f0; border:1px solid #ddd;">Empleado / Beneficiario</td>
                                <td style="width:32%; padding:4px 8px; border:1px solid #ddd;" t-esc="doc.employee_id.name or '-'"/>
                            </tr>
                            <tr>
                                <td style="font-weight:bold; padding:4px 8px; background:#f0f0f0; border:1px solid #ddd;">Fecha</td>
                                <td style="padding:4px 8px; border:1px solid #ddd;" t-esc="doc.date"/>
                                <td style="font-weight:bold; padding:4px 8px; background:#f0f0f0; border:1px solid #ddd;">Aprobador</td>
                                <td style="padding:4px 8px; border:1px solid #ddd;" t-esc="doc.approver_id.name or '-'"/>
                            </tr>
                            <tr>
                                <td style="font-weight:bold; padding:4px 8px; background:#f0f0f0; border:1px solid #ddd;">Diario</td>
                                <td style="padding:4px 8px; border:1px solid #ddd;" t-esc="doc.journal_id.name or '-'"/>
                                <td style="font-weight:bold; padding:4px 8px; background:#f0f0f0; border:1px solid #ddd;">Moneda</td>
                                <td style="padding:4px 8px; border:1px solid #ddd;" t-esc="doc.currency_id.name or '-'"/>
                            </tr>
                            <tr t-if="doc.account_id">
                                <td style="font-weight:bold; padding:4px 8px; background:#f0f0f0; border:1px solid #ddd;">Cuenta</td>
                                <td colspan="3" style="padding:4px 8px; border:1px solid #ddd;" t-esc="doc.account_id.display_name"/>
                            </tr>
                            <tr t-if="doc.rejection_note">
                                <td style="font-weight:bold; padding:4px 8px; background:#fdecea; border:1px solid #ddd; color:#dc3545;">Motivo de Rechazo</td>
                                <td colspan="3" style="padding:4px 8px; border:1px solid #ddd; color:#dc3545;" t-esc="doc.rejection_note"/>
                            </tr>
                        </table>

                        <!-- Líneas de liquidación -->
                        <div style="margin-bottom:4px; font-weight:bold; font-size:11px; color:#007B7F; border-bottom:2px solid #007B7F; padding-bottom:2px;">
                            LÍNEAS DE LIQUIDACIÓN
                        </div>
                        <table style="width:100%; border-collapse:collapse; font-size:10px; margin-bottom:16px;">
                            <thead>
                                <tr style="background-color:#007B7F; color:white;">
                                    <th style="padding:5px 6px; text-align:left; border:1px solid #005f62;">#</th>
                                    <th style="padding:5px 6px; text-align:left; border:1px solid #005f62;">Póliza</th>
                                    <th style="padding:5px 6px; text-align:left; border:1px solid #005f62;">Referencia</th>
                                    <th style="padding:5px 6px; text-align:left; border:1px solid #005f62;">Proveedor</th>
                                    <th style="padding:5px 6px; text-align:left; border:1px solid #005f62;">Empresa</th>
                                    <th style="padding:5px 6px; text-align:center; border:1px solid #005f62;">Fecha</th>
                                    <th style="padding:5px 6px; text-align:center; border:1px solid #005f62;">Mon.</th>
                                    <th style="padding:5px 6px; text-align:right; border:1px solid #005f62;">Total Doc.</th>
                                    <th style="padding:5px 6px; text-align:right; border:1px solid #005f62;">A Liquidar</th>
                                    <th style="padding:5px 6px; text-align:right; border:1px solid #005f62;">Convertido</th>
                                </tr>
                            </thead>
                            <tbody>
                                <t t-set="line_num" t-value="0"/>
                                <t t-foreach="doc.line_ids" t-as="line">
                                    <t t-set="line_num" t-value="line_num + 1"/>
                                    <tr t-attf-style="background-color:#{ '#f9f9f9' if line_num % 2 == 0 else 'white' };">
                                        <td style="padding:4px 6px; border:1px solid #ddd; text-align:center;" t-esc="line_num"/>
                                        <td style="padding:4px 6px; border:1px solid #ddd;" t-esc="line.move_name or '-'"/>
                                        <td style="padding:4px 6px; border:1px solid #ddd;" t-esc="line.ref or '-'"/>
                                        <td style="padding:4px 6px; border:1px solid #ddd;" t-esc="line.partner_id.name if line.partner_id else '-'"/>
                                        <td style="padding:4px 6px; border:1px solid #ddd;" t-esc="line.move_id.company_id.name if line.move_id and line.move_id.company_id else '-'"/>
                                        <td style="padding:4px 6px; border:1px solid #ddd; text-align:center;" t-esc="line.invoice_date"/>
                                        <td style="padding:4px 6px; border:1px solid #ddd; text-align:center;" t-esc="line.currency_id.name if line.currency_id else ''"/>
                                        <td style="padding:4px 6px; border:1px solid #ddd; text-align:right;" t-esc="line.amount_invoice" t-options='{"widget": "monetary", "display_currency": line.currency_id}'/>
                                        <td style="padding:4px 6px; border:1px solid #ddd; text-align:right;" t-esc="line.amount_to_pay" t-options='{"widget": "monetary", "display_currency": line.currency_id}'/>
                                        <td style="padding:4px 6px; border:1px solid #ddd; text-align:right;" t-esc="line.amount_in_settlement_currency" t-options='{"widget": "monetary", "display_currency": doc.currency_id}'/>
                                    </tr>
                                </t>
                            </tbody>
                            <tfoot>
                                <tr style="background-color:#e0e0e0; font-weight:bold;">
                                    <td colspan="9" style="padding:5px 6px; border:1px solid #bbb; text-align:right;">TOTAL A LIQUIDAR:</td>
                                    <td style="padding:5px 6px; border:1px solid #bbb; text-align:right;" t-esc="doc.amount_total" t-options='{"widget": "monetary", "display_currency": doc.currency_id}'/>
                                </tr>
                            </tfoot>
                        </table>

                        <!-- Pagos -->
                        <div t-if="doc.payment_ids" style="margin-bottom:16px;">
                            <div style="font-weight:bold; font-size:11px; color:#198754; border-bottom:2px solid #198754; padding-bottom:2px; margin-bottom:6px;">
                                PAGOS REGISTRADOS
                            </div>
                            <table style="width:100%; border-collapse:collapse; font-size:10px;">
                                <thead>
                                    <tr style="background:#f0f0f0;">
                                        <th style="padding:4px 6px; border:1px solid #ddd; text-align:left;">Referencia</th>
                                        <th style="padding:4px 6px; border:1px solid #ddd; text-align:center;">Fecha</th>
                                        <th style="padding:4px 6px; border:1px solid #ddd; text-align:left;">Diario</th>
                                        <th style="padding:4px 6px; border:1px solid #ddd; text-align:left;">Memo</th>
                                        <th style="padding:4px 6px; border:1px solid #ddd; text-align:right;">Monto</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <t t-foreach="doc.payment_ids" t-as="pay">
                                        <tr>
                                            <td style="padding:4px 6px; border:1px solid #ddd;" t-esc="pay.name or '-'"/>
                                            <td style="padding:4px 6px; border:1px solid #ddd; text-align:center;" t-esc="pay.date"/>
                                            <td style="padding:4px 6px; border:1px solid #ddd;" t-esc="pay.journal_id.name if pay.journal_id else '-'"/>
                                            <td style="padding:4px 6px; border:1px solid #ddd;" t-esc="pay.memo if pay.memo else '-'"/>
                                            <td style="padding:4px 6px; border:1px solid #ddd; text-align:right; font-weight:bold;" t-esc="pay.amount" t-options='{"widget": "monetary", "display_currency": pay.currency_id}'/>
                                        </tr>
                                    </t>
                                </tbody>
                            </table>
                        </div>

                        <!-- Notas -->
                        <div t-if="doc.notes" style="margin-bottom:16px;">
                            <div style="font-weight:bold; font-size:11px; color:#6c757d; border-bottom:1px solid #6c757d; padding-bottom:2px; margin-bottom:4px;">
                                NOTAS INTERNAS
                            </div>
                            <p style="font-size:10px; margin:0;" t-esc="doc.notes"/>
                        </div>

                        <!-- Firmas -->
                        <table style="width:100%; border-collapse:collapse; margin-top:40px; font-size:10px;">
                            <tr>
                                <td style="width:33%; text-align:center; padding:0 10px;">
                                    <div style="border-top:1px solid #333; padding-top:6px; margin-top:30px;">
                                        <strong>Elaborado por</strong><br/>
                                        <t t-esc="doc.create_uid.name"/>
                                    </div>
                                </td>
                                <td style="width:33%; text-align:center; padding:0 10px;">
                                    <div style="border-top:1px solid #333; padding-top:6px; margin-top:30px;">
                                        <strong>Aprobado por</strong><br/>
                                        <t t-esc="doc.approver_id.name or '-'"/>
                                    </div>
                                </td>
                                <td style="width:33%; text-align:center; padding:0 10px;">
                                    <div style="border-top:1px solid #333; padding-top:6px; margin-top:30px;">
                                        <strong>Beneficiario</strong><br/>
                                        <t t-esc="doc.employee_id.name or '-'"/>
                                    </div>
                                </td>
                            </tr>
                        </table>
                    </div>
                </t>
            </t>
        </t>
    </template>

</odoo>
