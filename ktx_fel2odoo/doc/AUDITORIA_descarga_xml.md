# Auditoría — Descarga de XML (compras y ventas) · ktx_fel2odoo

**Objetivo:** determinar si la imposibilidad de obtener los XML de la SAT es
del código/desarrollo en Odoo o del proveedor (apifelcore), **antes** de
escalar el caso.

**Fecha:** 2026-07-12 · **NIT auditado:** 93823509

---

## 1. Método

Se reprodujo, de forma aislada y con la **respuesta real** de
`consultar-documentos` del contribuyente, la lógica **verbatim** del módulo
para construir la petición `descargar-xml`, y se verificó el manejo de la
respuesta en todos sus formatos posibles.

## 2. Lado emisor (petición que Odoo envía)

El módulo envía, por cada DTE:

```
POST https://apifelcore.com/api/agencia-virtual/descargar-xml
Content-Type: application/json
Authorization: Bearer <token_plataforma>

{
  "nit": "93823509",
  "token_fel": "<token_fel>",
  "nit_receptor": "93823509",
  "numero_autorizacion": "1C108849-DA3F-4B59-BE34-1ED2E1CC5F11",
  "numeroAutorizacion": "1C108849-...",
  "no_autorizacion":   "1C108849-...",
  "noAutorizacion":    "1C108849-...",
  "autorizacion":      "1C108849-...",
  "uuid":              "1C108849-..."
}
```

Verificaciones (todas **OK** en los 3 DTE de muestra, FACT y FCAM):

- El número de autorización se **extrae correctamente** de la respuesta de
  consulta (clave `numero_autorizacion`).
- Va en el cuerpo bajo `numero_autorizacion` **y además** bajo el nombre exacto
  `noAutorizacion` (el que el proveedor usa hacia la SAT) y 4 alias más.
- `nit`, `token_fel`, `nit_receptor` presentes y correctos.
- Endpoint, método (POST), `Content-Type` y `Authorization` correctos.
- Coincide con el contrato documentado del proveedor (OpenAPI / Integration
  Guide: `POST /agencia-virtual/descargar-xml` con cuerpo JSON).

**Conclusión emisor:** la petición del módulo es correcta y completa.

## 3. Lado receptor (procesamiento del XML)

`_coerce_xml_bytes` se probó con las 7 formas posibles de respuesta (XML crudo,
base64, y envuelto en `xml`/`data`/`archivo`, etc.). **En todas** obtiene el XML
listo para crear la factura. El mismo XML alimenta la lógica probada de
`ktx_mass_import` (impuestos, frases, retenciones).

**Conclusión receptor:** si el proveedor devolviera el XML, el módulo lo
procesa y crea la factura sin problema.

## 4. Evidencia decisiva (log del proveedor)

Cuando apifelcore llama a la SAT en nombre del contribuyente:

```
POST https://felcons.c.sat.gob.gt/dte-agencia-virtual/api/consulta-dte/xml
     ?usuario=93823509&tipoOperacion=&...&noAutorizacion=&...
→ 401 Unauthorized / 403 Forbidden
(AgenciaVirtualController.php línea 725)
```

Dato clave: **`usuario=93823509` viene lleno**, pero **`noAutorizacion=` viene
vacío**. Es decir, el handler de apifelcore **sí lee** el campo `nit` de mi
cuerpo (lo pone como `usuario`), pero **no traslada** el número de autorización
—aunque lo envío bajo `numero_autorizacion`, `noAutorizacion` y 4 alias más—.

## 5. Veredicto

- ✅ `consultar-documentos`: funciona (localiza los DTE de compras y ventas).
- ✅ Petición `descargar-xml` del módulo: **correcta y completa**.
- ✅ Procesamiento del XML en Odoo: **correcto**.
- ❌ `descargar-xml` de apifelcore: **no reenvía el número de autorización a la
  SAT** (lo envía vacío), por lo que la SAT responde 401/403.

**No es el código ni el desarrollo en Odoo.** El fallo está en el endpoint
`descargar-xml` del proveedor (apifelcore), que pierde el número de
autorización al llamar a la SAT. Procede escalar a apifelcore con esta
evidencia.
