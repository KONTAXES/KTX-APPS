# -*- coding: utf-8 -*-
import base64
import logging
from urllib.parse import quote

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EnviarReciboWizard(models.TransientModel):
    _name = "ktx.planilla.enviar.recibo.wizard"
    _description = "Enviar Recibo de Nómina / Finiquito"

    linea_id = fields.Many2one(
        "ktx.planilla.linea", string="Línea de Planilla")
    liquidacion_id = fields.Many2one(
        "ktx.planilla.liquidacion", string="Liquidación")
    employee_id = fields.Many2one(
        "hr.employee", string="Empleado",
        compute="_compute_employee", store=True)
    canal = fields.Selection(
        selection=[
            ("email", "Correo Electrónico"),
            ("whatsapp", "WhatsApp"),
        ],
        string="Canal de Envío",
        required=True,
        default="email",
    )
    modo = fields.Selection(
        selection=[
            ("firma_link", "Link de Firma Electrónica (módulo Firmas)"),
            ("pdf", "Documento PDF (firma manuscrita)"),
        ],
        string="Qué Enviar",
        required=True,
        default=lambda self: "firma_link"
        if "sign.request" in self.env else "pdf",
        help="Link de firma: el empleado abre el documento en Odoo, lo firma "
             "electrónicamente y puede descargarlo; el documento firmado "
             "queda guardado en Firmas. PDF: se envía el documento para "
             "firma manuscrita.",
    )
    email = fields.Char(
        string="Correo del Empleado",
        compute="_compute_contacto", store=True, readonly=False)
    telefono = fields.Char(
        string="Teléfono / WhatsApp",
        compute="_compute_contacto", store=True, readonly=False)
    mensaje = fields.Text(
        string="Mensaje",
        compute="_compute_mensaje", store=True, readonly=False,
        help="Si envía un link de firma, el enlace se agrega automáticamente "
             "al final del mensaje.")
    firma_link = fields.Char(
        string="Link de Firma",
        readonly=True,
        copy=False,
        help="Enlace generado de la solicitud de firma; también queda "
             "registrado en el chatter del documento.")
    sign_disponible = fields.Boolean(compute="_compute_sign_disponible")

    @api.depends("linea_id", "liquidacion_id")
    def _compute_employee(self):
        for wiz in self:
            wiz.employee_id = (
                wiz.linea_id.employee_id or wiz.liquidacion_id.employee_id)

    @api.depends("employee_id")
    def _compute_contacto(self):
        for wiz in self:
            emp = wiz.employee_id.sudo()
            wiz.email = emp.work_email or emp.private_email or (
                emp.work_contact_id.email or "")
            wiz.telefono = emp.mobile_phone or emp.work_phone or (
                emp.work_contact_id.mobile or emp.work_contact_id.phone or "")

    @api.depends("linea_id", "liquidacion_id", "employee_id", "modo")
    def _compute_mensaje(self):
        for wiz in self:
            if wiz.liquidacion_id:
                doc = _("el finiquito y liquidación de prestaciones laborales")
                ref = wiz.liquidacion_id.name
            else:
                doc = _("el recibo de pago de nómina")
                ref = wiz.linea_id.planilla_id.name if wiz.linea_id else ""
            empresa = (wiz.linea_id.company_id.name
                       or wiz.liquidacion_id.company_id.name
                       or self.env.company.name)
            if wiz.modo == "firma_link":
                accion = _(
                    "Ingrese al siguiente enlace para revisarlo, firmarlo "
                    "electrónicamente y descargar su copia firmada.")
            else:
                accion = _(
                    "Se lo compartimos en PDF para su firma de recibido.")
            wiz.mensaje = _(
                "Estimado(a) %(emp)s:\n\n"
                "Le compartimos %(doc)s (%(ref)s) emitido por %(empresa)s. "
                "%(accion)s\n\n"
                "Al firmarlo —de forma manuscrita o electrónica— usted "
                "manifiesta que recibió conforme el pago detallado y acepta "
                "que la obligación correspondiente al período y conceptos "
                "liquidados queda saldada. La firma electrónica tiene la "
                "misma validez legal que la manuscrita, conforme al "
                "Decreto 47-2008 del Congreso de la República de Guatemala "
                "(Ley para el Reconocimiento de las Comunicaciones y Firmas "
                "Electrónicas).\n\n"
                "Cualquier duda sobre el cálculo puede reportarla a la "
                "administración.\n\nAtentamente,\n%(empresa)s"
            ) % {"emp": wiz.employee_id.name, "doc": doc, "ref": ref,
                 "empresa": empresa, "accion": accion}

    def _compute_sign_disponible(self):
        disponible = "sign.request" in self.env
        for wiz in self:
            wiz.sign_disponible = disponible

    # ------------------------------------------------------------------
    # Generación de documentos
    # ------------------------------------------------------------------
    def _generar_pdf(self):
        self.ensure_one()
        if self.liquidacion_id:
            reporte = "ktx_planilla_empleados_gt.action_report_liquidacion"
            registro = self.liquidacion_id
            nombre = _("Finiquito %s.pdf") % self.liquidacion_id.name.replace("/", "-")
        else:
            reporte = "ktx_planilla_empleados_gt.action_report_recibo_nomina"
            registro = self.linea_id
            nombre = _("Recibo %(pl)s %(emp)s.pdf") % {
                "pl": self.linea_id.planilla_id.name.replace("/", "-"),
                "emp": self.employee_id.name,
            }
        pdf, _mime = self.env["ir.actions.report"]._render_qweb_pdf(
            reporte, registro.ids)
        return pdf, nombre, registro

    def _registro_chatter(self):
        """Registro donde queda la bitácora del envío."""
        self.ensure_one()
        return self.liquidacion_id or self.linea_id.planilla_id

    def _crear_solicitud_firma(self):
        """Crea la solicitud en el módulo Firmas y devuelve (solicitud, link).

        El empleado abre el link, firma electrónicamente el documento dentro
        de Odoo y puede descargar su copia. El documento firmado queda
        guardado en Firmas (y en Documentos si la integración nativa
        Firmas → Documentos está configurada).
        """
        self.ensure_one()
        if "sign.request" not in self.env:
            raise UserError(_(
                "El módulo de Firmas (sign) no está instalado. Instálelo "
                "para firma electrónica con validez legal (Decreto 47-2008), "
                "o envíe el documento en PDF."))
        partner = self.employee_id._ktx_pl_get_partner()
        pdf, nombre, _registro = self._generar_pdf()
        adjunto = self.env["ir.attachment"].create({
            "name": nombre,
            "type": "binary",
            "datas": base64.b64encode(pdf),
            "mimetype": "application/pdf",
        })
        try:
            plantilla = self.env["sign.template"].create({
                "name": nombre.replace(".pdf", ""),
                "attachment_id": adjunto.id,
            })
            rol = self.env.ref("sign.sign_item_role_default",
                               raise_if_not_found=False)
            # Recuadro de firma sobre el área «RECIBIDO POR» del documento
            self.env["sign.item"].create({
                "template_id": plantilla.id,
                "type_id": self.env.ref("sign.sign_item_type_signature").id,
                "required": True,
                "responsible_id": rol.id if rol else False,
                "page": 1,
                "posX": 0.06, "posY": 0.82,
                "width": 0.28, "height": 0.07,
            })
            # no_sign_mail: el link se envía por el canal elegido aquí,
            # evitando el correo automático duplicado del módulo Firmas.
            solicitud = self.env["sign.request"].with_context(
                no_sign_mail=True).create({
                    "template_id": plantilla.id,
                    "reference": nombre.replace(".pdf", ""),
                    "request_item_ids": [(0, 0, {
                        "partner_id": partner.id,
                        "role_id": rol.id if rol else False,
                    })],
                })
            item = solicitud.request_item_ids[:1]
            base_url = solicitud.get_base_url()
            link = "%s/sign/document/%s/%s" % (
                base_url, solicitud.id, item.access_token)
        except Exception as e:
            _logger.warning("No se pudo crear la solicitud de firma: %s", e)
            raise UserError(_(
                "No se pudo crear la solicitud de firma digital (%s). "
                "Envíe el documento en PDF.") % e)
        self.firma_link = link
        self._registro_chatter().message_post(body=Markup(
            _("Solicitud de firma electrónica %(ref)s creada para %(emp)s. "
              "Link de firma: %(link)s")
        ) % {
            "ref": escape(solicitud.reference),
            "emp": escape(partner.name),
            "link": Markup('<a href="%s">%s</a>') % (link, link),
        })
        return solicitud, link

    # ------------------------------------------------------------------
    # Envío
    # ------------------------------------------------------------------
    def action_enviar(self):
        self.ensure_one()
        if not (self.linea_id or self.liquidacion_id):
            raise UserError(_("No hay documento que enviar."))
        link = None
        if self.modo == "firma_link":
            _solicitud, link = self._crear_solicitud_firma()
        if self.canal == "email":
            return self._enviar_email(link)
        return self._enviar_whatsapp(link)

    def _cuerpo_con_link(self, link):
        """Mensaje del wizard + botón/enlace de firma en HTML."""
        cuerpo = Markup("<p>%s</p>") % self.mensaje
        cuerpo = Markup(str(cuerpo).replace("\n", "<br/>"))
        if link:
            cuerpo += Markup(
                '<p style="margin: 18px 0; text-align: center;">'
                '<a href="%s" style="background-color: #198754; color: #fff; '
                'padding: 10px 24px; border-radius: 5px; '
                'text-decoration: none; font-weight: bold;">%s</a></p>'
                '<p style="font-size: 12px; color: #666;">%s<br/>'
                '<a href="%s">%s</a></p>'
            ) % (link, _("Revisar y Firmar Documento"),
                 _("Si el botón no funciona, copie este enlace en su navegador:"),
                 link, link)
        return cuerpo

    def _enviar_email(self, link=None):
        self.ensure_one()
        if not self.email:
            raise UserError(_("Indique el correo del empleado."))
        if self.liquidacion_id:
            referencia = _("Finiquito %s") % self.liquidacion_id.name
        else:
            referencia = _("Recibo de Nómina %(pl)s — %(emp)s") % {
                "pl": self.linea_id.planilla_id.name,
                "emp": self.employee_id.name,
            }
        vals = {
            "subject": _("Firma electrónica: %s") % referencia
            if link else referencia,
            "email_to": self.email,
            "body_html": self._cuerpo_con_link(link),
        }
        if not link:
            # Modo PDF: se adjunta el documento para firma manuscrita
            pdf, nombre, _registro = self._generar_pdf()
            adjunto = self.env["ir.attachment"].create({
                "name": nombre,
                "type": "binary",
                "datas": base64.b64encode(pdf),
                "mimetype": "application/pdf",
            })
            vals["attachment_ids"] = [(6, 0, adjunto.ids)]
        mail = self.env["mail.mail"].create(vals)
        mail.send()
        detalle = (_("link de firma electrónica enviado por correo a %s")
                   if link else
                   _("recibo en PDF enviado por correo a %s")) % self.email
        self._registro_chatter().message_post(
            body=escape(detalle.capitalize() + "."))
        return self._notificar(detalle.capitalize() + ".")

    def _enviar_whatsapp(self, link=None):
        self.ensure_one()
        if not self.telefono:
            raise UserError(_("Indique el teléfono del empleado."))
        texto = self.mensaje or ""
        if link:
            texto += _("\n\nFirme aquí su documento:\n%s") % link
        else:
            # Modo PDF: WhatsApp no permite adjuntar desde un link wa.me;
            # el PDF queda en el chatter para compartirlo manualmente.
            pdf, nombre, registro = self._generar_pdf()
            adjunto = self.env["ir.attachment"].create({
                "name": nombre,
                "type": "binary",
                "datas": base64.b64encode(pdf),
                "res_model": registro._name,
                "res_id": registro.id,
                "mimetype": "application/pdf",
            })
            self._registro_chatter().message_post(
                body=_("Recibo en PDF preparado para envío por WhatsApp a %s "
                       "(adjúntelo manualmente en la conversación).")
                % escape(self.telefono),
                attachment_ids=adjunto.ids)
        if link:
            self._registro_chatter().message_post(
                body=_("Link de firma electrónica enviado por WhatsApp a %s.")
                % escape(self.telefono))
        telefono = "".join(c for c in self.telefono if c.isdigit())
        if len(telefono) == 8:  # número local de Guatemala
            telefono = "502" + telefono
        url = "https://wa.me/%s?text=%s" % (telefono, quote(texto))
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    def _notificar(self, mensaje):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Envío de recibo"),
                "message": mensaje,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
