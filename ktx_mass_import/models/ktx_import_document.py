# -*- coding: utf-8 -*-
import base64
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime

from odoo import fields, models, _
from odoo.exceptions import UserError
from markupsafe import Markup

_logger = logging.getLogger(__name__)

DTE_NS = {'dte': 'http://www.sat.gob.gt/dte/fel/0.2.0'}

# Deteccion de declaraciones peligrosas: un DTE FEL legitimo NUNCA lleva DOCTYPE
# ni ENTITY. Rechazarlos bloquea XXE (entidades externas) y "billion laughs"
# (expansion de entidades) antes de parsear.
_XML_DANGER = re.compile(rb'<!\s*(DOCTYPE|ENTITY)', re.IGNORECASE)


def _safe_fromstring(xml_bytes):
    """Parsea XML de forma segura contra XXE y expansion de entidades.

    1) Rechaza cualquier XML con DOCTYPE/ENTITY (no aplica a DTE FEL).
    2) Usa defusedxml si esta instalado; si no, el ElementTree estandar (que
       no resuelve entidades externas por defecto).
    """
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode('utf-8')
    if _XML_DANGER.search(xml_bytes[:16384] or b''):
        raise UserError(_(
            'XML rechazado por seguridad: contiene DOCTYPE/ENTITY, no permitido '
            'en un DTE FEL.'))
    try:
        from defusedxml.ElementTree import fromstring as _df_fromstring
        return _df_fromstring(
            xml_bytes, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except ImportError:
        return ET.fromstring(xml_bytes)


# Secuencias tipicas de "mojibake": un XML UTF-8 que en algun paso previo se
# decodifico como ISO-8859-1/CP1252 (p. ej. resp.text con charset adivinado).
# Las tildes/enies quedan como 'Ã¡', 'Ã©', 'Ã±'... Estas marcas casi nunca
# aparecen en texto espanol correcto, asi que sirven para detectar el caso.
_MOJIBAKE_MARKERS = ('Ã', 'Â', 'â€')


def _repair_mojibake(text):
    """Recupera texto UTF-8 que fue mal decodificado como Latin-1 (mojibake).

    Solo actua si el texto tiene las marcas tipicas de mojibake y el
    'round-trip' latin-1 -> utf-8 tiene exito y REDUCE esas marcas; en
    cualquier otro caso devuelve el texto intacto (para no danar texto que ya
    esta bien). OJO: esto recupera el caso RECUPERABLE (bytes UTF-8 leidos con
    el codec equivocado). Cuando el origen ya perdio la tilde con
    encode('ascii','ignore') -> 'REVISION'->'REVISIN' o 'replace' -> 'asesor?a',
    la informacion ya no existe y NINGUN codigo puede reconstruirla."""
    if not text or not any(m in text for m in _MOJIBAKE_MARKERS):
        return text
    try:
        repaired = text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    before = sum(text.count(m) for m in _MOJIBAKE_MARKERS)
    after = sum(repaired.count(m) for m in _MOJIBAKE_MARKERS)
    return repaired if after < before else text


def _clean(text):
    """Normaliza texto a caracteres validos en espanol (incluye tildes y enies)."""
    if not text:
        return ''
    text = _repair_mojibake(str(text))
    text = unicodedata.normalize('NFC', text)
    replacements = {
        '–': '-', '—': '-', '‘': "'", '’': "'",
        '“': '"', '”': '"', '«': '"', '»': '"',
        '°': ' grados ', ' ': ' ',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    result = []
    for c in text:
        cat = unicodedata.category(c)
        if cat.startswith('L') or cat.startswith('N') or c in ' .,;:()-/#@&%*+="\'' or cat == 'Zs':
            result.append(c)
    return ' '.join(''.join(result).split())


def _parse_fecha(fecha_str):
    """Convierte la cadena FechaHoraEmision del XML a datetime."""
    if not fecha_str:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%d'):
        try:
            return datetime.strptime(fecha_str[:26], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(fecha_str[:19])
    except Exception:
        return None


class KtxImportDocument(models.Model):
    _name = 'ktx.import.document'
    _description = 'Documento XML FEL para Importacion'
    _order = 'sequence, id'

    session_id = fields.Many2one(
        'ktx.import.session', required=True, ondelete='cascade', index=True
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa', index=True,
        related='session_id.company_id', store=True
    )
    sequence = fields.Integer(default=10)
    attachment_id = fields.Many2one('ir.attachment', string='Adjunto')
    filename = fields.Char('Archivo', required=True)
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('valid', 'Vigente'),
        ('anulado', 'Anulado'),
        ('cais', 'CAIS'),
        ('civa', 'CIVA'),
        ('duplicate', 'Duplicado'),
        ('incompatible', 'No Compatible'),
        ('wrong_nit', 'NIT Incorrecto'),
        ('imported', 'Importado'),
        ('error', 'Error'),
    ], default='pending')

    # Datos cabecera parseados
    tipo_documento = fields.Char('Tipo DTE')
    numero_autorizacion = fields.Char('No. Autorizacion', index=True)
    serie = fields.Char('Serie')
    fecha_emision = fields.Datetime('Fecha Emision')
    nit_emisor = fields.Char('NIT Emisor')
    nombre_emisor = fields.Char('Emisor')
    nit_receptor = fields.Char('NIT Receptor')
    nombre_receptor = fields.Char('Receptor')
    moneda = fields.Char('Moneda', default='GTQ')
    gran_total = fields.Float('Gran Total', digits=(16, 2))
    frases_resumen = fields.Text('Frases SAT')
    invoice_id = fields.Many2one('account.move', string='Factura')
    error_message = fields.Text('Error')

    def _get_xml_bytes(self):
        self.ensure_one()
        if not self.attachment_id or not self.attachment_id.datas:
            raise UserError(_('Sin datos en adjunto: %s') % self.filename)
        return base64.b64decode(self.attachment_id.datas)

    def _parse_and_fill(self):
        """Parsea el XML y llena los campos del documento. Retorna True si ok."""
        self.ensure_one()
        try:
            xml_bytes = self._get_xml_bytes()
            data = self._parse_xml(xml_bytes)
            tipo_doc = data.get('tipo_documento', '')
            if data.get('anulado'):
                doc_state = 'anulado'
                doc_error = _('Documento ANULADO ante la SAT - no se importara.')
            elif tipo_doc == 'CAIS':
                doc_state = 'cais'
                doc_error = _('Constancia de Adquisicion de Insumos y Servicios (CAIS) - no se importara.')
            elif tipo_doc == 'CIVA':
                doc_state = 'civa'
                doc_error = _('Constancia de Exencion de IVA (CIVA) - no se importara.')
            else:
                doc_state = 'pending'
                doc_error = False
            self.write({
                'tipo_documento': tipo_doc,
                'numero_autorizacion': data.get('numero', ''),
                'serie': data.get('serie', ''),
                'fecha_emision': data.get('fecha_dt'),
                'nit_emisor': data.get('nit_emisor', ''),
                'nombre_emisor': data.get('nombre_emisor', ''),
                'nit_receptor': data.get('nit_receptor', ''),
                'nombre_receptor': data.get('nombre_receptor', ''),
                'moneda': data.get('moneda', 'GTQ'),
                'gran_total': data.get('gran_total', 0.0),
                'frases_resumen': data.get('frases_text', ''),
                'state': doc_state,
                'error_message': doc_error,
            })
            return True
        except ET.ParseError:
            self.write({'state': 'incompatible', 'error_message': 'El archivo no es un XML valido.'})
            return False
        except Exception as e:
            self.write({'state': 'incompatible', 'error_message': str(e)})
            return False

    def _parse_xml(self, xml_bytes):
        """Parsea un DTE FEL y retorna dict con todos los datos relevantes."""
        ns = DTE_NS
        root = _safe_fromstring(xml_bytes)

        # Deteccion de documento anulado: los DTE de anulacion incluyen el
        # elemento <Anulacion> / <AnulacionDTE> o lo llevan en la etiqueta raiz.
        root_local = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        anulado = (
            'Anulacion' in root_local
            or root.find('.//dte:Anulacion', ns) is not None
            or root.find('.//dte:AnulacionDTE', ns) is not None
        )

        dg = root.find('.//dte:DatosGenerales', ns)
        tipo_doc = dg.get('Tipo', '') if dg is not None else ''
        fecha_str = dg.get('FechaHoraEmision', '') if dg is not None else ''
        if not fecha_str and dg is not None:
            fecha_str = dg.get('FechaHoraAnulacion', '')
        moneda = dg.get('CodigoMoneda', 'GTQ') if dg is not None else 'GTQ'
        fecha_dt = _parse_fecha(fecha_str)

        em = root.find('.//dte:Emisor', ns)
        nit_emisor = _clean(em.get('NITEmisor', '')) if em is not None else ''
        nombre_emisor = _clean(em.get('NombreEmisor', '')) if em is not None else ''

        rec_el = root.find('.//dte:Receptor', ns)
        nit_receptor = _clean(rec_el.get('IDReceptor', '')) if rec_el is not None else ''
        nombre_receptor = _clean(rec_el.get('NombreReceptor', '')) if rec_el is not None else ''

        cert = root.find('.//dte:Certificacion', ns)
        numero = serie = ''
        if cert is not None:
            na = cert.find('dte:NumeroAutorizacion', ns)
            if na is not None:
                numero = na.get('Numero', '')
                serie = na.get('Serie', '')

        # Para documentos anulados extraemos lo disponible y salimos: nunca se
        # importan, asi que no hace falta parsear items ni frases.
        if anulado:
            if dg is not None:
                nit_emisor = nit_emisor or _clean(dg.get('NITEmisor', ''))
                nit_receptor = nit_receptor or _clean(dg.get('IDReceptor', ''))
                numero = numero or dg.get('NumeroDocumentoaAnular', '') or dg.get('NumeroAutorizacion', '')
            return {
                'anulado': True,
                'tipo_documento': tipo_doc or 'ANUL',
                'fecha_dt': fecha_dt,
                'moneda': moneda,
                'nit_emisor': nit_emisor,
                'nombre_emisor': nombre_emisor,
                'nit_receptor': nit_receptor,
                'nombre_receptor': nombre_receptor,
                'numero': numero,
                'serie': serie,
                'frases': [],
                'frases_text': '',
                'items': [],
                'gran_total': 0.0,
            }

        # Frases
        frases_list = []
        phrase_texts = []
        for frase_el in root.findall('.//dte:Frase', ns):
            tf = int(frase_el.get('TipoFrase', 0))
            ce = int(frase_el.get('CodigoEscenario', 0))
            frases_list.append({'tipo': tf, 'escenario': ce})
            cfg = self.env['ktx.phrase.config'].search([
                ('tipo_frase', '=', tf), ('codigo_escenario', '=', ce)
            ], limit=1)
            if cfg and cfg.descripcion_es:
                phrase_texts.append(cfg.descripcion_es)
            elif cfg:
                phrase_texts.append(cfg.descripcion)
            else:
                phrase_texts.append('Frase Tipo %d / Escenario %d' % (tf, ce))

        # Items
        items = []
        for item_el in root.findall('.//dte:Item', ns):
            bien_servicio = item_el.get('BienOServicio', 'B')
            num_linea = int(item_el.get('NumeroLinea', 1))

            def _fv(tag, default=0.0):
                val = item_el.findtext('dte:' + tag, None, ns)
                try:
                    return float(val) if val is not None else default
                except (ValueError, TypeError):
                    return default

            def _fs(tag):
                val = item_el.findtext('dte:' + tag, '', ns)
                return _clean(val)

            impuestos = []
            imp_container = item_el.find('dte:Impuestos', ns)
            if imp_container is not None:
                for imp_el in imp_container.findall('dte:Impuesto', ns):
                    impuestos.append({
                        'nombre_corto': (imp_el.findtext('dte:NombreCorto', '', ns) or '').strip(),
                        'codigo_ug': int(imp_el.findtext('dte:CodigoUnidadGravable', '0', ns) or 0),
                        'monto_gravable': float(imp_el.findtext('dte:MontoGravable', '0', ns) or 0),
                        'monto_impuesto': float(imp_el.findtext('dte:MontoImpuesto', '0', ns) or 0),
                    })

            items.append({
                'bien_servicio': bien_servicio,
                'numero_linea': num_linea,
                'cantidad': _fv('Cantidad') or 1.0,
                'descripcion': _fs('Descripcion'),
                'precio_unitario': _fv('PrecioUnitario'),
                'precio': _fv('Precio'),
                'descuento': _fv('Descuento'),
                'total': _fv('Total'),
                'impuestos': impuestos,
            })

        gran_total = 0.0
        totales = root.find('.//dte:Totales', ns)
        if totales is not None:
            gt_el = totales.find('dte:GranTotal', ns)
            if gt_el is not None and gt_el.text:
                try:
                    gran_total = float(gt_el.text)
                except (ValueError, TypeError):
                    pass

        return {
            'anulado': False,
            'tipo_documento': tipo_doc,
            'fecha_dt': fecha_dt,
            'moneda': moneda,
            'nit_emisor': nit_emisor,
            'nombre_emisor': nombre_emisor,
            'nit_receptor': nit_receptor,
            'nombre_receptor': nombre_receptor,
            'numero': numero,
            'serie': serie,
            'frases': frases_list,
            'frases_text': '\n'.join(phrase_texts),
            'items': items,
            'gran_total': gran_total,
        }

    def _validate(self, company_vat, allow_diff_nit, allow_diff_emisor, import_type):
        """Valida el documento y asigna estado."""
        self.ensure_one()
        # Los documentos no compatibles, anulados, CAIS o CIVA no se revalidan ni importan.
        if self.state in ('incompatible', 'anulado', 'cais', 'civa'):
            return

        if self.numero_autorizacion:
            existing = self.env['account.move'].search(
                [('ref', '=', self.numero_autorizacion)], limit=1
            )
            if existing:
                self.write({
                    'state': 'duplicate',
                    'error_message': _('Ya existe factura: %s') % existing.name,
                })
                return

        if company_vat:
            if import_type == 'purchase' and not allow_diff_nit:
                nit_rx = (self.nit_receptor or '').strip().upper()
                if nit_rx and nit_rx != 'CF' and nit_rx != company_vat:
                    self.write({
                        'state': 'wrong_nit',
                        'error_message': _('NIT Receptor (%s) != empresa (%s)') % (nit_rx, company_vat),
                    })
                    return
            if import_type == 'sale' and not allow_diff_emisor:
                nit_em = (self.nit_emisor or '').strip().upper()
                if nit_em and nit_em != company_vat:
                    self.write({
                        'state': 'wrong_nit',
                        'error_message': _('NIT Emisor (%s) != empresa (%s)') % (nit_em, company_vat),
                    })
                    return

        self.write({'state': 'valid', 'error_message': False})

    # Tipos de documento SAT FEL que corresponden a recibos
    _RECEIPT_TYPES = {'RECI'}
    # Tipos que generan notas de crédito
    _CREDIT_TYPES = {'NCRE', 'NABN'}
    # Tipos que generan notas de débito
    _DEBIT_TYPES = {'NDEB'}

    def _create_invoice(self, journal_id, import_type, journal_receipts_id=None):
        """Crea la factura Odoo desde este documento XML."""
        self.ensure_one()
        # Salvaguarda: nunca crear factura de documentos anulados, CAIS o CIVA.
        if self.state in ('anulado', 'cais', 'civa'):
            return self.env['account.move']

        company = self.company_id or self.env.company
        xml_bytes = self._get_xml_bytes()
        data = self._parse_xml(xml_bytes)

        partner = self._get_or_create_partner(data, import_type)

        currency = self.env['res.currency'].search([('name', '=', data['moneda'])], limit=1)

        tipo_doc = data.get('tipo_documento', 'FACT')
        if import_type == 'purchase':
            if tipo_doc in self._CREDIT_TYPES:
                move_type = 'in_refund'
            elif tipo_doc in self._DEBIT_TYPES:
                move_type = 'in_invoice'  # nota débito = cargo adicional, se registra como factura
            else:
                move_type = 'in_invoice'
        else:
            if tipo_doc in self._CREDIT_TYPES:
                move_type = 'out_refund'
            elif tipo_doc in self._DEBIT_TYPES:
                move_type = 'out_invoice'
            else:
                move_type = 'out_invoice'

        # Seleccionar diario según tipo de documento
        if tipo_doc in self._RECEIPT_TYPES and journal_receipts_id:
            selected_journal = journal_receipts_id
        else:
            selected_journal = journal_id

        # Frases: recopilar textos footer, taxes extra de retenciones y flag exento.
        # Se leen en el contexto de la empresa de la sesion para tomar el impuesto
        # de retencion configurado por ESA empresa (campo company_dependent).
        PhraseConfig = self.env['ktx.phrase.config'].with_company(company)
        phrase_taxes = self.env['account.tax']
        footer_texts = []
        clear_taxes = False
        # Seleccionar campo de retencion segun tipo de importacion
        phrase_tax_field = 'tax_id' if import_type == 'purchase' else 'tax_id_sale'
        for frase in data['frases']:
            cfg = PhraseConfig.search([
                ('tipo_frase', '=', frase['tipo']),
                ('codigo_escenario', '=', frase['escenario']),
            ], limit=1)
            if cfg:
                if cfg.include_in_footer and cfg.descripcion_es:
                    footer_texts.append(cfg.descripcion_es)
                phrase_tax = getattr(cfg, phrase_tax_field)
                if phrase_tax:
                    phrase_taxes |= phrase_tax
                if cfg.clear_taxes:
                    clear_taxes = True

        invoice_lines = []
        for item in data['items']:
            line_vals = self._build_line(item, phrase_taxes, clear_taxes, company, import_type)
            invoice_lines.append((0, 0, line_vals))

        if not invoice_lines:
            raise UserError(_('No se encontraron lineas en %s') % self.filename)

        inv_vals = {
            'partner_id': partner.id,
            'move_type': move_type,
            'company_id': company.id,
            'invoice_date': data['fecha_dt'].date() if data.get('fecha_dt') else fields.Date.today(),
            'journal_id': selected_journal.id,
            'ref': data['numero'],
            'invoice_user_id': self.env.user.id,
            'narration': '\n'.join(footer_texts) if footer_texts else False,
            'invoice_line_ids': invoice_lines,
        }
        if 'numero_serie' in self.env['account.move']._fields:
            inv_vals['numero_serie'] = data['serie']
        if currency:
            inv_vals['currency_id'] = currency.id

        invoice = self.env['account.move'].sudo().with_company(company).create(inv_vals)

        # El XML se adjunta en el propio mensaje del chatter (queda enlazado a
        # la factura y visible en el hilo, no solo en la barra de adjuntos).
        xml_attachments = []
        if self.attachment_id and self.attachment_id.datas:
            xml_attachments.append(
                (self.filename, base64.b64decode(self.attachment_id.datas)))

        chatter = Markup(
            '<b>Importado desde XML FEL</b><br/>'
            'No. Autorizacion: %s<br/>Serie: %s<br/>'
            'Emisor: %s (%s)<br/>Receptor: %s (%s)<br/>'
            'Gran Total XML: %s %s'
        ) % (
            data['numero'], data['serie'],
            data['nombre_emisor'], data['nit_emisor'],
            data['nombre_receptor'], data['nit_receptor'],
            data['moneda'], data['gran_total'],
        )
        if footer_texts:
            chatter += Markup('<br/><b>Frases SAT:</b><br/>') + Markup('<br/>').join(footer_texts)
        invoice.message_post(body=chatter, attachments=xml_attachments)

        self.write({'state': 'imported', 'invoice_id': invoice.id})
        return invoice

    def _build_line(self, item, phrase_taxes, clear_taxes=False, company=None, import_type='purchase'):
        """Construye vals de linea de factura a partir de datos del item XML."""
        company = company or self.company_id or self.env.company
        # Descuento: convertir monto a porcentaje exacto
        precio = item['precio']  # cantidad * precio_unitario
        descuento_monto = item['descuento']
        discount_pct = 0.0
        if precio > 0 and descuento_monto > 0:
            discount_pct = round((descuento_monto / precio) * 100, 6)

        # Impuestos por linea desde el catalogo de mapeo, leido en el contexto
        # de la empresa de la sesion. Asi cada empresa usa SU impuesto y nunca
        # se mezclan impuestos entre empresas (campo es company_dependent).
        # Se usa el campo de compras o ventas segun el tipo de importacion.
        TaxMapping = self.env['ktx.tax.mapping'].with_company(company)
        tax_field = 'tax_id' if import_type == 'purchase' else 'tax_id_sale'
        tax_ids = []
        if not clear_taxes:
            for imp in item.get('impuestos', []):
                mapping = TaxMapping.search([
                    ('nombre_corto', '=', imp['nombre_corto']),
                    ('codigo_unidad_gravable', '=', imp['codigo_ug']),
                    ('active', '=', True),
                ], limit=1)
                if not mapping and imp['codigo_ug'] != 0:
                    # Fallback: buscar comodin UG=0 para tipos con codigos variables
                    # (ej. TASA MUNICIPAL usa codigos de municipio de 7 digitos)
                    mapping = TaxMapping.search([
                        ('nombre_corto', '=', imp['nombre_corto']),
                        ('codigo_unidad_gravable', '=', 0),
                        ('active', '=', True),
                    ], limit=1)
                if mapping:
                    tax = getattr(mapping, tax_field)
                    if tax and tax.id not in tax_ids:
                        tax_ids.append(tax.id)

            # Impuestos extra de frases (retenciones)
            for t in phrase_taxes:
                if t.id not in tax_ids:
                    tax_ids.append(t.id)

        product = self._get_product(item, company)

        line_vals = {
            'name': item['descripcion'] or _('Bien o Servicio'),
            'quantity': item['cantidad'],
            'price_unit': item['precio_unitario'],
            'discount': discount_pct,
            # Siempre poner tax_ids explicitamente para evitar que Odoo herede
            # los impuestos del producto (especialmente critico en exentos).
            'tax_ids': [(6, 0, tax_ids)],
        }
        if product:
            # _get_product puede devolver product.product (ajustes) o
            # product.template (mapeo de impuestos); normalizamos a variante.
            if product._name == 'product.template':
                line_vals['product_id'] = product.product_variant_id.id
            else:
                line_vals['product_id'] = product.id
        return line_vals

    def _get_product(self, item, company=None):
        """Determina el producto Odoo para el item segun BienOServicio y mapeo."""
        company = company or self.company_id or self.env.company
        # 1. Buscar producto en mapeo de impuestos de la linea
        TaxMapping = self.env['ktx.tax.mapping'].with_company(company)
        for imp in item.get('impuestos', []):
            mapping = TaxMapping.search([
                ('nombre_corto', '=', imp['nombre_corto']),
                ('codigo_unidad_gravable', '=', imp['codigo_ug']),
            ], limit=1)
            if not mapping and imp.get('codigo_ug', 0) != 0:
                mapping = TaxMapping.search([
                    ('nombre_corto', '=', imp['nombre_corto']),
                    ('codigo_unidad_gravable', '=', 0),
                ], limit=1)
            if mapping and mapping.product_id:
                return mapping.product_id

        # 2. Producto configurado en ajustes del modulo
        params = self.env['ir.config_parameter'].sudo()
        if item.get('bien_servicio') == 'B':
            pid = params.get_param('ktx_mass_import.default_product_bien_id')
        else:
            pid = params.get_param('ktx_mass_import.default_product_servicio_id')
        if pid:
            prod = self.env['product.product'].browse(int(pid)).exists()
            if prod:
                return prod

        # 3. Compatibilidad con modulo anterior
        code = 'GTBIEN001' if item.get('bien_servicio') == 'B' else 'GTSERV002'
        return self.env['product.product'].search([('default_code', '=', code)], limit=1)

    def _get_partner_identity(self, data, import_type):
        """Retorna (nit, nombre) del contacto segun el tipo de importacion."""
        if import_type == 'purchase':
            return data.get('nit_emisor'), data.get('nombre_emisor')
        return data.get('nit_receptor'), data.get('nombre_receptor')

    def _find_partner(self, nit, nombre):
        """Busca un contacto existente por NIT o nombre. No crea."""
        nit_clean = (nit or '').strip().upper()
        if nit_clean and nit_clean != 'CF':
            return self.env['res.partner'].search(
                [('vat', '=', nit_clean), ('active', '=', True)], limit=1
            )
        return self.env['res.partner'].search(
            [('name', 'ilike', nombre or 'Consumidor Final'), ('active', '=', True)], limit=1
        )

    def _get_or_create_partner(self, data, import_type):
        """Busca o crea el contacto en Odoo."""
        nit, nombre = self._get_partner_identity(data, import_type)
        partner = self._find_partner(nit, nombre)
        if not partner:
            nit_clean = (nit or '').strip().upper()
            gt = self.env.ref('base.gt', raise_if_not_found=False)
            partner = self.env['res.partner'].sudo().create({
                'name': nombre or 'Consumidor Final',
                'vat': nit_clean if nit_clean and nit_clean != 'CF' else False,
                'street': 'CIUDAD',
                'country_id': gt.id if gt else False,
            })
        return partner
