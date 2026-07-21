# Cómo crear nuevas apariencias (formatos) para FEL2ODOO – Formato FEL GT

Guía para construir **módulos complementarios** de Odoo que agregan nuevas
apariencias de factura al módulo base `ktx_fel2odoo_format`. Cada apariencia
nueva vive en su propio módulo instalable (`ktx_fel2odoo_format_1`,
`ktx_fel2odoo_format_2`, …). El usuario las instala y aparecen automáticamente
como una opción más en **Contabilidad → Configuración → Formato FEL GT →
Formato/Apariencia**.

> Esta guía está pensada para dársela a Claude (o a cualquier desarrollador)
> junto con una imagen de la factura que quieres, y que genere el módulo listo
> para instalar.

---

## 1. Cómo funciona (arquitectura)

- **`ktx_fel2odoo_format` (base)** contiene toda la lógica: lee el XML del DTE
  FEL, arma los datos, genera el QR, resuelve qué reporte imprimir y lo adjunta
  al chatter. También trae la apariencia **KTX 1**.
- Un **módulo satélite** solo aporta 3 cosas:
  1. Una **opción nueva** en el campo de apariencia (`selection_add`).
  2. Los **reportes** (paperformat + `ir.actions.report`) para los 3 tamaños.
  3. Las **plantillas QWeb** con el diseño.
- El satélite **NO** reimplementa la lectura del XML, ni el QR, ni la
  configuración (logo, colores, imágenes, membrete): todo eso ya está en el
  base y se reutiliza.

El base encuentra el reporte del satélite **por convención de nombre**, sin
saber en qué módulo vive: busca el `ir.actions.report` cuyo **ID externo** sea
`action_report_<estilo>_<tamaño>`. Por eso basta con nombrar bien los registros.

- `<estilo>` = el código de tu apariencia, p. ej. `ktx2`.
- `<tamaño>` = uno de: `carta`, `media_carta`, `ticket`.

Ejemplo: para la apariencia `ktx2` en carta, el registro debe tener el ID
externo `action_report_ktx2_carta`.

---

## 2. Estructura de archivos de un módulo satélite

Ejemplo para `ktx_fel2odoo_format_1` (que aporta la apariencia **KTX 2**):

```
ktx_fel2odoo_format_1/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── res_company.py            # agrega 'ktx2' al selector de apariencia
├── report/
│   └── ktx2_report.xml           # paperformats + acciones + plantillas QWeb
└── static/
    └── description/
        ├── icon.png
        └── index.html            # página de presentación (App Store)
```

---

## 3. El manifest

`ktx_fel2odoo_format_1/__manifest__.py`

```python
# -*- coding: utf-8 -*-
{
    'name': 'FEL2ODOO - FORMATO FEL GT - Apariencia KTX 2',
    'summary': 'Apariencia adicional de factura para Formato FEL GT (KTX2)',
    'author': 'KTX APPS',
    'website': 'https://www.kontaxes.com',
    'category': 'Accounting/Localizations/Guatemala',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'countries': ['gt'],
    # CLAVE: depende del modulo base. Asi hereda toda la logica y los datos.
    'depends': ['ktx_fel2odoo_format'],
    'data': [
        'report/ktx2_report.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
```

---

## 4. Agregar la opción al selector de apariencia

El campo `ktx_fel_format_style` es un `Selection` en `res.company`. Para
**añadir** tu opción sin borrar las existentes se usa `selection_add` (patrón
estándar de Odoo). Basta con extender **`res.company`**: el campo de Ajustes
(`res.config.settings.ktx_fel_format_style`) es un campo `related` a ese, así
que hereda las opciones **automáticamente** (no lo extiendas también, o
crearías una clave duplicada).

`models/res_company.py`

```python
# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    ktx_fel_format_style = fields.Selection(
        selection_add=[('ktx2', 'KTX 2')],
        ondelete={'ktx2': 'set default'},
    )
```

`models/__init__.py`

```python
from . import res_company
```

`__init__.py` (raíz del módulo)

```python
from . import models
```

