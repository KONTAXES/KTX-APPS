# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Methods Claude may invoke through the ``odoo_action`` tool when a model has
# ``allow_action`` enabled. Mirrors the safe state-transition methods already
# used by ktx_mass_update (button_draft / action_post) plus common siblings.
DEFAULT_ACTION_ALLOWLIST = [
    "action_post",
    "button_draft",
    "button_cancel",
    "action_confirm",
    "action_cancel",
    "action_done",
    "action_validate",
    "action_approve",
    "toggle_active",
    # Accounting reconciliation
    "reconcile",
    "remove_move_reconcile",
]

VALID_OPERATIONS = ("read", "create", "write", "unlink", "action")


class ClaudeEnabledModel(models.Model):
    """Models exposed to Claude, with per-operation access control.

    An administrator selectively enables the Odoo models Claude may touch and,
    for each one, which operations are allowed. This is the single gate used by
    both the in-Odoo chat (phase 1) and the remote connector (phase 2).
    """

    _name = "claude.enabled.model"
    _description = "Modelo habilitado para Claude"
    _rec_name = "model_id"
    _order = "model_name"

    model_id = fields.Many2one(
        "ir.model",
        string="Modelo",
        required=True,
        index=True,
        ondelete="cascade",
        help="Modelo de Odoo habilitado para el acceso de Claude.",
    )
    model_name = fields.Char(
        related="model_id.model", string="Nombre técnico", store=True, readonly=True
    )
    active = fields.Boolean(default=True)
    allow_read = fields.Boolean(
        string="Permitir lectura", default=True, help="Buscar y leer registros."
    )
    allow_create = fields.Boolean(
        string="Permitir creación", default=False, help="Crear registros."
    )
    allow_write = fields.Boolean(
        string="Permitir modificación", default=False, help="Actualizar registros."
    )
    allow_unlink = fields.Boolean(
        string="Permitir eliminación", default=False, help="Eliminar registros."
    )
    allow_action = fields.Boolean(
        string="Permitir acciones de estado",
        default=False,
        help="Ejecutar métodos de cambio de estado de la lista permitida "
        "(p. ej. restablecer a borrador, confirmar, cancelar).",
    )
    allowed_methods = fields.Char(
        string="Métodos permitidos",
        help="Lista separada por comas de métodos que Claude puede ejecutar vía "
        "la herramienta de acción. Si se deja vacío se usa la lista segura por "
        "defecto (action_post, button_draft, button_cancel, ...).",
    )
    notes = fields.Text(string="Notas")

    _model_unique = models.Constraint(
        "UNIQUE(model_id)",
        "Cada modelo solo puede habilitarse una vez para Claude.",
    )

    @api.model
    def _check_operation(self, model_name, operation):
        """Return True if *operation* on *model_name* is allowed for Claude."""
        if operation not in VALID_OPERATIONS:
            raise ValidationError(_("Operación inválida: %s") % operation)
        record = self.sudo().search(
            [("model_name", "=", model_name), ("active", "=", True)], limit=1
        )
        if not record:
            return False
        return bool(record["allow_" + operation])

    @api.model
    def _allowed_methods_for(self, model_name):
        """Return the list of method names Claude may call on *model_name*."""
        record = self.sudo().search(
            [("model_name", "=", model_name), ("active", "=", True)], limit=1
        )
        if not record or not record.allow_action:
            return []
        if record.allowed_methods and record.allowed_methods.strip():
            return [m.strip() for m in record.allowed_methods.split(",") if m.strip()]
        return list(DEFAULT_ACTION_ALLOWLIST)
