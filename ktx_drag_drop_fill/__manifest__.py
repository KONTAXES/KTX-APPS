# -*- coding: utf-8 -*-
{
    "name": "Odoo como Excel - Drag & Drop",
    "version": "19.0.1.2.1",
    "category": "Productivity",
    "summary": "Selecciona, arrastra, rellena y copia celdas como en Excel, en cualquier lista editable de Odoo",
    "description": """
Odoo como Excel - Drag & Drop (KONTAXES)
========================================
Agrega seleccion de celdas y un "controlador de relleno" (fill handle) al
estilo Excel a las vistas de lista editables, a las lineas one2many y a la
lista de Facturas/Cuentas por pagar/Notas de credito.

Lanzamiento: GRATIS. Durante 2026, 50% de descuento. Precio normal: 110 USD.

Configuracion
-------------
- Ninguna para listas y one2many normales: al instalar el modulo,
  cualquier vista que ya sea editable (``editable="top"`` o
  ``editable="bottom"``) queda disponible.
- Para la lista de Facturas (``account.move``), este modulo agrega
  ``editable="bottom"`` a la vista estandar (``account.view_invoice_tree``),
  ya que esa lista no es editable en linea por defecto en Odoo. Los campos
  ya protegidos por estado en la vista original (por ejemplo
  ``readonly="state != 'draft'"``) siguen protegidos: solo los borradores
  quedan editables ahi. Este cambio aplica siempre (no solo con el modo
  Excel activo) para Facturas de cliente, de proveedor y notas de credito,
  ya que comparten la misma vista.
- Todo lo demás (arrastrar, seleccionar, copiar) se activa/desactiva
  unicamente con el icono de la bandeja del sistema.

Uso
---
1. En listas normales, el modo de activacion es configurable:
   - "Clic sostenido" (por defecto): un clic rapido se comporta como Odoo
     nativo; manten presionado (o arrastra) para iniciar la seleccion.
   - "Un clic": selecciona con un solo clic.
   En las lineas one2many dentro de un formulario (por ejemplo las lineas
   de una factura o pedido) basta un clic: la celda se edita como siempre
   y ademas se marca la seleccion con su controlador.
2. Ctrl+clic agrega celdas o rangos sueltos (no contiguos) a la seleccion;
   Shift+clic extiende el rectangulo activo desde el ancla - igual que en
   una hoja de calculo. Las celdas de solo lectura tambien se pueden
   seleccionar (para copiarlas), aunque no se puedan escribir.
3. Arrastra el controlador en cualquiera de las 4 direcciones para copiar
   el valor (o continuar una serie numerica si la seleccion ya tiene 2+
   valores que forman una progresion) en las celdas sobre las que pases.
4. Doble clic sobre el controlador rellena (o continua la serie) hacia
   abajo hasta la ultima fila visible.
5. Con una seleccion activa, Ctrl+C (o Cmd+C) copia las celdas al
   portapapeles (separadas por tabulador/salto de linea, como Excel) y
   muestra la animacion de "hormigas marchantes".
6. Escape o hacer clic fuera limpia la seleccion. Si hay registros
   marcados con las casillas de la izquierda, los clics vuelven a
   funcionar como seleccion de filas nativa de Odoo.
7. Los cambios quedan en modo edicion normal de Odoo (con onchange
   incluido), listos para guardar o descartar como cualquier edicion.

En la lista de Facturas (documentos): un clic abre la factura, un doble
clic sobre un borrador la deja seleccionada y editable en linea (nunca
navega fuera de un borrador), y solo se escriben cambios en borradores.
Algunas columnas de esa lista (producto, impuesto, monto, cuenta) son de
solo lectura porque provienen de las lineas internas de cada factura y no
se pueden editar desde el listado; aun asi se pueden seleccionar y copiar.

Interruptor rapido y apariencia
--------------------------------
- Un icono en la bandeja del sistema (arriba a la derecha) permite
  activar o desactivar la funcionalidad al instante, sin recargar la
  pagina. El icono se mantiene monocromatico (igual que el resto de
  iconos de la barra, tanto en modo claro como oscuro) y cambia al
  color del modulo cuando esta activo.
- La flecha junto al icono abre un panel para configurar el color, el
  grosor del marco/controlador, la forma del cursor mientras se
  selecciona, y el modo de activacion (un clic / clic sostenido).
- Cuando esta activo, el icono muestra sus celdas rellenas con el color
  configurado; cuando esta inactivo, las celdas quedan vacias.
- Cuando esta desactivado, las listas (fuera de Facturas) se comportan
  exactamente igual que el Odoo estandar.

Botones de copiar al pasar el mouse
-----------------------------------
Incluye los botones de copiar rapido (antes en un modulo aparte de
portapapeles, ya no necesario):
- Con el modo Excel APAGADO: al pasar el mouse sobre una celda con datos
  se retroilumina la celda (y suavemente su fila y columna, adaptado a
  tema claro/oscuro) y aparecen los botones de copiar CELDA y FILA; en el
  encabezado aparece el de copiar COLUMNA. Los botones no aparecen sobre
  celdas con botones o casillas, para no estorbarlas.
- Con el modo Excel ENCENDIDO: la copia de celda/fila se hace con la
  seleccion (clic sostenido + Ctrl+C), asi que solo queda el boton de
  copiar COLUMNA en el encabezado.
- En los formularios, al pasar el mouse sobre un campo con datos aparece
  un boton para copiar ese campo.

Notas
-----
- Tambien funciona en listas agrupadas: la fila se ubica en el registro
  correcto recorriendo los grupos expandidos; si por algun motivo el
  conteo no cuadra, la interaccion se cancela sin escribir nada (nunca
  "adivina" un registro).
- El relleno horizontal escribe el mismo valor/serie en columnas
  distintas; si el campo destino no es compatible (tipo distinto o de
  solo lectura), esa celda simplemente se omite.
- No incluye formulas: no es un motor de hoja de calculo, solo copia o
  continua progresiones numericas simples.
    """,
    "author": "KONTAXES",
    "website": "https://www.kontaxes.com",
    "support": "soporte@kontaxes.com",
    "license": "OPL-1",
    "price": 0.0,
    "currency": "USD",
    "depends": ["web", "account"],
    "data": [
        "views/account_move_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ktx_drag_drop_fill/static/src/js/ktx_drag_drop_fill_state.js",
            "ktx_drag_drop_fill/static/src/js/ktx_drag_drop_fill_util.js",
            "ktx_drag_drop_fill/static/src/js/ktx_drag_drop_fill_overlay.js",
            "ktx_drag_drop_fill/static/src/js/ktx_drag_drop_fill_list.js",
            "ktx_drag_drop_fill/static/src/js/ktx_drag_drop_fill_copy.js",
            "ktx_drag_drop_fill/static/src/js/ktx_drag_drop_fill_systray.js",
            "ktx_drag_drop_fill/static/src/xml/ktx_drag_drop_fill_systray.xml",
            "ktx_drag_drop_fill/static/src/css/ktx_drag_drop_fill.css",
        ],
    },
    "images": ["static/description/icon.png"],
    "web_icon": "ktx_drag_drop_fill,static/description/icon.png",
    "installable": True,
    "application": False,
    "auto_install": False,
}
