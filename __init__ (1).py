<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <record id="view_ktx_settlement_form" model="ir.ui.view">
        <field name="name">ktx.settlement.form</field>
        <field name="model">ktx.settlement</field>
        <field name="arch" type="xml">
            <form string="Liquidación">
                <header>
                    <button name="action_confirm"
                        string="Confirmar"
                        type="object"
                        class="btn-primary"
                        invisible="state != 'draft'"/>
                    <button name="action_approve"
                        string="Aprobar"
                        type="object"
                        class="btn-primary"
                        invisible="state != 'confirmed'"/>
                    <button name="action_reject"
                        string="Rechazar"
                        type="object"
                        class="btn-danger"
                        invisible="state not in ('confirmed', 'approved')"/>
                    <button name="action_post"
                        string="Publicar"
                        type="object"
                        class="btn-primary"
                        invisible="state != 'approved'"/>
                    <button name="action_open_payment_wizard"
                        string="Registrar Pago"
                        type="object"
                        class="btn-primary"
                        invisible="state not in ('posted', 'in_payment')"/>
                    <button name="action_cancel_move"
                        string="Cancelar Asiento"
                        type="object"
                        invisible="state != 'posted'"
                        confirm="¿Cancelar y eliminar el asiento contable? Volverá a estado Aprobado."/>
                    <button name="action_cancel"
                        string="Cancelar"
                        type="object"
                        invisible="state not in ('draft', 'rejected')"/>
                    <button name="action_reset_draft"
                        string="Restablecer a Borrador"
                        type="object"
                        invisible="state not in ('rejected', 'cancelled')"/>
                    <button name="action_view_journal_entry"
                        string="Ver Asiento"
                        type="object"
                        invisible="not move_id"/>
                    <button name="action_view_payment"
                        string="Ver Pagos"
                        type="object"
                        invisible="not payment_ids"/>
                    <button name="action_download_excel"
                        string="Descargar Excel"
                        type="object"
                        class="btn-secondary"
                        invisible="state == 'draft'"/>
                    <field name="state" widget="statusbar"
                        statusbar_visible="draft,confirmed,approved,posted,in_payment,paid"/>
                </header>

                <sheet>
                    <div class="position-absolute" style="top:0;right:0;z-index:10;padding:6px 18px;background:#198754;color:white;font-weight:700;font-size:13px;transform:rotate(45deg) translate(30px,-15px);transform-origin:center;box-shadow:0 2px 6px rgba(0,0,0,0.15)"
                        invisible="state != 'paid'">PAGADA</div>
                    <div class="position-absolute" style="top:0;right:0;z-index:10;padding:6px 18px;background:#ffc107;color:#212529;font-weight:700;font-size:13px;transform:rotate(45deg) translate(30px,-15px);transform-origin:center;box-shadow:0 2px 6px rgba(0,0,0,0.15)"
                        invisible="state != 'in_payment'">EN PROCESO</div>
                    <div class="position-absolute" style="top:0;right:0;z-index:10;padding:6px 18px;background:#0d6efd;color:white;font-weight:700;font-size:13px;transform:rotate(45deg) translate(30px,-15px);transform-origin:center;box-shadow:0 2px 6px rgba(0,0,0,0.15)"
                        invisible="state != 'posted'">PUBLICADA</div>
                    <div class="oe_title">
                        <h1>
                            <field name="name"
                                readonly="state != 'draft'"
                                placeholder="LIQ/YYYY/00001"/>
                        </h1>
                        <h3>
                            <field name="description"
                                readonly="state != 'draft'"
                                placeholder="Descripción (opcional)"/>
                        </h3>
                    </div>

                    <field name="has_cross_company_lines" invisible="1"/>

                    <field name="over_limit" invisible="1"/>

                    <div class="alert alert-warning" role="alert"
                        invisible="not over_limit">
                        ⚠️ El monto supera el límite de gasto configurado para este empleado.
                    </div>

                    <div class="alert alert-danger" role="alert"
                        invisible="state != 'rejected'">
                        <strong>Motivo de Rechazo: </strong>
                        <field name="rejection_note" readonly="1" nolabel="1"/>
                    </div>

                    <group>
                        <group string="Información General">
                            <field name="date" readonly="state != 'draft'"/>
                            <field name="journal_id" readonly="state != 'draft'" required="1"/>
                            <field name="account_id" readonly="state != 'draft'" required="1"/>
                            <field name="company_id"
                                readonly="state != 'draft'"
                                groups="base.group_multi_company"/>
                        </group>
                        <group string="Responsables y Moneda">
                            <field name="employee_id" string="Empleado / Beneficiario"
                                readonly="state != 'draft'"/>
                            <field name="approver_id" readonly="state != 'draft'"/>
                            <field name="company_currency_id" invisible="1"/>
                            <field name="currency_id" readonly="state != 'draft'"/>
                            <field name="rate_date"
                                readonly="state != 'draft'"/>
                            <field name="exchange_rate"
                                readonly="state != 'draft'"/>
                        </group>
                    </group>

                    <notebook>
                        <page string="Líneas de Liquidación" name="lines">
                            <button name="action_open_staging_selector"
                                string="Agregar Gastos..."
                                type="object"
                                class="btn-secondary mb-2"
                                invisible="state not in ('draft', 'confirmed')"/>
                            <field name="line_ids"
                                readonly="state not in ('draft', 'confirmed')">
                                <list string="Líneas" create="0">
                                    <field name="sequence" widget="handle"/>
                                    <field name="move_name" string="Número Póliza" readonly="1"/>
                                    <field name="ref" string="Referencia / Serie" readonly="1"/>
                                    <field name="partner_id" string="Proveedor" readonly="1"/>
                                    <field name="move_company_id" string="Empresa" readonly="1" optional="show"/>
                                    <field name="invoice_date" string="Fecha" readonly="1"/>
                                    <field name="currency_id" readonly="1" groups="base.group_multi_currency"/>
                                    <field name="amount_invoice" string="Total Doc." readonly="1"/>
                                    <field name="amount_to_pay" string="Monto a Liquidar"
                                           sum="Total a Liquidar"/>
                                    <field name="settlement_currency_id" column_invisible="1"/>
                                    <field name="amount_in_settlement_currency"
                                        string="Monto Convertido"
                                        readonly="1"
                                        sum="Total Convertido"/>
                                    <field name="analytic_account_id"
                                        string="Centro de Costo"
                                        optional="hide"/>
                                </list>
                            </field>
                        </page>

                        <page string="Notas Internas" name="notes">
                            <field name="notes"
                                placeholder="Agregar notas internas..."
                                readonly="state not in ('draft', 'confirmed')"/>
                        </page>
                        <page string="Intercompañía" name="intercompany"
                            invisible="not has_cross_company_lines">
                            <div class="alert alert-info" role="alert">
                                <strong>Asignación Multiempresa activa.</strong>
                                Configure las cuentas intercompañía para esta liquidación.
                                <br/>
                                <em>Recuerde activar las empresas involucradas en su perfil de usuario
                                (ícono de empresa en la barra superior) para que los asientos
                                se puedan crear en cada compañía.</em>
                            </div>
                            <group string="Esta empresa">
                                <field name="intercompany_receivable_id"
                                    string="Cuenta por Cobrar Intercompañía"
                                    readonly="state not in ('draft', 'confirmed', 'approved')"
                                    required="has_cross_company_lines"/>
                            </group>
                            <group string="Empresas del Gasto">
                                <field name="intercompany_account_ids" nolabel="1"
                                    readonly="state not in ('draft', 'confirmed', 'approved')">
                                    <list editable="bottom">
                                        <field name="company_id" string="Empresa del Gasto" width="200px"/>
                                        <field name="account_id" string="Cuenta por Pagar Intercompañía" width="400px"/>
                                    </list>
                                </field>
                            </group>
                        </page>
                        <page string="Diferencial Cambiario" name="forex"
                            invisible="not forex_note">
                            <field name="forex_note" readonly="1" nolabel="1"/>
                        </page>
                    </notebook>

                    <group string="Pagos Aplicados" invisible="not payment_ids">
                        <field name="payment_ids" nolabel="1" readonly="1">
                            <list create="0" delete="0">
                                <field name="date" string="Fecha"/>
                                <field name="journal_id" string="Diario"/>
                                <field name="amount" string="Monto" sum="Total Pagado"/>
                                <field name="currency_id" string="Moneda" groups="base.group_multi_currency"/>
                                <field name="payment_reference" string="Referencia"/>
                                <field name="state" string="Estado" widget="badge"/>
                            </list>
                        </field>
                    </group>

                    <group class="oe_subtotal_footer">
                        <field name="amount_total"
                            widget="monetary"
                            options="{'currency_field': 'currency_id'}"/>
                        <field name="amount_paid"
                            widget="monetary"
                            options="{'currency_field': 'currency_id'}"
                            invisible="not payment_ids"/>
                        <field name="amount_residual"
                            widget="monetary"
                            options="{'currency_field': 'currency_id'}"
                            invisible="not payment_ids"/>
                    </group>
                </sheet>

                <chatter/>
            </form>
        </field>
    </record>

    <record id="view_ktx_settlement_list" model="ir.ui.view">
        <field name="name">ktx.settlement.list</field>
        <field name="model">ktx.settlement</field>
        <field name="arch" type="xml">
            <list string="Liquidaciones"
                decoration-muted="state == 'draft'"
                decoration-warning="state == 'confirmed'"
                decoration-info="state == 'approved'"
                decoration-primary="state == 'posted'"
                decoration-success="state in ('in_payment', 'paid')"
                decoration-danger="state in ('rejected', 'cancelled')">
                <field name="name" string="Referencia"/>
                <field name="description" string="Descripción"/>
                <field name="date" string="Fecha"/>
                <field name="employee_id" string="Empleado"/>
                <field name="approver_id" string="Aprobador"/>
                <field name="currency_id" string="Moneda" groups="base.group_multi_currency"/>
                <field name="amount_total" string="Total" sum="Total General"/>
                <field name="state_color" column_invisible="1"/>
                <field name="state" string="Estado" widget="badge" options="{'color_field': 'state_color'}"/>
                <field name="company_id" groups="base.group_multi_company"/>
            </list>
        </field>
    </record>

    <record id="view_ktx_settlement_search" model="ir.ui.view">
        <field name="name">ktx.settlement.search</field>
        <field name="model">ktx.settlement</field>
        <field name="arch" type="xml">
            <search string="Buscar Liquidaciones">
                <field name="name" string="Referencia"/>
                <field name="employee_id" string="Empleado"/>
                <field name="approver_id" string="Aprobador"/>
                <filter name="filter_draft" string="Borrador" domain="[('state','=','draft')]"/>
                <filter name="filter_confirmed" string="Por Autorizar" domain="[('state','=','confirmed')]"/>
                <filter name="filter_approved" string="Aprobadas" domain="[('state','=','approved')]"/>
                <filter name="filter_posted" string="Publicadas" domain="[('state','=','posted')]"/>
                <filter name="filter_in_payment" string="En Proceso de Pago" domain="[('state','=','in_payment')]"/>
                <filter name="filter_paid" string="Pagadas" domain="[('state','=','paid')]"/>
                <filter name="filter_rejected" string="Rechazadas" domain="[('state','=','rejected')]"/>
            </search>
        </field>
    </record>

    <record id="action_ktx_settlement" model="ir.actions.act_window">
        <field name="name">Liquidaciones</field>
        <field name="res_model">ktx.settlement</field>
        <field name="view_mode">list,form</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">Crea tu primera liquidación.</p>
            <p>Agrega facturas o asientos desde Contabilidad usando la acción
               "Agregar a Liquidación", luego crea la liquidación aquí.</p>
        </field>
    </record>

    <!-- Vista lista sin botón Nuevo para Autorizaciones (prioridad baja para no interferir con la vista principal) -->
    <record id="view_ktx_settlement_approvals_list" model="ir.ui.view">
        <field name="name">ktx.settlement.approvals.list</field>
        <field name="model">ktx.settlement</field>
        <field name="priority">100</field>
        <field name="arch" type="xml">
            <list string="Autorizaciones" create="0"
                decoration-muted="state == 'draft'"
                decoration-warning="state == 'confirmed'"
                decoration-info="state == 'approved'"
                decoration-primary="state == 'posted'"
                decoration-success="state in ('in_payment', 'paid')"
                decoration-danger="state in ('rejected', 'cancelled')">
                <field name="name" string="Referencia"/>
                <field name="description" string="Descripción"/>
                <field name="date" string="Fecha"/>
                <field name="employee_id" string="Empleado"/>
                <field name="approver_id" string="Aprobador"/>
                <field name="currency_id" string="Moneda" groups="base.group_multi_currency"/>
                <field name="amount_total" string="Total" sum="Total General"/>
                <field name="state_color" column_invisible="1"/>
                <field name="state" string="Estado" widget="badge" options="{'color_field': 'state_color'}"/>
                <field name="company_id" groups="base.group_multi_company"/>
            </list>
        </field>
    </record>

    <record id="action_ktx_settlement_approvals" model="ir.actions.act_window">
        <field name="name">Autorizaciones</field>
        <field name="res_model">ktx.settlement</field>
        <field name="view_mode">list,form</field>
        <field name="views">[(ref('view_ktx_settlement_approvals_list'), 'list'), (False, 'form')]</field>
        <field name="domain">[('state', '=', 'confirmed')]</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                No hay liquidaciones pendientes de autorización.
            </p>
        </field>
    </record>

</odoo>
