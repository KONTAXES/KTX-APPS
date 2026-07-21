# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

GANTT_ARCH = """<gantt string="Asistencias"
       date_start="dt_inicio"
       date_stop="dt_fin"
       default_group_by="employee_id"
       color="color">
    <field name="employee_id"/>
    <field name="tipo"/>
    <field name="motivo"/>
</gantt>"""


def post_init_hook(env):
    """Crea la vista de cuadrícula (gantt) de asistencias si la instancia
    tiene el módulo web_gantt (Odoo Enterprise). En Community el módulo
    funciona igual con calendario, lista, kanban y pivot."""
    web_gantt = env["ir.module.module"].search(
        [("name", "=", "web_gantt"), ("state", "=", "installed")], limit=1)
    if not web_gantt:
        _logger.info(
            "web_gantt no está instalado: se omite la vista de cuadrícula "
            "de asistencias de Planilla GT.")
        return
    try:
        view = env["ir.ui.view"].search([
            ("model", "=", "ktx.planilla.asistencia"),
            ("type", "=", "gantt"),
        ], limit=1)
        if not view:
            view = env["ir.ui.view"].create({
                "name": "ktx.planilla.asistencia.gantt",
                "model": "ktx.planilla.asistencia",
                "type": "gantt",
                "arch": GANTT_ARCH,
            })
            env["ir.model.data"].create({
                "name": "view_asistencia_gantt",
                "module": "ktx_planilla_empleados_gt",
                "model": "ir.ui.view",
                "res_id": view.id,
                "noupdate": True,
            })
        accion = env.ref(
            "ktx_planilla_empleados_gt.action_asistencia",
            raise_if_not_found=False)
        if accion and "gantt" not in (accion.view_mode or ""):
            accion.view_mode = "gantt," + accion.view_mode
        _logger.info("Vista de cuadrícula (gantt) de asistencias creada.")
    except Exception as e:
        _logger.warning(
            "No se pudo crear la vista gantt de asistencias (%s); el módulo "
            "sigue funcionando con calendario, lista, kanban y pivot.", e)
