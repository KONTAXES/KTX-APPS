# -*- coding: utf-8 -*-
"""Configuracion y cliente REST para la integracion FEL <-> Odoo.

Se conecta al proveedor intermediario API FEL Core (apifelcore.com), que a su
vez consulta la Agencia Virtual de la SAT Guatemala. Descarga periodicamente
los DTE emitidos (ventas) y recibidos (compras) en XML y, reutilizando la
logica de importacion masiva (parseo FEL, mapeo de impuestos, frases SAT,
retenciones y creacion de contactos), crea las facturas en Odoo listas para
confirmar, con la menor intervencion humana posible.

Autenticacion (2 tokens, segun el proveedor):
  1. Token de plataforma: se obtiene con POST /login (email + password) y se
     envia como cabecera ``Authorization: Bearer``. El modulo lo gestiona y
     renueva solo; no se captura a mano.
  2. Token de Agencia Virtual (``token_fel``): credencial SAT/FEL cifrada del
     cliente (la que entrega el panel de apifelcore); viaja en el cuerpo de
     cada peticion de negocio.

Seguridad: las credenciales sensibles nunca se muestran en vistas de solo
lectura ni se registran en logs; el acceso al modelo se limita por grupos.
"""
import base64
import json
import logging
import unicodedata
from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

_logger = logging.getLogger(__name__)

# Segundos de espera por peticion HTTP al proveedor.
_HTTP_TIMEOUT = 90

# Vigencia asumida del token de plataforma antes de re-autenticar (horas).
_TOKEN_TTL_HOURS = 12

# Mapa tipo de operacion SAT -> tipo de importacion masiva.
_OPERACION_A_IMPORT = {
    'EMITIDOS': 'sale',
    'RECIBIDOS': 'purchase',
}

# Estados de DTE que NO deben importarse aunque el proveedor los devuelva.
_ESTADOS_EXCLUIDOS = {'ANULADO', 'RECHAZADO', 'I', 'R'}

# Campos de credenciales: al cambiarlos se exige re-probar la conexion.
_CREDENTIAL_FIELDS = ('base_url', 'email', 'password', 'nit', 'token_fel')

# Descarga de PDF: REACTIVADA para volver a probar (descargar-pdf, mismo
# endpoint documentado; el portal publico de la SAT puede seguir siendo
# intermitente). El freno de cuota en _attach_pdfs sigue protegiendo contra
# gastar llamadas de mas si la SAT vuelve a fallar.
_PDF_FEATURE_ENABLED = True


