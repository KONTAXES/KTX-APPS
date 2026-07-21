# -*- coding: utf-8 -*-
"""Formato grafico (PDF con QR) de la factura FEL a partir de su XML.

Independiente de quien haya adjuntado el XML del DTE a la factura (puede
venir de ktx_mass_import, de ktx_fel2odoo, o de cualquier otro origen):
este modulo solo busca un adjunto XML de DTE FEL en la factura y lo usa
para generar el PDF. No depende de esos modulos.
"""
import base64
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from urllib.parse import quote

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DTE_NS = {'dte': 'http://www.sat.gob.gt/dte/fel/0.2.0'}

# URL oficial del Verificador Integrado de la SAT (Guatemala) para DTE FEL.
# Formato confirmado con un ejemplo real:
# https://felpub.c.sat.gob.gt/verificador-web/publico/vistas/verificacionDte.jsf
#   ?tipo=autorizacion&numero=<UUID>&emisor=<NIT_EMISOR>&receptor=<ID_RECEPTOR>&monto=<TOTAL>
_SAT_VERIFICADOR_URL = 'https://felpub.c.sat.gob.gt/verificador-web/publico/vistas/verificacionDte.jsf'

# Igual que en ktx_mass_import: un DTE FEL legitimo nunca lleva DOCTYPE ni
# ENTITY. Rechazarlos bloquea XXE y expansion de entidades antes de parsear.
_XML_DANGER = re.compile(rb'<!\s*(DOCTYPE|ENTITY)', re.IGNORECASE)

# Nombres legibles de los tipos de DTE que emite la SAT de Guatemala.
_TIPO_DOCUMENTO_LABELS = {
    'FACT': 'FACTURA',
    'FPEQ': 'FACTURA PEQUENO CONTRIBUYENTE',
    'FCAM': 'FACTURA CAMBIARIA',
    'FCAP': 'FACTURA CAMBIARIA PEQUENO CONTRIBUYENTE',
    'NDEB': 'NOTA DE DEBITO',
    'NCRE': 'NOTA DE CREDITO',
    'RECI': 'RECIBO',
    'NABN': 'NOTA DE ABONO',
    'FESP': 'FACTURA ESPECIAL',
    'FAEX': 'FACTURA DE EXPORTACION',
}

_UNIDADES = ['', 'UNO', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE']
_DIECIS = ['DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISEIS',
           'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE']
_VEINTIS = ['VEINTE', 'VEINTIUNO', 'VEINTIDOS', 'VEINTITRES', 'VEINTICUATRO',
            'VEINTICINCO', 'VEINTISEIS', 'VEINTISIETE', 'VEINTIOCHO', 'VEINTINUEVE']
_DECENAS = ['', '', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA',
            'SETENTA', 'OCHENTA', 'NOVENTA']
_CENTENAS = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS',
             'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS']
_MONEDA_NOMBRES = {
    'GTQ': ('QUETZAL', 'QUETZALES'),
    'USD': ('DOLAR', 'DOLARES'),
    'EUR': ('EURO', 'EUROS'),
}