> El `ondelete={'ktx2': 'set default'}` evita errores si algún día se desinstala
> el satélite mientras alguna empresa tenía esa apariencia elegida: vuelve al
> valor por defecto (`ktx1`).

---

## 5. Los reportes y las plantillas QWeb

`report/ktx2_report.xml` define, para cada uno de los 3 tamaños:

1. Un `report.paperformat` (tamaño físico y márgenes).
2. Un `ir.actions.report` con el **ID externo** `action_report_ktx2_<tamaño>`.
3. La(s) plantilla(s) QWeb con el diseño.

Ejemplo mínimo (carta; repite el patrón para `media_carta` y `ticket`):

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>

    <!-- 1) Tamaño de papel: Carta con margenes en 0 (la marca de agua debe
         llegar al borde; el margen de lectura se pone con padding CSS). -->
    <record id="paperformat_ktx2_carta" model="report.paperformat">
        <field name="name">KTX2 - Carta</field>
        <field name="format">custom</field>
        <field name="page_height">279</field>
        <field name="page_width">216</field>
        <field name="orientation">Portrait</field>
        <field name="margin_top">0</field>
        <field name="margin_bottom">0</field>
        <field name="margin_left">0</field>
        <field name="margin_right">0</field>
        <field name="header_line" eval="False"/>
        <field name="header_spacing">0</field>
    </record>

    <!-- 2) Accion de reporte. El id DEBE ser action_report_ktx2_carta. -->
    <record id="action_report_ktx2_carta" model="ir.actions.report">
        <field name="name">Formato FEL GT (KTX2) - Carta</field>
        <field name="model">account.move</field>
        <field name="report_type">qweb-pdf</field>
        <field name="report_name">ktx_fel2odoo_format_1.report_ktx2_page</field>
        <field name="report_file">ktx_fel2odoo_format_1.report_ktx2_page</field>
        <field name="print_report_name">'FEL_Formato_%s' % (object.name or object.id)</field>
        <field name="paperformat_id" ref="paperformat_ktx2_carta"/>
    </record>

    <!-- (media_carta y ticket: otro paperformat + otra accion
         action_report_ktx2_media_carta / action_report_ktx2_ticket, que pueden
         apuntar a la MISMA plantilla report_ktx2_page o a una distinta) -->

    <!-- 3) La plantilla QWeb con el diseño. -->
    <template id="report_ktx2_page">
        <t t-call="web.html_container">
            <t t-foreach="docs" t-as="o">
                <!-- Trae TODOS los datos ya listos desde el modulo base -->
                <t t-set="dte" t-value="o._ktx_fel_get_format_data()"/>
                <t t-set="cfg" t-value="o._ktx_fel_format_company_data()"/>
                <t t-set="qr_src" t-value="o._ktx_fel_format_qr_img_src(dte['qr_url'])"/>
                <t t-set="accent" t-value="cfg['accent_color'] or '#e97132'"/>
                <t t-set="accent_text" t-value="cfg['accent_text'] or '#ffffff'"/>

                <div style="font-family: Arial, sans-serif; padding: 8mm; color:#222;">
                    <!-- ... AQUI VA TU DISEÑO usando dte, cfg, qr_src ... -->
                    <h1 t-attf-style="color:#{accent};">
                        <t t-esc="dte['emisor']['nombre_comercial'] or dte['emisor']['nombre']"/>
                    </h1>
                    <div>NIT: <t t-esc="dte['emisor']['nit']"/></div>
                    <div>Total: <t t-esc="dte['moneda']"/> <t t-esc="'%.2f' % dte['gran_total']"/></div>
                    <img t-if="qr_src" t-att-src="qr_src" style="width:32mm; height:32mm;"/>
                </div>
            </t>
        </t>
    </template>