class KtxFel2odooConfig(models.Model):
    _name = 'ktx.fel2odoo.config'
    _description = 'Configuracion Integracion FEL SAT <-> Odoo'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'company_id, name'
    _rec_name = 'name'

    name = fields.Char(
        'Nombre', required=True, default='Conexion FEL Core', tracking=True,
        help='Nombre descriptivo de esta conexion (p. ej. el NIT o empresa).'
    )
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True, index=True,
        default=lambda self: self.env.company, tracking=True,
    )

    # ------------------------------------------------------------------
    # Conexion al proveedor (API FEL Core)
    # ------------------------------------------------------------------
    base_url = fields.Char(
        'URL Base API', required=True, default='https://apifelcore.com/api',
        help='URL base del proveedor. Por defecto https://apifelcore.com/api'
    )
    email = fields.Char('Email de plataforma', help='Usuario para POST /login.')
    password = fields.Char('Password de plataforma', help='Contrasena para POST /login.')
    device_name = fields.Char('Nombre de dispositivo', default='odoo')
    nit = fields.Char(
        'NIT del contribuyente', help='NIT propio, sin guiones. Debe coincidir con el token.'
    )
    token_fel = fields.Char(
        'Token Agencia Virtual (token_fel)',
        help='Token cifrado SAT/FEL del cliente (el que entrega el panel de '
             'apifelcore). Se envia en el cuerpo de cada peticion.'
    )

    # Token de plataforma en cache (Bearer). Se renueva solo. No se muestra en
    # ninguna vista; el acceso al modelo ya esta restringido por ir.model.access.
    bearer_token = fields.Char('Token de plataforma (cache)', copy=False)
    token_date = fields.Datetime('Fecha del token', copy=False, readonly=True)

    # Estado de la conexion: se pone a True solo tras "Probar conexion" exitosa.
    connection_ok = fields.Boolean(
        'Conexion probada', default=False, readonly=True, copy=False, tracking=True,
        help='Se activa al probar la conexion con exito. Requisito para poder '
             'activar la sincronizacion automatica.'
    )

    # ------------------------------------------------------------------
    # Alcance de la sincronizacion
    # ------------------------------------------------------------------
    sync_sales = fields.Boolean(
        'Sincronizar Ventas (EMITIDOS)', default=True, tracking=True,
        help='Descarga los DTE emitidos y crea facturas de cliente.'
    )
    sync_purchases = fields.Boolean(
        'Sincronizar Compras (RECIBIDOS)', default=True, tracking=True,
        help='Descarga los DTE recibidos y crea facturas de proveedor.'
    )
    journal_sale_id = fields.Many2one(
        'account.journal', string='Diario de Ventas',
        domain="[('type', '=', 'sale')]",
    )
    journal_purchase_id = fields.Many2one(
        'account.journal', string='Diario de Compras',
        domain="[('type', '=', 'purchase')]",
    )
    tipo_documento = fields.Char(
        'Tipo de documento (opcional)',
        help='Filtra por tipo FEL (FACT, FCAM, NCRE, NDEB...). Vacio = todos.'
    )
    estado_dte = fields.Selection(
        [('VIGENTE', 'Vigente'), ('ANULADO', 'Anulado'),
         ('RECHAZADO', 'Rechazado')],
        string='Estado DTE', default='VIGENTE',
        help='Estado a solicitar al proveedor. Normalmente VIGENTE.'
    )

    # ------------------------------------------------------------------
    # Programacion / periodos
    # ------------------------------------------------------------------
    date_from_initial = fields.Date(
        'Fecha inicial',
        help='Si se define, TODAS las corridas consultan desde esta fecha hasta '
             'hoy (por ventanas de ~30 dias). Dejela vacia para sincronizar de '
             'forma incremental usando la ventana de dias hacia atras.'
    )
    lookback_days = fields.Integer(
        'Dias hacia atras', default=30,
        help='Cuando no hay una sincronizacion previa, cuantos dias hacia '
             'atras consultar. En corridas posteriores se solapan 3 dias '
             'para no perder documentos tardios.'
    )
    last_sync_sale = fields.Datetime('Ultima sync. ventas', readonly=True, copy=False)
    last_sync_purchase = fields.Datetime('Ultima sync. compras', readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Comportamiento / automatizacion
    # ------------------------------------------------------------------
    auto_confirm = fields.Boolean(
        'Confirmar facturas automaticamente', default=False, tracking=True,
        help='Si esta activo, las facturas creadas se publican (confirman) '
             'automaticamente. Si no, quedan en borrador para revision. '
             'DESACTIVADO por defecto.'
    )
    auto_classify_accounts = fields.Boolean(
        'Clasificar cuentas contables', default=True, tracking=True,
        help='Asigna la cuenta contable de cada linea segun reglas por palabra '
             'clave de la descripcion y, si no hay regla, segun la cuenta usada '
             'historicamente con ese proveedor. Deterministica y segura.'
    )
    use_ai_classification = fields.Boolean(
        'Clasificacion asistida por IA', default=False, tracking=True,
        help='Punto de integracion opcional con un asistente de IA (modulo de '
             'IA aparte, con su propia API key por cliente). DESACTIVADO por '
             'defecto. Si el modulo de IA no esta disponible, se omite de forma '
             'segura.'
    )
    download_pdf = fields.Boolean(
        'Descargar y adjuntar PDF', default=False, tracking=True,
        help='Ademas del XML, descarga el PDF del DTE y lo adjunta al chatter '
             'de la factura. OJO: consume UNA llamada API adicional por '
             'documento, y depende del portal PUBLICO de la SAT (no del '
             'proveedor), que puede ser intermitente. Si falla varias veces '
             'seguidas en una corrida, se detiene el resto del lote para no '
             'agotar la cuota en vano.'
    )
    enable_nit_button = fields.Boolean(
        'Boton "NIT FEL2ODOO" en contactos', default=True, tracking=True,
        help='Muestra en el formulario de contacto el boton inteligente '
             '"NIT FEL2ODOO", que consulta a la SAT el nombre oficial del NIT '
             'y actualiza el nombre del contacto. Si se desactiva, el boton no '
             'aparece para esta empresa.'
    )

    # ------------------------------------------------------------------
    # Emision de facturas (certificar ante la SAT)
    # ------------------------------------------------------------------
    enable_emision = fields.Boolean(
        'Habilitar emision de facturas', default=False, tracking=True,
        help='Interruptor maestro: permite EMITIR (certificar ante la SAT) '
             'facturas de venta con este proveedor. Solo puede activarse tras '
             'probar la conexion. Ademas, cada diario de VENTAS debe marcarse '
             'individualmente (pestana FEL2Odoo en el diario) para participar; '
             'este interruptor no activa ningun diario por si solo. Por ahora '
             'cubre unicamente facturas de venta normales (FACT); notas de '
             'credito y otros tipos de documento quedan pendientes de '
             'confirmar con el proveedor antes de habilitarse.'
    )

    # ------------------------------------------------------------------
    # Automatizacion y limite de llamadas API (control de cuota)
    # ------------------------------------------------------------------
    auto_sync_enabled = fields.Boolean(
        'Sincronizacion automatica (cron)', default=False, tracking=True, copy=False,
        help='Si esta DESACTIVADO, la accion planificada no ejecuta esta '
             'conexion (solo se sincroniza con el boton "Sincronizar ahora"). '
             'Solo puede activarse tras probar la conexion.'
    )
    sync_frequency = fields.Selection([
        ('6h', 'Cada 6 horas'),
        ('12h', 'Cada 12 horas'),
        ('daily', 'Diaria'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
    ], string='Frecuencia automatica', default='daily', tracking=True,
        help='Cada cuanto, como maximo, corre el flujo completo automaticamente.')
    last_auto_sync = fields.Datetime('Ultima corrida automatica', readonly=True, copy=False)

    monthly_call_limit = fields.Integer(
        'Limite de llamadas API/mes', default=15, tracking=True,
        help='Maximo de llamadas al proveedor por mes (0 = sin limite). Al '
             'alcanzarlo, la sincronizacion se detiene para no agotar su plan. '
             'Plan gratuito apifelcore: 15; de paga: 150.'
    )
    calls_used = fields.Integer('Llamadas usadas este mes', readonly=True, copy=False)
    calls_month = fields.Char('Mes del contador', readonly=True, copy=False)
    calls_left = fields.Integer('Llamadas restantes', compute='_compute_calls_left')

    log_ids = fields.One2many('ktx.fel2odoo.log', 'config_id', string='Bitacora')
    log_count = fields.Integer('Corridas', compute='_compute_counts')

    _company_uniq = models.Constraint(
        'unique(company_id)',
        'Ya existe una configuracion FEL para esta empresa.',
    )

    # ==================================================================
    # Computes / constraints / write hooks
    # ==================================================================
    @api.depends('log_ids')
    def _compute_counts(self):
        # read_group en una sola consulta en vez de un search_count por registro
        # (evita N+1 en la vista lista de conexiones).
        grouped = dict(self.env['ktx.fel2odoo.log']._read_group(
            [('config_id', 'in', self.ids)], ['config_id'], ['__count']))
        for rec in self:
            rec.log_count = grouped.get(rec, 0)

    @api.depends('calls_used', 'calls_month', 'monthly_call_limit')
    def _compute_calls_left(self):
        current = fields.Date.context_today(self).strftime('%Y-%m')
        for rec in self:
            used = rec.calls_used if rec.calls_month == current else 0
            rec.calls_left = (rec.monthly_call_limit - used
                              if rec.monthly_call_limit else 9999)

    @api.constrains('auto_sync_enabled', 'connection_ok')
    def _check_auto_ready(self):
        for rec in self:
            if rec.auto_sync_enabled and not rec.connection_ok:
                raise ValidationError(_(
                    'No puede activar la sincronizacion automatica sin probar la '
                    'conexion con exito (boton "Probar conexion").'))

    @api.constrains('enable_emision', 'connection_ok')
    def _check_emision_ready(self):
        for rec in self:
            if rec.enable_emision and not rec.connection_ok:
                raise ValidationError(_(
                    'No puede habilitar la emision de facturas sin probar la '
                    'conexion con exito (boton "Probar conexion").'))

    def write(self, vals):
        # Cambiar credenciales invalida la prueba de conexion, apaga el
        # automatico y la emision, para que no sigan corriendo con datos
        # posiblemente malos.
        if any(f in vals for f in _CREDENTIAL_FIELDS) and 'connection_ok' not in vals:
            vals['connection_ok'] = False
            vals.setdefault('auto_sync_enabled', False)
            vals.setdefault('enable_emision', False)
        return super().write(vals)

    # ==================================================================
    # Control de cuota de llamadas API
    # ==================================================================
    def _current_month(self):
        return fields.Date.context_today(self).strftime('%Y-%m')

    def _reset_quota_if_new_month(self):
        current = self._current_month()
        if self.calls_month != current:
            self.sudo().write({'calls_month': current, 'calls_used': 0})

    def _quota_left(self):
        """Llamadas disponibles este mes (grande si no hay limite)."""
        self.ensure_one()
        self._reset_quota_if_new_month()
        if not self.monthly_call_limit:
            return 10 ** 9
        return max(0, self.monthly_call_limit - self.calls_used)

    def _consume_call(self, n=1):
        self.ensure_one()
        self._reset_quota_if_new_month()
        # Incremento ATOMICO en la base (UPDATE ... SET calls_used = calls_used + n)
        # en vez de leer-en-Python-y-escribir: con varios workers/cron+manual en
        # paralelo, un read-modify-write pierde incrementos y la cuota real se
        # superaria. El UPDATE atomico no pierde ninguno.
        self.env.cr.execute(
            'UPDATE ktx_fel2odoo_config SET calls_used = COALESCE(calls_used, 0) + %s '
            'WHERE id = %s', (n, self.id))
        self.invalidate_recordset(['calls_used'])

    def action_reset_quota(self):
        self.ensure_one()
        self.sudo().write({'calls_used': 0, 'calls_month': self._current_month()})
        return self._notify(
            _('Contador reiniciado'),
            _('El contador de llamadas del mes se puso en cero.'), 'success')

    # ==================================================================
    # Cliente HTTP
    # ==================================================================
    def _api_url(self, path):
        base = (self.base_url or '').rstrip('/')
        return '%s/%s' % (base, path.lstrip('/'))

    def _headers(self, auth=True):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer %s' % (self.bearer_token or '')
        return headers

    def _check_requests(self):
        if requests is None:
            raise UserError(_(
                'La libreria de Python "requests" no esta disponible en este '
                'servidor Odoo y es necesaria para conectarse al proveedor.'))

    def _login(self):
        """Autentica en el proveedor y guarda el token de plataforma."""
        self.ensure_one()
        self._check_requests()
        if not self.email or not self.password:
            raise UserError(_('Configure el email y password de plataforma.'))
        url = self._api_url('login')
        payload = {
            'email': self.email,
            'password': self.password,
            'device_name': self.device_name or 'odoo',
        }
        try:
            resp = requests.post(
                url, data=json.dumps(payload),
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                timeout=_HTTP_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            raise UserError(_('No se pudo contactar al proveedor: %s') % exc)
        if resp.status_code != 200:
            raise UserError(_('Login fallido (HTTP %s): %s') % (resp.status_code, resp.text[:300]))
        try:
            data = resp.json()
        except ValueError:
            raise UserError(_('Respuesta de login no es JSON.'))
        token = data.get('token') or data.get('access_token')
        if not token:
            raise UserError(_('El proveedor no devolvio token.'))
        self.sudo().write({'bearer_token': token, 'token_date': fields.Datetime.now()})
        return token

    def _ensure_token(self, force=False):
        self.ensure_one()
        expired = True
        if self.token_date:
            expired = fields.Datetime.now() - self.token_date > timedelta(hours=_TOKEN_TTL_HOURS)
        if force or not self.bearer_token or expired:
            self._login()
        return self.bearer_token

    def _business_payload(self, extra=None):
        """Cuerpo base de negocio (nit + token_fel) con los extras dados."""
        payload = {'nit': (self.nit or '').strip(), 'token_fel': self.token_fel or ''}
        if extra:
            payload.update(extra)
        return payload

    def _api_post(self, path, payload, auth=True, _retry=True):
        """POST autenticado con re-login automatico ante 401 y control de cuota."""
        self.ensure_one()
        self._check_requests()
        # Las llamadas de negocio (agencia-virtual/*) cuentan contra la cuota.
        is_business = path.lstrip('/').startswith('agencia-virtual')
        if is_business and self._quota_left() <= 0:
            raise UserError(_(
                'Limite mensual de llamadas API alcanzado (%d). La sincronizacion '
                'se detuvo para no agotar su plan. Aumente el limite en la '
                'conexion o espere al proximo mes.') % self.monthly_call_limit)
        if auth:
            self._ensure_token()
        url = self._api_url(path)
        if is_business and _retry:
            # Se consume ANTES de enviar: la llamada al proveedor ya se hace,
            # cuente o no como exitosa de su lado. Solo en el primer intento
            # (_retry=True): el reintento interno tras un 401 (re-login) es la
            # MISMA operacion logica y no debe descontar cuota otra vez.
            self._consume_call(1)
        try:
            resp = requests.post(
                url, data=json.dumps(payload), headers=self._headers(auth),
                timeout=_HTTP_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            raise UserError(_('Error de red al llamar %s: %s') % (path, exc))
        if resp.status_code == 401 and auth and _retry:
            self._login()
            return self._api_post(path, payload, auth=auth, _retry=False)
        if resp.status_code == 403:
            raise UserError(_(
                'Plan no activo o limite de solicitudes excedido (403). '
                'Contacte al proveedor para activar/verificar que su plan '
                'incluye la consulta de DTE.\nRespuesta del proveedor: %s')
                % (resp.text[:400] or '(vacia)'))
        if resp.status_code == 400:
            raise UserError(_('Peticion invalida o NIT/token inconsistente (400): %s') % resp.text[:400])
        if resp.status_code == 404:
            return None
        if resp.status_code >= 500:
            raise UserError(_('Error interno del proveedor (HTTP %s): %s')
                            % (resp.status_code, resp.text[:400] or '(vacia)'))
        if resp.status_code != 200:
            raise UserError(_('Respuesta inesperada (HTTP %s): %s') % (resp.status_code, resp.text[:400]))
        try:
            return resp.json()
        except ValueError:
            # No es JSON: la respuesta es un cuerpo crudo (p. ej. el XML del DTE
            # devuelto directamente). Se devuelven los BYTES sin tocar, NO
            # resp.text: resp.text decodifica segun el charset ADIVINADO del
            # header HTTP (requests cae a ISO-8859-1 cuando el servidor no
            # declara charset), lo que corrompe las tildes/enies de un XML
            # UTF-8. Un XML debe decodificarse por su propia declaracion de
            # encoding, y para eso el parser necesita los bytes originales
            # (_coerce_xml_bytes / _coerce_pdf_bytes ya aceptan bytes).
            return resp.content

    # ==================================================================
    # Operaciones de negocio
    # ==================================================================
    @staticmethod
    def _fmt_date(dt):
        """Formato DD-MM-YYYY que exige el proveedor."""
        return dt.strftime('%d-%m-%Y')

    @staticmethod
    def _pick(d, keys, default=None):
        """Devuelve el primer valor presente entre varias claves candidatas."""
        if not isinstance(d, dict):
            return default
        for k in keys:
            if k in d and d[k] not in (None, ''):
                return d[k]
        return default

    @staticmethod
    def _debug_snippet(raw):
        """Serializa la respuesta del proveedor para la bitacora (truncada)."""
        try:
            return json.dumps(raw, ensure_ascii=False, default=str, indent=2)[:12000]
        except Exception:  # noqa: BLE001
            return str(raw)[:12000]

    def _compose_raw_log(self, dl_sample, pdf_sample, last_raw):
        """Arma el texto de 'raw_response' del log combinando las muestras de
        descargar-xml, descargar-pdf y la consulta."""
        partes = []
        if dl_sample:
            partes.append(dl_sample)
        if pdf_sample:
            partes.append('========\nPDF:\n' + pdf_sample)
        partes.append('========\nCONSULTA:\n' + self._debug_snippet(last_raw))
        return '\n\n'.join(partes)

    def _extract_doc_list(self, response):
        """Normaliza la respuesta de consultar-documentos a una lista de dicts."""
        if response is None:
            return []
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            for key in ('documentos', 'data', 'dtes', 'result', 'documents', 'items'):
                val = response.get(key)
                if isinstance(val, list):
                    return val
            for val in response.values():
                if isinstance(val, dict):
                    inner = self._extract_doc_list(val)
                    if inner:
                        return inner
        return []

    def _consultar_documentos(self, tipo_operacion, date_from, date_to):
        self.ensure_one()
        payload = self._business_payload({
            'tipo_operacion': tipo_operacion,
            'fecha_inicio': self._fmt_date(date_from),
            'fecha_fin': self._fmt_date(date_to),
        })
        if self.estado_dte:
            payload['estado_dte'] = self.estado_dte
        if self.tipo_documento:
            payload['tipo_documento'] = self.tipo_documento.strip().upper()
        return self._api_post('agencia-virtual/consultar-documentos', payload)

    def _numero_aliases(self, numero):
        """Envia el numero de autorizacion bajo varios nombres de campo, por si
        el endpoint del proveedor lee una clave distinta a la documentada."""
        return {
            'numero_autorizacion': numero,
            'numeroAutorizacion': numero,
            'no_autorizacion': numero,
            'noAutorizacion': numero,
            'autorizacion': numero,
            'uuid': numero,
        }

    def _descargar_xml_raw(self, nit_receptor, numero_autorizacion):
        """Devuelve la respuesta cruda de descargar-xml (para diagnostico)."""
        self.ensure_one()
        extra = {'nit_receptor': nit_receptor or 'CF'}
        extra.update(self._numero_aliases(numero_autorizacion))
        payload = self._business_payload(extra)
        return self._api_post('agencia-virtual/descargar-xml', payload)

    def _descargar_xml(self, nit_receptor, numero_autorizacion):
        """Descarga y devuelve los bytes del XML del DTE (o None)."""
        self.ensure_one()
        return self._coerce_xml_bytes(
            self._descargar_xml_raw(nit_receptor, numero_autorizacion))

    @staticmethod
    def _coerce_xml_bytes(response):
        """Extrae los bytes del XML desde respuestas de distinta forma, incluso
        anidadas (p. ej. {"data": {"xml": "<?xml ..."}}). Devuelve None si el
        contenido no es un XML valido (no se inventan bytes basura)."""
        if response is None:
            return None
        if isinstance(response, bytes):
            return response
        if isinstance(response, dict):
            raw = KtxFel2odooConfig._pick(
                response, ['xml', 'data', 'contenido', 'content', 'archivo',
                           'base64', 'xml_base64', 'result'])
            return KtxFel2odooConfig._coerce_xml_bytes(raw)
        if isinstance(response, (list, tuple)):
            for item in response:
                out = KtxFel2odooConfig._coerce_xml_bytes(item)
                if out:
                    return out
            return None
        text = str(response).strip()
        if not text:
            return None
        if text.startswith('<'):
            return text.encode('utf-8')
        try:
            decoded = base64.b64decode(text, validate=False)
            if decoded.lstrip()[:1] == b'<':
                return decoded
        except Exception:  # noqa: BLE001
            pass
        return None

    def _descargar_pdf_raw(self, nit_receptor, numero_autorizacion):
        """Devuelve la respuesta CRUDA de descargar-pdf (para diagnostico)."""
        self.ensure_one()
        extra = {'nit_receptor': nit_receptor or 'CF'}
        extra.update(self._numero_aliases(numero_autorizacion))
        payload = self._business_payload(extra)
        return self._api_post('agencia-virtual/descargar-pdf', payload)

    def _descargar_pdf(self, nit_receptor, numero_autorizacion):
        """Descarga el PDF del DTE. Devuelve bytes o None."""
        self.ensure_one()
        return self._coerce_pdf_bytes(
            self._descargar_pdf_raw(nit_receptor, numero_autorizacion))

    # ==================================================================
    # Consulta de nombre por NIT (agencia-virtual/nombre-receptor)
    # ==================================================================
    @api.model
    def _get_query_config(self, company):
        """Devuelve una conexion FEL2Odoo ACTIVA para hacer consultas de solo
        lectura (p. ej. nombre por NIT) en esta empresa, o lanza UserError."""
        config = self.search([
            ('company_id', '=', company.id),
            ('active', '=', True),
        ], limit=1)
        if not config:
            raise UserError(_(
                'No hay una conexion FEL2Odoo activa para la empresa "%s". '
                'Configurela en FEL2Odoo > Conexiones FEL.'
            ) % company.display_name)
        return config

    def _nombre_receptor_raw(self, nit):
        """Respuesta CRUDA de agencia-virtual/nombre-receptor para un NIT.

        Se envia el valor a consultar bajo varios alias de campo (como en el
        resto del modulo) por si el endpoint del proveedor lee una clave
        distinta a la documentada. OJO: no se toca 'nit' (que en el cuerpo de
        negocio es el NIT del EMISOR/cliente de la plataforma), sino
        'nit_receptor' y equivalentes (el NIT que se quiere resolver)."""
        self.ensure_one()
        valor = (nit or '').replace('-', '').strip().upper()
        extra = {
            'nit_receptor': valor,
            'nitReceptor': valor,
            'nit_consulta': valor,
        }
        return self._api_post('agencia-virtual/nombre-receptor',
                              self._business_payload(extra))

    @staticmethod
    def _extract_nombre_receptor(response):
        """Extrae el nombre desde respuestas de distinta forma (dict/lista/str,
        incluso anidadas en 'data'/'result'/'receptor'). Devuelve '' si no hay."""
        if response is None:
            return ''
        if isinstance(response, str):
            s = response.strip()
            return s if (s and s[:1] not in ('{', '[')) else ''
        if isinstance(response, dict):
            name = KtxFel2odooConfig._pick(response, [
                'nombre', 'nombre_receptor', 'nombreReceptor', 'nombre_completo',
                'nombreCompleto', 'razon_social', 'razonSocial', 'nombre_nit',
                'nombreNit', 'name'])
            if name and isinstance(name, str):
                return name.strip()
            for key in ('data', 'result', 'receptor', 'contribuyente', 'response', 'datos'):
                if key in response:
                    inner = KtxFel2odooConfig._extract_nombre_receptor(response[key])
                    if inner:
                        return inner
            return ''
        if isinstance(response, (list, tuple)):
            for item in response:
                inner = KtxFel2odooConfig._extract_nombre_receptor(item)
                if inner:
                    return inner
        return ''

    def _consultar_nombre_receptor(self, nit):
        """Consulta a la SAT (via apifelcore) el nombre oficial de un NIT.
        Devuelve el nombre (str) o '' si el proveedor no lo resolvio."""
        self.ensure_one()
        return self._extract_nombre_receptor(self._nombre_receptor_raw(nit))

    def _pdf_raw_diagnostic(self, numero, raw, pdf_bytes):
        """Resumen legible de la respuesta cruda de descargar-pdf, para el log
        de diagnostico: que forma tiene y si logramos extraer el PDF."""
        if isinstance(raw, dict):
            forma = 'dict claves=%s' % list(raw.keys())
            data = raw.get('data')
            if isinstance(data, dict):
                forma += ' data.claves=%s' % list(data.keys())
        elif isinstance(raw, (list, tuple)):
            forma = 'lista(%d)' % len(raw)
        else:
            forma = type(raw).__name__
        return _(
            'Primera respuesta de descargar-pdf (%s):\n'
            'Forma: %s\n¿PDF extraido? %s (%s bytes)\n---\nRespuesta cruda:\n%s'
        ) % (numero, forma, 'SI' if pdf_bytes else 'NO',
             len(pdf_bytes) if pdf_bytes else 0,
             self._debug_snippet(raw)[:1500])

    def _fetch_pdf_url(self, url):
        """Descarga bytes desde una URL de PDF. Acepta que la URL devuelva el
        PDF directamente (%PDF...) o un texto base64. Devuelve bytes o None."""
        if requests is None or not url:
            return None
        try:
            r = requests.get(url, timeout=_HTTP_TIMEOUT)
        except Exception:  # noqa: BLE001
            return None
        if r.status_code != 200 or not r.content:
            return None
        if r.content[:4] == b'%PDF':
            return r.content
        # Algunos enlaces devuelven el PDF como base64 en texto plano.
        return self._coerce_pdf_bytes(r.text, _depth=5)

    def _coerce_pdf_bytes(self, response, _depth=0):
        """Extrae los bytes del PDF desde respuestas de distinta forma, incluso
        anidadas (p. ej. {"success": true, "data": {"base64": "..."}} o
        {"data": {"url": "https://..."}}). El contrato documentado de
        descargar-pdf devuelve 'su URL de descarga junto con el contenido
        base64', pero sin fijar el nombre exacto de las claves ni el nivel de
        anidacion: por eso se busca de forma recursiva y se valida siempre la
        firma real del PDF (%PDF) antes de aceptar los bytes, sin inventar
        contenido. Devuelve bytes validos o None.

        Este es el arreglo del sintoma 'la SAT no lo genero a tiempo' cuando en
        realidad el proveedor SI respondio 200 con el PDF: antes se tomaba el
        dict 'data' completo como si fuera el contenido y el base64 real, que
        estaba adentro, nunca se leia."""
        if response is None or _depth > 6:
            return None
        if isinstance(response, bytes):
            return response if response[:4] == b'%PDF' else None
        if isinstance(response, str):
            text = response.strip()
            if not text:
                return None
            if text[:4].lower() == 'http':
                return self._fetch_pdf_url(text)
            try:
                decoded = base64.b64decode(text, validate=False)
                if decoded[:4] == b'%PDF':
                    return decoded
            except Exception:  # noqa: BLE001
                pass
            return None
        if isinstance(response, (list, tuple)):
            for item in response:
                out = self._coerce_pdf_bytes(item, _depth + 1)
                if out:
                    return out
            return None
        if isinstance(response, dict):
            # 1) Claves de contenido base64 directo.
            for key in ('base64', 'pdf_base64', 'pdf', 'contenido', 'content',
                        'archivo', 'file', 'documento'):
                if response.get(key):
                    out = self._coerce_pdf_bytes(response[key], _depth + 1)
                    if out:
                        return out
            # 2) Claves de URL de descarga.
            for key in ('url', 'pdf_url', 'enlace', 'link', 'download_url'):
                if response.get(key):
                    out = self._fetch_pdf_url(response[key])
                    if out:
                        return out
            # 3) Contenedores anidados (data, result, ...).
            for key in ('data', 'result', 'resultado', 'response', 'respuesta'):
                if response.get(key) not in (None, ''):
                    out = self._coerce_pdf_bytes(response[key], _depth + 1)
                    if out:
                        return out
            # 4) Ultimo recurso: recorrer todos los valores (se valida %PDF, asi
            #    que no hay riesgo de aceptar basura).
            for value in response.values():
                if isinstance(value, (dict, list, tuple, str, bytes)):
                    out = self._coerce_pdf_bytes(value, _depth + 1)
                    if out:
                        return out
            return None
        return None

    # ==================================================================
    # Emision de facturas (certificar ante la SAT)
    # ==================================================================
    @api.model
    def _get_emision_config(self, company):
        """Devuelve la conexion con la emision HABILITADA para esta empresa,
        o lanza UserError con instrucciones claras si no hay ninguna."""
        config = self.search([
            ('company_id', '=', company.id),
            ('enable_emision', '=', True),
            ('connection_ok', '=', True),
            ('active', '=', True),
        ], limit=1)
        if not config:
            raise UserError(_(
                'No hay una conexion FEL2Odoo con la emision de facturas '
                'habilitada para la empresa "%s". Configure y active la '
                'emision en FEL2Odoo > Conexiones FEL (pestana Emision).'
            ) % company.display_name)
        return config

    def _build_emision_payload(self, move):
        """Construye el cuerpo documentado de /agencia-virtual/emitir-documento
        a partir de una factura de venta confirmada. Solo cubre FACT (factura
        de venta normal); no incluye periodos/abono/fecha_fin (propios de
        factura cambiaria, fuera de alcance por ahora)."""
        self.ensure_one()
        partner = move.partner_id.commercial_partner_id or move.partner_id
        nit_receptor = (partner.vat or 'CF').replace('-', '').strip().upper() or 'CF'
        nombre_receptor = partner.name or _('CONSUMIDOR FINAL')
        direccion_receptor = ', '.join(
            p for p in (partner.street, partner.street2) if p) or _('Ciudad')

        items = []
        for line in move.invoice_line_ids:
            # display_type distingue el TIPO de linea: en esta version de
            # Odoo una linea de producto normal trae display_type='product'
            # (no False como en versiones viejas). Solo se omiten las
            # lineas realmente decorativas/tecnicas (seccion, nota, terminos
            # de pago, impuestos, redondeo...), NO las de producto.
            if line.display_type not in (False, 'product'):
                continue
            if not line.product_id and not line.name:
                continue
            tipo = 'S'
            if line.product_id:
                # 'product'/'consu' = bien (Odoo <17); Odoo 17+ unifico esos
                # dos en 'consu' con is_storable aparte. 'service' = servicio.
                tipo = 'S' if line.product_id.type == 'service' else 'B'

            # 'precio' es el TOTAL por unidad (con IVA incluido cuando
            # aplique, confirmado por el usuario) -- NO el precio unitario
            # sin impuesto. Se deriva de price_total/price_subtotal (ya
            # calculados por Odoo, incluyen el regimen de impuestos real de
            # la linea: 12%, 0%/exento, etc.) en vez de asumir una tasa fija.
            # tasa_efectiva = cuanto se le agrega al subtotal por impuestos.
            tasa_efectiva = ((line.price_total - line.price_subtotal) / line.price_subtotal
                             if line.price_subtotal else 0.0)
            precio_unitario_con_iva = round(line.price_unit * (1 + tasa_efectiva), 2)
            # El descuento se reporta en la MISMA base (con IVA), para que
            # precio*cantidad - descuento reconstruya el total real de la
            # linea (price_total) que ya calculo Odoo.
            descuento = round(precio_unitario_con_iva * line.quantity * (line.discount / 100.0), 2) \
                if line.discount else 0
            # Normaliza saltos de linea: es comun que 'name' traiga el
            # producto en la primera linea y texto libre en la(s) siguiente(s)
            # (ej. "[GTSERV002] SERVICIO\nPRUEBA"); la SAT espera una
            # descripcion de una sola linea.
            descripcion = (line.name or line.product_id.display_name or '')
            descripcion = ' '.join(descripcion.split())[:200]
            items.append({
                'cantidad': line.quantity,
                'descripcion': descripcion,
                'precio': precio_unitario_con_iva,
                'tipo': tipo,
                'descuento': descuento,
            })
        if not items:
            # Diagnostico detallado: en vez de un mensaje generico, se
            # muestra el estado real de cada linea para saber EXACTO por
            # que se omitio (en vez de adivinar de nuevo a ciegas).
            detalle = '; '.join(
                'linea %d: display_type=%r producto=%r nombre=%r' % (
                    i + 1, l.display_type, l.product_id.display_name if l.product_id else None, l.name)
                for i, l in enumerate(move.invoice_line_ids)
            ) or _('(move.invoice_line_ids esta vacio)')
            raise UserError(_(
                'La factura no tiene lineas facturables para emitir. '
                'Detalle de las lineas encontradas: %s') % detalle)

        try:
            codigo_postal = int(partner.zip) if partner.zip and partner.zip.strip().isdigit() else 1
        except (TypeError, ValueError):
            codigo_postal = 1

        # 'establecimiento' es INTEGER segun el contrato documentado
        # (emitir-documento: "establecimiento": 1). El numero de
        # establecimiento se guarda como texto en el diario, asi que se
        # convierte a entero aqui (por defecto 1 si viene vacio o no numerico).
        establecimiento_raw = (move.journal_id.ktx_fel2odoo_establecimiento or '1').strip()
        try:
            establecimiento = int(establecimiento_raw) if establecimiento_raw.isdigit() else 1
        except (TypeError, ValueError):
            establecimiento = 1

        extra = {
            'nit_receptor': nit_receptor,
            'nombre_receptor': nombre_receptor,
            'direccion_receptor': direccion_receptor,
            'correo_receptor': partner.email or '',
            'municipio_receptor': partner.city or '',
            'departamento_receptor': partner.state_id.name or '',
            'pais': partner.country_id.code or 'GT',
            'codigo_postal': codigo_postal,
            'establecimiento': establecimiento,
            'items': items,
        }
        return self._business_payload(extra)

    def _emitir_documento(self, move):
        """Emite (certifica ante la SAT) una factura de venta confirmada.
        Devuelve la respuesta cruda del proveedor SIN interpretarla: el
        formato de respuesta de este endpoint no viene documentado con un
        ejemplo, asi que quien llama (account.move) decide como leerla y dejar
        constancia. Lanza UserError si el proveedor no responde o rechaza."""
        self.ensure_one()
        if not self.enable_emision:
            raise UserError(_('La emision de facturas esta desactivada en esta conexion.'))
        payload = self._build_emision_payload(move)
        response = self._api_post('agencia-virtual/emitir-documento', payload)
        if response is None:
            raise UserError(_('El proveedor no devolvio respuesta al emitir la factura.'))
        if isinstance(response, dict) and response.get('success') is False:
            raise UserError(_('El proveedor rechazo la emision: %s') % (
                response.get('message') or response.get('error')
                or self._debug_snippet(response)[:300]))
        return response

    def _anular_documento(self, move, motivo):
        """Anula ante la SAT un documento previamente emitido por FEL2Odoo."""
        self.ensure_one()
        if not move.fel2odoo_uuid:
            raise UserError(_(
                'Esta factura no tiene un UUID de FEL2Odoo; no se puede '
                'anular desde aqui.'))
        partner = move.partner_id.commercial_partner_id or move.partner_id
        nit_receptor = (partner.vat or 'CF').replace('-', '').strip().upper() or 'CF'
        extra = {
            'numero_autorizacion': move.fel2odoo_uuid,
            'nit_receptor': nit_receptor,
            'observacion': motivo,
        }
        payload = self._business_payload(extra)
        response = self._api_post('agencia-virtual/anular-documento', payload)
        if response is None:
            raise UserError(_('El proveedor no devolvio respuesta al anular la factura.'))
        if isinstance(response, dict) and response.get('success') is False:
            raise UserError(_('El proveedor rechazo la anulacion: %s') % (
                response.get('message') or response.get('error')
                or self._debug_snippet(response)[:300]))
        return response

    # ==================================================================
    # Sincronizacion
    # ==================================================================
    def _compute_range(self, last_sync):
        """Calcula (fecha_inicio, fecha_fin) para una corrida."""
        today = fields.Date.context_today(self)
        if self.date_from_initial:
            return self.date_from_initial, today
        if last_sync:
            start = fields.Datetime.context_timestamp(self, last_sync).date() - timedelta(days=3)
        else:
            start = today - timedelta(days=max(self.lookback_days or 30, 1))
        return start, today

    @staticmethod
    def _iter_date_windows(start, end, max_days=30):
        """Parte un rango en ventanas de a lo sumo max_days."""
        cur = start
        while cur <= end:
            w_end = min(cur + timedelta(days=max_days - 1), end)
            yield cur, w_end
            cur = w_end + timedelta(days=1)

    def _ready_credentials(self):
        """True si estan todas las credenciales minimas."""
        self.ensure_one()
        return bool(self.base_url and self.email and self.password
                    and self.nit and self.token_fel)

    def action_test_connection(self):
        self.ensure_one()
        self._login()
        self.sudo().write({'connection_ok': True})
        return self._notify(
            _('Conexion exitosa'),
            _('Se autentico correctamente con el proveedor. Ya puede activar la '
              'sincronizacion automatica.'),
            'success')

    def action_toggle_auto_sync(self):
        """Activa/desactiva la sincronizacion automatica (con candado)."""
        self.ensure_one()
        if not self.auto_sync_enabled:
            if not self._ready_credentials():
                raise UserError(_('Complete todas las credenciales de la conexion.'))
            if not self.connection_ok:
                raise UserError(_(
                    'Primero pulse "Probar conexion". Solo con la conexion '
                    'verificada se puede activar el automatico.'))
            if self.sync_sales and not self.journal_sale_id:
                raise UserError(_('Seleccione el diario de ventas.'))
            if self.sync_purchases and not self.journal_purchase_id:
                raise UserError(_('Seleccione el diario de compras.'))
            self.auto_sync_enabled = True
            return self._notify(
                _('Automatico ACTIVO'),
                _('La sincronizacion automatica esta en vivo (%s).')
                % dict(self._fields['sync_frequency'].selection).get(self.sync_frequency, ''),
                'success')
        self.auto_sync_enabled = False
        return self._notify(
            _('Automatico desactivado'),
            _('La sincronizacion automatica se apago.'), 'warning')

    def action_sync_now(self):
        """Ejecuta la sincronizacion manual SOLO de esta configuracion y su
        empresa (nunca de otras empresas)."""
        self.ensure_one()
        results = self.with_company(self.company_id)._sync()
        summary = ', '.join(results) if results else _('Nada por sincronizar.')
        return self._notify(_('Sincronizacion FEL'), summary, 'success')

    def action_reset_sync(self):
        """Limpia las marcas de ultima sincronizacion."""
        self.ensure_one()
        self.write({'last_sync_sale': False, 'last_sync_purchase': False})
        return self._notify(
            _('Sincronizacion reiniciada'),
            _('La proxima corrida consultara desde la fecha inicial configurada.'),
            'success')

    def _sync(self):
        """Sincroniza ventas y/o compras. Devuelve resumenes por operacion."""
        self.ensure_one()
        results = []
        if self.sync_sales:
            results.append(self._run_operacion('EMITIDOS'))
        if self.sync_purchases:
            results.append(self._run_operacion('RECIBIDOS'))
        return results

    def _run_operacion(self, tipo_operacion):
        """Ejecuta una operacion (EMITIDOS/RECIBIDOS) y registra bitacora."""
        self.ensure_one()
        import_type = _OPERACION_A_IMPORT[tipo_operacion]
        last_field = 'last_sync_sale' if import_type == 'sale' else 'last_sync_purchase'
        journal = self.journal_sale_id if import_type == 'sale' else self.journal_purchase_id
        date_from, date_to = self._compute_range(self[last_field])

        Log = self.env['ktx.fel2odoo.log']
        log = Log.create({
            'config_id': self.id,
            'company_id': self.company_id.id,
            'tipo_operacion': tipo_operacion,
            'date_from': date_from,
            'date_to': date_to,
            'state': 'running',
        })
        try:
            if not journal:
                raise UserError(_('Configure el diario de %s.') % (
                    _('ventas') if import_type == 'sale' else _('compras')))
            if journal.company_id and journal.company_id != self.company_id:
                raise UserError(_(
                    'El diario "%s" pertenece a la empresa "%s", distinta de la '
                    'empresa de esta conexion ("%s"). Seleccione un diario de la '
                    'empresa correcta.') % (
                    journal.display_name, journal.company_id.display_name,
                    self.company_id.display_name))

            docs = []
            last_raw = None
            window_errors = []
            for w_from, w_to in self._iter_date_windows(date_from, date_to):
                try:
                    last_raw = self._consultar_documentos(tipo_operacion, w_from, w_to)
                    docs += self._extract_doc_list(last_raw)
                except UserError as exc:
                    _logger.warning('FEL2Odoo: consulta fallo %s..%s: %s', w_from, w_to, exc)
                    window_errors.append('%s..%s: %s' % (w_from, w_to, str(exc)[:150]))
            if window_errors and not docs:
                raise UserError('\n'.join(window_errors))
            xml_files, found, reasons, dl_errors, dl_sample = self._collect_new_xmls(
                docs, import_type)
            skipped = sum(reasons.values())

            invoices = self.env['account.move']
            session = False
            pdf_sample = ''
            if xml_files:
                session, invoices = self._create_invoices_from_xmls(
                    import_type, journal, xml_files)
                if _PDF_FEATURE_ENABLED and self.download_pdf and invoices:
                    pdf_sample = self._attach_pdfs(session, import_type)

            confirmed = 0
            if self.auto_confirm and invoices:
                confirmed = self._confirm_invoices(invoices)

            if self.use_ai_classification and invoices:
                self._ai_post_process(invoices, log)

            self.sudo().write({last_field: fields.Datetime.now()})
            message = self._build_summary(
                tipo_operacion, found, reasons, session, invoices, confirmed, dl_errors)
            log.write({
                'state': 'success',
                'session_id': session.id if session else False,
                'docs_found': found,
                'docs_skipped': skipped,
                'invoices_created': len(invoices),
                'invoices_confirmed': confirmed,
                'message': message,
                'raw_response': self._compose_raw_log(dl_sample, pdf_sample, last_raw),
            })
            base = _('%s: %d facturas de %d documentos.') % (
                tipo_operacion, len(invoices), found)
            if len(invoices) < found:
                base += _(' Motivo: %s.') % self._dominant_reason(
                    found, len(invoices), reasons, session, dl_errors)
            return base
        except Exception as exc:  # noqa: BLE001
            _logger.exception('FEL2Odoo sync error (%s)', tipo_operacion)
            log.write({'state': 'error', 'message': str(exc)})
            return _('%s: ERROR - %s') % (tipo_operacion, str(exc)[:200])

    def _dominant_reason(self, found, created, reasons, session, dl_errors):
        """Frase corta con el motivo PRINCIPAL por el que no se crearon todas
        las facturas, para mostrarla en el toast (el detalle va en la Bitacora).
        Distingue: ya existia, error del proveedor, sin cuota, o error de datos."""
        if not found:
            return _('no habia documentos en el rango consultado')
        # Buckets (conteo, frase). Se elige el mayor.
        buckets = []
        if reasons.get('existing'):
            buckets.append((reasons['existing'],
                            _('%d ya estaban registrados (no es error)') % reasons['existing']))
        if reasons.get('download_error'):
            buckets.append((reasons['download_error'],
                            _('%d con error del PROVEEDOR al descargar el XML')
                            % reasons['download_error']))
        if reasons.get('no_xml'):
            buckets.append((reasons['no_xml'],
                            _('%d sin XML devuelto por el proveedor') % reasons['no_xml']))
        if reasons.get('anulado'):
            buckets.append((reasons['anulado'],
                            _('%d anulados/excluidos') % reasons['anulado']))
        if reasons.get('quota'):
            buckets.append((10 ** 6,  # prioridad alta: bloqueo por cuota
                            _('se agoto la cuota mensual de llamadas')))
        if session:
            if session.duplicate_count:
                buckets.append((session.duplicate_count,
                                _('%d duplicados ya registrados') % session.duplicate_count))
            if session.wrong_nit_count:
                buckets.append((session.wrong_nit_count,
                                _('%d con NIT distinto al de la empresa')
                                % session.wrong_nit_count))
            if session.incompatible_count:
                buckets.append((session.incompatible_count,
                                _('%d XML no compatibles/invalidos') % session.incompatible_count))
            if session.cais_count or session.civa_count:
                buckets.append((session.cais_count + session.civa_count,
                                _('%d CAIS/CIVA (no se importan)')
                                % (session.cais_count + session.civa_count)))
            if session.error_count:
                buckets.append((session.error_count,
                                _('%d con error al crear la factura') % session.error_count))
        if not buckets:
            return _('ver detalle en la Bitacora')
        return max(buckets, key=lambda b: b[0])[1]

    def _build_summary(self, tipo, found, reasons, session, invoices, confirmed, dl_errors):
        """Resumen legible que informa el MOTIVO de cada omision:
        ya existia, anulado, error del proveedor, sin cuota, o problema al crear."""
        lines = [_('=== RESUMEN %s ===') % tipo]
        lines.append(_('Documentos en la SAT (rango consultado): %d') % found)
        lines.append(_('Facturas creadas: %d  |  Confirmadas: %d')
                     % (len(invoices), confirmed))

        pre = []
        if reasons.get('existing'):
            pre.append(_('- Ya existian en Odoo (no se descargaron, sin gastar llamada): %d')
                       % reasons['existing'])
        if reasons.get('anulado'):
            pre.append(_('- Anulados / estado excluido: %d') % reasons['anulado'])
        if reasons.get('quota'):
            pre.append(_('- Sin cuota disponible (limite mensual): quedaron pendientes'))
        if reasons.get('download_error'):
            pre.append(_('- ERROR DEL PROVEEDOR al descargar el XML: %d')
                       % reasons['download_error'])
        if reasons.get('no_xml'):
            pre.append(_('- El proveedor no devolvio XML: %d') % reasons['no_xml'])
        if pre:
            lines.append(_('Omitidos antes de descargar:'))
            lines += pre

        if session:
            post = []
            if session.duplicate_count:
                post.append(_('- Duplicados (ya registrados): %d') % session.duplicate_count)
            if session.wrong_nit_count:
                post.append(_('- NIT incorrecto (no coincide con la empresa): %d')
                            % session.wrong_nit_count)
            if session.incompatible_count:
                post.append(_('- XML no compatible / invalido: %d') % session.incompatible_count)
            if session.anulado_count:
                post.append(_('- Anulados: %d') % session.anulado_count)
            if session.cais_count or session.civa_count:
                post.append(_('- CAIS/CIVA (no se importan): %d')
                            % (session.cais_count + session.civa_count))
            if session.error_count:
                post.append(_('- Con error al crear la factura: %d') % session.error_count)
            if post:
                lines.append(_('De los descargados:'))
                lines += post

        if dl_errors:
            lines.append(_('Detalle de errores de descarga (proveedor):'))
            lines += ['  - ' + e for e in dl_errors]

        if found and not invoices:
            if reasons.get('existing') == found:
                lines.append(_('>> Motivo: TODOS ya estaban registrados. No es un error.'))
            elif reasons.get('download_error') or reasons.get('no_xml'):
                lines.append(_('>> Motivo: fallo del PROVEEDOR al entregar el XML.'))
            elif session and session.wrong_nit_count:
                lines.append(_('>> Motivo: el NIT de la empresa no coincide con el del DTE '
                               '(revise el NIT de la empresa o permita NIT distinto).'))
            elif session and session.incompatible_count:
                lines.append(_('>> Motivo: XML invalido/no compatible (posible error de datos).'))
        return '\n'.join(lines)

    def _collect_new_xmls(self, docs, import_type):
        """De la lista de documentos consultados, descarga SOLO los XML que aun
        NO existen en Odoo (comparando por numero de autorizacion), para ahorrar
        llamadas. Devuelve (xml_files, encontrados, omitidos, errores, muestra)."""
        self.ensure_one()
        Move = self.env['account.move']
        xml_files = []
        found = 0
        # Motivo de cada omision, para el resumen informativo.
        reasons = {'existing': 0, 'anulado': 0, 'download_error': 0,
                   'no_xml': 0, 'quota': 0}
        errors = []
        first_sample = None
        seen = set()
        for d in docs:
            # UUID (numero de autorizacion): unico, se usa para descargar el XML.
            numero = self._pick(d, [
                'numero_autorizacion', 'numeroAutorizacion', 'uuid', 'autorizacion',
                'no_autorizacion', 'llave', 'clave'])
            if not numero or numero in seen:
                continue
            seen.add(numero)
            found += 1

            estado = (self._pick(d, ['estado', 'estado_dte', 'estadoDte', 'status']) or '')
            if str(estado).strip().upper() in _ESTADOS_EXCLUIDOS:
                reasons['anulado'] += 1
                continue

            # Solo pendientes: si ya existe en Odoo, NO se descarga (ahorra llamada).
            # La importacion guarda en account.move.ref el NUMERO DE DOCUMENTO
            # (correlativo), no el UUID; por eso se compara contra ambas claves.
            # IMPORTANTE: se acota a la empresa de esta conexion. El correlativo
            # (numero_documento) NO es unico entre emisores, asi que sin filtrar
            # por company_id un correlativo repetido de OTRA empresa marcaria el
            # documento como 'existing' y nunca se importaria.
            numero_doc = self._pick(d, [
                'numero_documento', 'numeroDocumento', 'numero', 'no_documento'])
            dup_keys = [k for k in (numero, numero_doc) if k]
            if dup_keys and Move.sudo().search_count([
                    ('company_id', '=', self.company_id.id),
                    ('ref', 'in', dup_keys)]):
                reasons['existing'] += 1
                continue

            if self._quota_left() <= 0:
                reasons['quota'] += 1
                if not any(e.startswith('LIMITE') for e in errors):
                    errors.append(_('LIMITE mensual de llamadas alcanzado (%d); '
                                    'quedaron documentos sin descargar.')
                                  % self.monthly_call_limit)
                break

            if import_type == 'purchase':
                nit_receptor = self._pick(d, [
                    'nit_receptor', 'nitReceptor', 'receptor_nit', 'id_receptor',
                    'idReceptor']) or (self.nit or 'CF')
            else:
                nit_receptor = self._pick(d, [
                    'nit_receptor', 'nitReceptor', 'receptor_nit', 'id_receptor',
                    'idReceptor', 'nit_cliente']) or 'CF'

            try:
                raw = self._descargar_xml_raw(nit_receptor, numero)
                xml_bytes = self._coerce_xml_bytes(raw)
            except UserError as exc:
                _logger.warning('No se pudo descargar XML %s: %s', numero, exc)
                reasons['download_error'] += 1
                if len(errors) < 3:
                    errors.append('%s: %s' % (numero, str(exc)[:200]))
                continue
            if first_sample is None:
                head = (xml_bytes or b'')[:600]
                looks_xml = head.lstrip().startswith(b'<')
                first_sample = _(
                    'Primera respuesta de descargar-xml (%s):\n'
                    '¿Parece XML valido? %s\n---\n%s\n---\nRespuesta cruda:\n%s'
                ) % (numero, 'SI' if looks_xml else 'NO',
                     head.decode('utf-8', 'replace'),
                     self._debug_snippet(raw)[:1500])
            if not xml_bytes:
                reasons['no_xml'] += 1
                if len(errors) < 3:
                    errors.append(_('%s: el proveedor no devolvio el XML.') % numero)
                continue
            xml_files.append(('%s.xml' % numero, xml_bytes))
        return xml_files, found, reasons, errors, first_sample

    def _create_invoices_from_xmls(self, import_type, journal, xml_files):
        """Crea una sesion de importacion con los XML descargados y genera las
        facturas reutilizando toda su logica (impuestos, frases, etc.)."""
        self.ensure_one()
        company = self.company_id
        Session = self.env['ktx.import.session'].with_company(company)
        Attachment = self.env['ir.attachment'].sudo()

        att_ids = []
        for filename, xml_bytes in xml_files:
            att = Attachment.create({
                'name': filename,
                'datas': base64.b64encode(xml_bytes),
                'type': 'binary',
                'company_id': company.id,
            })
            att_ids.append(att.id)

        session = Session.create({
            'company_id': company.id,
            'import_type': import_type,
            'journal_id': journal.id,
            'attachment_ids': [(6, 0, att_ids)],
            'notes': _('Creada automaticamente por FEL2Odoo (%s).') % fields.Datetime.now(),
        })
        session.action_load_files()
        session.action_test()

        invoices = self.env['account.move']
        journal_receipts = session.journal_receipts_id or session.journal_id
        op_label = _('Compras (Recibidos)') if import_type == 'purchase' \
            else _('Ventas (Emitidos)')
        for doc in session.document_ids.filtered(lambda x: x.state == 'valid'):
            try:
                inv = doc._create_invoice(session.journal_id, import_type, journal_receipts)
                if inv:
                    invoices |= inv
                    # Constancia en el chatter de que la creo FEL2Odoo, con datos
                    # de trazabilidad (conexion, empresa, operacion y UUID).
                    uuid = (doc.filename or '').rsplit('.', 1)[0]
                    inv.message_post(body=Markup(_(
                        '<b>Factura creada automaticamente por FEL2ODOO</b><br/>'
                        'Conexion: %s<br/>Empresa: %s<br/>Operacion: %s<br/>'
                        'No. Autorizacion (UUID): %s<br/>'
                        'Emisor: %s (%s)<br/>Fecha DTE: %s<br/>'
                        'Total DTE: %s %s'
                    )) % (
                        self.name, company.display_name, op_label, uuid,
                        doc.nombre_emisor or '', doc.nit_emisor or '',
                        doc.fecha_emision or '', doc.moneda or '',
                        doc.gran_total or 0.0))
            except Exception as exc:  # noqa: BLE001
                _logger.error('FEL2Odoo: error creando factura %s: %s', doc.filename, exc)
                doc.write({'state': 'error', 'error_message': str(exc)})
        if invoices:
            session.state = 'done'
            if self.auto_classify_accounts:
                self._classify_accounts(invoices)
        return session, invoices

    def _attach_pdfs(self, session, import_type):
        """Descarga el PDF de cada documento importado y lo adjunta al chatter
        de su factura. El PDF se descarga con el UUID (numero de autorizacion
        real), que es el nombre del archivo XML (UUID.xml), no con el campo
        numero_autorizacion del documento (que guarda el correlativo).

        Distingue dos tipos de fallo:
        - La LLAMADA al proveedor falla (red, timeout, 500, cuota): ahi si se
          detiene el resto del lote, porque seguir solo gastaria llamadas.
        - El proveedor responde 200 pero no se pudo extraer un PDF valido: es
          un caso por documento (la SAT aun no genero la representacion, o vino
          en un formato inesperado); NO se detiene el lote, se sigue con los
          demas.

        Devuelve un texto de diagnostico con la primera respuesta cruda de
        descargar-pdf, para poder verla en el log de la sincronizacion."""
        self.ensure_one()
        pdf_sample = ''
        stop_batch = False
        stop_reason = ''
        for doc in session.document_ids.filtered(lambda d: d.state == 'imported' and d.invoice_id):
            if stop_batch:
                doc.invoice_id.message_post(body=_(
                    'PDF no descargado: se detuvieron los intentos en este lote '
                    '(%s).') % stop_reason)
                continue
            # El nombre del archivo descargado por la API es "<UUID>.xml".
            uuid = (doc.filename or '').rsplit('.', 1)[0]
            if not uuid:
                continue
            nit_receptor = doc.nit_receptor or (self.nit if import_type == 'purchase' else '') or 'CF'
            try:
                raw = self._descargar_pdf_raw(nit_receptor, uuid)
            except UserError as exc:
                _logger.warning('FEL2Odoo: fallo la llamada de PDF %s: %s', uuid, exc)
                doc.invoice_id.message_post(body=_(
                    'No se pudo obtener el PDF del DTE: la llamada al proveedor '
                    'fallo. Detalle: %s') % str(exc)[:300])
                stop_batch = True
                stop_reason = str(exc)[:150]
                continue
            pdf_bytes = self._coerce_pdf_bytes(raw)
            if not pdf_sample:
                pdf_sample = self._pdf_raw_diagnostic(uuid, raw, pdf_bytes)
            if not pdf_bytes:
                doc.invoice_id.message_post(body=_(
                    'El proveedor respondio pero no se pudo extraer un PDF valido '
                    'del DTE. Puede reintentar mas tarde desde la ficha de la '
                    'factura o el asistente de importacion.'))
                continue
            # message_post adjunta el PDF al chatter y lo enlaza a la factura.
            doc.invoice_id.message_post(
                body=_('PDF del DTE descargado por FEL2Odoo.'),
                attachments=[('%s.pdf' % uuid, pdf_bytes)])
        return pdf_sample

    def _confirm_invoices(self, invoices):
        """Publica las facturas creadas. Los errores no detienen la corrida."""
        confirmed = 0
        for inv in invoices:
            try:
                if inv.state == 'draft':
                    inv.action_post()
                    confirmed += 1
            except Exception as exc:  # noqa: BLE001
                _logger.warning('FEL2Odoo: no se pudo confirmar %s: %s', inv.name or inv.id, exc)
                inv.message_post(body=_('FEL2Odoo no pudo confirmar automaticamente: %s') % exc)
        return confirmed

    # ------------------------------------------------------------------
    # Clasificacion de cuentas contables
    # ------------------------------------------------------------------
    _EXPENSE_TYPES = ('expense', 'expense_depreciation', 'expense_direct_cost')
    _INCOME_TYPES = ('income', 'income_other')

    @staticmethod
    def _norm(text):
        """Minusculas y sin acentos, para comparar sin distinguir tildes."""
        if not text:
            return ''
        nfkd = unicodedata.normalize('NFKD', text)
        return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()

    def _classify_accounts(self, invoices):
        """Asigna la cuenta contable de cada linea segun reglas por descripcion
        y, en su defecto, segun el historial del proveedor. Solo en borrador."""
        self.ensure_one()
        # Cache de resolucion de cuentas por (company, tipo) para no repetir
        # busquedas al clasificar muchas lineas.
        acc_cache = {}
        for inv in invoices.filtered(lambda m: m.state == 'draft'):
            is_purchase = inv.move_type in ('in_invoice', 'in_refund')
            for line in inv.invoice_line_ids:
                if line.display_type:
                    continue
                acc = self._suggest_account(
                    line, inv.partner_id, is_purchase, inv.company_id, acc_cache)
                if acc and line.account_id != acc:
                    try:
                        line.account_id = acc
                    except Exception as exc:  # noqa: BLE001
                        _logger.warning('FEL2Odoo: no se pudo asignar cuenta: %s', exc)

    def _suggest_account(self, line, partner, is_purchase, company, acc_cache=None):
        """Devuelve la cuenta sugerida (regla por descripcion o historial)."""
        if acc_cache is None:
            acc_cache = {}
        desc = self._norm(line.name)
        op = 'purchase' if is_purchase else 'sale'
        Rule = self.env['ktx.fel2odoo.account.rule'].sudo()
        rules = Rule.search([
            ('company_id', 'in', (False, company.id)),
            ('operation', 'in', (op, 'both')),
        ], order='sequence, id')
        for r in rules:
            kw = self._norm(r.keyword).strip()
            if kw and kw in desc:
                acc = self._resolve_rule_account(r, is_purchase, company, acc_cache)
                if acc:
                    return acc
        return self._vendor_account(partner, is_purchase, company)

    def _resolve_rule_account(self, rule, is_purchase, company, acc_cache):
        """Resuelve la cuenta destino de una regla contra el plan de la empresa:
        1) cuenta concreta, 2) por codigo (exacto/prefijo), 3) por nombre (del
        tipo correcto). Devuelve un account.account o False."""
        # 1) Cuenta concreta.
        if rule.account_id and company.id in rule.account_id.company_ids.ids:
            return rule.account_id

        acc_types = self._EXPENSE_TYPES if is_purchase else self._INCOME_TYPES
        Account = self.env['account.account'].sudo()

        # 2) Por codigo (exacto y luego por prefijo).
        if rule.account_code:
            code = rule.account_code.strip()
            key = ('code', company.id, code)
            if key not in acc_cache:
                acc = Account.search([
                    ('company_ids', 'in', company.id),
                    ('code', '=', code),
                ], limit=1)
                if not acc:
                    acc = Account.search([
                        ('company_ids', 'in', company.id),
                        ('code', '=like', code + '%'),
                    ], order='code', limit=1)
                acc_cache[key] = acc
            if acc_cache[key]:
                return acc_cache[key]

        # 3) Por nombre, del tipo correcto (gasto/ingreso). Es lo mas portable.
        # Se comparan nombres normalizados (sin acentos) para funcionar en
        # cualquier plan de cuentas de Guatemala, con o sin tildes.
        if rule.account_name:
            hint = self._norm(rule.account_name).strip()
            pool_key = ('pool', company.id, acc_types)
            if pool_key not in acc_cache:
                acc_cache[pool_key] = Account.search([
                    ('company_ids', 'in', company.id),
                    ('account_type', 'in', acc_types),
                ])
            match_key = ('name', company.id, acc_types, hint)
            if match_key not in acc_cache:
                candidates = acc_cache[pool_key].filtered(
                    lambda a: hint in self._norm(a.name))
                # Preferir cuentas con codigo, luego el nombre mas corto (mas
                # generico) y por ultimo el codigo mas bajo: eleccion estable.
                acc_cache[match_key] = candidates.sorted(
                    key=lambda a: (not a.code, len(a.name or ''), a.code or '')
                )[:1]
            if acc_cache[match_key]:
                return acc_cache[match_key]
        return False

    def _vendor_account(self, partner, is_purchase, company):
        """Cuenta de gasto/ingreso mas usada historicamente con ese contacto."""
        if not partner:
            return False
        Line = self.env['account.move.line'].sudo()
        types = ('in_invoice', 'in_refund') if is_purchase else ('out_invoice', 'out_refund')
        acc_types = self._EXPENSE_TYPES if is_purchase else self._INCOME_TYPES
        lines = Line.search([
            ('partner_id', '=', partner.id),
            ('company_id', '=', company.id),
            ('parent_state', '=', 'posted'),
            ('display_type', '=', False),
            ('account_id.account_type', 'in', acc_types),
        ], limit=200, order='id desc')
        counts = {}
        for ln in lines:
            if ln.move_id.move_type in types:
                counts[ln.account_id.id] = counts.get(ln.account_id.id, 0) + 1
        if not counts:
            return False
        best_id = max(counts, key=counts.get)
        return self.env['account.account'].browse(best_id)

    def _ai_post_process(self, invoices, log):
        """Gancho opcional de clasificacion asistida por IA (modulo de IA aparte
        con su API key). Seguro: deja constancia y no bloquea el flujo."""
        self.ensure_one()
        log.message_post(body=_(
            'Clasificacion IA solicitada para %d facturas. Gancho de '
            'integracion disponible (_ai_post_process).') % len(invoices))
        return True

    # ==================================================================
    # Cron
    # ==================================================================
    _FREQ_HOURS = {'6h': 6, '12h': 12, 'daily': 24, 'weekly': 168, 'monthly': 720}

    def _is_due(self):
        """True si toca correr la sincronizacion automatica segun frecuencia."""
        self.ensure_one()
        if not self.last_auto_sync:
            return True
        hours = self._FREQ_HOURS.get(self.sync_frequency, 24)
        return fields.Datetime.now() - self.last_auto_sync >= timedelta(hours=hours)

    @api.model
    def _cron_sync_all(self):
        """Cron: sincroniza solo conexiones con automatico ACTIVADO, conexion
        probada, que ya toca por frecuencia y con cuota disponible."""
        configs = self.search([
            ('active', '=', True), ('auto_sync_enabled', '=', True),
            ('connection_ok', '=', True)])
        for config in configs:
            try:
                if not config._is_due():
                    continue
                if config._quota_left() <= 0:
                    _logger.info('FEL2Odoo: %s sin cuota; se omite.', config.name)
                    continue
                config.with_company(config.company_id)._sync()
                config.sudo().write({'last_auto_sync': fields.Datetime.now()})
            except Exception:  # noqa: BLE001
                _logger.exception('FEL2Odoo: fallo la sincronizacion de %s', config.name)
        return True

    # ==================================================================
    # Utilidades / acceso para agentes de IA
    # ==================================================================
    def action_view_logs(self):
        return self._action_related('ktx.fel2odoo.log', _('Bitacora FEL2Odoo'))

    def _action_related(self, model, name):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': [('config_id', '=', self.id)],
            'context': {'default_config_id': self.id},
        }

    def action_open_test_wizard(self):
        """Abre el asistente de carga masiva / prueba con XML manual."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar XML (masivo/manual)'),
            'res_model': 'ktx.fel2odoo.test.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_config_id': self.id,
                'default_import_type': 'purchase',
                'default_journal_id': self.journal_purchase_id.id,
            },
        }

    def _ai_guard(self):
        """Control de acceso para acciones de IA/externas: exige gestor contable
        y valida ACL/reglas de registro. Deja traza en el chatter."""
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_(
                'El control por IA/integracion requiere permisos de gestor '
                'contable (account.group_account_manager).'))
        self.check_access_rights('write')
        self.check_access_rule('write')

    def ai_enable_auto_sync(self):
        """Activa la sincronizacion automatica (respeta el candado de conexion)."""
        self._ai_guard()
        if not self.auto_sync_enabled:
            if not (self._ready_credentials() and self.connection_ok):
                raise UserError(_(
                    'No se puede activar: complete las credenciales y pulse '
                    '"Probar conexion" primero.'))
            self.write({'auto_sync_enabled': True})
            self.message_post(body=_('Automatico ACTIVADO por %s (IA/integracion).')
                              % self.env.user.name)
        return True

    def ai_disable_auto_sync(self):
        """Desactiva la sincronizacion automatica."""
        self._ai_guard()
        if self.auto_sync_enabled:
            self.write({'auto_sync_enabled': False})
            self.message_post(body=_('Automatico desactivado por %s (IA/integracion).')
                              % self.env.user.name)
        return True

    def ai_sync_now(self):
        """Ejecuta una sincronizacion bajo demanda (respeta cuota y candado)."""
        self._ai_guard()
        if not self.connection_ok:
            raise UserError(_('Pruebe la conexion antes de sincronizar.'))
        return self._sync()

    @api.model
    def ai_status(self, company_id=None):
        """Interfaz de solo lectura para agentes de IA / integraciones externas:
        indica si el flujo esta activo y su estado, sin exponer secretos.

        Devuelve un dict serializable. Respeta permisos: el llamante debe tener
        acceso de lectura al modelo (grupo contable)."""
        domain = [('active', '=', True)]
        if company_id:
            domain.append(('company_id', '=', company_id))
        out = []
        for cfg in self.search(domain):
            out.append({
                'id': cfg.id,
                'name': cfg.name,
                'company': cfg.company_id.display_name,
                'connection_ok': cfg.connection_ok,
                'auto_sync_enabled': cfg.auto_sync_enabled,
                'sync_frequency': cfg.sync_frequency,
                'last_auto_sync': fields.Datetime.to_string(cfg.last_auto_sync) or None,
                'calls_used': cfg.calls_used,
                'calls_left': cfg.calls_left,
                'monthly_call_limit': cfg.monthly_call_limit,
            })
        return out

    def _notify(self, title, message, ntype='success', sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': ntype,
                'sticky': sticky,
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
