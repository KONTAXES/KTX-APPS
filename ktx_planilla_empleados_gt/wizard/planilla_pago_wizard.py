# -*- coding: utf-8 -*-
import base64
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PlanillaPagoWizard(models.TransientModel):
    _name = "ktx.planilla.pago.wizard"
    _description = "Registrar Pago de Planilla"

    planilla_id = fields.Many2one(
        "ktx.planilla",
        string="Planilla",
        required=True,
        readonly=True,
    )
    liquidacion_id = fields.Many2one(
        "ktx.planilla.liquidacion",
        string="Liquidación",
        readonly=True,
    )
    linea_ids = fields.Many2many(
        "ktx.planilla.linea",
        string="Líneas a Pagar",
        required=True,
        domain="[('planilla_id', '=', planilla_id), ('pagada', '=', False)]",
    )
    company_id = fields.Many2one(
        related="planilla_id.company_id", string="Compañía")
    currency_id = fields.Many2one(
        related="planilla_id.currency_id", string="Moneda")
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
    )
    payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Método de Pago",
        domain="[('id', 'in', metodo_disponible_ids)]",
        help="Cheque o transferencia, según los métodos configurados en el diario.",
    )
    metodo_disponible_ids = fields.Many2many(
        "account.payment.method.line",
        compute="_compute_metodos_disponibles",
    )
    payment_date = fields.Date(
        string="Fecha de Pago",
        required=True,
        default=fields.Date.context_today,
    )
    communication = fields.Char(string="Memo")
    payment_reference = fields.Char(
        string="Referencia de Pago",
        help="Número de cheque o de transferencia; aparece en el recibo y en "
             "el extracto bancario.",
    )
    total_a_pagar = fields.Monetary(
        string="Total a Pagar",
        compute="_compute_total",
        currency_field="currency_id",
    )
    generar_recibos = fields.Boolean(
        string="Generar Recibos de Nómina",
        default=True,
        help="Adjunta el recibo de nómina en PDF a cada pago generado.",
    )

    @api.depends("journal_id")
    def _compute_metodos_disponibles(self):
        for wiz in self:
            wiz.metodo_disponible_ids = (
                wiz.journal_id.outbound_payment_method_line_ids
                if wiz.journal_id else False
            )

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        metodos = self.journal_id.outbound_payment_method_line_ids
        self.payment_method_line_id = metodos[:1]

    @api.depends("linea_ids.total_liquido", "linea_ids.monto_pagado")
    def _compute_total(self):
        for wiz in self:
            wiz.total_a_pagar = sum(
                l.total_liquido - l.monto_pagado for l in wiz.linea_ids)

    def action_pagar(self):
        """Crea un pago por empleado: por pagar sueldos contra el banco."""
        self.ensure_one()
        if not self.linea_ids:
            raise UserError(_("No hay líneas para pagar."))
        pagos = self.env["account.payment"]
        for linea in self.linea_ids:
            if linea.pagada:
                continue
            if not linea.move_id or linea.move_id.state != "posted":
                raise UserError(_(
                    "La línea de %s no tiene partida contable publicada.")
                    % linea.employee_id.name)
            partner = linea.employee_id._ktx_pl_get_partner()
            cta_pagar = linea._cuenta(
                "ktx_pl_account_pagar_id", "ktx_pl_account_pagar_sueldos_id",
                _("Por Pagar Sueldos y Salarios"))
            monto = linea.total_liquido - linea.monto_pagado
            if monto <= 0:
                continue
            vals = {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": partner.id,
                "journal_id": self.journal_id.id,
                "date": self.payment_date,
                "amount": monto,
                "currency_id": self.currency_id.id,
                "memo": self.communication or "%s — %s" % (
                    linea.planilla_id.name, linea.employee_id.name),
                "company_id": self.company_id.id,
                "destination_account_id": cta_pagar.id,
                "ktx_pl_linea_id": linea.id,
            }
            if self.liquidacion_id:
                vals["ktx_pl_liquidacion_id"] = self.liquidacion_id.id
            if self.payment_reference:
                vals["payment_reference"] = self.payment_reference
            if self.payment_method_line_id:
                vals["payment_method_line_id"] = self.payment_method_line_id.id
            pago = self.env["account.payment"].create(vals)
            pago.action_post()
            self._conciliar(pago, linea, cta_pagar)
            if self.generar_recibos:
                self._adjuntar_recibo(pago, linea)
            pagos |= pago

        self.linea_ids.planilla_id._actualizar_estado_pago()
        if self.liquidacion_id:
            self.liquidacion_id._actualizar_estado_pago()
        elif self.planilla_id.liquidacion_id:
            self.planilla_id.liquidacion_id._actualizar_estado_pago()

        self.planilla_id.message_post(body=_(
            "%(n)s pago(s) registrado(s) por un total de %(m).2f.",
            n=len(pagos), m=sum(pagos.mapped("amount"))))
        return {
            "type": "ir.actions.act_window",
            "name": _("Pagos de Planilla"),
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", pagos.ids)],
        }

    def _conciliar(self, pago, linea, cuenta):
        """Concilia la línea por pagar de la partida de planilla con el pago."""
        try:
            lineas_planilla = linea.move_id.line_ids.filtered(
                lambda l: l.account_id == cuenta and not l.reconciled)
            lineas_pago = pago.move_id.line_ids.filtered(
                lambda l: l.account_id == cuenta and not l.reconciled)
            por_conciliar = lineas_planilla | lineas_pago
            if por_conciliar:
                por_conciliar.reconcile()
        except Exception as e:
            _logger.warning(
                "No se pudo conciliar el pago de planilla %s: %s",
                pago.name, e)

    def _adjuntar_recibo(self, pago, linea):
        """Genera el recibo de nómina en PDF y lo adjunta al pago."""
        try:
            pdf, _mime = self.env["ir.actions.report"]._render_qweb_pdf(
                "ktx_planilla_empleados_gt.action_report_recibo_nomina",
                linea.ids)
            nombre = _("Recibo de Nomina %(pl)s %(emp)s.pdf") % {
                "pl": linea.planilla_id.name.replace("/", "-"),
                "emp": linea.employee_id.name,
            }
            adjunto = self.env["ir.attachment"].create({
                "name": nombre,
                "type": "binary",
                "datas": base64.b64encode(pdf),
                "res_model": "account.payment",
                "res_id": pago.id,
                "mimetype": "application/pdf",
            })
            pago.message_post(
                body=_("Recibo de nómina adjuntado."),
                attachment_ids=adjunto.ids)
        except Exception as e:
            _logger.warning("No se pudo generar el recibo del pago %s: %s",
                            pago.name, e)
