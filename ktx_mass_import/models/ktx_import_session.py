# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class KtxImportSession(models.Model):
    _name = 'ktx.import.session'
    _description = 'Sesion de Importacion Masiva SAT FEL'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(
        'Referencia', required=True, copy=False,
        tracking=True, readonly=True,
        default='/',
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True, index=True,
        default=lambda self: self.env.company
    )
    import_type = fields.Selection([
        ('purchase', 'Facturas de Compras (Recibidas)'),
        ('sale', 'Facturas de Ventas (Emitidas)'),
    ], string='Tipo', required=True, default='purchase', tracking=True)
    state = fields.Selection([
        ('draft', 'Nuevo'),
        ('loaded', 'Archivos Cargados'),
        ('tested', 'Probado'),
        ('done', 'Importado'),
    ], default='draft', tracking=True, copy=False)
    journal_id = fields.Many2one(
        'account.journal', string='Diario Facturas',
        domain="[('type', 'in', ['sale', 'purchase'])]"
    )
    journal_receipts_id = fields.Many2one(
        'account.journal', string='Diario Recibos',
        domain="[('type', 'in', ['sale', 'purchase'])]",
        help='Diario para documentos tipo RECI. Si se deja vacio se usa el Diario Facturas.'
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', 'ktx_session_att_rel', 'session_id', 'att_id',
        string='Archivos XML'
    )
    document_ids = fields.One2many(
        'ktx.import.document', 'session_id', string='Documentos'
    )
    contact_ids = fields.One2many(
        'ktx.import.contact', 'session_id', string='Contactos Nuevos Detectados'
    )
    notes = fields.Text('Notas')

    # --- Contadores ---
    total_count = fields.Integer('Total', compute='_compute_counts', store=True)
    valid_count = fields.Integer('Vigentes', compute='_compute_counts', store=True)
    anulado_count = fields.Integer('Anulados', compute='_compute_counts', store=True)
    cais_count = fields.Integer('CAIS', compute='_compute_counts', store=True)
    civa_count = fields.Integer('CIVA', compute='_compute_counts', store=True)
    duplicate_count = fields.Integer('Duplicados', compute='_compute_counts', store=True)
    incompatible_count = fields.Integer('No Compatibles', compute='_compute_counts', store=True)
    wrong_nit_count = fields.Integer('NIT Incorrecto', compute='_compute_counts', store=True)
    imported_count = fields.Integer('Importados', compute='_compute_counts', store=True)
    error_count = fields.Integer('Con Error', compute='_compute_counts', store=True)
    new_contact_count = fields.Integer('Contactos Nuevos', compute='_compute_counts', store=True)

    # Indice de busqueda: agrega NIT/serie/autorizacion de los documentos
    # para permitir filtrar la sesion por estos datos en la barra de busqueda.
    search_index = fields.Char(
        'Indice de busqueda', compute='_compute_search_index', store=True)

    @api.depends('document_ids.nit_emisor', 'document_ids.nit_receptor',
                 'document_ids.serie', 'document_ids.numero_autorizacion')
    def _compute_search_index(self):
        for rec in self:
            parts = []
            for d in rec.document_ids:
                parts += [d.nit_emisor or '', d.nit_receptor or '',
                          d.serie or '', d.numero_autorizacion or '']
            rec.search_index = ' '.join(p for p in parts if p)

    @api.depends('document_ids.state', 'contact_ids')
    def _compute_counts(self):
        for rec in self:
            docs = rec.document_ids
            rec.total_count = len(docs)
            rec.valid_count = len(docs.filtered(lambda d: d.state == 'valid'))
            rec.anulado_count = len(docs.filtered(lambda d: d.state == 'anulado'))
            rec.cais_count = len(docs.filtered(lambda d: d.state == 'cais'))
            rec.civa_count = len(docs.filtered(lambda d: d.state == 'civa'))
            rec.duplicate_count = len(docs.filtered(lambda d: d.state == 'duplicate'))
            rec.incompatible_count = len(docs.filtered(lambda d: d.state == 'incompatible'))
            rec.wrong_nit_count = len(docs.filtered(lambda d: d.state == 'wrong_nit'))
            rec.imported_count = len(docs.filtered(lambda d: d.state == 'imported'))
            rec.error_count = len(docs.filtered(lambda d: d.state == 'error'))
            rec.new_contact_count = len(rec.contact_ids)

    @api.model_create_multi
    def create(self, vals_list):
        IrSeq = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            if vals.get('name', '/') in (False, '/', ''):
                seq = IrSeq.search([('code', '=', 'ktx.import.session')], limit=1)
                if not seq:
                    seq = IrSeq.create({
                        'name': 'KTX Importacion Masiva FEL',
                        'code': 'ktx.import.session',
                        'prefix': 'IMP/%(year)s/%(month)s/',
                        'padding': 4,
                        'number_next': 1,
                        'number_increment': 1,
                        'company_id': False,
                    })
                vals['name'] = seq._next() or '/'
        return super().create(vals_list)

    def action_load_files(self):
        """Parsea los adjuntos XML y crea registros de documento."""
        self.ensure_one()
        self.document_ids.filtered(lambda d: d.state != 'imported').unlink()

        loaded = 0
        anulados = 0
        cais = 0
        civa = 0
        incompatible = 0
        for att in self.attachment_ids:
            doc = self.env['ktx.import.document'].create({
                'session_id': self.id,
                'attachment_id': att.id,
                'filename': att.name,
                'state': 'pending',
                'company_id': self.company_id.id,
            })
            ok = doc._parse_and_fill()
            if not ok:
                incompatible += 1
            elif doc.state == 'anulado':
                anulados += 1
            elif doc.state == 'cais':
                cais += 1
            elif doc.state == 'civa':
                civa += 1
            else:
                loaded += 1

        self.state = 'loaded'
        parts = [_('Cargados: %d vigentes') % loaded]
        if anulados:
            parts.append(_('%d anulados') % anulados)
        if cais:
            parts.append(_('%d CAIS') % cais)
        if civa:
            parts.append(_('%d CIVA') % civa)
        if incompatible:
            parts.append(_('%d no compatibles') % incompatible)
        msg = ', '.join(parts) + '.'
        self.message_post(body=msg)
        ntype = 'success' if incompatible == 0 else 'warning'
        return self._notify(_('Archivos cargados'), msg, ntype)

    def action_test(self):
        """Valida todos los documentos: duplicados, NIT, formato. Detecta y
        crea los contactos nuevos para configurar sus cuentas contables."""
        self.ensure_one()
        company_vat = (self.env.company.vat or '').strip().upper()
        params = self.env['ir.config_parameter'].sudo()
        allow_diff_nit = params.get_param('ktx_mass_import.allow_different_nit', 'False') == 'True'
        allow_diff_emisor = params.get_param('ktx_mass_import.allow_different_emisor_nit', 'False') == 'True'

        for doc in self.document_ids.filtered(lambda d: d.state not in ('imported', 'incompatible', 'anulado', 'cais', 'civa')):
            doc._validate(company_vat, allow_diff_nit, allow_diff_emisor, self.import_type)

        # Detectar contactos nuevos a partir de los documentos vigentes.
        new_contacts = self._collect_new_contacts()

        self.state = 'tested'

        issues = self.document_ids.filtered(lambda d: d.state in ('duplicate', 'wrong_nit', 'error'))
        if issues:
            details = '\n'.join(
                '[%s] %s: %s' % (d.state.upper(), d.filename, d.error_message or '')
                for d in issues[:30]
            )
            msg = _('%d problemas detectados:\n%s') % (len(issues), details)
            self.message_post(body=Markup(msg.replace('\n', '<br/>')))
            return self._notify(_('Atencion - Problemas detectados'), msg, 'danger', sticky=True)

        extra = ''
        if self.anulado_count:
            extra += _(' %d anulados seran omitidos.') % self.anulado_count
        if self.cais_count:
            extra += _(' %d CAIS seran omitidos.') % self.cais_count
        if self.civa_count:
            extra += _(' %d CIVA seran omitidos.') % self.civa_count
        if new_contacts:
            extra += _(' %d contactos nuevos creados (configure sus cuentas).') % new_contacts
        msg = _('Todo parece correcto. %d documentos vigentes listos para importar.') % self.valid_count + extra
        self.message_post(body=msg)
        return self._notify(_('Validacion exitosa'), msg, 'success')

    def _collect_new_contacts(self):
        """Crea los contactos que no existen en Odoo y los registra en la
        sesion para que el usuario asigne sus cuentas por cobrar/pagar.
        Retorna la cantidad de contactos nuevos creados en esta llamada."""
        self.ensure_one()
        Document = self.env['ktx.import.document']
        Contact = self.env['ktx.import.contact']
        gt = self.env.ref('base.gt', raise_if_not_found=False)

        existing_partner_ids = set(self.contact_ids.mapped('partner_id').ids)
        seen_vats = set()
        created = 0
        for doc in self.document_ids.filtered(lambda d: d.state == 'valid'):
            data = {
                'nit_emisor': doc.nit_emisor, 'nombre_emisor': doc.nombre_emisor,
                'nit_receptor': doc.nit_receptor, 'nombre_receptor': doc.nombre_receptor,
            }
            nit, nombre = Document._get_partner_identity(data, self.import_type)
            nit_clean = (nit or '').strip().upper()
            if not nit_clean or nit_clean == 'CF' or nit_clean in seen_vats:
                continue
            seen_vats.add(nit_clean)

            if Document._find_partner(nit, nombre):
                continue  # ya existe en Odoo

            partner = self.env['res.partner'].sudo().create({
                'name': nombre or nit_clean,
                'vat': nit_clean,
                'street': 'CIUDAD',
                'country_id': gt.id if gt else False,
            })
            if partner.id not in existing_partner_ids:
                Contact.create({'session_id': self.id, 'partner_id': partner.id})
                existing_partner_ids.add(partner.id)
                created += 1
        return created

    def action_delete_anulados(self):
        self.ensure_one()
        to_del = self.document_ids.filtered(lambda d: d.state == 'anulado')
        count = len(to_del)
        to_del.unlink()
        return self._notify(_('Anulados eliminados'),
                            _('%d documentos anulados eliminados de la lista.') % count, 'warning')

    def action_delete_cais(self):
        self.ensure_one()
        to_del = self.document_ids.filtered(lambda d: d.state == 'cais')
        count = len(to_del)
        to_del.unlink()
        return self._notify(_('CAIS eliminados'),
                            _('%d documentos CAIS eliminados de la lista.') % count, 'warning')

    def action_delete_civa(self):
        self.ensure_one()
        to_del = self.document_ids.filtered(lambda d: d.state == 'civa')
        count = len(to_del)
        to_del.unlink()
        return self._notify(_('CIVA eliminados'),
                            _('%d documentos CIVA eliminados de la lista.') % count, 'warning')

    def action_delete_duplicates(self):
        self.ensure_one()
        to_del = self.document_ids.filtered(lambda d: d.state == 'duplicate')
        count = len(to_del)
        to_del.unlink()
        return self._notify(_('Duplicados eliminados'), _('%d documentos duplicados eliminados.') % count, 'warning')

    def action_delete_incompatible(self):
        self.ensure_one()
        to_del = self.document_ids.filtered(lambda d: d.state == 'incompatible')
        count = len(to_del)
        to_del.unlink()
        return self._notify(_('No compatibles eliminados'), _('%d documentos no compatibles eliminados.') % count, 'warning')

    def action_delete_wrong_nit(self):
        self.ensure_one()
        to_del = self.document_ids.filtered(lambda d: d.state == 'wrong_nit')
        count = len(to_del)
        to_del.unlink()
        return self._notify(_('NIT incorrecto eliminados'), _('%d documentos con NIT incorrecto eliminados.') % count, 'warning')

    def action_create_invoices(self):
        """Crea facturas en Odoo para todos los documentos vigentes validos."""
        self.ensure_one()
        if not self.journal_id:
            raise UserError(_('Seleccione un Diario Contable antes de crear las facturas.'))

        invoices = self.env['account.move']
        errors = 0
        journal_receipts = self.journal_receipts_id or self.journal_id
        for doc in self.document_ids.filtered(lambda d: d.state == 'valid'):
            try:
                inv = doc._create_invoice(self.journal_id, self.import_type, journal_receipts)
                if inv:
                    invoices |= inv
            except Exception as e:
                _logger.error('Error creando factura para %s: %s', doc.filename, str(e))
                doc.write({'state': 'error', 'error_message': str(e)})
                errors += 1

        if invoices:
            self.state = 'done'
            self.message_post(body=_('Se crearon %d facturas. Errores: %d.') % (len(invoices), errors))
            action = self.env['ir.actions.act_window']._for_xml_id(
                'account.action_move_in_invoice_type' if self.import_type == 'purchase'
                else 'account.action_move_out_invoice_type'
            )
            action['domain'] = [('id', 'in', invoices.ids)]
            return action

        return self._notify(
            _('Sin facturas'), _('No se crearon facturas. Errores: %d.') % errors, 'danger'
        )

    def _notify(self, title, message, ntype='success', sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': ntype,
                'sticky': sticky,
                # Recarga el formulario tras la notificacion para que se
                # actualicen el estado y los botones de la siguiente fase.
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
