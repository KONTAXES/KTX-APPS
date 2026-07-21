# -*- coding: utf-8 -*-
import calendar
import io
import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ktx_check_print.utils.amount_in_words import amount_to_words_es

_logger = logging.getLogger(__name__)

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre",
    11: "Noviembre", 12: "Diciembre",
}


class Planilla(models.Model):
    _name = "ktx.planilla"
    _description = "Planilla de Empleados GT"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_to desc, name desc"
    _check_company_auto = True

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        default="/",
        index=True,
        tracking=True,
    )
    numero = fields.Integer(
        string="Planilla No.",
        help="Número correlativo que se imprime en el encabezado del reporte "
             "(libro de salarios, art. 102 Código de Trabajo).",
    )
    tipo = fields.Selection(
        selection=[
            ("sueldo", "Sueldos y Salarios"),
            ("bono14", "Bonificación Anual (Bono 14)"),
            ("aguinaldo", "Aguinaldo"),
            ("vacaciones", "Vacaciones"),
            ("liquidacion", "Liquidación"),
        ],
        string="Tipo de Planilla",
        required=True,
        default="sueldo",
        tracking=True,
    )
    periodicidad = fields.Selection(
        selection=[
            ("mensual", "Mensual"),
            ("quincenal", "Quincenal"),
            ("semanal", "Semanal"),
            ("diario", "Por Día"),
            ("evento", "Por Evento / Obra"),
        ],
        string="Periodicidad",
        default="mensual",
        required=True,
        tracking=True,
        help="Determina el período que cubre la planilla y la proporción del "
             "sueldo base a pagar.",
    )
    date_from = fields.Date(
        string="Del",
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
        tracking=True,
    )
    date_to = fields.Date(
        string="Al",
        required=True,
        default=lambda self: (
            fields.Date.context_today(self).replace(day=1)
            + relativedelta(months=1, days=-1)
        ),
        tracking=True,
    )
    fecha_contable = fields.Date(
        string="Fecha Contable",
        help="Fecha de las partidas contables. Si se deja vacía se usa la "
             "fecha final del período.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Moneda",
        related="company_id.currency_id",
        store=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario Contable",
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        check_company=True,
        default=lambda self: self.env.company.ktx_pl_journal_id,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Borrador"),
            ("calculated", "Calculada"),
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
    employee_ids = fields.Many2many(
        "hr.employee",
        string="Empleados a Incluir",
        domain="[('company_id', '=', company_id)]",
        help="Si se deja vacío, al calcular se incluyen todos los empleados "
             "activos de la compañía con sueldo base y la misma frecuencia "
             "de pago de la planilla.",
    )
    line_ids = fields.One2many(
        "ktx.planilla.linea",
        "planilla_id",
        string="Líneas",
        copy=False,
    )
    liquidacion_id = fields.Many2one(
        "ktx.planilla.liquidacion",
        string="Liquidación Origen",
        copy=False,
        readonly=True,
    )
    es_anticipo = fields.Boolean(
        string="Es Anticipo de Salario",
        compute="_compute_es_anticipo",
        store=True,
        help="Las planillas de sueldos no mensuales (quincenal, semanal, "
             "por día, por evento) se registran como ANTICIPO de salarios: "
             "la partida carga la cuenta de Anticipos a Empleados contra "
             "Sueldos por Pagar, y el pago cancela el por pagar contra el "
             "banco. La planilla oficial del mes (mensual) consolida el "
             "salario completo, aplica IGSS/ISR/provisiones y compensa los "
             "anticipos del período.",
    )
    anticipo_linea_ids = fields.Many2many(
        "ktx.planilla.linea",
        string="Anticipos del Mes",
        compute="_compute_anticipo_linea_ids",
        help="Líneas de las planillas de anticipo (quincenal, semanal, "
             "diario) del mismo mes que consolida esta planilla mensual.",
    )
    notas = fields.Text(string="Notas")

    # --- Totales ---
    total_devengado = fields.Monetary(
        compute="_compute_totales", store=True, string="Total Devengado")
    total_descuentos = fields.Monetary(
        compute="_compute_totales", store=True, string="Total Descuentos")
    total_liquido = fields.Monetary(
        compute="_compute_totales", store=True, string="Total Líquido")
    total_patronal = fields.Monetary(
        compute="_compute_totales", store=True, string="Total Cuota Patronal")
    total_provisiones = fields.Monetary(
        compute="_compute_totales", store=True, string="Total Provisiones")
    empleados_count = fields.Integer(
        compute="_compute_totales", store=True, string="No. Empleados")
    pagos_count = fields.Integer(compute="_compute_pagos_count")
    asientos_count = fields.Integer(compute="_compute_asientos_count")
    payment_progress = fields.Float(
        compute="_compute_payment_progress", string="Avance de Pago (%)")

    mes_nombre = fields.Char(compute="_compute_mes_nombre", string="Mes")

    _fechas_check = models.Constraint(
        "CHECK(date_to >= date_from)",
        "La fecha final del período debe ser posterior a la inicial.",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends(
        "line_ids.total_devengado", "line_ids.total_descuentos",
        "line_ids.total_liquido", "line_ids.total_patronal",
        "line_ids.total_provisiones",
    )
    def _compute_totales(self):
        for pl in self:
            pl.total_devengado = sum(pl.line_ids.mapped("total_devengado"))
            pl.total_descuentos = sum(pl.line_ids.mapped("total_descuentos"))
            pl.total_liquido = sum(pl.line_ids.mapped("total_liquido"))
            pl.total_patronal = sum(pl.line_ids.mapped("total_patronal"))
            pl.total_provisiones = sum(pl.line_ids.mapped("total_provisiones"))
            pl.empleados_count = len(pl.line_ids)

    def _compute_pagos_count(self):
        for pl in self:
            pl.pagos_count = len(pl.line_ids.payment_ids)

    def _compute_asientos_count(self):
        for pl in self:
            pl.asientos_count = len(pl.line_ids.move_id)

    def _compute_payment_progress(self):
        for pl in self:
            total = len(pl.line_ids)
            pagadas = len(pl.line_ids.filtered("pagada"))
            pl.payment_progress = (pagadas / total * 100.0) if total else 0.0

    def _compute_mes_nombre(self):
        for pl in self:
            pl.mes_nombre = (
                "%s de %s" % (MESES_ES[pl.date_to.month], pl.date_to.year)
                if pl.date_to else ""
            )

    @api.depends("tipo", "periodicidad")
    def _compute_es_anticipo(self):
        for pl in self:
            pl.es_anticipo = (
                pl.tipo == "sueldo" and pl.periodicidad != "mensual")

    def _compute_anticipo_linea_ids(self):
        Linea = self.env["ktx.planilla.linea"]
        for pl in self:
            if pl.tipo != "sueldo" or pl.periodicidad != "mensual" \
                    or not (pl.date_from and pl.date_to):
                pl.anticipo_linea_ids = False
                continue
            pl.anticipo_linea_ids = Linea.search([
                ("company_id", "=", pl.company_id.id),
                ("planilla_id.es_anticipo", "=", True),
                ("planilla_id.state", "!=", "cancel"),
                ("date_to", ">=", pl.date_from),
                ("date_to", "<=", pl.date_to),
            ])

    @api.onchange("periodicidad")
    def _onchange_periodicidad(self):
        hoy = fields.Date.context_today(self)
        if self.periodicidad == "mensual":
            self.date_from = hoy.replace(day=1)
            self.date_to = hoy.replace(day=1) + relativedelta(months=1, days=-1)
        elif self.periodicidad == "quincenal":
            if hoy.day <= 15:
                self.date_from = hoy.replace(day=1)
                self.date_to = hoy.replace(day=15)
            else:
                self.date_from = hoy.replace(day=16)
                self.date_to = hoy.replace(day=1) + relativedelta(months=1, days=-1)
        elif self.periodicidad == "semanal":
            self.date_from = hoy - relativedelta(days=hoy.weekday())
            self.date_to = self.date_from + relativedelta(days=6)

    @api.onchange("tipo")
    def _onchange_tipo(self):
        hoy = fields.Date.context_today(self)
        if self.tipo == "bono14":
            # Período legal del Bono 14: 1 de julio a 30 de junio (Decreto 42-92)
            anio = hoy.year if hoy.month >= 7 else hoy.year - 1
            self.date_from = date(anio - 1, 7, 1)
            self.date_to = date(anio, 6, 30)
        elif self.tipo == "aguinaldo":
            # Período legal del aguinaldo: 1 de diciembre a 30 de noviembre (Decreto 76-78)
            anio = hoy.year if hoy.month >= 12 else hoy.year
            self.date_from = date(anio - 1, 12, 1)
            self.date_to = date(anio, 11, 30)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "ktx.planilla") or "/"
            if not vals.get("numero"):
                vals["numero"] = self.search_count([
                    ("company_id", "=", vals.get("company_id", self.env.company.id)),
                    ("tipo", "=", vals.get("tipo", "sueldo")),
                ]) + 1
        return super().create(vals_list)

    def unlink(self):
        if any(pl.state not in ("draft", "cancel") for pl in self):
            raise UserError(
                _("Solo se pueden eliminar planillas en borrador o canceladas."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Cálculo
    # ------------------------------------------------------------------
    def _empleados_a_incluir(self):
        self.ensure_one()
        if self.employee_ids:
            return self.employee_ids
        domain = [
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ]
        empleados = self.env["hr.employee"].search(domain)
        if self.tipo == "sueldo" and self.periodicidad != "mensual":
            # Planilla de anticipo: solo empleados con esa frecuencia de pago
            empleados = empleados.filtered(
                lambda e: e.ktx_pl_sueldo_base > 0
                and e.ktx_pl_frecuencia_pago == self.periodicidad
            )
        else:
            # Planilla mensual oficial (y prestaciones): todos los empleados,
            # sin importar la frecuencia con la que se les anticipa.
            empleados = empleados.filtered(lambda e: e.ktx_pl_sueldo_base > 0)
        return empleados

    def action_calcular(self):
        for pl in self:
            if pl.state not in ("draft", "calculated"):
                raise UserError(
                    _("Solo se pueden calcular planillas en borrador."))
            if pl.tipo == "liquidacion" and not pl.liquidacion_id:
                raise UserError(
                    _("Las planillas de liquidación se generan desde el "
                      "documento de Liquidación de Prestaciones."))
            pl.line_ids.filtered(lambda l: not l.pagada).unlink()
            empleados = pl._empleados_a_incluir() - pl.line_ids.employee_id
            lineas = []
            for num, emp in enumerate(empleados.sorted("name"), start=len(pl.line_ids) + 1):
                vals = pl._preparar_linea(emp)
                vals["secuencia"] = num
                lineas.append(vals)
            self.env["ktx.planilla.linea"].create(lineas)
            pl.line_ids._recalcular()
            pl.state = "calculated"
        return True

    def _preparar_linea(self, empleado):
        self.ensure_one()
        return {
            "planilla_id": self.id,
            "employee_id": empleado.id,
            "puesto": empleado.job_title or empleado.job_id.name or "",
        }

    def action_regresar_borrador(self):
        for pl in self:
            if pl.line_ids.move_id.filtered(lambda m: m.state == "posted"):
                raise UserError(
                    _("La planilla tiene partidas contables publicadas. "
                      "Cancélelas antes de regresar a borrador."))
            pl.state = "draft"
        return True

    def action_cancelar(self):
        for pl in self:
            if pl.line_ids.payment_ids.filtered(lambda p: p.state not in ("draft", "canceled")):
                raise UserError(
                    _("La planilla tiene pagos registrados; anúlelos primero."))
            moves = pl.line_ids.move_id
            moves.filtered(lambda m: m.state == "posted").button_draft()
            moves.with_context(force_delete=True).unlink()
            pl.state = "cancel"
        return True

    # ------------------------------------------------------------------
    # Contabilización: una partida por empleado
    # ------------------------------------------------------------------
    def action_contabilizar(self):
        for pl in self:
            if pl.state != "calculated":
                raise UserError(
                    _("Primero calcule la planilla."))
            if not pl.line_ids:
                raise UserError(_("La planilla no tiene líneas."))
            journal = pl.journal_id or pl.company_id.ktx_pl_journal_id
            if not journal:
                raise UserError(
                    _("Configure el diario de planilla en Ajustes → Planilla GT."))
            for linea in pl.line_ids.filtered(lambda l: not l.move_id):
                move = linea._crear_asiento(journal)
                linea.move_id = move
                move.action_post()
                if not pl.es_anticipo and linea.anticipos:
                    linea._conciliar_anticipos()
            pl.state = "posted"
            pl.message_post(body=_(
                "Planilla contabilizada: %s partidas generadas.") % len(pl.line_ids))
        return True

    def action_registrar_pagos(self):
        self.ensure_one()
        if self.state not in ("posted", "paid"):
            raise UserError(_("Primero contabilice la planilla."))
        lineas = self.line_ids.filtered(lambda l: not l.pagada)
        if not lineas:
            raise UserError(_("Todas las líneas ya están pagadas."))
        wizard = self.env["ktx.planilla.pago.wizard"].create({
            "planilla_id": self.id,
            "linea_ids": [(6, 0, lineas.ids)],
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Registrar Pago de Planilla"),
            "res_model": "ktx.planilla.pago.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _actualizar_estado_pago(self):
        for pl in self:
            if pl.state == "posted" and pl.line_ids and all(
                    l.pagada for l in pl.line_ids):
                pl.state = "paid"

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------
    def action_ver_asientos(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Partidas de %s") % self.name,
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.line_ids.move_id.ids)],
        }

    def action_ver_pagos(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pagos de %s") % self.name,
            "res_model": "account.payment",
            "view_mode": "list,form",
            "domain": [("id", "in", self.line_ids.payment_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Reportes
    # ------------------------------------------------------------------
    def _total_devengado_letras(self):
        self.ensure_one()
        return amount_to_words_es(self.total_devengado).capitalize()

    def _total_liquido_letras(self):
        self.ensure_one()
        return amount_to_words_es(self.total_liquido).capitalize()

    def _titulo_reporte(self):
        self.ensure_one()
        titulos = {
            "sueldo": _("Planilla de Sueldos"),
            "bono14": _("Planilla de Bonificación Anual (Bono 14)"),
            "aguinaldo": _("Planilla de Aguinaldo"),
            "vacaciones": _("Planilla de Vacaciones"),
            "liquidacion": _("Planilla de Liquidación"),
        }
        return titulos.get(self.tipo, _("Planilla"))

    def action_imprimir_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "ktx_planilla_empleados_gt.action_report_planilla"
        ).report_action(self)

    def action_exportar_excel(self):
        """Genera la planilla en Excel con el formato del libro de salarios."""
        self.ensure_one()
        try:
            import xlsxwriter  # noqa: F401
        except ImportError:
            raise UserError(
                _("xlsxwriter no está instalado. Ejecute: pip install xlsxwriter"))
        import base64

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = wb.add_worksheet(_("Planilla"))
        ws.set_landscape()
        ws.set_paper(5)  # oficio/legal
        ws.fit_to_pages(1, 0)

        f_title = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "font_size": 12})
        f_sub = wb.add_format({"align": "center", "font_size": 9})
        f_head = wb.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "border": 1, "text_wrap": True, "bg_color": "#DDEBF7",
            "font_size": 8})
        f_txt = wb.add_format({"border": 1, "font_size": 8})
        f_num = wb.add_format({
            "border": 1, "num_format": "#,##0.00", "font_size": 8})
        f_tot = wb.add_format({
            "border": 1, "bold": True, "num_format": "#,##0.00",
            "bg_color": "#F2F2F2", "font_size": 8})
        f_leyenda = wb.add_format({"font_size": 8})

        headers = [
            (_("No."), 4), (_("Nombres"), 24), (_("Puesto"), 14),
            (_("Sueldo Ordinario"), 10), (_("Sueldo Extraordinario"), 10),
            (_("Comisiones"), 10), (_("Bonificaciones"), 10), (_("Otros"), 8),
            (_("Total Devengado"), 11), (_("IGSS"), 9), (_("ISR"), 8),
            (_("Anticipo"), 8), (_("Judiciales"), 8), (_("Otros Desc."), 8),
            (_("Total Descuentos"), 11), (_("Total Líquido"), 11),
            (_("Firma"), 14),
        ]
        ncols = len(headers)

        ws.merge_range(0, 0, 0, ncols - 1,
                       _("Nombre de la Empresa: %s") % (self.company_id.name or ""),
                       f_title)
        ws.merge_range(
            1, 0, 1, ncols - 1,
            _("%(titulo)s No. %(num)s, correspondiente a %(mes)s. "
              "(cifras en %(moneda)s)") % {
                "titulo": self._titulo_reporte(),
                "num": self.numero or "",
                "mes": self.mes_nombre,
                "moneda": self.currency_id.name or "Quetzales",
            },
            f_sub)

        row = 3
        for col, (texto, ancho) in enumerate(headers):
            ws.set_column(col, col, ancho)
            ws.write(row, col, texto, f_head)
        row += 1

        for linea in self.line_ids.sorted("secuencia"):
            ws.write(row, 0, linea.secuencia, f_txt)
            ws.write(row, 1, linea.employee_id.name or "", f_txt)
            ws.write(row, 2, linea.puesto or "", f_txt)
            ws.write(row, 3, linea.sueldo_ordinario, f_num)
            ws.write(row, 4, linea.sueldo_extraordinario, f_num)
            ws.write(row, 5, linea.comisiones, f_num)
            ws.write(row, 6, linea.bonificacion_incentivo, f_num)
            ws.write(row, 7, linea.otros_ingresos, f_num)
            ws.write(row, 8, linea.total_devengado, f_num)
            ws.write(row, 9, linea.igss_laboral, f_num)
            ws.write(row, 10, linea.isr, f_num)
            ws.write(row, 11, linea.anticipos, f_num)
            ws.write(row, 12, linea.judiciales, f_num)
            ws.write(row, 13, linea.otros_descuentos, f_num)
            ws.write(row, 14, linea.total_descuentos, f_num)
            ws.write(row, 15, linea.total_liquido, f_num)
            ws.write(row, 16, "", f_txt)
            row += 1

        ws.write(row, 1, _("Totales"), f_tot)
        ws.write(row, 0, "", f_tot)
        ws.write(row, 2, "", f_tot)
        for col, campo in [
            (3, "sueldo_ordinario"), (4, "sueldo_extraordinario"),
            (5, "comisiones"), (6, "bonificacion_incentivo"),
            (7, "otros_ingresos"), (8, "total_devengado"),
            (9, "igss_laboral"), (10, "isr"), (11, "anticipos"),
            (12, "judiciales"), (13, "otros_descuentos"),
            (14, "total_descuentos"), (15, "total_liquido"),
        ]:
            ws.write(row, col, sum(self.line_ids.mapped(campo)), f_tot)
        ws.write(row, 16, "", f_tot)
        row += 2

        ws.merge_range(
            row, 0, row, ncols - 1,
            _("De conformidad con los datos anteriores, el total devengado de "
              "la planilla asciende a la cantidad de: %s")
            % self._total_devengado_letras(), f_leyenda)
        row += 1
        ws.merge_range(
            row, 0, row, ncols - 1,
            _("Un total líquido de: %s") % self._total_liquido_letras(),
            f_leyenda)
        row += 2
        d = self.date_to or fields.Date.context_today(self)
        ws.merge_range(
            row, 0, row, ncols - 1,
            _("Guatemala, %(dia)s de %(mes)s de %(anio)s") % {
                "dia": d.day, "mes": MESES_ES[d.month].lower(), "anio": d.year},
            f_sub)
        row += 3
        f_firma = wb.add_format({"align": "center", "font_size": 8, "top": 1})
        ws.merge_range(row, 5, row, 10,
                       self.company_id.ktx_pl_contador_nombre or " ", f_firma)
        row += 1
        ws.merge_range(
            row, 5, row, 10,
            _("Perito Contador No. %s")
            % (self.company_id.ktx_pl_contador_registro or "________"), f_sub)

        wb.close()
        filename = "%s_%s.xlsx" % (
            self._titulo_reporte().replace(" ", "_"), self.name.replace("/", "-"))
        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(output.getvalue()).decode(),
            "res_model": self._name,
            "res_id": self.id,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }

    # ------------------------------------------------------------------
    # Utilidades de período
    # ------------------------------------------------------------------
    def _dias_base_periodo(self):
        """Días base del período para prorratear el sueldo.

        Para períodos mensuales completos devuelve los días del mes calendario
        (28-31) de modo que el mes completo pague el sueldo íntegro.
        """
        self.ensure_one()
        if self.periodicidad == "mensual":
            return calendar.monthrange(self.date_to.year, self.date_to.month)[1]
        if self.periodicidad == "quincenal":
            return calendar.monthrange(self.date_to.year, self.date_to.month)[1]
        return max((self.date_to - self.date_from).days + 1, 1)
