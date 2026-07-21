# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # ------------------------------------------------------------------
    # Datos de planilla
    # ------------------------------------------------------------------
    ktx_pl_sueldo_base = fields.Monetary(
        string="Sueldo Base Mensual",
        currency_field="ktx_pl_currency_id",
        tracking=True,
        groups="hr.group_hr_user",
        help="Sueldo ordinario mensual pactado. No puede ser menor al salario "
             "mínimo vigente según la actividad económica (Acuerdo Gubernativo "
             "anual de salarios mínimos).",
    )
    ktx_pl_bonificacion_incentivo = fields.Monetary(
        string="Bonificación Incentivo",
        currency_field="ktx_pl_currency_id",
        groups="hr.group_hr_user",
        help="Bonificación incentivo mensual (Decreto 78-89). Mínimo legal Q250.00. "
             "Si se deja en 0 se usa el valor configurado en la compañía.",
    )
    ktx_pl_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_ktx_pl_currency_id",
        string="Moneda Planilla",
    )
    ktx_pl_frecuencia_pago = fields.Selection(
        selection=[
            ("mensual", "Mensual"),
            ("quincenal", "Quincenal"),
            ("semanal", "Semanal"),
            ("diario", "Por Día"),
            ("evento", "Por Evento / Obra"),
        ],
        string="Frecuencia de Pago",
        default="mensual",
        groups="hr.group_hr_user",
        tracking=True,
    )
    ktx_pl_fecha_inicio = fields.Date(
        string="Inicio Relación Laboral",
        groups="hr.group_hr_user",
        tracking=True,
        help="Fecha de inicio de la relación laboral. Base para el cálculo de "
             "prestaciones, Bono 14, aguinaldo, vacaciones e indemnización.",
    )
    ktx_pl_afiliacion_igss = fields.Char(
        string="No. Afiliación IGSS",
        groups="hr.group_hr_user",
    )
    ktx_pl_nit = fields.Char(
        string="NIT",
        groups="hr.group_hr_user",
    )
    ktx_pl_ubicacion = fields.Char(
        string="Ubicación Asignada",
        groups="hr.group_hr_user",
        help="Sede, proyecto o punto de trabajo asignado; se imprime en el recibo.",
    )

    # --- Jornada y horario (arts. 116-122 Código de Trabajo) ---
    ktx_pl_jornada = fields.Selection(
        selection=[
            ("diurna", "Diurna (8 h/día, 44 h/semana)"),
            ("nocturna", "Nocturna (6 h/día, 36 h/semana)"),
            ("mixta", "Mixta (7 h/día, 42 h/semana)"),
            ("rotativa", "Rotativa / Turnos"),
        ],
        string="Jornada",
        default="diurna",
        groups="hr.group_hr_user",
        help="Jornada ordinaria de trabajo según los arts. 116-117 del "
             "Código de Trabajo. Las horas fuera de la jornada se pagan "
             "como extraordinarias con 50% de recargo (art. 121).",
    )
    ktx_pl_horas_dia = fields.Float(
        string="Horas por Día",
        default=8.0,
        groups="hr.group_hr_user",
        help="Horas ordinarias de trabajo al día. Base para valorar la hora "
             "ordinaria y las horas extra.",
    )
    ktx_pl_hora_entrada = fields.Float(
        string="Hora de Entrada",
        default=8.0,
        groups="hr.group_hr_user",
        help="Hora de entrada habitual en formato 24h (8.5 = 08:30). Se usa "
             "para prellenar las asistencias.",
    )
    ktx_pl_hora_salida = fields.Float(
        string="Hora de Salida",
        default=17.0,
        groups="hr.group_hr_user",
    )
    ktx_pl_almuerzo_horas = fields.Float(
        string="Horas de Almuerzo",
        default=1.0,
        groups="hr.group_hr_user",
        help="Tiempo de almuerzo/descanso que se descuenta de las horas "
             "trabajadas del día.",
    )

    # --- Datos bancarios para el recibo ---
    ktx_pl_banco = fields.Char(string="Banco", groups="hr.group_hr_user")
    ktx_pl_cuenta_bancaria = fields.Char(
        string="Cuenta Bancaria", groups="hr.group_hr_user")
    ktx_pl_tipo_cuenta = fields.Selection(
        selection=[
            ("monetaria", "Monetaria"),
            ("ahorro", "Ahorro"),
        ],
        string="Tipo de Cuenta",
        groups="hr.group_hr_user",
    )

    # --- Reglas de cálculo ---
    ktx_pl_aplica_igss = fields.Boolean(
        string="Aplica IGSS",
        default=True,
        groups="hr.group_hr_user",
        help="Desmarcar solo para trabajadores no afiliados (p. ej. patronos "
             "con menos de 3 trabajadores no inscritos al régimen).",
    )
    ktx_pl_aplica_isr = fields.Boolean(
        string="Aplica Retención ISR",
        default=True,
        groups="hr.group_hr_user",
        help="Si está activo, se proyecta la renta anual y se retiene ISR "
             "mensual cuando supera la deducción legal (Decreto 10-2012).",
    )
    ktx_pl_prestaciones_universales = fields.Boolean(
        string="Prestaciones Universales",
        default=False,
        groups="hr.group_hr_user",
        tracking=True,
        help="Si está activo, la indemnización se paga SIEMPRE al terminar la "
             "relación laboral, aunque sea renuncia o despido justificado "
             "(política de empresa más favorable que el mínimo legal, art. 106 "
             "Constitución: los derechos laborales son irrenunciables pero "
             "superables por pacto).",
    )

    # --- Cobro / pago por cuenta ajena ---
    ktx_pl_cuenta_ajena = fields.Boolean(
        string="Cobro/Pago por Cuenta Ajena",
        groups="hr.group_hr_user",
        help="El costo de este colaborador se cobra o repaga a un tercero "
             "(p. ej. outsourcing o administración de personal). Se vincula "
             "con el módulo de Liquidaciones para el cargo al tercero.",
    )
    ktx_pl_cuenta_ajena_partner_id = fields.Many2one(
        "res.partner",
        string="Tercero (Cuenta Ajena)",
        groups="hr.group_hr_user",
        help="Cliente o empresa a quien se factura o carga el costo del colaborador.",
    )
    ktx_pl_cuenta_ajena_monto = fields.Monetary(
        string="Cobro Administrativo Mensual",
        currency_field="ktx_pl_currency_id",
        groups="hr.group_hr_user",
        help="Monto administrativo mensual que se cobra al tercero además del "
             "costo laboral.",
    )

    # --- Contadores para botones inteligentes ---
    ktx_pl_asistencia_count = fields.Integer(
        compute="_compute_ktx_pl_counts", groups="hr.group_hr_user")
    ktx_pl_linea_count = fields.Integer(
        compute="_compute_ktx_pl_counts", groups="hr.group_hr_user")
    ktx_pl_liquidacion_count = fields.Integer(
        compute="_compute_ktx_pl_counts", groups="hr.group_hr_user")

    def _compute_ktx_pl_currency_id(self):
        for emp in self:
            emp.ktx_pl_currency_id = (
                emp.company_id.currency_id or self.env.company.currency_id
            )

    def _compute_ktx_pl_counts(self):
        asistencia = self.env["ktx.planilla.asistencia"]
        linea = self.env["ktx.planilla.linea"]
        liquidacion = self.env["ktx.planilla.liquidacion"]
        for emp in self:
            emp.ktx_pl_asistencia_count = asistencia.search_count(
                [("employee_id", "=", emp.id)])
            emp.ktx_pl_linea_count = linea.search_count(
                [("employee_id", "=", emp.id)])
            emp.ktx_pl_liquidacion_count = liquidacion.search_count(
                [("employee_id", "=", emp.id)])

    # ------------------------------------------------------------------
    # Acciones de botones inteligentes
    # ------------------------------------------------------------------
    def action_ktx_pl_ver_asistencias(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Asistencias de %s") % self.name,
            "res_model": "ktx.planilla.asistencia",
            "view_mode": "calendar,list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }

    def action_ktx_pl_ver_lineas(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Planillas de %s") % self.name,
            "res_model": "ktx.planilla.linea",
            "view_mode": "list,form,pivot",
            "domain": [("employee_id", "=", self.id)],
            "context": {"search_default_group_planilla": 1},
        }

    def action_ktx_pl_ver_liquidaciones(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Liquidaciones de %s") % self.name,
            "res_model": "ktx.planilla.liquidacion",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }

    # ------------------------------------------------------------------
    # Utilidades de planilla
    # ------------------------------------------------------------------
    def _ktx_pl_get_partner(self):
        """Contacto (res.partner) del empleado, para pagos y partidas."""
        self.ensure_one()
        partner = self.work_contact_id or self.user_id.partner_id
        if not partner:
            raise UserError(
                _("El empleado %s no tiene un contacto asociado. Configure la "
                  "dirección de trabajo/contacto en su ficha de empleado.")
                % self.name
            )
        return partner

    def _ktx_pl_bonificacion(self):
        """Bonificación incentivo mensual aplicable."""
        self.ensure_one()
        return (
            self.ktx_pl_bonificacion_incentivo
            or self.company_id.ktx_pl_bonificacion_incentivo
            or self.env.company.ktx_pl_bonificacion_incentivo
        )

    def _ktx_pl_salario_promedio(self, fecha_hasta=None, meses=6):
        """Salario ordinario promedio mensual de los últimos ``meses`` meses.

        Base legal: art. 82 Código de Trabajo — la indemnización se calcula
        sobre el promedio de los salarios devengados durante los últimos seis
        meses de vigencia del contrato. Se toman las líneas de planilla de
        sueldo contabilizadas o pagadas (ordinario + extraordinario +
        comisiones, sin bonificación incentivo). Si no hay historial se usa
        el sueldo base del empleado.
        """
        self.ensure_one()
        fecha_hasta = fecha_hasta or fields.Date.context_today(self)
        fecha_desde = fecha_hasta - relativedelta(months=meses)
        lineas = self.env["ktx.planilla.linea"].search([
            ("employee_id", "=", self.id),
            ("planilla_id.tipo", "=", "sueldo"),
            ("planilla_id.state", "in", ("posted", "paid")),
            ("planilla_id.date_to", ">", fecha_desde),
            ("planilla_id.date_to", "<=", fecha_hasta),
        ])
        if not lineas:
            return self.ktx_pl_sueldo_base or 0.0
        total = sum(
            l.sueldo_ordinario + l.sueldo_extraordinario + l.comisiones
            for l in lineas
        )
        # Meses distintos con datos: una planilla quincenal aporta 2 líneas
        # al mismo mes, por eso se promedia por mes calendario y no por línea.
        meses_con_datos = {
            (l.planilla_id.date_to.year, l.planilla_id.date_to.month)
            for l in lineas
        }
        return total / max(len(meses_con_datos), 1)
