# ktx_fel2odoo

Sincronización automática de Documentos Tributarios Electrónicos (DTE) de la
SAT Guatemala hacia Odoo 19, a través del proveedor intermediario
**API FEL Core** (`https://apifelcore.com/api`).

> Nota: versiones previas incluían backends de "SAT directo" (scraping) y de la
> "API Pública oficial de la SAT" (aún en propuesta). Se retiraron por no ser
> viables/estables; el módulo se enfoca en el intermediario API FEL Core.

## Qué hace

1. **Autenticación (2 tokens)**
   - *Token de plataforma*: se obtiene con `POST /login` (email + password) y se
     envía como cabecera `Authorization: Bearer`. Se cachea y renueva solo.
   - *Token de Agencia Virtual* (`token_fel`): credencial SAT/FEL cifrada del
     cliente; viaja en el cuerpo (`body`) de cada petición de negocio.

2. **Consulta periódica** (acción planificada / cron, cada 6 h por defecto):
   - `POST /agencia-virtual/consultar-documentos` para `EMITIDOS` (ventas) y
     `RECIBIDOS` (compras), por rango de fechas.
   - `POST /agencia-virtual/descargar-xml` de cada documento nuevo.

3. **Creación de facturas**: reutiliza toda la lógica del módulo
   `ktx_mass_import` (parseo FEL, mapeo de impuestos por línea, frases SAT,
   retenciones ISR/IVA, descuentos y creación de contactos), creando una sesión
   de importación por corrida. Las facturas quedan en borrador **listas para
   confirmar**, o se confirman automáticamente si activa la opción.

4. **Anti-duplicados**: no reimporta documentos cuyo número de autorización ya
   exista como `ref` en `account.move`.

5. **Bitácora**: cada corrida registra documentos encontrados, omitidos,
   facturas creadas/confirmadas y el detalle de errores.

## Dependencias

- `ktx_mass_import` (lógica de creación de facturas desde XML FEL).
- `account`, `mail`, `base`.
- Python: `requests` (incluido en Odoo).

## Configuración

1. Contabilidad → **FEL SAT Automático → Conexiones FEL** → crear una conexión.
2. Pestaña *Conexión*: URL base, email/password de plataforma, NIT y `token_fel`.
   Pulse **Probar conexión**.
3. Pestaña *Sincronización*: active ventas y/o compras y elija los diarios.
4. Pestaña *Programación e IA*: fecha inicial / días hacia atrás, confirmación
   automática y clasificación IA opcional.
5. **Sincronizar ahora** para una corrida manual, o deje que el cron
   *"FEL2Odoo: Sincronizar DTE desde la SAT"* lo haga solo.

## Notas de integración

- Las formas exactas de respuesta del proveedor (nombres de campos y del XML)
  se leen de forma **defensiva** (varias claves candidatas y XML directo o
  base64). Revise la Bitácora ante cualquier discrepancia y ajuste si el
  proveedor formaliza su contrato.
- `_ai_post_process` es un **gancho** para clasificación asistida por IA
  (`ktx_claude_ai` / MCP). Por defecto solo deja constancia; extiéndalo para
  automatizar aún más la clasificación antes de publicar.
