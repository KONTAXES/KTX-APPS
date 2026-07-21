# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

# Tipos que cuentan como día laborado para el cálculo de planilla
TIPOS_TRABAJADOS = ("asistencia", "vacaciones", "permiso_goce", "felicitacion")
# Tipos que descuentan día de sueldo
TIPOS_DESCUENTO = ("falta", "permiso_sin_goce", "suspension")

# Colores del grid/calendario: verde = asistencia, rojo/marrón = falta,
# naranja = parcial con permiso, azul = vacaciones…
COLOR_POR_TIPO = {
    "asistencia": 10,       # verde
    "falta": 1,             # rojo/marrón
    "falta_justificada": 2, # naranja
    "vacaciones": 4,        # azul claro
    "permiso_goce": 2,      # naranja (asistencia parcial con permiso)
    "permiso_sin_goce": 6,  # rosado
    "suspension": 9,        # fucsia
    "llamada_atencion": 3,  # amarillo
    "felicitacion": 5,      # morado
    "descanso": 7,          # gris azulado
}

TZ_GT = "America/Guatemala"


class PlanillaAsistencia(models.Model):
    _name = "ktx.planilla.asistencia"
    _description = "Asistencia / Evento de Planilla GT"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "fecha desc, employee_id"
    _rec_name = "display_name"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Empleado",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )
    department_id = fields.Many2one(
        related="employee_id.department_id",
        string="Departamento",
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    fecha = fields.Date(
        string="Fecha",
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    tipo = fields.Selection(
        selection=[
            ("asistencia", "Asistencia"),
            ("falta", "Falta Injustificada"),
            ("falta_justificada", "Falta Justificada"),
            ("vacaciones", "Vacaciones"),
            ("permiso_goce", "Permiso con Goce"),
            ("permiso_sin_goce", "Permiso sin Goce"),
            ("suspension", "Suspensión IGSS"),
            ("llamada_atencion", "Llamada de Atención"),
            ("felicitacion", "Felicitación"),
            ("descanso", "Descanso / Asueto"),
        ],
        string="Tipo",
        required=True,
        default="asistencia",
        tracking=True,
    )
    hora_entrada = fields.Float(
        string="Hora Entrada",
        help="Hora de entrada en formato 24h (ej. 8.0 = 08:00).",
    )
    hora_salida = fields.Float(
        string="Hora Salida",
        help="Hora de salida en formato 24h (ej. 17.5 = 17:30).",
    )
    horas_trabajadas = fields.Float(
        string="Horas Trabajadas",
        compute="_compute_horas_trabajadas",
        store=True,
        readonly=False,
        help="Horas efectivas del día (descontando el almuerzo configurado "
             "en el empleado).",
    )
    horas_extra = fields.Float(
        string="Horas Extra",
        help="Horas extraordinarias del día (art. 121 Código de Trabajo: se "
             "pagan con al menos 50% de recargo).",
    )
    # --- Fechas-hora para la vista de cuadrícula (grid/gantt) ---
    dt_inicio = fields.Datetime(
        string="Inicio",
        compute="_compute_dt",
        inverse="_inverse_dt",
        store=True,
        index=True,
    )
    dt_fin = fields.Datetime(
        string="Fin",
        compute="_compute_dt",
        inverse="_inverse_dt",
        store=True,
    )
    motivo = fields.Char(
        string="Motivo / Observaciones",
        tracking=True,
    )
    color = fields.Integer(
        string="Color",
        compute="_compute_color",
    )
    descuenta_dia = fields.Boolean(
        string="Descuenta Día",
        compute="_compute_descuenta_dia",
        store=True,
        help="Indica si este registro descuenta un día de sueldo en la planilla.",
    )

    _empleado_fecha_tipo_uniq = models.Constraint(
        "UNIQUE(employee_id, fecha, tipo)",
        "Ya existe un registro de este tipo para el empleado en esa fecha.",
    )

    # ------------------------------------------------------------------
    # Utilidades de horario
    # ------------------------------------------------------------------
    def _tz(self):
        nombre = (self.env.user.tz or self.env.company.partner_id.tz or TZ_GT)
        try:
            return pytz.timezone(nombre)
        except Exception:
            return pytz.timezone(TZ_GT)

    @api.model
    def _horario_empleado(self, employee):
        """(hora_entrada, hora_salida, almuerzo) configurados en el empleado."""
        emp = employee.sudo() if employee else None
        entrada = emp.ktx_pl_hora_entrada if emp and emp.ktx_pl_hora_entrada else 8.0
        salida = emp.ktx_pl_hora_salida if emp and emp.ktx_pl_hora_salida else 17.0
        almuerzo = emp.ktx_pl_almuerzo_horas if emp else 1.0
        return entrada, salida, almuerzo

    def _float_a_time(self, valor):
        horas = int(valor) % 24
        minutos = int(round((valor - int(valor)) * 60))
        if minutos >= 60:
            minutos = 59
        return time(horas, minutos)

    @api.model
    def default_get(self, fields_list):
        """Prellenado desde la cuadrícula: al presionar la celda de un
        empleado/día se crea la asistencia con el horario configurado."""
        res = super().default_get(fields_list)
        ctx = self.env.context
        employee = None
        emp_id = res.get("employee_id") or ctx.get("default_employee_id")
        if emp_id:
            employee = self.env["hr.employee"].browse(emp_id)
        entrada, salida, _alm = self._horario_empleado(employee)

        dt_ini = ctx.get("default_dt_inicio")
        dt_fin = ctx.get("default_dt_fin")
        if dt_ini:
            tz = self._tz()
            ini = fields.Datetime.to_datetime(dt_ini)
            fin = fields.Datetime.to_datetime(dt_fin) if dt_fin else None
            ini_local = pytz.utc.localize(ini).astimezone(tz)
            fin_local = pytz.utc.localize(fin).astimezone(tz) if fin else None
            res.setdefault("fecha", ini_local.date())
            duracion = (fin - ini).total_seconds() / 3600.0 if fin else 24.0
            if duracion >= 23.0:
                # Celda de día completo: usar el horario del empleado
                res.setdefault("hora_entrada", entrada)
                res.setdefault("hora_salida", salida)
            else:
                res.setdefault(
                    "hora_entrada",
                    ini_local.hour + ini_local.minute / 60.0)
                if fin_local:
                    res.setdefault(
                        "hora_salida",
                        fin_local.hour + fin_local.minute / 60.0)
        elif "hora_entrada" in fields_list and not res.get("hora_entrada"):
            res.setdefault("hora_entrada", entrada)
            res.setdefault("hora_salida", salida)
        return res

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("employee_id", "fecha", "tipo")
    def _compute_display_name(self):
        tipos = dict(self._fields["tipo"].selection)
        for rec in self:
            partes = [rec.employee_id.name or "", tipos.get(rec.tipo, "")]
            if rec.fecha:
                partes.append(fields.Date.to_string(rec.fecha))
            rec.display_name = " · ".join(p for p in partes if p)

    @api.onchange("employee_id", "tipo")
    def _onchange_employee_horario(self):
        if self.employee_id and self.tipo == "asistencia" and \
                not self.hora_entrada and not self.hora_salida:
            entrada, salida, _alm = self._horario_empleado(self.employee_id)
            self.hora_entrada = entrada
            self.hora_salida = salida

    @api.depends("hora_entrada", "hora_salida", "tipo", "employee_id")
    def _compute_horas_trabajadas(self):
        for rec in self:
            if rec.hora_salida and rec.hora_entrada and \
                    rec.hora_salida > rec.hora_entrada:
                _e, _s, almuerzo = self._horario_empleado(rec.employee_id)
                span = rec.hora_salida - rec.hora_entrada
                rec.horas_trabajadas = max(span - (almuerzo or 0.0), 0.0) \
                    if span > (almuerzo or 0.0) else span
            elif not rec.horas_trabajadas:
                rec.horas_trabajadas = 0.0

    @api.depends("fecha", "hora_entrada", "hora_salida", "tipo", "employee_id")
    def _compute_dt(self):
        for rec in self:
            if not rec.fecha:
                rec.dt_inicio = False
                rec.dt_fin = False
                continue
            tz = rec._tz()
            entrada, salida, _alm = self._horario_empleado(rec.employee_id)
            h_ini = rec.hora_entrada or entrada
            h_fin = rec.hora_salida or salida
            if h_fin <= h_ini:
                h_fin = min(h_ini + 1.0, 23.98)
            ini_local = tz.localize(
                datetime.combine(rec.fecha, rec._float_a_time(h_ini)))
            fin_local = tz.localize(
                datetime.combine(rec.fecha, rec._float_a_time(h_fin)))
            rec.dt_inicio = ini_local.astimezone(pytz.utc).replace(tzinfo=None)
            rec.dt_fin = fin_local.astimezone(pytz.utc).replace(tzinfo=None)

    def _inverse_dt(self):
        for rec in self:
            if not rec.dt_inicio:
                continue
            tz = rec._tz()
            ini_local = pytz.utc.localize(rec.dt_inicio).astimezone(tz)
            rec.fecha = ini_local.date()
            rec.hora_entrada = ini_local.hour + ini_local.minute / 60.0
            if rec.dt_fin:
                fin_local = pytz.utc.localize(rec.dt_fin).astimezone(tz)
                # Si el fin cae en otro día (celda de día completo del grid),
                # se recorta al horario configurado del empleado.
                if fin_local.date() != ini_local.date():
                    entrada, salida, _alm = self._horario_empleado(
                        rec.employee_id)
                    rec.hora_entrada = entrada
                    rec.hora_salida = salida
                else:
                    rec.hora_salida = (
                        fin_local.hour + fin_local.minute / 60.0)

    def _compute_color(self):
        for rec in self:
            rec.color = COLOR_POR_TIPO.get(rec.tipo, 0)

    @api.depends("tipo")
    def _compute_descuenta_dia(self):
        for rec in self:
            rec.descuenta_dia = rec.tipo in TIPOS_DESCUENTO

    @api.constrains("hora_entrada", "hora_salida")
    def _check_horas(self):
        for rec in self:
            for valor in (rec.hora_entrada, rec.hora_salida):
                if valor and not 0.0 <= valor < 24.0:
                    raise ValidationError(
                        _("Las horas deben estar entre 0:00 y 23:59."))
