# -*- coding: utf-8 -*-
import base64
import io
import json
import zipfile

from odoo import fields, models
from odoo.exceptions import UserError

from ..models.ktx_login_asset import ASSET_TYPE_EXTENSIONS

MAX_ENTRIES = 200
MAX_TOTAL_UNCOMPRESSED = 80 * 1024 * 1024  # 80 MB safety cap against zip bombs

_EXT_TO_TYPE = {
    ext: asset_type
    for asset_type, extensions in ASSET_TYPE_EXTENSIONS.items()
    for ext in extensions
}


class KtxLoginThemeImportWizard(models.TransientModel):
    """Bulk-import a bundle of login extensions (CSS/JS/fonts/images/video)
    from a single .zip file, so a whole "theme package" can be uploaded in
    one shot instead of file by file.

    Everything is read into memory and stored as ``ktx.login.asset`` DB
    records (attachments) -- nothing is ever extracted to the filesystem,
    which removes the zip-slip / path-traversal risk entirely and keeps the
    module friendly to multi-worker and containerized/Odoo.sh deployments.
    """

    _name = "ktx.login.theme.import.wizard"
    _description = "Login Studio - Importar paquete de extensiones (.zip)"

    theme_id = fields.Many2one("ktx.login.theme", required=True)
    zip_file = fields.Binary(string="Archivo .zip", required=True)
    zip_file_name = fields.Char()
    overwrite_existing = fields.Boolean(
        string="Sobrescribir archivos existentes con el mismo nombre", default=True,
    )
    publish_after_import = fields.Boolean(
        string="Publicar automaticamente (excepto JavaScript)",
        help="El JavaScript nunca se publica automaticamente: siempre requiere "
             "revision manual y confirmacion de riesgo.",
    )
    summary = fields.Text(readonly=True)

    def _load_manifest(self, zf, names):
        for name in names:
            if name.lower().rsplit("/", 1)[-1] == "manifest.json":
                try:
                    return json.loads(zf.read(name).decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    raise UserError("manifest.json invalido: %s" % exc)
        return {}

    def action_import(self):
        self.ensure_one()
        if not self.zip_file:
            raise UserError("Selecciona un archivo .zip para importar.")

        raw_zip = base64.b64decode(self.zip_file)
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw_zip))
        except zipfile.BadZipFile:
            raise UserError("El archivo subido no es un .zip valido.")

        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_ENTRIES:
            raise UserError(
                "El paquete contiene demasiados archivos (%s). Maximo permitido: %s."
                % (len(infos), MAX_ENTRIES)
            )
        total_uncompressed = sum(i.file_size for i in infos)
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
            raise UserError(
                "El contenido descomprimido del paquete supera el limite de "
                "seguridad (%s MB)." % (MAX_TOTAL_UNCOMPRESSED // (1024 * 1024))
            )

        names = [i.filename for i in infos]
        manifest = self._load_manifest(zf, names)
        manifest_by_basename = {
            (entry.get("file") or "").rsplit("/", 1)[-1]: entry
            for entry in manifest.get("assets", [])
            if entry.get("file")
        }

        Asset = self.env["ktx.login.asset"]
        created, updated, skipped, published, needs_review = [], [], [], [], []
        max_bytes = (self.theme_id.max_asset_size_mb or 3) * 1024 * 1024

        for info in infos:
            basename = info.filename.rsplit("/", 1)[-1]
            if not basename or basename.lower() == "manifest.json":
                continue
            ext = "." + basename.rsplit(".", 1)[-1].lower() if "." in basename else ""
            asset_type = _EXT_TO_TYPE.get(ext)
            if not asset_type:
                skipped.append("%s (extension no soportada)" % basename)
                continue
            if info.file_size > max_bytes:
                skipped.append("%s (supera %s MB)" % (basename, self.theme_id.max_asset_size_mb))
                continue

            meta = manifest_by_basename.get(basename, {})
            content = zf.read(info.filename)
            vals = {
                "theme_id": self.theme_id.id,
                "name": meta.get("name") or basename,
                "asset_type": meta.get("type") or asset_type,
                "scope": meta.get("scope") or "all",
                "target": meta.get("target") or ("body_end" if asset_type == "js" else "head"),
                "sequence": meta.get("sequence") or 10,
                "file_name": basename,
                "datas": base64.b64encode(content),
            }

            existing = Asset.search([
                ("theme_id", "=", self.theme_id.id), ("file_name", "=", basename),
            ], limit=1)
            try:
                if existing and self.overwrite_existing:
                    existing.write(vals)
                    updated.append(basename)
                    record = existing
                elif existing:
                    skipped.append("%s (ya existe, sobrescritura desactivada)" % basename)
                    continue
                else:
                    record = Asset.create(vals)
                    created.append(basename)
            except Exception as exc:  # noqa: BLE001 - surface validation errors per-file
                skipped.append("%s (%s)" % (basename, exc))
                continue

            if self.publish_after_import:
                if record.asset_type == "js":
                    needs_review.append(basename)
                else:
                    record.action_publish()
                    published.append(basename)

        lines = [
            "Importacion completada para el tema '%s'." % self.theme_id.name,
            "Creados: %s" % (", ".join(created) or "-"),
            "Actualizados: %s" % (", ".join(updated) or "-"),
            "Publicados automaticamente: %s" % (", ".join(published) or "-"),
            "Pendientes de revision manual (JavaScript): %s" % (", ".join(needs_review) or "-"),
            "Omitidos: %s" % (", ".join(skipped) or "-"),
        ]
        self.summary = "\n".join(lines)

        return {
            "type": "ir.actions.act_window",
            "name": "Resultado de la importacion",
            "res_model": "ktx.login.theme.import.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
