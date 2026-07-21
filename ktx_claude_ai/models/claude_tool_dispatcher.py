# -*- coding: utf-8 -*-
import json
import logging
import re
import time

from odoo import _, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

_MODEL_NAME_RE = re.compile(r"^[a-zA-Z0-9._]+$")


class ClaudeToolError(Exception):
    """Raised when a tool cannot be executed; surfaced to Claude as an error
    tool_result so it can adapt instead of aborting the whole turn."""


class ClaudeConfirmationRequired(Exception):
    """Raised when a destructive/mass operation needs explicit confirmation."""


class ClaudeToolDispatcher(models.AbstractModel):
    """Single source of truth for what Claude can do in Odoo.

    Exposes the tool catalogue (``_get_tool_schemas``) and executes tool calls
    (``execute_tool``) under the *current user's* access rights — ACLs and
    record rules apply. ``sudo`` is used only for plumbing (config, enabled
    models, audit log), never for the data operations themselves.
    """

    _name = "claude.tool.dispatcher"
    _description = "Despachador de herramientas de Claude"

    # ------------------------------------------------------------------ config
    def _config(self, key, default=None):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("ktx_claude_ai." + key, default)
        )

    def _max_batch_size(self):
        try:
            return int(self._config("max_batch_size", "50"))
        except (TypeError, ValueError):
            return 50

    def _require_confirmation(self):
        return self._config("require_confirmation", "True") == "True"

    # --------------------------------------------------------------- tool defs
    def _get_tool_schemas(self):
        """Return the Anthropic ``tools`` list. One definition feeds both the
        in-Odoo chat and (phase 2) the MCP ``tools/list`` endpoint."""
        return [
            {
                "name": "whoami",
                "description": (
                    "Devuelve información sobre el usuario y las compañías con las que "
                    "Claude está conectado en este momento: nombre, login, email, "
                    "empresa activa y lista de compañías permitidas. "
                    "Úsala para verificar la identidad y el contexto de empresa antes "
                    "de operar, o cuando el usuario pregunte '¿con qué usuario estás "
                    "conectado?' o '¿a qué compañía tienes acceso?'."
                ),
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "list_models",
                "description": "Lista los modelos de Odoo habilitados para Claude "
                "y qué operaciones están permitidas en cada uno. Úsala primero si "
                "no sabes el nombre técnico de un modelo.",
                "input_schema": {"type": "object", "properties": {}},
            },
            {
                "name": "odoo_fields_get",
                "description": "Devuelve la definición de los campos de un modelo "
                "(nombre técnico, tipo, etiqueta, requerido, relación). Úsala "
                "antes de crear o modificar registros para conocer los campos.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string", "description": "Nombre técnico, p. ej. res.partner"},
                    },
                    "required": ["model"],
                },
            },
            {
                "name": "odoo_name_search",
                "description": "Busca registros por nombre y devuelve sus IDs. "
                "Úsala para resolver referencias (p. ej. encontrar el id de un "
                "contacto o de una cuenta a partir de su nombre).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "name": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["model", "name"],
                },
            },
            {
                "name": "odoo_search",
                "description": "Busca y lee registros que cumplan un dominio de "
                "Odoo. El dominio es una lista de tripletas, p. ej. "
                "[[\"state\",\"=\",\"draft\"]]. Devuelve los campos solicitados. "
                "IMPORTANTE: usa odoo_fields_get para verificar que los campos "
                "del dominio existen antes de buscar. Campos eliminados en Odoo 19 "
                "que NO debes usar: account.move.line.exclude_from_invoice_tab "
                "(eliminado), account.move.line.is_rounding_line (eliminado). "
                "Para pagos usa account.payment (payment_type, partner_type, amount), "
                "NO account.move con move_type='out_payment'/'in_payment'.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "domain": {
                            "type": "array",
                            "description": "Dominio de búsqueda de Odoo (lista de tripletas).",
                            "items": {},
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Campos a devolver. Vacío = un conjunto razonable.",
                        },
                        "limit": {"type": "integer", "default": 80},
                        "offset": {"type": "integer", "default": 0},
                        "order": {"type": "string"},
                    },
                    "required": ["model"],
                },
            },
            {
                "name": "odoo_read",
                "description": "Lee campos de registros concretos por sus IDs.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "ids": {"type": "array", "items": {"type": "integer"}},
                        "fields": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["model", "ids"],
                },
            },
            {
                "name": "odoo_create",
                "description": "Crea un registro nuevo con los valores indicados y "
                "devuelve su id. Para crear varios, llama varias veces.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "values": {
                            "type": "object",
                            "description": "Diccionario campo→valor. Usa IDs para "
                            "campos relacionales (many2one). Para many2many/one2many "
                            "usa comandos de Odoo, p. ej. [[6,0,[id1,id2]]].",
                        },
                    },
                    "required": ["model", "values"],
                },
            },
            {
                "name": "odoo_write",
                "description": "Modifica uno o varios registros (escritura masiva) "
                "aplicando los mismos valores a todos los IDs indicados.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "ids": {"type": "array", "items": {"type": "integer"}},
                        "values": {"type": "object"},
                        "confirm": {
                            "type": "boolean",
                            "description": "Pon true para confirmar una operación "
                            "masiva tras avisar al usuario.",
                            "default": False,
                        },
                    },
                    "required": ["model", "ids", "values"],
                },
            },
            {
                "name": "odoo_unlink",
                "description": "Elimina registros por sus IDs (individual o masivo). "
                "Operación destructiva: requiere confirm=true tras avisar al usuario.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "ids": {"type": "array", "items": {"type": "integer"}},
                        "confirm": {"type": "boolean", "default": False},
                    },
                    "required": ["model", "ids"],
                },
            },
            {
                "name": "odoo_action",
                "description": "Ejecuta una acción de cambio de estado sobre uno o "
                "varios registros: restablecer a borrador (button_draft), confirmar "
                "(action_post / action_confirm), cancelar (button_cancel), etc. "
                "Solo se permiten métodos de la lista permitida del modelo.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "ids": {"type": "array", "items": {"type": "integer"}},
                        "method": {
                            "type": "string",
                            "description": "Método a ejecutar, p. ej. button_draft.",
                        },
                        "confirm": {"type": "boolean", "default": False},
                    },
                    "required": ["model", "ids", "method"],
                },
            },
            {
                "name": "odoo_aggregate",
                "description": (
                    "Agrupa y agrega registros de Odoo mediante read_group (equivalente a "
                    "GROUP BY en SQL). Imprescindible para reportes: totales de IVA por "
                    "impuesto, ventas por cliente, movimientos por cuenta contable, etc. "
                    "Devuelve una fila por grupo con los acumulados solicitados.\n\n"
                    "Ejemplos de fields con función de agregación:\n"
                    "  ['price_subtotal:sum', 'balance:sum', 'quantity:sum', 'id:count']\n\n"
                    "Ejemplo groupby:\n"
                    "  ['tax_line_id']  →  agrupa por impuesto\n"
                    "  ['date:month']   →  agrupa por mes\n"
                    "  ['partner_id', 'date:month']  →  doble agrupación"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string", "description": "Nombre técnico del modelo."},
                        "domain": {
                            "type": "array",
                            "items": {},
                            "description": "Dominio de filtro (lista de tripletas). Vacío = todos.",
                        },
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Campos a incluir, con función de agregación cuando aplique: "
                                "'campo:sum', 'campo:avg', 'campo:min', 'campo:max', 'campo:count'. "
                                "Los campos en groupby no necesitan función."
                            ),
                        },
                        "groupby": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Campos por los que agrupar. Soporta truncado temporal: "
                                "'date:day', 'date:week', 'date:month', 'date:quarter', 'date:year'."
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Número máximo de grupos a devolver (default 200).",
                        },
                        "order": {
                            "type": "string",
                            "description": "Orden de los grupos, p. ej. 'date_begin desc'.",
                        },
                    },
                    "required": ["model", "groupby"],
                },
            },
            {
                "name": "odoo_count",
                "description": "Cuenta cuántos registros de un modelo cumplen "
                "un dominio de Odoo, sin traer los datos. Mucho más rápido y "
                "económico que odoo_search cuando solo necesitas el total.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "domain": {
                            "type": "array",
                            "description": "Dominio de búsqueda (lista de tripletas). "
                            "Vacío = todos los registros.",
                            "items": {},
                        },
                    },
                    "required": ["model"],
                },
            },
            {
                "name": "odoo_get_url",
                "description": "Devuelve la URL del cliente web de Odoo para abrir "
                "un registro concreto. Úsala cuando quieras dar al usuario un enlace "
                "directo a un registro recién creado o encontrado.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "id": {"type": "integer", "description": "ID del registro."},
                    },
                    "required": ["model", "id"],
                },
            },
        ]

    # ----------------------------------------------------------------- helpers
    def _sanitize_model(self, model_name):
        if not model_name or not _MODEL_NAME_RE.match(model_name):
            raise ClaudeToolError(_("Nombre de modelo inválido: %s") % model_name)
        if model_name not in self.env:
            raise ClaudeToolError(_("El modelo '%s' no existe.") % model_name)
        return model_name

    def _filter_fields(self, model_name, fields_list):
        """Return (valid_fields, skipped) filtering out names not on the model.

        Instead of crashing with ValueError when Claude guesses a wrong field
        name (e.g. 'amount' instead of 'amount_total', 'date_due' instead of
        'invoice_date_due'), we silently skip them and include a 'skipped_fields'
        key in the result so Claude knows to adjust.
        """
        if not fields_list:
            return [], []
        model_fields = set(self.env[model_name]._fields)
        valid = [f for f in fields_list if f in model_fields]
        skipped = [f for f in fields_list if f not in model_fields]
        return valid, skipped

    def _check(self, model_name, operation):
        if not self.env["claude.enabled.model"]._check_operation(model_name, operation):
            raise ClaudeToolError(
                _("La operación '%(op)s' no está habilitada para el modelo "
                  "'%(model)s'. Un administrador debe habilitarla en "
                  "Ajustes → Claude AI → Modelos.")
                % {"op": operation, "model": model_name}
            )

    def _log(self, vals):
        if self._config("log_enabled", "True") != "True":
            return
        try:
            self.env["claude.request.log"].sudo().create(vals)
        except Exception:  # pragma: no cover - logging must never break a turn
            _logger.exception("No se pudo escribir la bitácora de Claude")

    # --------------------------------------------------------------- dispatch
    def execute_tool(self, name, tool_input, source="odoo_chat"):
        """Run a single tool call and return a JSON-serializable result dict.

        Never raises: tool/permission errors are returned as ``{"error": ...}``
        so Claude receives a tool_result and can recover.
        """
        tool_input = tool_input or {}
        started = time.monotonic()
        model_name = tool_input.get("model")
        record_ids = tool_input.get("ids")
        try:
            handler = getattr(self, "_tool_" + name, None)
            if handler is None:
                raise ClaudeToolError(_("Herramienta desconocida: %s") % name)
            result = handler(tool_input)
            self._log({
                "source": source,
                "tool_name": name,
                "model_name": model_name,
                "operation": name,
                "record_ids": str(record_ids) if record_ids else False,
                "success": True,
                "duration_ms": int((time.monotonic() - started) * 1000),
            })
            return result
        except ClaudeConfirmationRequired as exc:
            return {"status": "confirmation_required", "message": str(exc)}
        except (ClaudeToolError, ValidationError, UserError, AccessError) as exc:
            msg = exc.args[0] if exc.args else str(exc)
            self._log({
                "source": source,
                "tool_name": name,
                "model_name": model_name,
                "operation": name,
                "record_ids": str(record_ids) if record_ids else False,
                "success": False,
                "error_message": str(msg),
                "duration_ms": int((time.monotonic() - started) * 1000),
            })
            return {"error": str(msg)}
        except Exception as exc:  # pragma: no cover - unexpected
            _logger.exception("Error inesperado en la herramienta %s", name)
            self._log({
                "source": source,
                "tool_name": name,
                "model_name": model_name,
                "success": False,
                "error_message": str(exc),
                "duration_ms": int((time.monotonic() - started) * 1000),
            })
            return {"error": _("Error interno: %s") % exc}

    # ------------------------------------------------------------------ tools
    def _tool_whoami(self, params):
        """Return identity and company context of the connected user."""
        user = self.env.user
        allowed_ids = self.env.context.get("allowed_company_ids") or user.company_ids.ids
        allowed = (
            self.env["res.company"].sudo().browse(allowed_ids)
            .filtered(lambda c: c.id in user.company_ids.ids)
        )
        return {
            "user_id": user.id,
            "name": user.name,
            "login": user.login,
            "email": user.email or user.login,
            "active_company": {
                "id": user.company_id.id,
                "name": user.company_id.name,
            },
            "allowed_companies": [
                {"id": c.id, "name": c.name} for c in allowed
            ],
        }

    def _tool_list_models(self, params):
        records = self.env["claude.enabled.model"].sudo().search(
            [("active", "=", True)]
        )
        models_info = []
        for rec in records:
            models_info.append({
                "model": rec.model_name,
                "name": rec.model_id.name,
                "operations": [
                    op for op in ("read", "create", "write", "unlink", "action")
                    if rec["allow_" + op]
                ],
            })
        return {"models": models_info}

    def _tool_odoo_fields_get(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "read")
        fields_info = self.env[model_name].fields_get(
            attributes=["string", "type", "required", "readonly", "relation", "selection", "help"]
        )
        return {"model": model_name, "fields": fields_info}

    def _tool_odoo_name_search(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "read")
        limit = int(params.get("limit") or 10)
        extra_domain = self._company_domain(model_name, [])
        results = self.env[model_name].name_search(
            name=params.get("name") or "", args=extra_domain, limit=limit
        )
        return {"model": model_name, "results": [{"id": r[0], "name": r[1]} for r in results]}

    def _company_domain(self, model_name, domain):
        """Inject a company restriction into *domain* when needed.

        Two cases:
        - ``res.company``: restrict to the companies the user is actually
          allowed to access (``user.company_ids``).  Odoo's built-in record
          rule for this model uses ``allowed_company_ids`` from the session
          context, which is not available in a stateless API call, so we
          enforce it explicitly.
        - Any model that has a ``company_id`` Many2one to ``res.company``:
          restrict to the user's allowed companies so records from other
          companies are never returned.
        """
        user = self.env.user
        allowed = user.company_ids.ids
        if not allowed:
            return domain

        if model_name == "res.company":
            return [("id", "in", allowed)] + list(domain or [])

        model_obj = self.env.get(model_name)
        if model_obj is not None:
            f = model_obj._fields.get("company_id")
            if f and getattr(f, "comodel_name", None) == "res.company":
                return [("company_id", "in", allowed + [False])] + list(domain or [])

        return domain

    def _tool_odoo_search(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "read")
        domain = params.get("domain") or []
        if not isinstance(domain, list):
            raise ClaudeToolError(_("'domain' debe ser una lista."))
        domain = self._company_domain(model_name, domain)
        fields_list = params.get("fields") or []
        limit = int(params.get("limit") or 80)
        offset = int(params.get("offset") or 0)
        order = params.get("order") or None
        valid_fields, skipped = self._filter_fields(model_name, fields_list)
        records = self.env[model_name].search(
            domain, limit=limit, offset=offset, order=order
        )
        data = records.read(valid_fields) if valid_fields else records.read()
        result = {"model": model_name, "count": len(data), "records": data}
        if skipped:
            result["skipped_fields"] = skipped
            result["hint"] = (
                "Los campos %s no existen en %s. Usa odoo_fields_get para "
                "ver los nombres correctos." % (skipped, model_name)
            )
        return result

    def _tool_odoo_read(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "read")
        ids = params.get("ids") or []
        if not isinstance(ids, list):
            raise ClaudeToolError(_("'ids' debe ser una lista de enteros."))
        fields_list = params.get("fields") or []
        valid_fields, skipped = self._filter_fields(model_name, fields_list)
        # Filter to only records the user's companies allow, using search
        # instead of raw browse to respect _company_domain.
        company_domain = self._company_domain(model_name, [("id", "in", ids)])
        records = self.env[model_name].search(company_domain)
        data = records.read(valid_fields) if valid_fields else records.read()
        result = {"model": model_name, "count": len(data), "records": data}
        if skipped:
            result["skipped_fields"] = skipped
            result["hint"] = (
                "Los campos %s no existen en %s. Usa odoo_fields_get para "
                "ver los nombres correctos." % (skipped, model_name)
            )
        return result

    def _tool_odoo_create(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "create")
        values = params.get("values")
        if not isinstance(values, dict) or not values:
            raise ClaudeToolError(_("'values' debe ser un diccionario no vacío."))
        record = self.env[model_name].create(values)
        return {"model": model_name, "id": record.id, "created": True}

    def _tool_odoo_write(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "write")
        ids = params.get("ids") or []
        values = params.get("values")
        if not isinstance(ids, list) or not ids:
            raise ClaudeToolError(_("'ids' debe ser una lista no vacía."))
        if not isinstance(values, dict) or not values:
            raise ClaudeToolError(_("'values' debe ser un diccionario no vacío."))
        self._guard_mass(len(ids), params.get("confirm"), _("modificar"))
        records = self.env[model_name].browse(ids).exists()
        records.write(values)
        return {"model": model_name, "updated_ids": records.ids, "count": len(records)}

    def _tool_odoo_unlink(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "unlink")
        ids = params.get("ids") or []
        if not isinstance(ids, list) or not ids:
            raise ClaudeToolError(_("'ids' debe ser una lista no vacía."))
        # unlink is always destructive → always confirm.
        if self._require_confirmation() and not params.get("confirm"):
            raise ClaudeConfirmationRequired(
                _("Vas a ELIMINAR %(n)s registro(s) de %(model)s. Avisa al usuario y "
                  "vuelve a llamar con confirm=true si lo aprueba.")
                % {"n": len(ids), "model": model_name}
            )
        records = self.env[model_name].browse(ids).exists()
        deleted = records.ids
        records.unlink()
        return {"model": model_name, "deleted_ids": deleted, "count": len(deleted)}

    def _tool_odoo_action(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "action")
        ids = params.get("ids") or []
        method = params.get("method")
        if not isinstance(ids, list) or not ids:
            raise ClaudeToolError(_("'ids' debe ser una lista no vacía."))
        allowed = self.env["claude.enabled.model"]._allowed_methods_for(model_name)
        if method not in allowed:
            raise ClaudeToolError(
                _("El método '%(m)s' no está permitido para %(model)s. "
                  "Permitidos: %(allowed)s")
                % {"m": method, "model": model_name, "allowed": ", ".join(allowed)}
            )
        self._guard_mass(len(ids), params.get("confirm"), _("aplicar '%s' a") % method)
        records = self.env[model_name].browse(ids).exists()
        # Defensive: only call public-but-safe-listed callables.
        func = getattr(records, method, None)
        if not callable(func):
            raise ClaudeToolError(_("El método '%s' no es ejecutable.") % method)
        func()
        return {"model": model_name, "method": method, "record_ids": records.ids,
                "count": len(records)}

    def _tool_odoo_aggregate(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "read")
        domain = params.get("domain") or []
        if not isinstance(domain, list):
            raise ClaudeToolError(_("'domain' debe ser una lista."))
        domain = self._company_domain(model_name, domain)
        fields_list = params.get("fields") or []
        groupby = params.get("groupby") or []
        if not groupby:
            raise ClaudeToolError(_("'groupby' es obligatorio y no puede estar vacío."))
        limit = int(params.get("limit") or 200)
        order = params.get("order") or None
        rows = self.env[model_name].read_group(
            domain=domain,
            fields=fields_list,
            groupby=groupby,
            limit=limit,
            orderby=order or False,
            lazy=False,
        )
        # Clean up internal Odoo keys (__domain, __context, __fold) before returning.
        clean = []
        for row in rows:
            clean.append({k: v for k, v in row.items() if not k.startswith("__")})
        return {"model": model_name, "groupby": groupby, "count": len(clean), "rows": clean}

    def _tool_odoo_count(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "read")
        domain = params.get("domain") or []
        if not isinstance(domain, list):
            raise ClaudeToolError(_("'domain' debe ser una lista."))
        domain = self._company_domain(model_name, domain)
        count = self.env[model_name].search_count(domain)
        return {"model": model_name, "domain": domain, "count": count}

    def _tool_odoo_get_url(self, params):
        model_name = self._sanitize_model(params.get("model"))
        self._check(model_name, "read")
        rec_id = params.get("id")
        if not isinstance(rec_id, int) or rec_id <= 0:
            raise ClaudeToolError(_("'id' debe ser un entero positivo."))
        base = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("web.base.url", "")
        ).rstrip("/")
        url = f"{base}/web#model={model_name}&id={rec_id}&view_type=form"
        return {"model": model_name, "id": rec_id, "url": url}

    def _guard_mass(self, count, confirm, verb):
        """Require confirmation when an operation touches more than the
        configured batch size."""
        if (
            self._require_confirmation()
            and count > self._max_batch_size()
            and not confirm
        ):
            raise ClaudeConfirmationRequired(
                _("Vas a %(verb)s %(n)s registros (operación masiva). Avisa al "
                  "usuario y vuelve a llamar con confirm=true si lo aprueba.")
                % {"verb": verb, "n": count}
            )