# Catalogo de Frases SAT FEL (TipoFrase, CodigoEscenario) -> texto, igual al
# catalogo que usa ktx_mass_import (ktx.phrase.config / ktx_frases_data.xml,
# CatalogoFrases-0.6.0). Se copia aqui (en vez de depender de ese modulo)
# para que este modulo siga siendo independiente. Confirmado contra un DTE
# real emitido por otro proveedor (Tipo 1 / Escenario 1 imprime exactamente
# "Sujeto a pagos trimestrales ISR").
_FRASES_SAT = {
    (1, 1): 'Sujeto a pagos trimestrales ISR',
    (1, 2): 'Sujeto a retencion definitiva ISR',
    (1, 3): 'Sujeto a pago directo ISR',
    (1, 4): 'Exento del ISR',
    (2, 1): 'Agente de Retencion del IVA',
    (3, 1): 'No genera derecho a credito fiscal',
    (4, 1): 'Exportacion de bienes',
    (4, 2): 'Exportacion de servicios',
    (4, 3): 'Servicios bancarios y financieros',
    (4, 4): 'Cooperativas - operaciones de ahorro y credito',
    (4, 5): 'Donaciones y aportes',
    (4, 6): 'Cuotas de agremiacion y aportaciones a partidos politicos',
    (4, 7): 'Educacion - colegios y centros educativos privados',
    (4, 8): 'Universidades privadas',
    (4, 9): 'Servicios de culto religioso',
    (4, 10): 'Servicios medicos y hospitalarios',
    (4, 11): 'Seguros de vida',
    (4, 12): 'Intereses sobre operaciones de credito',
    (4, 13): 'Arrendamiento de inmuebles para vivienda',
    (4, 14): 'Medicamentos y productos farmaceuticos',
    (4, 15): 'Zona Libre de Industria y Comercio ZOLIC',
    (4, 16): 'Primera venta de vivienda',
    (4, 17): 'Operaciones de maquila',
    (4, 18): 'Zona Franca',
    (4, 19): 'Transporte extraurbano de personas',
    (4, 20): 'Venta de vehiculos usados',
    (4, 21): 'Mercados cantonales y municipales - ventas al menudeo',
    (4, 22): 'Energia electrica - servicio domiciliar',
    (4, 23): 'Valores y acciones del mercado de capitales',
    (4, 24): 'Insumos agricolas',
    (4, 25): 'Masa de pan y productos de panaderia tradicional',
    (4, 26): 'Matriculas y colegiaturas de establecimientos educativos privados',
    (4, 27): 'Periodicos, revistas y libros',
    (4, 28): 'Servicios de agua potable y alcantarillado',
    (4, 29): 'Venta de vehiculos electricos e hidrogeno',
    (4, 30): 'Servicio de transporte de hidrogeno',
    (4, 31): 'Recarga de energia para vehiculos electricos',
    (4, 32): 'Energia renovable certificada',
    (4, 33): 'Importacion de vehiculos electricos e hidrogeno',
    (4, 34): 'Materiales y equipos para vehiculos electricos',
    (4, 35): 'Servicios de mantenimiento de vehiculos electricos',
    (4, 36): 'Otros servicios relacionados con energia limpia',
    (5, 1): 'Factura especial - proveedor se nego a emitir factura',
    (6, 1): 'Contribuyente agropecuario - pago sobre ventas brutas 5%',
    (6, 2): 'Contribuyente agropecuario - pago sobre utilidades',
    (7, 1): 'Pequeno contribuyente del regimen electronico',
    (7, 2): 'Contribuyente agropecuario del regimen electronico',
    (8, 1): 'Exento ISR - Universidades',
    (8, 2): 'Exento ISR - Colegios privados reconocidos',
    (8, 3): 'Exento ISR - Iglesias y entidades religiosas',
    (8, 4): 'Exento ISR - Sindicatos de trabajadores',
    (8, 5): 'Exento ISR - Partidos politicos',
    (8, 6): 'Exento ISR - Colegios profesionales',
    (8, 7): 'Exento ISR - Cooperativas',
    (8, 8): 'Exento ISR - Zona Libre de Industria y Comercio ZOLIC',
    (8, 9): 'Exento ISR - Servicios de energia limpia y vehiculos electricos',
    (8, 10): 'Exento ISR - Entidades civiles sin fines de lucro',
    (8, 11): 'Exento ISR - Cuotas de condominios',
    (8, 12): 'Exento ISR - Otras entidades reconocidas por ley',
    (9, 1): 'Subsidio al gas licuado de petroleo',
    (9, 2): 'Apoyo al subsidio de combustibles',
    (9, 3): 'Impuesto sobre la renta del viajero - pasajes aereos',
    (9, 4): 'Ubicacion o localizacion temporal',
    (9, 5): 'Gastos personales no deducibles del negocio',
    (9, 6): 'Exportacion provisional de mercancias',
    (9, 7): 'Despacho de combustible',
    (9, 8): 'Importacion temporal de bienes',
    (9, 9): 'Recarga electronica de tarjetas',
    (9, 10): 'Venta de loteria y juegos de azar',
    (9, 11): 'Operaciones de caja chica',
    (9, 12): 'Servicios de turismo',
    (9, 13): 'Venta de bienes inmuebles',
    (9, 14): 'Servicios de seguros y fianzas',
    (9, 15): 'Gasto de representacion',
    (9, 16): 'Vivienda del trabajador',
    (9, 17): 'Espectaculos publicos',
    (9, 18): 'Operaciones de arrendamiento financiero (leasing)',
    (9, 19): 'Otras operaciones especiales',
    (10, 1): 'Sector primario - productos agropecuarios 1.5%',
    (10, 2): 'Sector primario - exportaciones agropecuarias 2%',
    (11, 1): 'Sector pecuario - operaciones hidrobiologicas y apicolas',
    (11, 2): 'Sector pecuario - ganado en pie y aves de corral',
    (11, 3): 'Sector pecuario - exportaciones ganaderas',
    (12, 1): 'Sin efecto de debito o credito fiscal - sector primario',
    (12, 2): 'Sin efecto de debito o credito fiscal - sector pecuario',
}


