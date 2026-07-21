# -*- coding: utf-8 -*-
import calendar
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ktx_check_print.utils.amount_in_words import amount_to_words_es

from .asistencia import TIPOS_DESCUENTO

_logger = logging.getLogger(__name__)

PERIODOS_POR_ANIO = {
    "mensual": 12.0,
    "quincenal": 24.0,
    "semanal": 52.0,
    "diario": 365.0,
    "evento": 12.0,
}

MESES_SELECTION = [
    ("01", "Enero"), ("02", "Febrero"), ("03", "Marzo"), ("04", "Abril"),
    ("05", "Mayo"), ("06", "Junio"), ("07", "Julio"), ("08", "Agosto"),
    ("09", "Septiembre"), ("10", "Octubre"), ("11", "Noviembre"),
    ("12", "Diciembre"),
]


class PlanillaLinea(models.Model):
    _name = "ktx.planilla.linea"
    _description = "Línea de Planilla GT (un empleado)"
    _order = "planilla_id desc, secuencia, id"
    _check_company_auto = True

    planilla_id = fields.Many2one(
        "ktx.planilla",
        string="Planilla",
        index=True,
        ondelete="cascade",
        help="Si se deja vacío al capturar por empleado, el sistema busca o "
             "crea automáticamente la planilla del período según la "
             "frecuencia de pago del empleado.",
    )
    secuencia = fields.Integer(string="No.", default=1)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Empleado",
        required=True,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contacto",
        compute="_compute_partner_id",
        store=True,
    )
    puesto = fields.Char(string="Puesto")
    department_id = fields.Many2one(
        related="employee_id.department_id", string="Departamento", store=True)
    company_id = fields.Many2one(
        related="planilla_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="planilla_id.currency_id", store=True)
    tipo = fields.Selection(related="planilla_id.tipo", store=True)
    state = fields.Selection(related="planilla_id.state", store=True)
    es_anticipo = fields.Boolean(
        related="planilla_id.es_anticipo", store=True)
    date_from = fields.Date(related="planilla_id.date_from", store=True)
    date_to = fields.Date(related="planilla_id.date_to", store=True)
    mes = fields.Selection(
        MESES_SELECTION, string="Mes",
        compute="_compute_mes_anio", store=True)
    anio = fields.Char(
        string="Año", compute="_compute_mes_anio", store=True)

    # ------------------------------------------------------------------
    # Días y asistencias del período
    # ------------------------------------------------------------------
    dias_periodo = fields.Integer(
        string="Días del Período", compute="_compute_dias", store=True)
    dias_laborados = fields.Integer(
        string="Días Laborados",
        compute="_compute_asistencias", store=True, readonly=False)
    dias_falta = fields.Integer(
        string="Faltas",
        compute="_compute_asistencias", store=True, readonly=False,
        help="Faltas injustificadas, permisos sin goce y suspensiones que "
             "descuentan día de sueldo.")
    dias_vacaciones = fields.Integer(
        string="Días de Vacaciones",
        compute="_compute_asistencias", store=True, readonly=False)
    horas_extra = fields.Float(
        string="Horas Extra",
        compute="_compute_asistencias", store=True, readonly=False)
    llamadas_atencion = fields.Integer(
        string="Llamadas de Atención",
        compute="_compute_asistencias", store=True)
    felicitaciones = fields.Integer(
        string="Felicitaciones",
        compute="_compute_asistencias", store=True)

    # ------------------------------------------------------------------
    # Devengado
    # ------------------------------------------------------------------
    sueldo_ordinario = fields.Monetary(string="Sueldo Ordinario")
    sueldo_extraordinario = fields.Monetary(
        string="Sueldo Extraordinario",
        help="Pago de horas extra con recargo del 50% (art. 121 Código de Trabajo).")
    comisiones = fields.Monetary(string="Comisiones")
    bonificacion_incentivo = fields.Monetary(
        string="Bonificación Incentivo",
        help="Decreto 78-89: exenta de IGSS, afecta a ISR.")
    otros_ingresos = fields.Monetary(
        string="Otros Ingresos",
        help="Viáticos no comprobables, bonos de productividad u otros pagos al colaborador.")
    total_devengado = fields.Monetary(
        string="Total Devengado", compute="_compute_totales", store=True)

    # ------------------------------------------------------------------
    # Descuentos
    # ------------------------------------------------------------------
    igss_laboral = fields.Monetary(
        string="IGSS Laboral",
        compute="_compute_igss", store=True, readonly=False,
        help="Cuota laboral sobre salario ordinario + extraordinario + "
             "comisiones. La bonificación incentivo está exenta.")
    isr = fields.Monetary(
        string="ISR",
        compute="_compute_isr", store=True, readonly=False,
        help="Retención mensual proyectada de ISR en relación de dependencia "
             "(Decreto 10-2012, arts. 72-75). Editable para ajustes de "
             "planilla SAT-1331.")
    isr_manual = fields.Boolean(
        string="ISR Manual",
        help="Si está activo, el sistema no recalcula el ISR de esta línea.")
    anticipos = fields.Monetary(
        string="Anticipos",
        help="Anticipos de sueldo otorgados que se descuentan en este período. "
             "En la planilla mensual se llena automáticamente con el líquido "
             "de las planillas de anticipo (quincenal, semanal, diario) "
             "contabilizadas del mes.")
    anticipo_linea_ids = fields.Many2many(
        "ktx.planilla.linea",
        relation="ktx_pl_linea_anticipo_rel",
        column1="linea_id",
        column2="anticipo_id",
        string="Anticipos Compensados",
        help="Líneas de planillas de anticipo del mes que esta línea "
             "mensual consolida y compensa.")
    judiciales = fields.Monetary(
        string="Descuentos Judiciales",
        help="Embargos o pensiones alimenticias ordenados por juez competente.")
    otros_descuentos = fields.Monetary(string="Otros Descuentos")
    total_descuentos = fields.Monetary(
        string="Total Descuentos", compute="_compute_totales", store=True)
    total_liquido = fields.Monetary(
        string="Total Líquido", compute="_compute_totales", store=True)

    # ------------------------------------------------------------------
    # Cuota patronal
    # ------------------------------------------------------------------
    igss_patronal = fields.Monetary(
        string="IGSS Patronal", compute="_compute_igss", store=True, readonly=False)
    irtra = fields.Monetary(
        string="IRTRA", compute="_compute_igss", store=True, readonly=False)
    intecap = fields.Monetary(
        string="INTECAP", compute="_compute_igss", store=True, readonly=False)
    total_patronal = fields.Monetary(
        string="Total Patronal", compute="_compute_totales", store=True)

    # ------------------------------------------------------------------
    # Provisiones de prestaciones
    # ------------------------------------------------------------------
    prov_indemnizacion = fields.Monetary(
        string="Prov. Indemnización",
        compute="_compute_provisiones", store=True, readonly=False)
    prov_aguinaldo = fields.Monetary(
        string="Prov. Aguinaldo",
        compute="_compute_provisiones", store=True, readonly=False)
    prov_bono14 = fields.Monetary(
        string="Prov. Bono 14",
        compute="_compute_provisiones", store=True, readonly=False)
    prov_vacaciones = fields.Monetary(
        string="Prov. Vacaciones",
        compute="_compute_provisiones", store=True, readonly=False)
    total_provisiones = fields.Monetary(
        string="Total Provisiones", compute="_compute_totales", store=True)

    # ------------------------------------------------------------------
    # Cuenta ajena
    # ------------------------------------------------------------------
    cuenta_ajena = fields.Boolean(
        string="Cuenta Ajena",
        compute="_compute_cuenta_ajena", store=True, readonly=False)
    cuenta_ajena_partner_id = fields.Many2one(
        "res.partner", string="Tercero (Cuenta Ajena)",
        compute="_compute_cuenta_ajena", store=True, readonly=False)
    cuenta_ajena_monto = fields.Monetary(
        string="Cobro Administrativo",
        compute="_compute_cuenta_ajena", store=True, readonly=False,
        help="Monto administrativo que se cobra al tercero por este colaborador.")
    settlement_id = fields.Many2one(
        "ktx.settlement", string="Liquidación de Gastos Vinculada",
        help="Liquidación (módulo Liquidaciones) donde se carga el costo de "
             "este colaborador al tercero.")

    # ------------------------------------------------------------------
    # Contabilidad y pago
    # ------------------------------------------------------------------
    move_id = fields.Many2one(
        "account.move", string="Partida Contable", copy=False, readonly=True)
    payment_ids = fields.One2many(
        "account.payment", "ktx_pl_linea_id", string="Pagos", copy=False)
    monto_pagado = fields.Monetary(
        string="Pagado", compute="_compute_pago", store=True)
    pagada = fields.Boolean(
        string="Pagada", compute="_compute_pago", store=True)
    notas = fields.Char(string="Observaciones")

    _empleado_planilla_uniq = models.Constraint(
        "UNIQUE(planilla_id, employee_id)",
        "El empleado ya está incluido en esta planilla.",
    )

    # ==================================================================
    # Captura por empleado: la planilla se busca o crea automáticamente
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        recalcular = self.browse()
        for vals in vals_list:
            if not vals.get("planilla_id"):
                if not vals.get("employee_id"):
                    raise UserError(_("Indique el empleado de la línea."))
                empleado = self.env["hr.employee"].browse(vals["employee_id"])
                planilla = self._buscar_o_crear_planilla(empleado)
                vals["planilla_id"] = planilla.id
                if not vals.get("secuencia") or vals["secuencia"] == 1:
                    vals["secuencia"] = len(planilla.line_ids) + 1
                if not vals.get("puesto"):
                    vals["puesto"] = (empleado.job_title
                                      or empleado.job_id.name or "")
                vals["_ktx_recalcular"] = True
        marcados = [vals.pop("_ktx_recalcular", False) for vals in vals_list]
        lineas = super().create(vals_list)
        for linea, marcado in zip(lineas, marcados):
            if not marcado:
                continue
            if not (linea.sueldo_ordinario or linea.otros_ingresos):
                recalcular |= linea
            elif (linea.tipo == "sueldo"
                    and linea.planilla_id.periodicidad == "mensual"
                    and not linea.anticipos):
                # Montos capturados a mano: solo se consolidan los anticipos
                anticipos = linea._buscar_anticipos_mes()
                if anticipos:
                    linea.write({
                        "anticipo_linea_ids": [(6, 0, anticipos.ids)],
                        "anticipos": sum(anticipos.mapped("total_liquido")),
                    })
        if recalcular:
            recalcular._recalcular()
            planillas = recalcular.planilla_id.filtered(
                lambda p: p.state == "draft")
            planillas.write({"state": "calculated"})
        return lineas

    @api.model
    def _buscar_o_crear_planilla(self, empleado, fecha=None):
        """Planilla de sueldos del período actual según la frecuencia de
        pago del empleado: la busca en borrador/calculada o la crea."""
        fecha = fecha or fields.Date.context_today(self)
        frecuencia = empleado.sudo().ktx_pl_frecuencia_pago or "mensual"
        if frecuencia == "mensual":
            date_from = fecha.replace(day=1)
            date_to = date_from + relativedelta(months=1, days=-1)
        elif frecuencia == "quincenal":
            if fecha.day <= 15:
                date_from = fecha.replace(day=1)
                date_to = fecha.replace(day=15)
            else:
                date_from = fecha.replace(day=16)
                date_to = fecha.replace(day=1) + relativedelta(
                    months=1, days=-1)
        elif frecuencia == "semanal":
            date_from = fecha - relativedelta(days=fecha.weekday())
            date_to = date_from + relativedelta(days=6)
        else:  # diario / evento
            date_from = date_to = fecha
        Planilla = self.env["ktx.planilla"]
        planilla = Planilla.search([
            ("company_id", "=", empleado.company_id.id or self.env.company.id),
            ("tipo", "=", "sueldo"),
            ("periodicidad", "=", frecuencia),
            ("date_from", "=", date_from),
            ("date_to", "=", date_to),
            ("state", "in", ("draft", "calculated")),
        ], limit=1)
        if not planilla:
            planilla = Planilla.create({
                "tipo": "sueldo",
                "periodicidad": frecuencia,
                "date_from": date_from,
                "date_to": date_to,
                "company_id": empleado.company_id.id or self.env.company.id,
            })
        return planilla

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends("employee_id", "planilla_id.name")
    def _compute_display_name(self):
        for linea in self:
            linea.display_name = "%s · %s" % (
                linea.planilla_id.name or "", linea.employee_id.name or "")

    @api.onchange("employee_id")
    def _onchange_employee_id_captura(self):
        """Captura por empleado: preingresa los montos según la
        configuración del empleado; todos quedan editables."""
        if not self.employee_id or self.planilla_id:
            return
        emp = self.employee_id.sudo()
        self.puesto = emp.job_title or emp.job_id.name or ""
        frecuencia = emp.ktx_pl_frecuencia_pago or "mensual"
        factor = {
            "mensual": 1.0,
            "quincenal": 0.5,
            "semanal": 7.0 / 30.0,
            "diario": 1.0 / 30.0,
            "evento": 1.0,
        }.get(frecuencia, 1.0)
        self.sueldo_ordinario = round(
            (emp.ktx_pl_sueldo_base or 0.0) * factor, 2)
        self.bonificacion_incentivo = round(
            emp._ktx_pl_bonificacion() * factor, 2)

    @api.depends("employee_id")
    def _compute_partner_id(self):
        for linea in self:
            linea.partner_id = (
                linea.employee_id.work_contact_id
                or linea.employee_id.user_id.partner_id
            )

    @api.depends("date_to")
    def _compute_mes_anio(self):
        for linea in self:
            if linea.date_to:
                linea.mes = "%02d" % linea.date_to.month
                linea.anio = str(linea.date_to.year)
            else:
                linea.mes = False
                linea.anio = False

    @api.depends("date_from", "date_to")
    def _compute_dias(self):
        for linea in self:
            if linea.date_from and linea.date_to:
                linea.dias_periodo = (linea.date_to - linea.date_from).days + 1
            else:
                linea.dias_periodo = 0

    @api.depends("employee_id", "date_from", "date_to")
    def _compute_asistencias(self):
        Asistencia = self.env["ktx.planilla.asistencia"]
        for linea in self:
            if not (linea.employee_id and linea.date_from and linea.date_to):
                linea.dias_laborados = 0
                linea.dias_falta = 0
                linea.dias_vacaciones = 0
                linea.horas_extra = 0.0
                linea.llamadas_atencion = 0
                linea.felicitaciones = 0
                continue
            registros = Asistencia.search([
                ("employee_id", "=", linea.employee_id.id),
                ("fecha", ">=", linea.date_from),
                ("fecha", "<=", linea.date_to),
            ])
            linea.dias_laborados = len(
                registros.filtered(lambda r: r.tipo == "asistencia"))
            linea.dias_falta = len(
                registros.filtered(lambda r: r.tipo in TIPOS_DESCUENTO))
            linea.dias_vacaciones = len(
                registros.filtered(lambda r: r.tipo == "vacaciones"))
            linea.horas_extra = sum(registros.mapped("horas_extra"))
            linea.llamadas_atencion = len(
                registros.filtered(lambda r: r.tipo == "llamada_atencion"))
            linea.felicitaciones = len(
                registros.filtered(lambda r: r.tipo == "felicitacion"))

    @api.depends("employee_id")
    def _compute_cuenta_ajena(self):
        for linea in self:
            emp = linea.employee_id.sudo()
            linea.cuenta_ajena = emp.ktx_pl_cuenta_ajena
            linea.cuenta_ajena_partner_id = emp.ktx_pl_cuenta_ajena_partner_id
            linea.cuenta_ajena_monto = emp.ktx_pl_cuenta_ajena_monto

    @api.depends("sueldo_ordinario", "sueldo_extraordinario", "comisiones",
                 "tipo", "employee_id")
    def _compute_igss(self):
        for linea in self:
            company = linea.company_id or self.env.company
            emp = linea.employee_id.sudo()
            base = (linea.sueldo_ordinario + linea.sueldo_extraordinario
                    + linea.comisiones)
            # Bono 14 y aguinaldo no son salario afecto a IGSS
            # (Decretos 42-92 art. 2 y 76-78 art. 1). Los anticipos
            # (quincena, semana, día) no retienen: las retenciones legales
            # se aplican en la planilla mensual consolidada.
            if linea.tipo in ("bono14", "aguinaldo", "liquidacion") or \
                    linea.es_anticipo or not emp.ktx_pl_aplica_igss:
                linea.igss_laboral = 0.0
                linea.igss_patronal = 0.0
                linea.irtra = 0.0
                linea.intecap = 0.0
                continue
            linea.igss_laboral = base * company.ktx_pl_igss_laboral / 100.0
            linea.igss_patronal = base * company.ktx_pl_igss_patronal / 100.0
            linea.irtra = base * company.ktx_pl_irtra / 100.0
            linea.intecap = base * company.ktx_pl_intecap / 100.0

    @api.depends("sueldo_ordinario", "sueldo_extraordinario", "comisiones",
                 "bonificacion_incentivo", "otros_ingresos", "igss_laboral",
                 "isr_manual", "tipo", "employee_id")
    def _compute_isr(self):
        for linea in self:
            if linea.isr_manual:
                continue
            linea.isr = linea._calcular_isr_mensual()

    def _calcular_isr_mensual(self):
        """Retención mensual de ISR en relación de dependencia.

        Proyección anual simplificada (Decreto 10-2012, arts. 72-75):
          renta bruta anual = devengado del período × períodos por año
          (aguinaldo y Bono 14 son rentas exentas hasta el 100% del sueldo,
           por lo que no se suman a la proyección)
          renta imponible = renta bruta − deducción fija (Q48,000)
                            − IGSS laboral anual
          impuesto = 5% hasta Q300,000; Q15,000 + 7% sobre el excedente
          retención mensual = impuesto anual ÷ 12
        """
        self.ensure_one()
        emp = self.employee_id.sudo()
        if self.tipo in ("bono14", "aguinaldo") or self.es_anticipo \
                or not emp.ktx_pl_aplica_isr:
            return 0.0
        company = self.company_id or self.env.company
        periodicidad = self.planilla_id.periodicidad or "mensual"
        periodos = PERIODOS_POR_ANIO.get(periodicidad, 12.0)
        if periodicidad in ("diario", "evento"):
            # Sin base cierta para proyectar: se deja a criterio del encargado.
            return 0.0
        devengado = (self.sueldo_ordinario + self.sueldo_extraordinario
                     + self.comisiones + self.bonificacion_incentivo
                     + self.otros_ingresos)
        renta_bruta = devengado * periodos
        igss_anual = self.igss_laboral * periodos
        imponible = renta_bruta - company.ktx_pl_isr_deduccion_fija - igss_anual
        if imponible <= 0:
            return 0.0
        limite = company.ktx_pl_isr_tramo1_limite
        if imponible <= limite:
            impuesto_anual = imponible * company.ktx_pl_isr_tramo1_tasa / 100.0
        else:
            impuesto_anual = (
                company.ktx_pl_isr_tramo2_cuota_fija
                + (imponible - limite) * company.ktx_pl_isr_tramo2_tasa / 100.0
            )
        return round(impuesto_anual / 12.0, 2)

    @api.depends("sueldo_ordinario", "sueldo_extraordinario", "comisiones",
                 "tipo")
    def _compute_provisiones(self):
        for linea in self:
            company = linea.company_id or self.env.company
            base = (linea.sueldo_ordinario + linea.sueldo_extraordinario
                    + linea.comisiones)
            if (linea.tipo != "sueldo" or linea.es_anticipo
                    or company.ktx_pl_provision_frecuencia != "mensual"):
                linea.prov_indemnizacion = 0.0
                linea.prov_aguinaldo = 0.0
                linea.prov_bono14 = 0.0
                linea.prov_vacaciones = 0.0
                continue
            linea.prov_indemnizacion = base * company.ktx_pl_prov_indemnizacion / 100.0
            linea.prov_aguinaldo = base * company.ktx_pl_prov_aguinaldo / 100.0
            linea.prov_bono14 = base * company.ktx_pl_prov_bono14 / 100.0
            linea.prov_vacaciones = base * company.ktx_pl_prov_vacaciones / 100.0

    @api.depends("sueldo_ordinario", "sueldo_extraordinario", "comisiones",
                 "bonificacion_incentivo", "otros_ingresos", "igss_laboral",
                 "isr", "anticipos", "judiciales", "otros_descuentos",
                 "igss_patronal", "irtra", "intecap", "prov_indemnizacion",
                 "prov_aguinaldo", "prov_bono14", "prov_vacaciones")
    def _compute_totales(self):
        for linea in self:
            linea.total_devengado = (
                linea.sueldo_ordinario + linea.sueldo_extraordinario
                + linea.comisiones + linea.bonificacion_incentivo
                + linea.otros_ingresos)
            linea.total_descuentos = (
                linea.igss_laboral + linea.isr + linea.anticipos
                + linea.judiciales + linea.otros_descuentos)
            linea.total_liquido = linea.total_devengado - linea.total_descuentos
            linea.total_patronal = linea.igss_patronal + linea.irtra + linea.intecap
            linea.total_provisiones = (
                linea.prov_indemnizacion + linea.prov_aguinaldo
                + linea.prov_bono14 + linea.prov_vacaciones)

    @api.depends("payment_ids.state", "payment_ids.amount", "total_liquido")
    def _compute_pago(self):
        for linea in self:
            pagos = linea.payment_ids.filtered(
                lambda p: p.state not in ("draft", "canceled", "rejected"))
            linea.monto_pagado = sum(pagos.mapped("amount"))
            linea.pagada = (
                linea.total_liquido > 0
                and linea.monto_pagado >= linea.total_liquido - 0.01
            )

    # ==================================================================
    # Cálculo del devengado
    # ==================================================================
    def _recalcular(self):
        """Calcula el devengado de cada línea según el tipo de planilla."""
        for linea in self:
            metodo = getattr(
                linea, "_calcular_%s" % linea.tipo, linea._calcular_sueldo)
            metodo()
        return True

    def _calcular_sueldo(self):
        self.ensure_one()
        emp = self.employee_id.sudo()
        planilla = self.planilla_id
        sueldo_mensual = emp.ktx_pl_sueldo_base or 0.0
        bonif_mensual = emp._ktx_pl_bonificacion()
        dias_base = planilla._dias_base_periodo()
        dias_periodo = self.dias_periodo or dias_base

        if planilla.periodicidad == "mensual":
            factor = min(dias_periodo / dias_base, 1.0)
        elif planilla.periodicidad == "quincenal":
            # Quincena exacta: medio sueldo, sin importar 30/31/28 días
            factor = 0.5
        elif planilla.periodicidad == "semanal":
            factor = 7.0 / 30.0
        else:  # diario / evento
            factor = dias_periodo / 30.0

        # Descuento de faltas: día de salario ordinario por falta (art. 63 CdT)
        valor_dia = sueldo_mensual / 30.0
        sueldo = sueldo_mensual * factor - self.dias_falta * valor_dia
        bonif = bonif_mensual * factor

        # Horas extra al 150% (art. 121 CdT): valor hora ordinaria × 1.5
        horas_dia = emp.ktx_pl_horas_dia or 8.0
        valor_hora = sueldo_mensual / 30.0 / horas_dia
        extra = self.horas_extra * valor_hora * 1.5

        vals = {
            "sueldo_ordinario": max(round(sueldo, 2), 0.0),
            "sueldo_extraordinario": round(extra, 2),
            "bonificacion_incentivo": max(round(bonif, 2), 0.0),
        }
        if planilla.periodicidad == "mensual":
            # Planilla oficial del mes: consolida y compensa los anticipos
            # (quincenal, semanal, diario) ya contabilizados del período.
            anticipos = self._buscar_anticipos_mes()
            vals["anticipo_linea_ids"] = [(6, 0, anticipos.ids)]
            vals["anticipos"] = sum(anticipos.mapped("total_liquido"))
        elif self.es_anticipo:
            vals["anticipos"] = 0.0
        self.write(vals)

    def _buscar_anticipos_mes(self):
        """Líneas de anticipo contabilizadas del mismo empleado y mes."""
        self.ensure_one()
        planilla = self.planilla_id
        return self.search([
            ("employee_id", "=", self.employee_id.id),
            ("company_id", "=", self.company_id.id),
            ("planilla_id.es_anticipo", "=", True),
            ("planilla_id.state", "in", ("posted", "paid")),
            ("date_to", ">=", planilla.date_from),
            ("date_to", "<=", planilla.date_to),
            ("id", "!=", self.id),
        ])

    def _calcular_bono14(self):
        """Bono 14 (Decreto 42-92): salario promedio ordinario del período
        1-jul → 30-jun, proporcional a los días laborados del período."""
        self.ensure_one()
        self._calcular_prestacion_anual()

    def _calcular_aguinaldo(self):
        """Aguinaldo (Decreto 76-78): salario promedio del período
        1-dic → 30-nov, proporcional a los días laborados del período."""
        self.ensure_one()
        self._calcular_prestacion_anual()

    def _calcular_prestacion_anual(self):
        self.ensure_one()
        emp = self.employee_id.sudo()
        planilla = self.planilla_id
        promedio = emp._ktx_pl_salario_promedio(
            fecha_hasta=planilla.date_to, meses=6)
        inicio = emp.ktx_pl_fecha_inicio or planilla.date_from
        desde = max(planilla.date_from, inicio)
        dias = max((planilla.date_to - desde).days + 1, 0)
        dias = min(dias, 365)
        monto = promedio / 365.0 * dias
        self.write({
            "sueldo_ordinario": round(monto, 2),
            "sueldo_extraordinario": 0.0,
            "bonificacion_incentivo": 0.0,
            "notas": _("Promedio Q%(p).2f × %(d)s/365 días",
                       p=promedio, d=dias),
        })

    def _calcular_vacaciones(self):
        """Vacaciones (arts. 130-134 CdT): 15 días hábiles por año. El pago
        en dinero solo procede al terminar la relación laboral o como planilla
        del período de goce."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        promedio = emp._ktx_pl_salario_promedio(
            fecha_hasta=self.planilla_id.date_to, meses=6)
        dias = self.dias_vacaciones or 15
        monto = promedio / 30.0 * dias
        self.write({
            "sueldo_ordinario": round(monto, 2),
            "sueldo_extraordinario": 0.0,
            "bonificacion_incentivo": 0.0,
            "dias_vacaciones": dias,
            "notas": _("Promedio Q%(p).2f / 30 × %(d)s días", p=promedio, d=dias),
        })

    def _calcular_liquidacion(self):
        # El detalle viene del documento de liquidación; no se recalcula aquí.
        self.ensure_one()

    def action_recalcular(self):
        for linea in self:
            if linea.state not in ("draft", "calculated"):
                raise UserError(
                    _("Solo se pueden recalcular líneas de planillas en "
                      "borrador o calculadas."))
        return self._recalcular()

    # ==================================================================
    # Partida contable (una por empleado)
    # ==================================================================
    def _cuenta(self, campo_partner, campo_company, descripcion):
        """Resuelve una cuenta: primero la del contacto, luego la de compañía."""
        self.ensure_one()
        cuenta = None
        if campo_partner and self.partner_id:
            cuenta = self.partner_id[campo_partner]
        if not cuenta and campo_company:
            cuenta = self.company_id[campo_company]
        if not cuenta:
            raise UserError(
                _("No hay cuenta configurada para «%(desc)s». Configúrela en "
                  "Ajustes → Planilla GT o en el contacto del empleado %(emp)s.",
                  desc=descripcion, emp=self.employee_id.name))
        return cuenta

    def _crear_asiento(self, journal):
        """Crea la partida contable de esta línea (un asiento por empleado).

        Anticipo (quincenal/semanal/diario): Anticipos a Empleados (activo)
        contra Sueldos por Pagar, por el líquido anticipado. El gasto real,
        IGSS, ISR y provisiones se registran en la planilla mensual, que
        compensa el anticipo acreditando la misma cuenta de activo.
        """
        self.ensure_one()
        planilla = self.planilla_id
        partner = self.employee_id._ktx_pl_get_partner()
        fecha = planilla.fecha_contable or planilla.date_to
        company = self.company_id

        if self.es_anticipo:
            return self._crear_asiento_anticipo(journal, partner, fecha, company)

        cta_gasto = self._cuenta(
            "ktx_pl_account_gasto_id", "ktx_pl_account_gasto_sueldo_id",
            _("Gasto Sueldos y Salarios"))
        cta_pagar = self._cuenta(
            "ktx_pl_account_pagar_id", "ktx_pl_account_pagar_sueldos_id",
            _("Por Pagar Sueldos y Salarios"))
        cta_gasto_bonif = company.ktx_pl_account_gasto_bonificacion_id or cta_gasto
        cta_gasto_patronal = company.ktx_pl_account_gasto_patronal_id or cta_gasto
        cta_gasto_prest = company.ktx_pl_account_gasto_prestaciones_id or cta_gasto

        etiqueta = "%s %s" % (planilla._titulo_reporte(), planilla.mes_nombre)
        lineas = []

        def agregar(cuenta, debe, haber, nombre):
            if round(debe, 2) <= 0 and round(haber, 2) <= 0:
                return
            lineas.append((0, 0, {
                "account_id": cuenta.id,
                "partner_id": partner.id,
                "name": nombre,
                "debit": round(debe, 2),
                "credit": round(haber, 2),
            }))

        gasto_ordinario = (self.sueldo_ordinario + self.sueldo_extraordinario
                           + self.comisiones + self.otros_ingresos)
        if self.tipo == "liquidacion":
            agregar(cta_gasto_prest, gasto_ordinario, 0,
                    _("Prestaciones laborales — %s") % self.employee_id.name)
        else:
            agregar(cta_gasto, gasto_ordinario, 0,
                    _("%(et)s — %(emp)s", et=etiqueta, emp=self.employee_id.name))
        agregar(cta_gasto_bonif, self.bonificacion_incentivo, 0,
                _("Bonificación incentivo — %s") % self.employee_id.name)
        agregar(cta_gasto_patronal, self.total_patronal, 0,
                _("Cuotas patronales IGSS/IRTRA/INTECAP — %s")
                % self.employee_id.name)
        agregar(cta_gasto_prest, self.total_provisiones, 0,
                _("Provisión prestaciones laborales — %s")
                % self.employee_id.name)

        agregar(cta_pagar, 0, self.total_liquido,
                _("Líquido a pagar — %s") % self.employee_id.name)

        total_igss = self.igss_laboral + self.total_patronal
        if total_igss:
            cta_igss = company.ktx_pl_account_igss_pagar_id
            if not cta_igss:
                raise UserError(_(
                    "Configure la cuenta «IGSS por Pagar» en Ajustes → Planilla GT."))
            agregar(cta_igss, 0, total_igss,
                    _("IGSS laboral y patronal, IRTRA, INTECAP"))
        if self.isr:
            cta_isr = company.ktx_pl_account_isr_pagar_id
            if not cta_isr:
                raise UserError(_(
                    "Configure la cuenta «ISR Retenido por Pagar» en Ajustes → Planilla GT."))
            agregar(cta_isr, 0, self.isr, _("ISR retenido"))
        if self.judiciales:
            cta_jud = company.ktx_pl_account_judicial_pagar_id
            if not cta_jud:
                raise UserError(_(
                    "Configure la cuenta «Descuentos Judiciales por Pagar» en "
                    "Ajustes → Planilla GT."))
            agregar(cta_jud, 0, self.judiciales, _("Descuentos judiciales"))
        if self.otros_descuentos:
            cta_otros = company.ktx_pl_account_otros_desc_id
            if not cta_otros:
                raise UserError(_(
                    "Configure la cuenta «Otros Descuentos por Pagar» en "
                    "Ajustes → Planilla GT."))
            agregar(cta_otros, 0, self.otros_descuentos, _("Otros descuentos"))
        if self.anticipos:
            cta_ant = company.ktx_pl_account_anticipos_id
            if not cta_ant:
                raise UserError(_(
                    "Configure la cuenta «Anticipos a Empleados» en "
                    "Ajustes → Planilla GT."))
            agregar(cta_ant, 0, self.anticipos, _("Descuento de anticipos"))

        provisiones = [
            (self.prov_indemnizacion, "ktx_pl_account_prov_indemnizacion_id",
             _("Provisión indemnización")),
            (self.prov_aguinaldo, "ktx_pl_account_prov_aguinaldo_id",
             _("Provisión aguinaldo")),
            (self.prov_bono14, "ktx_pl_account_prov_bono14_id",
             _("Provisión Bono 14")),
            (self.prov_vacaciones, "ktx_pl_account_prov_vacaciones_id",
             _("Provisión vacaciones")),
        ]
        for monto, campo, nombre in provisiones:
            if monto:
                cuenta = company[campo]
                if not cuenta:
                    raise UserError(_(
                        "Configure la cuenta «%s (Pasivo)» en Ajustes → "
                        "Planilla GT o desactive la provisión.") % nombre)
                agregar(cuenta, 0, monto, nombre)

        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": fecha,
            "ref": "%s — %s" % (etiqueta, self.employee_id.name),
            "company_id": company.id,
            "line_ids": lineas,
            "ktx_pl_linea_id": self.id,
        })
        return move

    def _crear_asiento_anticipo(self, journal, partner, fecha, company):
        """Partida del anticipo: Anticipos a Empleados vs Sueldos por Pagar."""
        self.ensure_one()
        cta_anticipos = company.ktx_pl_account_anticipos_id
        if not cta_anticipos:
            raise UserError(_(
                "Configure la cuenta «Anticipos a Empleados» en Ajustes → "
                "Planilla GT para contabilizar planillas de anticipo "
                "(quincenal, semanal, diario)."))
        cta_pagar = self._cuenta(
            "ktx_pl_account_pagar_id", "ktx_pl_account_pagar_sueldos_id",
            _("Por Pagar Sueldos y Salarios"))
        if self.total_liquido <= 0:
            raise UserError(_(
                "La línea de %s no tiene líquido a anticipar.")
                % self.employee_id.name)
        etiqueta = _("Anticipo de salario %(per)s — %(emp)s") % {
            "per": self._periodo_texto().lower(),
            "emp": self.employee_id.name,
        }
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": fecha,
            "ref": etiqueta,
            "company_id": company.id,
            "ktx_pl_linea_id": self.id,
            "line_ids": [
                (0, 0, {
                    "account_id": cta_anticipos.id,
                    "partner_id": partner.id,
                    "name": etiqueta,
                    "debit": round(self.total_liquido, 2),
                    "credit": 0.0,
                }),
                (0, 0, {
                    "account_id": cta_pagar.id,
                    "partner_id": partner.id,
                    "name": _("Líquido a pagar — %s") % self.employee_id.name,
                    "debit": 0.0,
                    "credit": round(self.total_liquido, 2),
                }),
            ],
        })
        return move

    def _conciliar_anticipos(self):
        """Concilia la compensación de anticipos de la planilla mensual con
        las partidas de anticipo del mes (misma cuenta de activo)."""
        self.ensure_one()
        cta = self.company_id.ktx_pl_account_anticipos_id
        if not cta or not self.move_id or not self.anticipo_linea_ids:
            return
        try:
            if not cta.reconcile:
                return
            lineas = (
                (self.move_id | self.anticipo_linea_ids.move_id)
                .line_ids.filtered(
                    lambda l: l.account_id == cta
                    and l.partner_id == self.partner_id
                    and not l.reconciled)
            )
            if len(lineas) > 1:
                lineas.reconcile()
        except Exception as e:
            _logger.warning(
                "No se pudo conciliar los anticipos de %s: %s",
                self.employee_id.name, e)

    def action_registrar_pago(self):
        self.ensure_one()
        if not self.move_id or self.move_id.state != "posted":
            raise UserError(_("Primero contabilice la planilla."))
        if self.pagada:
            raise UserError(_("Esta línea ya está pagada."))
        wizard = self.env["ktx.planilla.pago.wizard"].create({
            "planilla_id": self.planilla_id.id,
            "linea_ids": [(6, 0, self.ids)],
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Registrar Pago — %s") % self.employee_id.name,
            "res_model": "ktx.planilla.pago.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_imprimir_recibo(self):
        self.ensure_one()
        return self.env.ref(
            "ktx_planilla_empleados_gt.action_report_recibo_nomina"
        ).report_action(self)

    def action_enviar_recibo(self):
        self.ensure_one()
        wizard = self.env["ktx.planilla.enviar.recibo.wizard"].create({
            "linea_id": self.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Enviar Recibo — %s") % self.employee_id.name,
            "res_model": "ktx.planilla.enviar.recibo.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    # ==================================================================
    # Utilidades para reportes
    # ==================================================================
    def _liquido_en_letras(self):
        self.ensure_one()
        return amount_to_words_es(self.total_liquido)

    def _periodo_texto(self):
        self.ensure_one()
        if not (self.date_from and self.date_to):
            return ""
        meses = dict(MESES_SELECTION)
        return _("DEL %(d1)s AL %(d2)s DE %(mes)s DE %(anio)s") % {
            "d1": "%02d" % self.date_from.day,
            "d2": "%02d" % self.date_to.day,
            "mes": meses["%02d" % self.date_to.month].upper(),
            "anio": self.date_to.year,
        }

    def _pago_principal(self):
        self.ensure_one()
        pagos = self.payment_ids.filtered(
            lambda p: p.state not in ("draft", "canceled", "rejected"))
        return pagos[:1]

    def _dias_habiles_mes(self):
        self.ensure_one()
        if not (self.date_from and self.date_to):
            return 0
        return calendar.monthrange(self.date_to.year, self.date_to.month)[1]
