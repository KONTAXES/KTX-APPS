# -*- coding: utf-8 -*-
"""Emision y anulacion de facturas de venta ante la SAT via FEL2Odoo.

Usa el mismo proveedor intermediario (apifelcore.com) ya configurado en
ktx.fel2odoo.config para CERTIFICAR facturas de venta (FACT) directamente
desde Odoo, ademas de sincronizar las que ya existen en la SAT. Solo
funciona en diarios de venta marcados explicitamente (ver
ktx_fel2odoo_account_journal.py, pestana "FEL2Odoo" en el diario).

Alcance actual (V1): solo facturas de venta normales confirmadas
(out_invoice, tipo FACT). Notas de credito, factura especial, factura
cambiaria y exportacion quedan pendientes de confirmar con el proveedor,
ya que el endpoint de emision no documenta un parametro de tipo de
documento ni de referencia a un documento original.

Logica para evitar duplicidad de certificaciones y coexistir con otros
modulos (p. ej. l10n_gt_corp/corposistemas, que usa OTRO certificador y
NO se modifica aqui):
- Todo lo de este modulo esta gateado por journal_id.ktx_fel2odoo_enabled:
  si el diario de la factura NO esta marcado para FEL2Odoo, este modulo no
  interviene en absoluto (button_cancel/action_post se comportan igual que
  sin este modulo instalado, delegando a super()/otros modulos).
- Certificar (action_post / auto o manual) se BLOQUEA si el estado ya es
  'emitido' (no se repite) o 'anulado' (no se puede volver a certificar un
  documento anulado ante la SAT).
- Anular pasa SIEMPRE por el mismo wizard (motivo opcional, con generico
  "Anular documento" si se deja vacio), sea por el boton dedicado o por el
  flujo estandar de Odoo (restablecer a borrador + Cancelar), que este
  modulo intercepta SOLO cuando aplica (diario FEL2Odoo + estado emitido).

Seguridad: la emision crea un documento LEGAL REAL ante la SAT. Por eso:
- Requiere 'enable_emision' en la conexion Y 'ktx_fel2odoo_enabled' en el
  diario de la factura.
- Solo opera sobre facturas de venta ya CONFIRMADAS (posted).
- Restringida a gestores contables.
- El formato de respuesta de /emitir-documento no viene documentado con un
  ejemplo: si no se puede identificar un UUID valido en la respuesta, NO se
  marca como emitida (para no arriesgar un duplicado); se deja la
  respuesta cruda en el chatter para revision manual.
"""
from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    fel2odoo_state = fields.Selection([
        ('none', 'No emitido'),
        ('emitido', 'Emitido (SAT)'),
        ('anulado', 'Anulado (SAT)'),
        ('error', 'Error al emitir'),
    ], string='Estado FEL2Odoo', default='none', copy=False, readonly=True, tracking=True)
    fel2odoo_uuid = fields.Char('UUID FEL', copy=False, readonly=True)
    fel2odoo_serie = fields.Char('Serie FEL', copy=False, readonly=True)
    fel2odoo_numero = fields.Char('Numero FEL', copy=False, readonly=True)
    fel2odoo_error = fields.Text('Ultimo error FEL2Odoo', copy=False, readonly=True)
    # Related SOLO para poder usarlo en condiciones invisible= de la vista
    # (las rutas punteadas tipo journal_id.xxx no funcionan ahi directamente).
    fel2odoo_journal_enabled = fields.Boolean(
        related='journal_id.ktx_fel2odoo_enabled', readonly=True)

    # ==================================================================
    # Overrides del ciclo de vida (confirmar / cancelar)
    # ==================================================================
    def action_post(self):
        # Un documento ya anulado ante la SAT no puede volver a confirmarse:
        # el UUID original ya quedo invalidado en la SAT, no se reutiliza.
        blocked = self.filtered(
            lambda m: m.journal_id.ktx_fel2odoo_enabled and m.fel2odoo_state == 'anulado')
        if blocked:
            raise UserError(_(
                'La(s) factura(s) %s ya fueron ANULADAS ante la SAT y no '
                'pueden volver a confirmarse (el documento original quedo '
                'invalidado). Cree una factura nueva si corresponde.'
            ) % ', '.join(blocked.mapped('name')))

        res = super().action_post()

        for move in self:
            if (move.move_type == 'out_invoice'
                    and move.journal_id.ktx_fel2odoo_enabled
                    and move.journal_id.ktx_fel2odoo_auto_certificar
                    and move.fel2odoo_state != 'emitido'):
                move._fel2odoo_emitir_auto()
        return res

    def button_cancel(self):
        # Si alguna factura seleccionada ya fue emitida por FEL2Odoo, no se
        # puede cancelar directo: primero hay que anularla ante la SAT (con
        # motivo). Las demas (diario no configurado, o ya sin emitir/ya
        # anuladas) siguen el flujo normal de Odoo sin interferencia.
        needs_sat = self.filtered(
            lambda m: m.journal_id.ktx_fel2odoo_enabled and m.fel2odoo_state == 'emitido')
        if not needs_sat:
            return super().button_cancel()
        if needs_sat != self or len(needs_sat) > 1:
            raise UserError(_(
                'Anule de una en una las facturas certificadas por FEL2Odoo '
                '(%s), indicando el motivo de anulacion.'
            ) % ', '.join(needs_sat.mapped('name')))
        return needs_sat.action_fel2odoo_anular_wizard()

    # ==================================================================
    # Emision
    # ==================================================================
    def action_fel2odoo_emitir(self):
        """Emite esta factura de venta ante la SAT usando FEL2Odoo (manual)."""
        self.ensure_one()
        self._fel2odoo_check_emitible()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Solo un gestor contable puede emitir facturas ante la SAT.'))

        Config = self.env['ktx.fel2odoo.config']
        config = Config._get_emision_config(self.company_id)
        try:
            response = config.with_company(self.company_id)._emitir_documento(self)
        except UserError as exc:
            self.write({'fel2odoo_state': 'error', 'fel2odoo_error': str(exc)})
            raise
        self._apply_emision_response(config, response)
        return config._notify(
            _('Factura emitida'),
            _('Factura %s emitida ante la SAT.') % self.name, 'success')

    def _fel2odoo_emitir_auto(self):
        """Certificacion automatica al confirmar (diario con
        ktx_fel2odoo_auto_certificar). A diferencia de la accion manual, un
        fallo aqui NO revierte la publicacion: solo queda registrado como
        error para reintentar manualmente despues (igual que el patron ya
        usado en l10n_gt_corp para su propio certificador)."""
        self.ensure_one()
        try:
            self._fel2odoo_check_emitible()
        except UserError:
            return
        Config = self.env['ktx.fel2odoo.config']
        try:
            config = Config._get_emision_config(self.company_id)
            response = config.with_company(self.company_id)._emitir_documento(self)
            self._apply_emision_response(config, response)
        except UserError as exc:
            self.write({'fel2odoo_state': 'error', 'fel2odoo_error': str(exc)})
            self.message_post(body=_(
                'FEL2Odoo no pudo certificar automaticamente al confirmar: %s') % exc)

    def _fel2odoo_check_emitible(self):
        """Validaciones comunes a la emision manual y automatica. Es la
        barrera central contra duplicar certificaciones."""
        self.ensure_one()
        if self.move_type != 'out_invoice':
            raise UserError(_(
                'Por ahora FEL2Odoo solo puede emitir facturas de venta normales.'))
        if self.state != 'posted':
            raise UserError(_('Confirme (publique) la factura antes de emitirla ante la SAT.'))
        if not self.journal_id.ktx_fel2odoo_enabled:
            raise UserError(_(
                'El diario "%s" no esta configurado para FEL2Odoo (pestana '
                'FEL2Odoo en el diario).') % self.journal_id.display_name)
        if self.fel2odoo_state == 'emitido':
            raise UserError(_(
                'Esta factura ya fue emitida ante la SAT por FEL2Odoo (UUID %s).'
            ) % self.fel2odoo_uuid)
        if self.fel2odoo_state == 'anulado':
            raise UserError(_(
                'Esta factura fue anulada ante la SAT; no se puede volver a emitir.'))
        self._fel2odoo_check_regimen_iva()

    def _fel2odoo_check_regimen_iva(self):
        """El endpoint de emision NO permite indicar el regimen ni el IVA por
        item (no existe ese parametro documentado): apifelcore decide
        internamente segun el regimen YA REGISTRADO ante la SAT para el NIT.
        Por eso, si la empresa esta en un regimen que NO debe llevar IVA
        (pequeno contribuyente y variantes) pero la factura de Odoo SI tiene
        impuesto configurado en sus lineas, es una inconsistencia real de
        configuracion (no algo que este modulo pueda corregir enviando algun
        parametro): se bloquea ANTES de emitir para revisar los impuestos."""
        self.ensure_one()
        company = self.company_id
        if 'vat_affiliation' not in company._fields:
            return
        regimenes_sin_iva = ('PEQ', 'PEE', 'EXE', 'EXI')
        if company.vat_affiliation not in regimenes_sin_iva:
            return
        tiene_iva = any(
            tax.amount for line in self.invoice_line_ids
            if line.display_type in (False, 'product')
            for tax in line.tax_ids
        )
        if tiene_iva:
            raise UserError(_(
                'La empresa esta registrada con el regimen "%s" ante la SAT '
                '(no deberia incluir IVA), pero esta factura tiene lineas '
                'con impuesto configurado. El proveedor no permite indicar '
                'el regimen por la API de emision: debe coincidir con lo ya '
                'registrado ante la SAT/apifelcore para este NIT. Revise los '
                'impuestos de la factura antes de emitir.'
            ) % company.vat_affiliation)

    def _apply_emision_response(self, config, response):
        """Interpreta la respuesta del proveedor (formato NO documentado con
        un ejemplo): intenta varias claves candidatas para UUID/serie/numero
        y, si vienen, adjunta el XML/PDF al chatter. Si no logra identificar
        un UUID valido, NO marca la factura como emitida (para no arriesgar
        un duplicado en un reintento) y deja la respuesta cruda en el
        chatter para revision manual."""
        self.ensure_one()
        data = response
        if isinstance(response, dict):
            for key in ('data', 'result', 'documento', 'dte'):
                inner = response.get(key)
                if isinstance(inner, dict):
                    data = inner
                    break
        pick = config._pick
        uuid = pick(data, ['uuid', 'numero_autorizacion', 'numeroAutorizacion', 'no_autorizacion'])
        serie = pick(data, ['serie', 'fe_serie'])
        numero = pick(data, ['numero', 'numero_documento', 'fe_number', 'correlativo'])
        xml_raw = pick(data, ['xml', 'xml_base64'])

        if not uuid:
            self.write({
                'fel2odoo_state': 'error',
                'fel2odoo_error': _(
                    'El proveedor respondio pero no se pudo identificar el '
                    'UUID en la respuesta. Revise el chatter antes de reintentar.'),
            })
            self.message_post(body=Markup(_(
                '<b>Emision FEL2Odoo: respuesta sin UUID reconocible</b><br/>'
                'Revise manualmente antes de asumir que se emitio (para no '
                'arriesgar un duplicado si reintenta).<br/><pre>%s</pre>'
            )) % config._debug_snippet(response)[:4000])
            raise UserError(_(
                'El proveedor respondio pero FEL2Odoo no pudo identificar el '
                'UUID del documento emitido. Revise el chatter de la factura '
                'antes de reintentar.'))

        vals = {
            'fel2odoo_state': 'emitido',
            'fel2odoo_uuid': uuid,
            'fel2odoo_error': False,
        }
        if serie:
            vals['fel2odoo_serie'] = serie
        if numero:
            vals['fel2odoo_numero'] = numero
            # Se replica en 'ref' para que las busquedas/filtros estandar de
            # Odoo (que buscan por ref) tambien encuentren estas facturas.
            vals['ref'] = numero
        self.write(vals)

        chatter = Markup(_(
            '<b>Factura emitida ante la SAT por FEL2ODOO</b><br/>'
            'UUID: %s<br/>Serie: %s<br/>Numero: %s'
        )) % (uuid, serie or '-', numero or '-')
        attachments = []
        xml_bytes = config._coerce_xml_bytes(xml_raw) if xml_raw else None
        if xml_bytes:
            attachments.append(('%s.xml' % uuid, xml_bytes))
        # Se reutiliza el extractor recursivo de PDF (maneja base64 anidado en
        # 'data' y URL de descarga, igual que descargar-pdf), en vez de decodificar
        # a mano solo el primer nivel: asi la factura emitida adjunta el PDF sin
        # importar la forma exacta de la respuesta del proveedor.
        pdf_bytes = config._coerce_pdf_bytes(response)
        if pdf_bytes:
            attachments.append(('%s.pdf' % uuid, pdf_bytes))
        self.message_post(body=chatter, attachments=attachments)

    # ==================================================================
    # Anulacion
    # ==================================================================
    def action_fel2odoo_anular_wizard(self):
        """Abre el asistente para anular esta factura ante la SAT (pide
        motivo, opcional). Mismo destino tanto si se llama desde el boton
        dedicado como desde el override de button_cancel."""
        self.ensure_one()
        if self.fel2odoo_state != 'emitido':
            raise UserError(_('Solo se pueden anular facturas emitidas por FEL2Odoo.'))
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('Solo un gestor contable puede anular facturas ante la SAT.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Anular factura ante la SAT'),
            'res_model': 'ktx.fel2odoo.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_id': self.id},
        }