def _apocopar(texto):
    """'VEINTIUNO' -> 'VEINTIUN' cuando precede a un sustantivo masculino
    (MIL, MILLONES, o el nombre de la moneda), como corresponde en espanol."""
    return texto[:-1] if texto.endswith('UNO') else texto


def _contrast_text_color(hex_color):
    """Blanco o negro segun cual tenga mejor contraste sobre ese color de
    fondo (formula de luminancia percibida YIQ). Umbral alto (200 en vez
    del clasico 128/50%): el texto blanco se usa por defecto para
    practicamente cualquier color de acento con algo de saturacion
    (naranjas, rojos, verdes, azules, morados); el negro queda solo para
    fondos genuinamente claros (pasteles, amarillos, grises claros, blancos)."""
    value = (hex_color or '').lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    if len(value) != 6:
        return '#ffffff'
    try:
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return '#ffffff'
    luminancia = (299 * r + 587 * g + 114 * b) / 1000
    return '#000000' if luminancia >= 200 else '#ffffff'


def _tres_digitos_a_letras(n):
    if n == 0:
        return ''
    if n == 100:
        return 'CIEN'
    centenas, resto = divmod(n, 100)
    partes = []
    if centenas:
        partes.append(_CENTENAS[centenas])
    if resto:
        if resto < 10:
            partes.append(_UNIDADES[resto])
        elif resto < 20:
            partes.append(_DIECIS[resto - 10])
        elif resto < 30:
            partes.append(_VEINTIS[resto - 20])
        else:
            decenas, unidades = divmod(resto, 10)
            if unidades:
                partes.append('%s Y %s' % (_DECENAS[decenas], _UNIDADES[unidades]))
            else:
                partes.append(_DECENAS[decenas])
    return ' '.join(partes)


def _entero_a_letras(n):
    if n == 0:
        return 'CERO'
    partes = []
    millones, resto = divmod(n, 1000000)
    miles, unidades = divmod(resto, 1000)
    if millones:
        if millones == 1:
            partes.append('UN MILLON')
        else:
            partes.append('%s MILLONES' % _apocopar(_tres_digitos_a_letras(millones)))
    if miles:
        if miles == 1:
            partes.append('MIL')
        else:
            partes.append('%s MIL' % _apocopar(_tres_digitos_a_letras(miles)))
    if unidades:
        partes.append(_tres_digitos_a_letras(unidades))
    return ' '.join(p for p in partes if p)


def _monto_a_letras(monto, moneda='GTQ'):
    """'TOTAL EN LETRAS', igual que en las facturas impresas en Guatemala:
    monto entero deletreado en espanol + nombre de la moneda + centavos en
    formato XX/100."""
    monto = round(float(monto or 0), 2)
    entero = int(monto)
    centavos = int(round((monto - entero) * 100))
    singular, plural = _MONEDA_NOMBRES.get(moneda, (moneda, moneda))
    if entero == 1:
        return 'UN %s CON %02d/100' % (singular, centavos)
    letras = _apocopar(_entero_a_letras(entero))
    return '%s %s CON %02d/100' % (letras, plural, centavos)


