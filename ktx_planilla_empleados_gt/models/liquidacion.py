# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ktx_check_print.utils.amount_in_words import amount_to_words_es

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre",
    11: "noviembre", 12: "diciembre",
}


class PlanillaLiquidacion(models.Model):
    _name = "ktx.planilla.liquidacion"
    _description = "Liquidación de Prestaciones Laborales GT"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "fecha_fin desc, name desc"
    _check_company_auto = True

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        default="/",
        index=True,
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Empleado",
        required=True,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", store=True)
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("calculated", "Calculada"),
            ("confirmed", "Confirmada"),
            ("posted", "Contabilizada"),
            ("paid", "Pagada"),
            ("cancel", "Cancelada"),
        ],
        string="Estado",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Relación laboral
    # ------------------------------------------------------------------
    fecha_inicio = fields.Date(
        string="Inicio Relación Laboral",
        compute="_compute_fecha_inicio",
        store=True,
        readonly=False,
        required=True,
        tracking=True,
    )
    fecha_fin = fields.Date(
        string="Fin Relación Laboral",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    dias_relacion = fields.Integer(
        string="Días en la Empresa",
        compute="_compute_dias_relacion",
        store=True,
    )
    tipo_finalizacion = fields.Selection(
        selection=[
            ("despido_injustificado", "Despido Injustificado"),
            ("despido_justificado", "Despido Justificado"),
            ("renuncia", "Renuncia"),
            ("mutuo_acuerdo", "Mutuo Acuerdo"),
            ("otro", "Otro"),
        ],
        string="Motivo de Finalización",
        required=True,
        default="renuncia",
        tracking=True,
        help="Despido injustificado: la indemnización es obligatoria (art. 82 "
             "Código de Trabajo). Despido justificado (art. 77) y renuncia: "
             "no hay indemnización legal, salvo que el empleado tenga "
             "activadas las prestaciones universales.",
    )
    justificacion = fields.Text(
        string="Justificación / Causal",
        help="Detalle de la causal de despido (art. 77 CdT), texto de la "
             "renuncia o del acuerdo. Se conserva como respaldo documental.",
    )
    salario_promedio = fields.Monetary(
        string="Salario Promedio (6 meses)",
        compute="_compute_salario_promedio",
        store=True,
        readonly=False,
        tracking=True,
        help="Promedio de los salarios ordinarios devengados en los últimos "
             "6 meses (art. 82 CdT). Base de cálculo de todas las prestaciones. "
             "Editable si se necesita ajustar.",
    )
    vacaciones_gozadas = fields.Float(
        string="Días de Vacaciones Gozadas",
        help="Días de vacaciones ya gozados que se restan del cálculo "
             "(las vacaciones prescriben — solo se liquidan las de los "
             "últimos 5 años, art. 136 CdT).",
    )

    # ------------------------------------------------------------------
    # Prestaciones a incluir
    # ------------------------------------------------------------------
    incluir_salario = fields.Boolean(
        string="Incluir Salario Pendiente",
        help="Incluye los días de salario del último período aún no pagado.")
    salario_pendiente_desde = fields.Date(
        string="Salario Pendiente Desde",
        help="Fecha siguiente al último día de salario ya pagado.")
    incluir_indemnizacion = fields.Boolean(
        string="Incluir Indemnización",
        compute="_compute_incluir_indemnizacion",
        store=True,
        readonly=False,
        tracking=True,
    )
    indemnizacion_obligatoria = fields.Boolean(
        compute="_compute_incluir_indemnizacion",
        store=True,
        string="Indemnización Obligatoria",
    )
    incluir_bono14 = fields.Boolean(string="Incluir Bono 14", default=True)
    incluir_aguinaldo = fields.Boolean(string="Incluir Aguinaldo", default=True)
    incluir_vacaciones = fields.Boolean(
        string="Incluir Vacaciones no Gozadas", default=True)

    # ------------------------------------------------------------------
    # Cálculos (editables tras calcular, para ajustes finos)
    # ------------------------------------------------------------------
    salario_dias = fields.Integer(string="Salario: Días", readonly=True)
    salario_monto = fields.Monetary(string="Salario Pendiente")
    indemnizacion_dias = fields.Integer(string="Indemnización: Días", readonly=True)
    indemnizacion_monto = fields.Monetary(string="Indemnización")
    bono14_dias = fields.Integer(string="Bono 14: Días", readonly=True)
    bono14_monto = fields.Monetary(string="Bono 14 Proporcional")
    aguinaldo_dias = fields.Integer(string="Aguinaldo: Días", readonly=True)
    aguinaldo_monto = fields.Monetary(string="Aguinaldo Proporcional")
    vacaciones_dias = fields.Float(string="Vacaciones: Días", readonly=True)
    vacaciones_monto = fields.Monetary(string="Vacaciones no Gozadas")
    total = fields.Monetary(
        string="Total a Liquidar",
        compute="_compute_total",
        store=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Plan de pagos y vínculos
    # ------------------------------------------------------------------
    pago_ids = fields.One2many(
        "ktx.planilla.liquidacion.pago",
        "liquidacion_id",
        string="Plan de Pagos",
        help="Si la liquidación se pagará fraccionada, detalle aquí las fechas "
             "y montos; se enumeran en el finiquito.",
    )
    planilla_id = fields.Many2one(
        "ktx.planilla", string="Planilla de Liquidación",
        copy=False, readonly=True)
    linea_id = fields.Many2one(
        "ktx.planilla.linea", string="Línea de Planilla",
        compute="_compute_linea_id")
    payment_ids = fields.One2many(
        "account.payment", "ktx_pl_liquidacion_id",
        string="Pagos", copy=False)
    notas = fields.Text(string="Notas")

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends("employee_id")
    def _compute_fecha_inicio(self):
        for liq in self:
            if liq.employee_id and not liq.fecha_inicio:
                liq.fecha_inicio = liq.employee_id.sudo().ktx_pl_fecha_inicio

    @api.depends("fecha_inicio", "fecha_fin")
    def _compute_dias_relacion(self):
        for liq in self:
            if liq.fecha_inicio and liq.fecha_fin:
                liq.dias_relacion = (liq.fecha_fin - liq.fecha_inicio).days + 1
            else:
                liq.dias_relacion = 0

    @api.depends("employee_id", "fecha_fin")
    def _compute_salario_promedio(self):
        for liq in self:
            if liq.employee_id and not liq.salario_promedio:
                liq.salario_promedio = liq.employee_id.sudo(
                )._ktx_pl_salario_promedio(fecha_hasta=liq.fecha_fin, meses=6)

    @api.depends("tipo_finalizacion", "employee_id")
    def _compute_incluir_indemnizacion(self):
        for liq in self:
            universal = liq.employee_id.sudo().ktx_pl_prestaciones_universales
            obligatoria = (
                liq.tipo_finalizacion == "despido_injustificado" or universal)
            liq.indemnizacion_obligatoria = obligatoria
            if obligatoria:
                liq.incluir_indemnizacion = True

    @api.depends("salario_monto", "indemnizacion_monto", "bono14_monto",
                 "aguinaldo_monto", "vacaciones_monto")
    def _compute_total(self):
        for liq in self:
            liq.total = (liq.salario_monto + liq.indemnizacion_monto
                         + liq.bono14_monto + liq.aguinaldo_monto
                         + liq.vacaciones_monto)

    def _compute_linea_id(self):
        for liq in self:
            liq.linea_id = liq.planilla_id.line_ids[:1]

    @api.constrains("fecha_inicio", "fecha_fin")
    def _check_fechas(self):
        for liq in self:
            if liq.fecha_inicio and liq.fecha_fin and \
                    liq.fecha_fin < liq.fecha_inicio:
                raise UserError(_(
                    "La fecha de fin de la relación laboral debe ser "
                    "posterior a la de inicio."))

    # ==================================================================
    # Ciclo de vida
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "ktx.planilla.liquidacion") or "/"
        return super().create(vals_list)

    def unlink(self):
        if any(liq.state not in ("draft", "cancel") for liq in self):
            raise UserError(_(
                "Solo se pueden eliminar liquidaciones en borrador o canceladas."))
        return super().unlink()

    # ==================================================================
    # Cálculo de prestaciones
    # ==================================================================
    def action_calcular(self):
        """Calcula cada prestación según el Código de Trabajo y decretos.

        Indemnización (art. 82 CdT): un mes de salario por año de servicios
        continuos; base = salario promedio de 6 meses + 1/12 de aguinaldo +
        1/12 de Bono 14 (doctrina y jurisprudencia laboral).
        Bono 14 (Decreto 42-92): proporcional desde el 1-jul anterior.
        Aguinaldo (Decreto 76-78): proporcional desde el 1-dic anterior.
        Vacaciones (arts. 130-134 CdT): 15 días hábiles por año, las no
        gozadas se compensan en dinero al terminar la relación (art. 133).
        """
        for liq in self:
            if liq.state not in ("draft", "calculated"):
                raise UserError(_("Solo se calculan liquidaciones en borrador."))
            if not (liq.fecha_inicio and liq.fecha_fin):
                raise UserError(_("Indique las fechas de inicio y fin de la "
                                  "relación laboral."))
            promedio = liq.salario_promedio or liq.employee_id.sudo(
            )._ktx_pl_salario_promedio(fecha_hasta=liq.fecha_fin, meses=6)
            if not promedio:
                raise UserError(_(
                    "No se pudo determinar el salario promedio. Indíquelo "
                    "manualmente o configure el sueldo base del empleado."))
            liq.salario_promedio = promedio
            fin = liq.fecha_fin
            inicio = liq.fecha_inicio

            # --- Salario pendiente ---
            if liq.incluir_salario and liq.salario_pendiente_desde:
                dias = max((fin - liq.salario_pendiente_desde).days + 1, 0)
                liq.salario_dias = dias
                liq.salario_monto = round(promedio / 30.0 * dias, 2)
            else:
                liq.salario_dias = 0
                liq.salario_monto = 0.0

            # --- Indemnización ---
            if liq.incluir_indemnizacion:
                dias = liq.dias_relacion
                base = promedio + (promedio / 12.0) * 2  # + aguinaldo y bono14
                liq.indemnizacion_dias = dias
                liq.indemnizacion_monto = round(base * dias / 365.0, 2)
            else:
                liq.indemnizacion_dias = 0
                liq.indemnizacion_monto = 0.0

            # --- Bono 14: período 1-jul → 30-jun ---
            if liq.incluir_bono14:
                anio = fin.year if fin >= date(fin.year, 7, 1) else fin.year - 1
                inicio_b14 = max(date(anio, 7, 1), inicio)
                dias = max((fin - inicio_b14).days + 1, 0)
                liq.bono14_dias = dias
                liq.bono14_monto = round(promedio / 365.0 * dias, 2)
            else:
                liq.bono14_dias = 0
                liq.bono14_monto = 0.0

            # --- Aguinaldo: período 1-dic → 30-nov ---
            if liq.incluir_aguinaldo:
                anio = fin.year if fin >= date(fin.year, 12, 1) else fin.year - 1
                inicio_ag = max(date(anio, 12, 1), inicio)
                dias = max((fin - inicio_ag).days + 1, 0)
                liq.aguinaldo_dias = dias
                liq.aguinaldo_monto = round(promedio / 365.0 * dias, 2)
            else:
                liq.aguinaldo_dias = 0
                liq.aguinaldo_monto = 0.0

            # --- Vacaciones no gozadas ---
            if liq.incluir_vacaciones:
                dias_derecho = liq.dias_relacion * 15.0 / 365.0
                dias = max(dias_derecho - liq.vacaciones_gozadas, 0.0)
                liq.vacaciones_dias = round(dias, 2)
                liq.vacaciones_monto = round(promedio / 30.0 * dias, 2)
            else:
                liq.vacaciones_dias = 0.0
                liq.vacaciones_monto = 0.0

            liq.state = "calculated"
        return True

    def action_confirmar(self):
        """Confirma la liquidación y genera la planilla tipo liquidación."""
        for liq in self:
            if liq.state != "calculated":
                raise UserError(_("Primero calcule la liquidación."))
            if liq.tipo_finalizacion == "despido_injustificado" and \
                    not liq.incluir_indemnizacion:
                raise UserError(_(
                    "En despido injustificado la indemnización es obligatoria "
                    "(art. 82 del Código de Trabajo)."))
            if liq.tipo_finalizacion in ("despido_justificado", "otro") and \
                    not liq.justificacion:
                raise UserError(_(
                    "Documente la justificación / causal de la finalización "
                    "(art. 77 del Código de Trabajo)."))
            planilla = self.env["ktx.planilla"].create({
                "tipo": "liquidacion",
                "periodicidad": "evento",
                "date_from": liq.fecha_inicio,
                "date_to": liq.fecha_fin,
                "company_id": liq.company_id.id,
                "liquidacion_id": liq.id,
                "notas": _("Liquidación de prestaciones laborales %s")
                % liq.name,
            })
            prestaciones = (liq.indemnizacion_monto + liq.bono14_monto
                            + liq.aguinaldo_monto + liq.vacaciones_monto)
            self.env["ktx.planilla.linea"].create({
                "planilla_id": planilla.id,
                "employee_id": liq.employee_id.id,
                "puesto": liq.employee_id.job_title
                or liq.employee_id.job_id.name or "",
                "secuencia": 1,
                "sueldo_ordinario": liq.salario_monto,
                "otros_ingresos": prestaciones,
                "notas": _("Liquidación %s") % liq.name,
            })
            planilla.state = "calculated"
            liq.planilla_id = planilla
            liq.state = "confirmed"
            liq.message_post(body=_(
                "Liquidación confirmada. Planilla %s generada.") % planilla.name)
        return True

    def action_contabilizar(self):
        for liq in self:
            if liq.state != "confirmed":
                raise UserError(_("Primero confirme la liquidación."))
            liq.planilla_id.action_contabilizar()
            liq.state = "posted"
        return True

    def action_registrar_pago(self):
        self.ensure_one()
        if self.state not in ("posted", "paid"):
            raise UserError(_("Primero contabilice la liquidación."))
        accion = self.planilla_id.action_registrar_pagos()
        wizard = self.env["ktx.planilla.pago.wizard"].browse(accion["res_id"])
        wizard.liquidacion_id = self.id
        return accion

    def action_cancelar(self):
        for liq in self:
            if liq.payment_ids.filtered(
                    lambda p: p.state not in ("draft", "canceled")):
                raise UserError(_(
                    "La liquidación tiene pagos registrados; anúlelos primero."))
            if liq.planilla_id:
                liq.planilla_id.action_cancelar()
            liq.state = "cancel"
        return True

    def action_regresar_borrador(self):
        for liq in self:
            if liq.state not in ("calculated", "cancel"):
                raise UserError(_(
                    "Solo se puede regresar a borrador desde Calculada o "
                    "Cancelada."))
            liq.state = "draft"
        return True

    def _actualizar_estado_pago(self):
        for liq in self:
            if liq.state == "posted" and liq.linea_id and liq.linea_id.pagada:
                liq.state = "paid"

    def action_imprimir_finiquito(self):
        self.ensure_one()
        return self.env.ref(
            "ktx_planilla_empleados_gt.action_report_liquidacion"
        ).report_action(self)

    def action_enviar_recibo(self):
        self.ensure_one()
        wizard = self.env["ktx.planilla.enviar.recibo.wizard"].create({
            "liquidacion_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Enviar Finiquito — %s") % self.employee_id.name,
            "res_model": "ktx.planilla.enviar.recibo.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    # ==================================================================
    # Utilidades para el finiquito
    # ==================================================================
    def _fecha_texto(self, fecha=None):
        self.ensure_one()
        f = fecha or fields.Date.context_today(self)
        return _("%(dia)s de %(mes)s de %(anio)s") % {
            "dia": f.day, "mes": MESES_ES[f.month], "anio": f.year}

    def _total_letras(self):
        self.ensure_one()
        return amount_to_words_es(self.total)

    def _tipo_finalizacion_texto(self):
        self.ensure_one()
        return dict(self._fields["tipo_finalizacion"].selection).get(
            self.tipo_finalizacion, "")

    def _filas_prestaciones(self):
        """Filas para la tabla del finiquito: (No., prestación, base legal,
        días aplicables, monto)."""
        self.ensure_one()
        filas = []
        if self.salario_monto:
            filas.append((_("Salario Pendiente"),
                          _("Arts. 88-97 Código de Trabajo"),
                          self.salario_dias, self.salario_monto))
        if self.incluir_bono14:
            filas.append((_("Bono 14"), _("Decreto 42-92"),
                          self.bono14_dias, self.bono14_monto))
        if self.incluir_aguinaldo:
            filas.append((_("Aguinaldo"), _("Decreto 76-78"),
                          self.aguinaldo_dias, self.aguinaldo_monto))
        if self.incluir_vacaciones:
            filas.append((_("Vacaciones"),
                          _("Arts. 130-134 Código de Trabajo"),
                          self.vacaciones_dias, self.vacaciones_monto))
        if self.incluir_indemnizacion:
            filas.append((_("Indemnización"),
                          _("Art. 82 Código de Trabajo"),
                          self.indemnizacion_dias, self.indemnizacion_monto))
        return [(i + 1,) + f for i, f in enumerate(filas)]


class PlanillaLiquidacionPago(models.Model):
    _name = "ktx.planilla.liquidacion.pago"
    _description = "Plan de Pago de Liquidación"
    _order = "fecha, id"

    liquidacion_id = fields.Many2one(
        "ktx.planilla.liquidacion",
        string="Liquidación",
        required=True,
        ondelete="cascade",
    )
    fecha = fields.Date(string="Fecha Programada", required=True)
    monto = fields.Monetary(string="Monto", required=True)
    currency_id = fields.Many2one(
        related="liquidacion_id.currency_id", store=True)
    descripcion = fields.Char(
        string="Descripción",
        help="Ej.: Primer pago, a efectuarse a finales de febrero.")
