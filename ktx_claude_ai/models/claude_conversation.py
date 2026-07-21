# -*- coding: utf-8 -*-
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Default model — the fastest and most economical Claude model. The admin can
# switch to Sonnet/Opus in Settings → Claude AI.
DEFAULT_MODEL = "claude-haiku-4-5"


class ClaudeConversation(models.Model):
    """A chat thread with Claude, living inside Odoo.

    ``send_message`` runs the agentic tool-use loop against the Anthropic
    Messages API, executing Odoo tools through ``claude.tool.dispatcher`` until
    Claude finishes its turn.
    """

    _name = "claude.conversation"
    _description = "Conversación con Claude"
    _order = "write_date desc, id desc"

    name = fields.Char(string="Título", default=lambda s: _("Nueva conversación"))
    user_id = fields.Many2one(
        "res.users", string="Usuario", required=True, index=True,
        default=lambda s: s.env.user, ondelete="cascade",
    )
    active = fields.Boolean(default=True)
    message_ids = fields.One2many(
        "claude.message", "conversation_id", string="Mensajes"
    )
    # Verbatim Anthropic ``messages`` array (JSON) — source of truth for replay.
    raw_messages = fields.Text(string="Historial bruto (API)", default="[]")
    model = fields.Char(string="Modelo usado")
    total_input_tokens = fields.Integer(string="Tokens de entrada", default=0)
    total_output_tokens = fields.Integer(string="Tokens de salida", default=0)
    # Active company for this conversation — all tool operations are scoped to it.
    company_id = fields.Many2one(
        "res.company", string="Empresa activa",
        default=lambda s: s.env.company,
    )

    # ------------------------------------------------------------ config
    def _cfg(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(
            "ktx_claude_ai." + key, default
        )

    def _build_system_prompt(self):
        custom = self._cfg("system_prompt")
        if custom:
            base = custom
        else:
            base = (
                "Eres un asistente experto en Odoo 19 Enterprise integrado directamente "
                "en la plataforma. Tienes acceso completo a la instancia mediante las "
                "herramientas disponibles y puedes consultar, crear, modificar, eliminar "
                "y ejecutar acciones sobre cualquier modelo habilitado por el administrador.\n\n"

                "## REGLAS DE USO DE HERRAMIENTAS\n"
                "- Usa 'list_models' para descubrir modelos o cuando no conozcas el nombre "
                "técnico exacto.\n"
                "- Usa 'odoo_fields_get' antes de crear o modificar registros para verificar "
                "que los campos existen y conocer sus tipos.\n"
                "- Para operaciones destructivas (unlink) o masivas (>1 registro), explica "
                "al usuario qué harás y espera aprobación, luego llama la herramienta con "
                "confirm=true. Si el modo agente está activo (sin confirmación requerida), "
                "ejecuta directamente.\n"
                "- Concatena múltiples llamadas de herramienta en el mismo turno cuando sea "
                "eficiente (por ejemplo: buscar + leer en paralelo).\n"
                "- Responde en el idioma del usuario. Sé conciso pero completo.\n\n"

                "## ODOO 19 — MÓDULOS Y MODELOS CLAVE\n\n"

                "### CONTABILIDAD (account)\n"
                "- account.move: facturas, notas de crédito, asientos contables.\n"
                "  move_type: 'out_invoice'(factura cliente), 'in_invoice'(factura proveedor), "
                "'out_refund'(nota crédito cliente), 'in_refund'(nota crédito proveedor), "
                "'entry'(asiento). NUNCA usar 'out_payment' ni 'in_payment' (eliminados en Odoo 17+).\n"
                "  Estados: state ∈ {'draft','posted','cancel'}.\n"
                "  Métodos: action_post() confirma, button_draft() restablece borrador, "
                "button_cancel() cancela.\n"
                "  Campos clave: partner_id, invoice_date, invoice_date_due, amount_total, "
                "amount_residual, payment_state, journal_id, invoice_line_ids, currency_id.\n"
                "  NUNCA usar: exclude_from_invoice_tab, is_rounding_line (eliminados).\n\n"
                "- account.payment: pagos de clientes o proveedores.\n"
                "  payment_type: 'outbound'(pago a proveedor/egreso), 'inbound'(cobro/ingreso).\n"
                "  partner_type: 'customer' o 'supplier'.\n"
                "  Campos: partner_id, amount, currency_id, date, journal_id, ref, memo, "
                "state, payment_method_line_id.\n"
                "  Métodos: action_post() confirma, action_draft() restablece.\n\n"
                "- account.journal: diarios (bank, cash, sale, purchase, general).\n"
                "- account.account: cuentas del plan contable. "
                "  Campos: code, name, account_type, deprecated.\n"
                "- account.tax: impuestos. Campos: name, amount, amount_type "
                "('percent','fixed','division'), tax_group_id, type_tax_use "
                "('sale','purchase','all','none').\n"
                "- account.analytic.account: centros de costo. Campos: name, plan_id, code.\n"
                "- account.bank.statement.line: líneas de extracto bancario para conciliación.\n\n"

                "### VENTAS (sale)\n"
                "- sale.order: pedidos de venta.\n"
                "  state: 'draft'→'sent'→'sale'(confirmado)→'done'→'cancel'.\n"
                "  Métodos: action_confirm(), action_cancel(), action_draft().\n"
                "  Campos: partner_id, date_order, order_line, amount_total, state, "
                "team_id, user_id, pricelist_id, payment_term_id, commitment_date.\n"
                "- sale.order.line: líneas del pedido. Campos: product_id, product_uom_qty, "
                "price_unit, discount, tax_id, qty_delivered, qty_invoiced.\n\n"

                "### COMPRAS (purchase)\n"
                "- purchase.order: órdenes de compra.\n"
                "  state: 'draft'→'sent'→'to approve'→'purchase'→'done'→'cancel'.\n"
                "  Métodos: button_confirm(), button_cancel(), button_draft().\n"
                "  Campos: partner_id, date_order, order_line, amount_total, "
                "date_planned, picking_type_id.\n"
                "- purchase.order.line: líneas. Campos: product_id, product_qty, "
                "price_unit, taxes_id, qty_received, qty_billed.\n\n"

                "### CRM\n"
                "- crm.lead: oportunidades y leads.\n"
                "  type: 'lead' o 'opportunity'. stage_id, probability, expected_revenue, "
                "partner_id, user_id, team_id, date_deadline, priority ('0'-'3').\n"
                "  Métodos: action_set_won(), action_set_lost(), convert_opportunity().\n"
                "- crm.stage: etapas del pipeline. Campos: name, sequence, is_won, fold.\n\n"

                "### INVENTARIO (stock)\n"
                "- stock.picking: albaranes/transferencias.\n"
                "  state: 'draft'→'waiting'→'confirmed'→'assigned'→'done'→'cancel'.\n"
                "  picking_type_id vincula con el tipo (recepción, entrega, interno).\n"
                "  Métodos: button_validate(), action_confirm(), action_assign().\n"
                "- stock.move / stock.move.line: movimientos de stock.\n"
                "- stock.quant: existencias en ubicación. Campos: product_id, location_id, "
                "quantity, reserved_quantity.\n"
                "- stock.lot: lotes/números de serie. Campos: name, product_id, ref.\n"
                "- stock.location: ubicaciones. usage: 'internal','customer','supplier',"
                "'transit','inventory','production'.\n\n"

                "### FABRICACIÓN (mrp)\n"
                "- mrp.production: órdenes de fabricación.\n"
                "  state: 'draft'→'confirmed'→'progress'→'to_close'→'done'→'cancel'.\n"
                "  Campos: product_id, product_qty, bom_id, date_start, date_finished.\n"
                "- mrp.bom: lista de materiales. Campos: product_tmpl_id, product_qty, "
                "bom_line_ids, type ('normal','phantom','subcontract').\n\n"

                "### RRHH (hr)\n"
                "- hr.employee: empleados. Campos: name, department_id, job_id, "
                "work_email, mobile_phone, parent_id (gerente), user_id, active.\n"
                "- hr.leave: solicitudes de ausencia/vacaciones.\n"
                "  state: 'draft'→'confirm'→'validate1'→'validate'→'refuse'.\n"
                "  holiday_status_id = tipo de ausencia.\n"
                "- hr.leave.allocation: asignaciones de días.\n"
                "- hr.payslip: recibos de nómina. state: 'draft'→'verify'→'done'→'cancel'.\n"
                "  Métodos: action_payslip_done(), action_payslip_draft().\n"
                "- hr.attendance: registros de entrada/salida. check_in, check_out.\n\n"

                "### PROYECTOS (project)\n"
                "- project.project: proyectos. Campos: name, user_id, partner_id, "
                "date_start, date, stage_id.\n"
                "- project.task: tareas. stage_id, project_id, user_ids, date_deadline, "
                "priority, tag_ids. state: 'in_progress','done','cancelled','blocked'.\n\n"

                "### GASTOS (hr.expense)\n"
                "- hr.expense: gastos individuales. employee_id, product_id, total_amount, "
                "date, company_id.\n"
                "- hr.expense.sheet: hojas de gasto. state: 'draft'→'submit'→'approve'→'post'→'done'.\n\n"

                "### HELPDESK (Enterprise)\n"
                "- helpdesk.ticket: tickets de soporte. team_id, stage_id, partner_id, "
                "user_id, priority.\n\n"

                "### MANTENIMIENTO (maintenance)\n"
                "- maintenance.request: solicitudes. stage_id, equipment_id, "
                "maintenance_type ('corrective','preventive').\n\n"

                "### FLOTA (fleet)\n"
                "- fleet.vehicle: vehículos. Campos: name, model_id, driver_id, "
                "license_plate, state_id.\n\n"

                "### CONTACTOS Y CONFIGURACIÓN\n"
                "- res.partner: contactos (clientes, proveedores, empleados).\n"
                "  Campos: name, email, phone, mobile, street, city, zip, country_id, "
                "state_id, vat, customer_rank, supplier_rank, company_type "
                "('person'/'company'), parent_id.\n"
                "- res.users: usuarios del sistema. Campos: name, login, email, groups_id, "
                "partner_id, company_ids.\n"
                "- res.company: empresas. Campos: name, vat, currency_id, street, "
                "country_id, email, phone.\n"
                "- product.template / product.product: productos. "
                "  type: 'consu'(consumible), 'service', 'product'(almacenable). "
                "  Campos: name, list_price, standard_price, uom_id, categ_id, "
                "taxes_id, supplier_taxes_id, active.\n\n"

                "## PATRONES IMPORTANTES\n"
                "- IDs many2one: pasar siempre el ID entero, no el nombre. "
                "Usar odoo_name_search para buscar el ID de un registro por nombre.\n"
                "- Dominios de búsqueda: [['field','operador','valor']]. "
                "Operadores: '=','!=','>','<','>=','<=','like','ilike','in','not in',"
                "'child_of','parent_of'.\n"
                "- Campos Date: formato 'YYYY-MM-DD'. Datetime: 'YYYY-MM-DD HH:MM:SS'.\n"
                "- Many2many en write/create: [(6,0,[ids])] para reemplazar, [(4,id)] para agregar.\n"
                "- One2many en create: [(0,0,{vals})] para crear línea hija.\n"
                "- odoo_action solo ejecuta métodos de Python del modelo, no acciones "
                "del menú. Ejemplos de métodos: action_post, button_confirm, "
                "action_cancel, action_draft, button_validate.\n\n"

                "## CAMPOS Y MODELOS ELIMINADOS EN ODOO 19 — NO USAR\n"
                "- account.move.line.exclude_from_invoice_tab (eliminado)\n"
                "- account.move.line.is_rounding_line (eliminado)\n"
                "- account.move move_type='out_payment' y 'in_payment' (eliminados)\n"
                "- Para pagos: usa account.payment con payment_type='outbound'/'inbound'\n"
            )
        user = self.env.user
        # Use conversation-level company when set; fall back to user's default.
        active_company = (
            self.company_id if self and self.company_id else user.company_id
        )
        allowed_companies = user.company_ids.sorted("name")
        if len(allowed_companies) > 1:
            companies_list = ", ".join(
                "'%s' (id=%s)" % (c.name, c.id) for c in allowed_companies
            )
            company_scope = _(
                "\nEmpresas permitidas para este usuario (SOLO estas): %(list)s.\n"
                "REGLA ESTRICTA: nunca mezcles ni muestres datos de otras empresas "
                "que no estén en esta lista. Si el usuario pregunta '¿a qué compañías "
                "tienes acceso?' responde exclusivamente con las de esta lista."
            ) % {"list": companies_list}
        else:
            company_scope = ""
        context = _(
            "\n\nContexto de Odoo: base de datos '%(db)s', usuario '%(user)s' "
            "(id %(uid)s), empresa activa '%(company)s' (id %(cid)s), "
            "idioma '%(lang)s'.%(company_scope)s\n"
            "IMPORTANTE: Todas las operaciones deben realizarse en la empresa "
            "'%(company)s' (id=%(cid)s) a menos que el usuario indique "
            "explícitamente cambiar a otra empresa de la lista permitida."
        ) % {
            "db": self.env.cr.dbname,
            "user": user.name,
            "uid": user.id,
            "company": active_company.name,
            "cid": active_company.id,
            "lang": user.lang or "en_US",
            "company_scope": company_scope,
        }
        return base + context

    def _build_system_prompt_with_record(self, active_model=None, active_id=None):
        """System prompt that includes the record the user is currently viewing."""
        base = self._build_system_prompt()
        if not active_model or not active_id:
            return base
        try:
            active_id = int(active_id)
            if active_model not in self.env:
                return base
            record = self.env[active_model].browse(active_id)
            if not record.exists():
                return base
            model_meta = self.env["ir.model"].sudo().search(
                [("model", "=", active_model)], limit=1
            )
            model_label = model_meta.name if model_meta else active_model
            name = record.display_name if hasattr(record, "display_name") else str(active_id)
            extra = _(
                "\n\nEl usuario está viendo actualmente el registro "
                "'%(name)s' (%(model_label)s, id=%(id)s, modelo técnico: %(model)s). "
                "Si el usuario menciona 'este registro', 'esta factura', 'este contacto', "
                "etc., probablemente se refiere a ese registro."
            ) % {
                "name": name,
                "model_label": model_label,
                "id": active_id,
                "model": active_model,
            }
            return base + extra
        except Exception:
            _logger.debug("Could not read active record %s:%s for context", active_model, active_id)
            return base

    # ------------------------------------------------------------ display
    def _post(self, role, body=None, **vals):
        return self.env["claude.message"].create(
            {"conversation_id": self.id, "role": role, "body": body, **vals}
        )

    def _render_assistant_blocks(self, content):
        """Create display rows for an assistant turn (text + reasoning)."""
        new_msgs = self.env["claude.message"]
        for block in content:
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                new_msgs |= self._post("assistant", block["text"])
            elif btype == "thinking" and block.get("thinking"):
                new_msgs |= self._post("thinking", block["thinking"])
        return new_msgs

    # ------------------------------------------------------------ main loop
    def send_message(self, body, active_model=None, active_id=None, images=None):
        """Send a user message, run the tool-use loop, persist and return the
        new display messages plus token stats.

        :param active_model: technical name of the Odoo model the user is
            currently viewing (e.g. ``account.move``). Optional.
        :param active_id: integer ID of the record being viewed. Optional.
        :param images: list of dicts ``{"media_type": "image/jpeg", "data": "<base64>"}``
            for vision (multi-modal) messages. Optional.
        :returns: dict ``{"messages": [...], "total_input_tokens": N,
            "total_output_tokens": N}``
        """
        self.ensure_one()
        if self._cfg("enabled", "False") != "True":
            raise UserError(
                _("Claude AI está desactivado. Actívelo en Ajustes → Claude AI.")
            )
        body = (body or "").strip()
        if not body and not images:
            return {"messages": [], "total_input_tokens": self.total_input_tokens,
                    "total_output_tokens": self.total_output_tokens}

        active_company = self.company_id or self.env.company
        dispatcher = self.env["claude.tool.dispatcher"].with_company(active_company)
        api = self.env["claude.api"]
        tools = dispatcher._get_tool_schemas()
        system = self._build_system_prompt_with_record(active_model, active_id)
        model = self._cfg("model") or DEFAULT_MODEL
        max_tokens = int(self._cfg("max_tokens", "8192") or 8192)
        max_steps = int(self._cfg("max_steps", "12") or 12)
        thinking = (
            {"type": "adaptive", "display": "summarized"}
            if self._cfg("thinking", "True") == "True"
            else None
        )

        # Build user content block (text-only or multi-modal with images)
        if images:
            user_content = []
            if body:
                user_content.append({"type": "text", "text": body})
            for img in (images or []):
                user_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type", "image/jpeg"),
                        "data": img["data"],
                    },
                })
        else:
            user_content = body

        raw = json.loads(self.raw_messages or "[]")
        raw.append({"role": "user", "content": user_content})
        first_id = self.env["claude.message"].search(
            [("conversation_id", "=", self.id)], order="id desc", limit=1
        ).id or 0
        self._post("user", body or _("[imagen adjunta]"))
        if self.name == _("Nueva conversación"):
            title = body or _("Imagen")
            self.name = (title[:60] + "…") if len(title) > 60 else title

        for _step in range(max_steps):
            response = api.create_message(
                model=model, system=system, messages=raw, tools=tools,
                max_tokens=max_tokens, thinking=thinking,
            )
            content = response.get("content", [])
            raw.append({"role": "assistant", "content": content})
            self.model = response.get("model") or model
            usage = response.get("usage") or {}
            self.total_input_tokens += usage.get("input_tokens", 0) or 0
            self.total_output_tokens += usage.get("output_tokens", 0) or 0

            stop_reason = response.get("stop_reason")
            if stop_reason == "refusal":
                self._post("error", _("Claude rechazó la solicitud por motivos de "
                                      "seguridad."))
                break

            self._render_assistant_blocks(content)

            tool_uses = [b for b in content if b.get("type") == "tool_use"]
            if not tool_uses:
                # end_turn, max_tokens, etc. → turn finished.
                break

            tool_results = []
            for block in tool_uses:
                result = dispatcher.execute_tool(
                    block.get("name"), block.get("input") or {}, source="odoo_chat"
                )
                is_error = bool(result.get("error"))
                self._post(
                    "tool",
                    body=self._summarize_tool(block, result),
                    tool_name=block.get("name"),
                    tool_input=json.dumps(block.get("input") or {}, ensure_ascii=False),
                    tool_result=json.dumps(result, default=str, ensure_ascii=False),
                    tool_success=not is_error,
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.get("id"),
                    "content": json.dumps(result, default=str, ensure_ascii=False),
                    "is_error": is_error,
                })
            raw.append({"role": "user", "content": tool_results})
        else:
            self._post("error", _("Se alcanzó el número máximo de pasos del agente."))

        self.raw_messages = json.dumps(raw, default=str)
        new_messages = self.env["claude.message"].search(
            [("conversation_id", "=", self.id), ("id", ">", first_id)], order="id"
        )
        return {
            "messages": [m._to_frontend() for m in new_messages],
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }

    def _summarize_tool(self, block, result):
        name = block.get("name")
        if result.get("error"):
            return _("⚠ %(tool)s: %(err)s") % {"tool": name, "err": result["error"]}
        if result.get("status") == "confirmation_required":
            return _("⏸ %(tool)s requiere confirmación: %(msg)s") % {
                "tool": name, "msg": result.get("message", "")}
        # Friendly one-liners per tool.
        if name == "odoo_create":
            return _("✓ Creado %(model)s id=%(id)s") % {
                "model": result.get("model"), "id": result.get("id")}
        if name == "odoo_write":
            return _("✓ Modificados %(n)s registro(s) de %(model)s") % {
                "n": result.get("count"), "model": result.get("model")}
        if name == "odoo_unlink":
            return _("✓ Eliminados %(n)s registro(s) de %(model)s") % {
                "n": result.get("count"), "model": result.get("model")}
        if name == "odoo_action":
            return _("✓ %(method)s aplicado a %(n)s registro(s) de %(model)s") % {
                "method": result.get("method"), "n": result.get("count"),
                "model": result.get("model")}
        if name in ("odoo_search", "odoo_read"):
            return _("🔍 %(n)s registro(s) de %(model)s") % {
                "n": result.get("count"), "model": result.get("model")}
        if name == "odoo_count":
            return _("🔢 %(model)s: %(n)s registro(s)") % {
                "n": result.get("count"), "model": result.get("model")}
        if name == "odoo_get_url":
            return _("🔗 URL generada para %(model)s id=%(id)s") % {
                "model": result.get("model"), "id": result.get("id")}
        return _("✓ %s") % name

    # ------------------------------------------------------------ frontend API
    def get_conversation_tokens(self):
        """Return token totals for this conversation (used by the chat UI)."""
        self.ensure_one()
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }

    @api.model
    def get_chat_config(self):
        """Lightweight config probe used by the floating systray button.

        Returns enabled flag plus the list of companies the current user may
        switch to (only populated when the user belongs to more than one company).
        """
        user = self.env.user
        companies = []
        if len(user.company_ids) > 1:
            companies = [
                {"id": c.id, "name": c.name}
                for c in user.company_ids.sorted("name")
            ]
        return {
            "enabled": self._cfg("enabled", "False") == "True",
            "companies": companies,
            "current_company_id": user.company_id.id,
            "current_company_name": user.company_id.name,
        }

    @api.model
    def get_user_companies(self):
        """Return companies available to the current user."""
        user = self.env.user
        return [
            {"id": c.id, "name": c.name}
            for c in user.company_ids.sorted("name")
        ]

    def set_company(self, company_id):
        """Set the active company for this conversation.

        Validates that the current user actually belongs to the requested company.
        """
        self.ensure_one()
        user = self.env.user
        if company_id not in user.company_ids.ids:
            raise UserError(
                _("No tienes acceso a la empresa con id %s.") % company_id
            )
        self.company_id = company_id
        company_name = self.env["res.company"].browse(company_id).name
        self._post("tool", body=_("🏢 Empresa cambiada a '%(name)s'") % {"name": company_name},
                   tool_name="set_company", tool_input="{}", tool_result="{}", tool_success=True)
        return {"company_id": company_id, "company_name": company_name}

    @api.model
    def get_conversations(self):
        convs = self.search([("user_id", "=", self.env.uid)])
        return [
            {
                "id": c.id,
                "name": c.name,
                "company_id": c.company_id.id or False,
                "company_name": c.company_id.name or "",
            }
            for c in convs
        ]

    def get_messages(self):
        self.ensure_one()
        return [m._to_frontend() for m in self.message_ids]

    @api.model
    def create_conversation(self, company_id=None):
        vals = {}
        if company_id:
            user = self.env.user
            if company_id in user.company_ids.ids:
                vals["company_id"] = company_id
        conv = self.create(vals)
        return {
            "id": conv.id,
            "name": conv.name,
            "company_id": conv.company_id.id or False,
            "company_name": conv.company_id.name or "",
        }

    def delete_conversation(self):
        """Delete this conversation and all its messages. Called from the chat UI."""
        self.ensure_one()
        if self.user_id.id != self.env.uid:
            raise UserError(_("Solo puedes eliminar tus propias conversaciones."))
        self.unlink()
        return True