</odoo>
```

> Puedes usar UNA sola plantilla para los 3 tamaños (como hace KTX1 con
> `report_ktx1_page`) y ajustar detalles con `cfg['paper_size']`, o hacer
> plantillas separadas. Para el **ticket** casi siempre conviene una plantilla
> aparte (una sola columna, monoespaciada), porque el ancho es de 72 mm.

---

## 6. Contrato de datos disponible en la plantilla

Estos son los **únicos** métodos que necesitas llamar desde el QWeb. Devuelven
diccionarios ya armados a partir del XML del DTE y de la configuración.

### `o._ktx_fel_get_format_data()` → `dte`

| Clave | Tipo | Contenido |
|---|---|---|
| `tipo_documento` | str | Código SAT: `FACT`, `FPEQ`, `NCRE`… |
| `tipo_documento_label` | str | Nombre legible: `FACTURA`, `NOTA DE CREDITO`… |
| `moneda` | str | `GTQ`, `USD`… |
| `fecha_emision` | str | Fecha/hora de emisión del DTE |
| `iva_monto` | float | Total de IVA (suma de impuestos "IVA") |
| `total_en_letras` | str | `SEISCIENTOS CINCUENTA QUETZALES CON 00/100` |
| `gran_total` | float | Gran total |
| `afiliacion_iva` | str | `GEN`, `PEQ`… |
| `qr_url` | str | URL del verificador SAT (para el QR) |
| `emisor` | dict | `nit, nombre, nombre_comercial, correo, direccion, municipio, departamento, pais` |
| `receptor` | dict | `id, nombre, correo, direccion, municipio, departamento` |
| `items` | list | cada uno: `numero_linea, bien_servicio, cantidad, unidad_medida, descripcion, precio_unitario, precio, descuento, total, impuestos[]` |
| `total_impuestos` | list | cada uno: `nombre_corto, monto` |
| `frases` | list | cada una: `tipo, escenario, texto` (texto oficial de la frase SAT, o `None`) |
| `certificacion` | dict | `uuid, serie, numero, fecha, nit_certificador, nombre_certificador` |

### `o._ktx_fel_format_company_data()` → `cfg`

| Clave | Tipo | Contenido |
|---|---|---|
| `logo` | binary | Logo efectivo (el de la empresa o el subido en la config) |
| `logo_position` | str | `left` / `right` |
| `accent_color` | str | Color de acento en hex (elegido en la config) |
| `accent_text` | str | `#ffffff` o `#000000` — el color de texto legible SOBRE el acento (ya calculado por contraste) |
| `paper_size` | str | `carta` / `media_carta` / `ticket` |
| `style` | str | El estilo activo (`ktx1`, `ktx2`…) |
| `side_image` | binary | Imagen lateral opcional (o falsy) |
| `background_image` | binary | Marca de agua opcional (o falsy) |
| `show_footer` | bool | Si mostrar membrete/pie |
| `footer_description` | str | Texto libre del pie |
| `social_website / social_phone / social_email / social_facebook / social_instagram / social_x` | str | Datos de contacto/redes |

### `o._ktx_fel_format_qr_img_src(dte['qr_url'])` → str

Devuelve un `data:image/png;base64,...` con el **QR ya generado**. Úsalo directo
en `<img t-att-src="qr_src"/>`. No generes el QR por tu cuenta.

### Imágenes (logo / lateral / fondo)

Para pintar un binary usa el helper nativo de Odoo `image_data_uri(...)`:

```xml
<img t-if="cfg['logo']" t-att-src="image_data_uri(cfg['logo'])"
     style="max-width:40mm; max-height:40mm;"/>
```

---

## 7. Reglas de oro para que el PDF salga bien (wkhtmltopdf)

El motor de PDF es antiguo (WebKit). Estas reglas ya están probadas en KTX1 y
te ahorran horas:

1. **Esquinas redondeadas:** `border-radius` NO funciona en `<table>` con
   `border-collapse: collapse`. Envuelve la tabla en un `<div>` con
   `border-radius` + `overflow: hidden` y quítale el borde a la tabla interna.
2. **Color de texto en tablas:** el `color` NO se hereda de forma fiable de un
   `<div>` hacia las celdas de una `<table>` interna. Pon `color:` **en el
   `<tr>` o en cada `<td>`**, no solo en un contenedor externo.
