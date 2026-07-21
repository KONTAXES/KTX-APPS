# -*- coding: utf-8 -*-
{
    'name': 'FEL2ODOO - FORMATO FEL GT',
    'summary': 'Da formato grafico (con QR) a la factura electronica FEL de la SAT Guatemala, '
               'a partir del XML del DTE, listo para imprimir/descargar y adjuntar al chatter',
    'description': '''
FEL2ODOO - FORMATO FEL GT
=========================

Convierte el XML del DTE (Documento Tributario Electronico) certificado por
la SAT de Guatemala en un **PDF con formato de factura**, listo para
imprimir, descargar o enviar al cliente -- igual que un comprobante
"bonito" de los que generan portales como feltoprint, pero directamente
dentro de Odoo, sin subir el archivo a ningun sitio externo.

Funciona con el XML que ya haya quedado adjunto a la factura, sin importar
si se importo con **Importacion Masiva XML-SAT** (ktx_mass_import) o se
sincronizo/emitio con **FEL2Odoo** (ktx_fel2odoo): este modulo es
independiente y solo necesita encontrar el adjunto XML del DTE en la
factura.

Que hace
--------
- Boton **"Imprimir FEL"** en la factura de venta, junto al
  boton nativo de Imprimir. Solo aparece si esta **activado** en
  Contabilidad > Configuracion y si la factura tiene un XML FEL adjunto.
- Genera un PDF con el formato tipico de una factura FEL guatemalteca:
  datos del emisor y receptor, caja DTE con serie/numero/fecha, detalle de
  items, frase de la SAT, IVA, total en letras, numero de autorizacion
  (UUID), datos del certificador, y **codigo QR** que enlaza al
  verificador oficial de la SAT (felpub.c.sat.gob.gt), igual que en el
  documento original.
- **Formato configurable** desde Contabilidad > Configuracion: apariencia
  (**KTX1**, con mas opciones -KTX2, KTX3...- en camino), **3 tamanos de
  papel** (Carta, Media Carta, Ticket de impresora termica 72mm), color de
  acento, logo grande (el de la empresa u otro subido aqui) a la izquierda
  o derecha, imagen lateral opcional (si no se sube, no se reserva
  espacio), imagen de fondo opcional a modo de marca de agua que llega
  hasta el borde de la pagina, y membrete/pie de pagina opcional con
  descripcion adicional y datos de redes sociales.
- **Frase de la SAT con su texto real**, no solo el codigo: catalogo
  completo de Tipo/Escenario de frases FEL (el mismo catalogo que usa
  Importacion Masiva XML-SAT).
- El **codigo QR se genera directamente** con el motor nativo de codigo
  de barras de Odoo (sin depender de una peticion HTTP adicional durante
  la generacion del PDF), evitando que quede en blanco.
- Cada vez que se genera, el PDF tambien se adjunta de forma visible y
  descargable en el **chatter** de la factura.
- Desactivado por defecto: no aparece nada hasta que se activa la opcion.

----
Propiedad de **KTX APPS** — NIT 93823509.
Contenido generado con ayuda de IA, con estricta planificacion y gestion de KTX.
    ''',
    'author': 'KTX APPS',
    'website': "https://www.kontaxes.com",
    'category': 'Accounting/Localizations/Guatemala',
    'version': '19.0.1.19.0',
    'license': 'OPL-1',
    'countries': ['gt'],
    # LANZAMIENTO 2026: GRATIS (50% OFF sobre el precio normal de 40 USD).
    # Al terminar el lanzamiento, subir 'price' a 40.00.
    'price': 0.0,
    'currency': 'USD',
    'depends': [
        'base',
        'account',
        'mail',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/account_move_views.xml',
        'report/ktx_fel2odoo_format_report.xml',
    ],
    'images': [
        'static/description/banner.png',
    ],
    'web_icon': 'ktx_fel2odoo_format,static/description/icon.png',
    'installable': True,
    'application': False,
    'auto_install': False,
}