def _safe_fromstring(xml_bytes):
    """Parsea XML de forma segura contra XXE y expansion de entidades."""
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode('utf-8')
    if _XML_DANGER.search(xml_bytes[:16384] or b''):
        raise UserError(_(
            'XML rechazado por seguridad: contiene DOCTYPE/ENTITY, no '
            'permitido en un DTE FEL.'))
    try:
        from defusedxml.ElementTree import fromstring as _df_fromstring
        return _df_fromstring(
            xml_bytes, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except ImportError:
        return ET.fromstring(xml_bytes)


# Marcas tipicas de "mojibake": un XML UTF-8 decodificado como ISO-8859-1/CP1252
# en algun paso previo deja las tildes como 'Ã¡', 'Ã©', 'Ã±'...
_MOJIBAKE_MARKERS = ('Ã', 'Â', 'â€')


def _repair_mojibake(text):
    """Recupera texto UTF-8 mal decodificado como Latin-1 (mojibake). Solo
    actua si hay marcas de mojibake y el round-trip latin-1 -> utf-8 las
    reduce; si no, devuelve el texto intacto. No puede reconstruir tildes que
    el origen ya perdio con encode('ascii', 'ignore'/'replace')."""
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
    """Normaliza texto (tildes/enies) y colapsa espacios/saltos de linea."""
    if not text:
        return ''
    text = _repair_mojibake(str(text))
    text = unicodedata.normalize('NFC', text)
    return ' '.join(text.split())


def _num(text, default=0.0):
    try:
        return float(text) if text not in (None, '') else default
    except (TypeError, ValueError):
        return default


def _parse_dte_for_format(xml_bytes):
    """Extrae del XML del DTE todos los datos necesarios para el formato
    grafico (mas completos que los que usa ktx_mass_import para crear la
    factura, ya que aqui se necesita direccion, certificacion completa, etc.).
    Devuelve un dict listo para el QWeb, o lanza UserError si el XML
    no es un DTE FEL valido."""
    root = _safe_fromstring(xml_bytes)
    ns = DTE_NS

    dg = root.find('.//dte:DatosGenerales', ns)
    if dg is None:
        raise UserError(_(
            'El XML adjunto no parece ser un DTE FEL valido (no tiene '
            'DatosGenerales).'))

    em = root.find('.//dte:Emisor', ns)
    dir_em = em.find('dte:DireccionEmisor', ns) if em is not None else None
    rec = root.find('.//dte:Receptor', ns)
    dir_rec = rec.find('dte:DireccionReceptor', ns) if rec is not None else None
    cert = root.find('.//dte:Certificacion', ns)
    na = cert.find('dte:NumeroAutorizacion', ns) if cert is not None else None

    uuid = (na.text or '').strip() if na is not None and na.text else ''
    serie = na.get('Serie', '') if na is not None else ''
    numero = na.get('Numero', '') if na is not None else ''
    fecha_cert = cert.findtext('dte:FechaHoraCertificacion', '', ns) if cert is not None else ''
    nit_certificador = cert.findtext('dte:NITCertificador', '', ns) if cert is not None else ''
    nombre_certificador = cert.findtext('dte:NombreCertificador', '', ns) if cert is not None else ''

    items = []
    for item_el in root.findall('.//dte:Item', ns):
        impuestos = []
        imp_container = item_el.find('dte:Impuestos', ns)
        if imp_container is not None:
            for imp_el in imp_container.findall('dte:Impuesto', ns):
                impuestos.append({
                    'nombre_corto': _clean(imp_el.findtext('dte:NombreCorto', '', ns)),
                    'monto_gravable': _num(imp_el.findtext('dte:MontoGravable', '0', ns)),
                    'monto_impuesto': _num(imp_el.findtext('dte:MontoImpuesto', '0', ns)),
                })
        items.append({
            'numero_linea': item_el.get('NumeroLinea', ''),
            'bien_servicio': item_el.get('BienOServicio', ''),
            'cantidad': _num(item_el.findtext('dte:Cantidad', '1', ns), 1.0),
            'unidad_medida': _clean(item_el.findtext('dte:UnidadMedida', '', ns)),
            'descripcion': _clean(item_el.findtext('dte:Descripcion', '', ns)),
            'precio_unitario': _num(item_el.findtext('dte:PrecioUnitario', '0', ns)),
            'precio': _num(item_el.findtext('dte:Precio', '0', ns)),
            'descuento': _num(item_el.findtext('dte:Descuento', '0', ns)),
            'total': _num(item_el.findtext('dte:Total', '0', ns)),
            'impuestos': impuestos,
        })

    totales_el = root.find('.//dte:Totales', ns)
    total_impuestos = []
    gran_total = 0.0
    if totales_el is not None:
        ti = totales_el.find('dte:TotalImpuestos', ns)
        if ti is not None:
            for t_el in ti.findall('dte:TotalImpuesto', ns):
                total_impuestos.append({
                    'nombre_corto': t_el.get('NombreCorto', ''),
                    'monto': _num(t_el.get('TotalMontoImpuesto', '0')),
                })
        gran_total = _num(totales_el.findtext('dte:GranTotal', '0', ns))

    frases = []
    for frase_el in root.findall('.//dte:Frase', ns):
        tipo_frase_raw = frase_el.get('TipoFrase', '')
        cod_escenario_raw = frase_el.get('CodigoEscenario', '')
        try:
            texto = _FRASES_SAT.get((int(tipo_frase_raw), int(cod_escenario_raw)))
        except (TypeError, ValueError):
            texto = None
        frases.append({
            'tipo': tipo_frase_raw,
            'escenario': cod_escenario_raw,
            'texto': texto,
        })

    iva_monto = sum(
        ti['monto'] for ti in total_impuestos
        if (ti['nombre_corto'] or '').strip().upper() == 'IVA'
    )

    tipo_documento = dg.get('Tipo', '')
    moneda = dg.get('CodigoMoneda', 'GTQ')

    return {
        'tipo_documento': tipo_documento,
        'tipo_documento_label': _TIPO_DOCUMENTO_LABELS.get(tipo_documento, tipo_documento or 'DTE'),
        'moneda': moneda,
        'iva_monto': iva_monto,
        'total_en_letras': _monto_a_letras(gran_total, moneda),
        'fecha_emision': dg.get('FechaHoraEmision', ''),
        'afiliacion_iva': em.get('AfiliacionIVA', '') if em is not None else '',
        'emisor': {
            'nit': _clean(em.get('NITEmisor', '')) if em is not None else '',
            'nombre': _clean(em.get('NombreEmisor', '')) if em is not None else '',
            'nombre_comercial': _clean(em.get('NombreComercial', '')) if em is not None else '',
            'correo': _clean(em.get('CorreoEmisor', '')) if em is not None else '',
            'direccion': _clean(dir_em.findtext('dte:Direccion', '', ns)) if dir_em is not None else '',
            'municipio': _clean(dir_em.findtext('dte:Municipio', '', ns)) if dir_em is not None else '',
            'departamento': _clean(dir_em.findtext('dte:Departamento', '', ns)) if dir_em is not None else '',
            'pais': _clean(dir_em.findtext('dte:Pais', '', ns)) if dir_em is not None else '',
        },
        'receptor': {
            'id': _clean(rec.get('IDReceptor', '')) if rec is not None else '',
            'nombre': _clean(rec.get('NombreReceptor', '')) if rec is not None else '',
            'correo': _clean(rec.get('CorreoReceptor', '')) if rec is not None else '',
            'direccion': _clean(dir_rec.findtext('dte:Direccion', '', ns)) if dir_rec is not None else '',
            'municipio': _clean(dir_rec.findtext('dte:Municipio', '', ns)) if dir_rec is not None else '',
            'departamento': _clean(dir_rec.findtext('dte:Departamento', '', ns)) if dir_rec is not None else '',
        },
        'items': items,
        'total_impuestos': total_impuestos,
        'gran_total': gran_total,
        'frases': frases,
        'certificacion': {
            'uuid': uuid,
            'serie': serie,
            'numero': numero,
            'fecha': fecha_cert,
            'nit_certificador': nit_certificador,
            'nombre_certificador': nombre_certificador,
        },
    }


class AccountMove(models.Model):
    _inherit = 'account.move'

    ktx_fel_format_available = fields.Boolean(
        compute='_compute_ktx_fel_format_available')

    def _compute_ktx_fel_format_available(self):
        for move in self:
            move.ktx_fel_format_available = bool(
                move.company_id.ktx_fel_format_enabled
                and move.move_type in ('out_invoice', 'out_refund')
                and move._ktx_fel_find_xml_attachment()
            )

    def _ktx_fel_find_xml_attachment(self):
        """Busca el adjunto XML del DTE FEL en esta factura (sin importar quien
        lo haya adjuntado: ktx_mass_import, ktx_fel2odoo, u otro origen).

        Prefiere el XML cuyo contenido tenga realmente el namespace FEL de la
        SAT, para no confundirlo con cualquier otro .xml adjunto a la factura
        (p. ej. un XML del cliente): asi el boton 'Imprimir FEL' solo aparece
        cuando de verdad hay un DTE FEL. Si ninguno lo tiene, cae al mas
        reciente (comportamiento previo) para no romper casos borde."""
        self.ensure_one()
        candidates = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'account.move'),
            ('res_id', '=', self.id),
            '|',
            ('mimetype', 'in', ('text/xml', 'application/xml')),
            ('name', '=ilike', '%.xml'),
        ], order='id desc', limit=10)
        for att in candidates:
            try:
                head = base64.b64decode(att.datas or b'')[:2048]
            except Exception:  # noqa: BLE001
                continue
            if b'sat.gob.gt/dte/fel' in head:
                return att
        return candidates[:1]

    def _ktx_fel_get_format_data(self):
        """Encuentra el XML adjunto y lo parsea. Lo llama tanto la accion del
        boton (para validar antes de renderizar) como la plantilla QWeb del
        reporte (una sola vez por factura, via t-set)."""
        self.ensure_one()
        attachment = self._ktx_fel_find_xml_attachment()
        if not attachment:
            raise UserError(_(
                'No se encontro el XML del DTE FEL adjunto a esta factura. '
                'El Formato FEL GT requiere el XML original (importado o '
                'emitido por FEL2Odoo) para generar el PDF.'))
        try:
            xml_bytes = base64.b64decode(attachment.datas or b'')
            data = _parse_dte_for_format(xml_bytes)
        except UserError:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.exception('KTX FEL2Odoo Format: error al parsear XML de %s', self.name)
            raise UserError(_('No se pudo leer el XML del DTE: %s') % exc)
        data['qr_url'] = self._ktx_fel_format_qr_url(data)
        return data

    def action_print_fel_format(self):
        """Genera el PDF con formato de la factura FEL a partir del XML
        adjunto, lo adjunta al chatter (visible y descargable) y lo
        descarga."""
        self.ensure_one()
        if not self.company_id.ktx_fel_format_enabled:
            raise UserError(_(
                'El Formato FEL GT (KTX) no esta activado. Actívelo en '
                'Contabilidad > Configuracion > Ajustes.'))
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_('El Formato FEL GT solo aplica a facturas de venta.'))
        # Valida ANTES de renderizar, para dar un error claro en vez de un
        # fallo generico del motor de reportes si el XML falta o es invalido.
        self._ktx_fel_get_format_data()

        style = self.company_id.ktx_fel_format_style or 'ktx1'
        paper_size = self.company_id.ktx_fel_format_paper_size or 'carta'
        report = self._ktx_fel_format_resolve_report(style, paper_size)
        if not report:
            raise UserError(_(
                'La combinacion de Formato "%(style)s" y Tamano de papel '
                '"%(paper_size)s" todavia no esta disponible.'
            ) % {'style': style, 'paper_size': paper_size})

        pdf_content, _mime = report.sudo()._render_qweb_pdf(report.report_name, self.ids)

        pdf_attachment = self.env['ir.attachment'].sudo().create({
            'name': 'FEL_Formato_%s.pdf' % (self.name or self.id),
            'datas': base64.b64encode(pdf_content),
            'res_model': 'account.move',
            'res_id': self.id,
            'mimetype': 'application/pdf',
            'type': 'binary',
        })
        self.message_post(
            body=_('PDF con formato FEL generado (KTX FEL2Odoo Format).'),
            attachment_ids=[pdf_attachment.id],
        )
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % pdf_attachment.id,
            'target': 'self',
        }

    @api.model
    def _ktx_fel_format_resolve_report(self, style, paper_size):
        """Encuentra el ir.actions.report de una apariencia+tamano SIN fijar el
        modulo que lo define. Asi, modulos complementarios (ktx_fel2odoo_format_1,
        _2, ...) que agreguen nuevas apariencias solo tienen que registrar su
        accion de reporte con el ID externo 'action_report_<estilo>_<tamano>'
        (p. ej. 'action_report_ktx2_carta') y este modulo base la encuentra sola.

        Se busca por ir.model.data.name (el ID externo SIN el prefijo de modulo),
        por lo que funciona sin importar en que modulo viva el reporte."""
        xmlid_name = 'action_report_%s_%s' % (style, paper_size)
        data = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'ir.actions.report'),
            ('name', '=', xmlid_name),
        ], limit=1)
        if not data:
            return self.env['ir.actions.report']
        return self.env['ir.actions.report'].browse(data.res_id)

    def _ktx_fel_format_qr_url(self, data):
        """URL del Verificador Integrado de la SAT que codifica el QR,
        exactamente con el mismo formato de parametros que usa la propia
        SAT en sus DTE: tipo, numero (UUID), emisor (NIT), receptor,
        monto."""
        cert = data['certificacion']
        params = {
            'tipo': 'autorizacion',
            'numero': cert['uuid'],
            'emisor': data['emisor']['nit'],
            'receptor': data['receptor']['id'],
            'monto': '%.6f' % (data['gran_total'] or 0.0),
        }
        query = '&'.join('%s=%s' % (k, quote(str(v))) for k, v in params.items())
        return '%s?%s' % (_SAT_VERIFICADOR_URL, query)

    def _ktx_fel_format_qr_img_src(self, qr_url):
        """Genera el PNG del QR directamente en Python (con el mismo motor
        de codigo de barras nativo de Odoo, ir.actions.report.barcode) y lo
        devuelve como data URI en base64.

        NO se usa la URL '/report/barcode/...' como src de la imagen: eso
        requeriria que wkhtmltopdf haga una peticion HTTP adicional al
        propio servidor mientras genera el PDF, algo que en varios entornos
        (Odoo.sh, multiples workers, proxies) no resuelve bien y deja la
        imagen en blanco -- que es exactamente el sintoma reportado ("el QR
        no funciona"). Generando el PNG en el propio proceso Python y
        embebiendolo en base64 se evita ese problema por completo."""
        try:
            png_bytes = self.env['ir.actions.report'].barcode(
                'QR', qr_url, width=180, height=180)
        except (ValueError, AttributeError):
            _logger.exception('KTX FEL2Odoo Format: no se pudo generar el QR')
            return False
        return 'data:image/png;base64,%s' % base64.b64encode(png_bytes).decode()

    def _ktx_fel_format_company_data(self):
        """Reune la configuracion visual de la empresa para el reporte:
        logo efectivo, posicion, imagen lateral, fondo/marca de agua,
        membrete/pie de pagina con redes sociales."""
        self.ensure_one()
        # bin_size=False: sin esto, si el contexto de la llamada trae
        # bin_size=True (heredado de alguna vista de lista/kanban previa),
        # los campos Binary devuelven solo un texto con el tamano (ej.
        # "245.00 Kb") en vez de los datos reales -- eso hacia que la
        # imagen de fondo/marca de agua no apareciera.
        company = self.company_id.with_context(bin_size=False)
        accent_color = company.ktx_fel_format_accent_color or '#e97132'
        return {
            'logo': company._ktx_fel_format_effective_logo(),
            'logo_position': company.ktx_fel_format_logo_position or 'left',
            'accent_color': accent_color,
            # Texto blanco o negro segun el contraste del color de acento
            # elegido, para que siempre se pueda leer sobre las barras/cajas
            # de ese color (acento oscuro -> texto blanco, acento claro ->
            # texto negro).
            'accent_text': _contrast_text_color(accent_color),
            'paper_size': company.ktx_fel_format_paper_size or 'carta',
            'style': company.ktx_fel_format_style or 'ktx1',
            'side_image': company.ktx_fel_format_side_image,
            'background_image': company.ktx_fel_format_background_image,
            'show_footer': company.ktx_fel_format_show_footer,
            'footer_description': company.ktx_fel_format_footer_description,
            'social_website': company.ktx_fel_format_social_website,
            'social_phone': company.ktx_fel_format_social_phone,
            'social_email': company.ktx_fel_format_social_email,
            'social_facebook': company.ktx_fel_format_social_facebook,
            'social_instagram': company.ktx_fel_format_social_instagram,
            'social_x': company.ktx_fel_format_social_x,
        }
