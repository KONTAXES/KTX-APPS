# -*- coding: utf-8 -*-
import base64
import hashlib
import mimetypes

from werkzeug.utils import secure_filename

from odoo import api, fields, models
from odoo.exceptions import ValidationError

ASSET_TYPE_EXTENSIONS = {
    "css": (".css",),
    "js": (".js",),
    "font": (".woff", ".woff2", ".ttf", ".otf"),
    "image": (".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"),
    "video": (".mp4", ".webm"),
}

ASSET_TYPE_MIMETYPE = {
    "css": "text/css",
    "js": "application/javascript",
    "font": {
        ".woff": "font/woff", ".woff2": "font/woff2",
        ".ttf": "font/ttf", ".otf": "font/otf",
    },
    "image": {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml", ".webp": "image/webp", ".gif": "image/gif",
    },
    "video": {".mp4": "video/mp4", ".webm": "video/webm"},
}

# Heuristic guard: text-based assets must not contain server-side / shell
# markers. This is defense-in-depth, not a substitute for reviewing what an
# admin uploads -- Login Studio never executes uploaded files server-side,
# it only ever serves them as static bytes to the browser.
_SUSPICIOUS_MARKERS = (b"<?php", b"<%", b"#!/", b"#!\\")


class KtxLoginAsset(models.Model):
    """A single uploaded static resource (CSS/JS/font/image/video) that gets
    attached to the public login page.

    Nothing here is ever evaluated or executed by the server: files are
    stored as plain bytes and streamed back to the browser through
    ``KtxLoginStudioController.asset`` with the correct ``Content-Type``.
    A syntax error in an uploaded file can only ever break itself in the
    browser -- never the surrounding page or the real login form, which
    Odoo continues to render on its own.
    """

    _name = "ktx.login.asset"
    _description = "Login Studio - Extension (CSS/JS/Font/Image/Video)"
    _inherit = ["mail.thread"]
    _order = "sequence, id"

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    theme_id = fields.Many2one(
        "ktx.login.theme", string="Tema", required=True, ondelete="cascade",
    )

    asset_type = fields.Selection(
        [("css", "Hoja de estilos CSS"), ("js", "JavaScript"),
         ("font", "Fuente Web"), ("image", "Imagen"), ("video", "Video de fondo")],
        required=True, default="css", tracking=True,
    )
    scope = fields.Selection(
        [("all", "Todas las paginas"), ("login", "Solo Login"),
         ("signup", "Solo Registro"), ("reset", "Solo Recuperar Contrasena")],
        default="all", required=True,
    )
    target = fields.Selection(
        [("head", "Cabecera (antes del contenido)"),
         ("body_end", "Final de la pagina (recomendado para JS)")],
        default="body_end", required=True,
    )

    datas = fields.Binary(string="Archivo", attachment=True, required=True)
    file_name = fields.Char(string="Nombre de archivo", required=True)
    mimetype = fields.Char(compute="_compute_file_meta", store=True)
    file_size = fields.Integer(string="Tamano (bytes)", compute="_compute_file_meta", store=True)
    checksum = fields.Char(compute="_compute_file_meta", store=True)

    state = fields.Selection(
        [("draft", "Borrador"), ("published", "Publicado")],
        default="draft", required=True, tracking=True,
    )
    risk_ack = fields.Boolean(
        string="Confirmo el riesgo de publicar JavaScript",
        help="El JavaScript publicado se ejecuta directamente en la pagina publica "
             "de login. Debes confirmar que revisaste y confias en este archivo "
             "antes de poder publicarlo.",
    )

    version = fields.Integer(default=1, readonly=True)
    previous_datas = fields.Binary(readonly=True, attachment=True)
    previous_file_name = fields.Char(readonly=True)
    previous_version = fields.Integer(readonly=True)

    help_text = fields.Char(compute="_compute_help_text")

    def _compute_help_text(self):
        for record in self:
            record.help_text = (
                "Se sirve como <script src> externo; un error de sintaxis solo "
                "afecta a este archivo, nunca al formulario de login."
                if record.asset_type == "js" else
                "Se sirve como recurso estatico independiente del formulario de login."
            )

    @api.depends("datas", "file_name")
    def _compute_file_meta(self):
        for record in self:
            if not record.datas:
                record.mimetype = False
                record.file_size = 0
                record.checksum = False
                continue
            raw = base64.b64decode(record.datas)
            record.file_size = len(raw)
            record.checksum = hashlib.sha256(raw).hexdigest()[:16]
            ext = self._get_extension(record.file_name)
            mt = ASSET_TYPE_MIMETYPE.get(record.asset_type)
            if isinstance(mt, dict):
                record.mimetype = mt.get(ext) or mimetypes.guess_type(record.file_name or "")[0]
            else:
                record.mimetype = mt

    @staticmethod
    def _get_extension(file_name):
        if not file_name or "." not in file_name:
            return ""
        return "." + file_name.rsplit(".", 1)[-1].lower()

    @api.constrains("file_name", "asset_type")
    def _check_extension(self):
        for record in self:
            allowed = ASSET_TYPE_EXTENSIONS.get(record.asset_type, ())
            ext = self._get_extension(record.file_name)
            if ext not in allowed:
                raise ValidationError(
                    "Extension '%s' no permitida para el tipo '%s'. Extensiones "
                    "validas: %s" % (ext or "(ninguna)", record.asset_type, ", ".join(allowed))
                )

    @api.constrains("datas", "theme_id")
    def _check_file_size(self):
        for record in self:
            if not record.datas:
                continue
            max_bytes = (record.theme_id.max_asset_size_mb or 3) * 1024 * 1024
            if record.file_size > max_bytes:
                raise ValidationError(
                    "El archivo '%s' pesa %.2f MB, el maximo permitido para este "
                    "tema es %s MB." % (
                        record.file_name, record.file_size / (1024 * 1024),
                        record.theme_id.max_asset_size_mb,
                    )
                )

    @api.constrains("datas", "asset_type")
    def _check_suspicious_content(self):
        for record in self:
            if not record.datas or record.asset_type not in ("css", "js"):
                continue
            raw = base64.b64decode(record.datas)
            head = raw[:512].lower()
            for marker in _SUSPICIOUS_MARKERS:
                if marker in head:
                    raise ValidationError(
                        "El archivo '%s' contiene marcadores de codigo de servidor "
                        "(%s) y fue rechazado por seguridad. Sube unicamente CSS/JS "
                        "puro para el navegador." % (record.file_name, marker.decode())
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("file_name"):
                vals["file_name"] = secure_filename(vals["file_name"])
        return super().create(vals_list)

    def write(self, vals):
        if "file_name" in vals and vals["file_name"]:
            vals["file_name"] = secure_filename(vals["file_name"])
        if "datas" not in vals:
            return super().write(vals)

        # A new file must be reviewed/published again before going live, and
        # the previous good version is kept for one-click rollback. Handled
        # per-record since each may currently hold different bytes/version.
        new_datas = vals["datas"]
        for record in self:
            record_vals = dict(vals)
            if record.datas and new_datas and new_datas != record.datas:
                record_vals.setdefault("previous_datas", record.datas)
                record_vals.setdefault("previous_file_name", record.file_name)
                record_vals.setdefault("previous_version", record.version)
                record_vals.setdefault("version", record.version + 1)
                record_vals.setdefault("state", "draft")
                record_vals.setdefault("risk_ack", False)
            super(KtxLoginAsset, record).write(record_vals)
        return True

    def action_publish(self):
        for record in self:
            if not record.datas:
                raise ValidationError("No hay archivo para publicar en '%s'." % record.name)
            if record.asset_type == "js" and not record.risk_ack:
                raise ValidationError(
                    "Debes marcar 'Confirmo el riesgo de publicar JavaScript' "
                    "antes de publicar '%s'." % record.name
                )
        self.write({"state": "published"})
        for record in self:
            record.message_post(body="Extension publicada (v%s)." % record.version)

    def action_unpublish(self):
        self.write({"state": "draft"})

    def action_rollback(self):
        for record in self:
            if not record.previous_datas:
                raise ValidationError(
                    "No hay una version anterior guardada para '%s'." % record.name)
            record.write({
                "datas": record.previous_datas,
                "file_name": record.previous_file_name,
                "previous_datas": False,
                "previous_file_name": False,
                "version": record.previous_version or record.version,
                "state": "published",
                "risk_ack": record.risk_ack,
            })
            record.message_post(body="Extension restaurada a la version anterior (rollback).")

    def get_public_url(self):
        self.ensure_one()
        return "/ktx_login_studio/asset/%s-%s/%s" % (self.id, self.checksum, self.file_name)