3. **Marca de agua a página completa:** no le pongas ancho/alto en `mm` fijos
   (queda más chica que la hoja). Usa un contenedor `position: relative` con
   `min-height: 277mm` (carta) y dentro un `position: absolute; top:0; right:0;
   bottom:0; left:0;` con la imagen como `background`, y `opacity` baja.
4. **Tipografía uniforme:** para forzar el MISMO tipo y tamaño en todo, usa un
   `<style>` con `.tuclase, .tuclase * { font-family:...; font-size:...; }`
   (con `!important` si hace falta).
5. **QR / imágenes:** siempre embebidas en base64 (los helpers ya lo hacen). No
   uses URLs `/report/barcode` ni imágenes remotas: fallan en el render.
6. **Márgenes:** el paperformat va en 0 y el "margen de lectura" se hace con
   `padding` CSS, para que fondos/marcas de agua lleguen al borde real.

---

## 8. Cómo diseñarlo con Claude

Prompt sugerido (adjunta una imagen de la factura que quieres):

> "Crea un módulo Odoo 19 `ktx_fel2odoo_format_2` que agregue la apariencia
> **KTX 3** a `ktx_fel2odoo_format`. Sigue la guía `COMO_CREAR_APARIENCIAS.md`
> (selection_add en res.company y res.config.settings, reportes con id externo
> `action_report_ktx3_carta` / `_media_carta` / `_ticket`, y plantillas QWeb).
> El diseño debe verse como la imagen adjunta. Usa SOLO los datos del contrato
> (`dte`, `cfg`, `qr_src`) y respeta las reglas de wkhtmltopdf de la guía.
> Usa el color de acento `cfg['accent_color']` y el texto `cfg['accent_text']`
> para que sea configurable. Entrégalo listo para instalar."

Claude te devolverá el árbol de archivos completo. Revisa que:
- Los IDs externos de los reportes sean exactamente `action_report_<estilo>_<tamaño>`.
- El `selection_add` esté en los dos modelos.
- El manifest dependa de `ktx_fel2odoo_format`.

---

## 9. Cómo hacerlo instalable

### Opción A — En tu repositorio / Odoo.sh
1. Coloca la carpeta `ktx_fel2odoo_format_1/` junto a los demás módulos del repo.
2. Haz commit y push. Odoo.sh reconstruye.
3. En Odoo: **Aplicaciones → Actualizar lista de aplicaciones**, busca la
   apariencia e **Instálala**.

### Opción B — Instalación manual (ZIP)
1. Comprime la carpeta del módulo en un `.zip`.
2. Colócala en una ruta de `addons_path` del servidor (o súbela por
   Aplicaciones → Importar módulo, si está habilitado).
3. **Actualizar lista de aplicaciones** → buscar → **Instalar**.

### Opción C — Publicar en el Odoo App Store
1. Asegúrate de tener `static/description/icon.png` e `index.html`.
2. Sube el módulo en https://apps.odoo.com como complemento (depende de
   `ktx_fel2odoo_format`).

Tras instalar: **Contabilidad → Configuración → Formato FEL GT → Formato/Apariencia**
ahora muestra la nueva opción. Selecciónala y usa el botón **Imprimir FEL** en
la factura.

---

## 10. Checklist antes de publicar

- [ ] `depends` incluye `ktx_fel2odoo_format`.
- [ ] `selection_add` en **res.company** (Ajustes lo hereda solo; NO lo dupliques).
- [ ] `ondelete` definido para tu código de estilo.
- [ ] Reportes con id externo `action_report_<estilo>_carta`, `_media_carta`, `_ticket`.
- [ ] Cada `ir.actions.report` tiene su `paperformat_id`.
- [ ] La plantilla usa solo `dte`, `cfg`, `qr_src` (no reimplementa lógica).
- [ ] El QR se pinta con `_ktx_fel_format_qr_img_src` (base64), no con URL.
- [ ] El XML valida (`python3 -c "import xml.etree.ElementTree as ET; ET.parse('report/....xml')"`).
- [ ] El Python compila (`python3 -m py_compile models/*.py`).
- [ ] Probado en los 3 tamaños con una factura real.

---

Propiedad de **KTX APPS** — NIT 93823509.
