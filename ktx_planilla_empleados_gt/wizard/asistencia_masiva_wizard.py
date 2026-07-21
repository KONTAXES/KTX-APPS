# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AsistenciaMasivaWizard(models.TransientModel):
    _name = "ktx.planilla.asistencia.masiva"
    _description = "Captura Masiva de Asistencias"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Empleados",
        required=True,
        domain="[('company_id', '=', company_id)]",
    )
    date_from = fields.Date(
        string="Desde",
        required=True,
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        string="Hasta",
        required=True,
        default=fields.Date.context_today,
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
    )
    usar_horario_empleado = fields.Boolean(
        string="Usar Horario del Empleado",
        default=True,
        help="Usa la hora de entrada/salida configurada en la pestaña "
             "Planilla GT de cada empleado. Desactive para fijar un horario "
             "único para todos.",
    )
    hora_entrada = fields.Float(string="Hora Entrada", default=8.0)
    hora_salida = fields.Float(string="Hora Salida", default=17.0)
    incluir_sabados = fields.Boolean(string="Incluir Sábados", default=True)
    incluir_domingos = fields.Boolean(string="Incluir Domingos", default=False)
    motivo = fields.Char(string="Motivo / Observaciones")
    sobrescribir = fields.Boolean(
        string="Sobrescribir Existentes",
        help="Si está activo, los registros existentes del mismo tipo en el "
             "rango se actualizan en lugar de omitirse.",
    )

    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from and (not self.date_to or self.date_to < self.date_from):
            self.date_to = self.date_from

    def action_generar(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_("La fecha final debe ser mayor o igual a la inicial."))
        if (self.date_to - self.date_from).days > 366:
            raise UserError(_("El rango no puede ser mayor a un año."))

        Asistencia = self.env["ktx.planilla.asistencia"]
        con_horario = self.tipo == "asistencia"
        creados = actualizados = 0
        for empleado in self.employee_ids:
            if con_horario and self.usar_horario_empleado:
                entrada, salida, _alm = Asistencia._horario_empleado(empleado)
            else:
                entrada, salida = self.hora_entrada, self.hora_salida
            fecha = self.date_from
            while fecha <= self.date_to:
                dia_semana = fecha.weekday()  # 5 = sábado, 6 = domingo
                if (dia_semana == 5 and not self.incluir_sabados) or \
                   (dia_semana == 6 and not self.incluir_domingos):
                    fecha += timedelta(days=1)
                    continue
                existente = Asistencia.search([
                    ("employee_id", "=", empleado.id),
                    ("fecha", "=", fecha),
                    ("tipo", "=", self.tipo),
                ], limit=1)
                vals = {
                    "employee_id": empleado.id,
                    "company_id": self.company_id.id,
                    "fecha": fecha,
                    "tipo": self.tipo,
                    "hora_entrada": entrada if con_horario else 0.0,
                    "hora_salida": salida if con_horario else 0.0,
                    "motivo": self.motivo,
                }
                if existente:
                    if self.sobrescribir:
                        existente.write(vals)
                        actualizados += 1
                else:
                    Asistencia.create(vals)
                    creados += 1
                fecha += timedelta(days=1)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Asistencias generadas"),
                "message": _("%(c)s registros creados, %(a)s actualizados.",
                             c=creados, a=actualizados),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
