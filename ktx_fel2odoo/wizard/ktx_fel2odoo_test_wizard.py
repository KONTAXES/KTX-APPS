# -*- coding: utf-8 -*-
"""Modo de prueba: crea facturas desde XML FEL cargados manualmente.

Permite validar todo el flujo de creacion de facturas (parseo FEL, mapeo de
impuestos, frases SAT, retenciones y contactos) sin depender de la API del
proveedor. Util mientras se activa el plan de apifelcore o para reprocesar un
XML puntual.
"""
import base64

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class KtxFel2odooTestWizard(models.TransientModel):
    _name = 'ktx.fel2odoo.test.wizard'
    _description = 'Prueba FEL2Odoo con XML manual'

    config_id = fields.Many2one(
        'ktx.fel2odoo.config', string='Conexion', required=True,
        default=lambda self: self.env['ktx.fel2odoo.config'].search([], limit=1),
    )
    company_id = fields.Many2one(
        'res.company', related='config_id.company_id', readonly=True)
    import_type = fields.Selection([
        ('purchase', 'Compras (Recibidas)'),
        ('sale', 'Ventas (Emitidas)'),
    ], string='Tipo', required=True, default='purchase')
    journal_id = fields.Many2one(
        'account.journal', string='Diario',
        domain="[('type', 'in', ('sale', 'purchase'))]", required=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Archivos XML',
        help='Cargue uno o varios XML FEL descargados de la SAT.')
    auto_confirm = fields.Boolean(
        'Confirmar facturas', default=False,
        help='Publica (confirma) las facturas creadas.')

    @api.onchange('import_type', 'config_id')
    def _onchange_journal_default(self):
        """Propone el diario configurado en la conexion segun el tipo."""
        for wiz in self:
            if not wiz.config_id:
                continue
            wiz.journal_id = (
                wiz.config_id.journal_purchase_id
                if wiz.import_type == 'purchase'
                else wiz.config_id.journal_sale_id)

    def action_run(self):
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_('Adjunte al menos un archivo XML FEL.'))
        if not self.journal_id:
            raise UserError(_('Seleccione un diario contable.'))

        xml_files = []
        for att in self.attachment_ids:
            if att.datas:
                xml_files.append((att.name or 'documento.xml',
                                  base64.b64decode(att.datas)))
        if not xml_files:
            raise UserError(_('Los archivos adjuntos no tienen contenido.'))

        config = self.config_id.with_company(self.company_id)
        session, invoices = config._create_invoices_from_xmls(
            self.import_type, self.journal_id, xml_files)
        if self.auto_confirm and invoices:
            config._confirm_invoices(invoices)

        if invoices:
            action = self.env['ir.actions.act_window']._for_xml_id(
                'account.action_move_in_invoice_type' if self.import_type == 'purchase'
                else 'account.action_move_out_invoice_type')
            action['domain'] = [('id', 'in', invoices.ids)]
            action['context'] = {}
            return action

        # Sin facturas: abrir la sesion de importacion para ver el motivo.
        if session:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Sesion de importacion'),
                'res_model': 'ktx.import.session',
                'res_id': session.id,
                'view_mode': 'form',
            }
        raise UserError(_('No se pudo crear ninguna factura. Revise los XML.'))
