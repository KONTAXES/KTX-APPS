# Claude AI para Odoo (`ktx_claude_ai`)

Conecta Odoo **directamente** con Claude (Anthropic) — sin aplicaciones de
terceros, sin Claude de escritorio y sin instalación en terminal. Pegas tu API
key de Anthropic en Ajustes y conversas con Claude dentro de Odoo, igual que los
conectores de ChatGPT o Gemini. Claude puede **crear, modificar, eliminar,
restablecer a borrador y cambiar de estado** tus registros —individual o
masivamente— según lo que escribas, respetando los permisos del usuario.

## Estado del desarrollo

Este módulo se construye **por fases** (acordado con el cliente):

- **Fase 1 — Chat de Claude dentro de Odoo (este módulo).** Completo:
  ajustes con API key, panel de chat OWL, bucle agéntico con *tool use*,
  permisos por modelo/operación, confirmación de operaciones destructivas y
  masivas, y bitácora de auditoría.
- **Fase 2 — Conector remoto (MCP + OAuth 2.1).** Implementado: expone esta
  misma Odoo como “conector personalizado” en Claude.ai web y la app de
  escritorio, reutilizando el mismo núcleo de herramientas y permisos
  (`claude.tool.dispatcher`). No requiere instalación local. Ver “Conector
  remoto” más abajo.

> **Nota honesta sobre “sincronización”:** Anthropic **no** ofrece una API para
> leer el historial de conversaciones de Claude.ai o de la app de escritorio,
> por lo que el *texto* de esas conversaciones no puede importarse a Odoo. Lo
> que sí queda unificado es la **base de datos** (todo opera sobre la misma
> Odoo) y el **historial de acciones** (bitácora). Cuando exista la Fase 2, las
> acciones hechas desde el conector también se registrarán aquí.

## Requisitos

- Odoo 19.0 (Community o Enterprise).
- **Sin dependencias externas de Python:** usa `requests` (incluido en Odoo),
  por lo que instala sin complicaciones en Odoo Online, Odoo.sh y on-premise —
  no requiere `pip install`.
- Una API key de Anthropic (de `console.anthropic.com`).

## Precio

Periodo de lanzamiento: **GRATIS hasta nuevo aviso**. Valor real del módulo:
**$200 USD**; en 2026 quedará con **50% de descuento**.

## Instalación y configuración

1. Instala el módulo **Claude AI para Odoo**.
2. Ve a **Ajustes → Claude AI**:
   - Marca **Activar Claude AI**.
   - Pega tu **API Key de Anthropic** (de `console.anthropic.com`).
   - Elige el **modelo** (por defecto Claude Opus 4.8).
3. En **Claude AI → Configuración → Modelos habilitados**, habilita los modelos
   y operaciones que Claude podrá usar. Por seguridad, de fábrica solo viene
   `res.partner` en modo lectura; todo lo demás debes habilitarlo
   explícitamente. Puedes usar el botón **Habilitar modelos** para añadir varios
   de una vez.
4. Abre **Claude AI → Chat** y conversa.

## Seguridad

- **Interruptor global** y **control por modelo y operación**
  (lectura / creación / escritura / eliminación / acciones de estado).
- Las herramientas se ejecutan con **los permisos del usuario de Odoo**
  (reglas de acceso y reglas de registro vigentes); no se usa `sudo` general
  para manipular datos.
- Las **operaciones destructivas** (`unlink`) y las **masivas** (por encima del
  umbral configurable) requieren confirmación: la herramienta devuelve
  `confirmation_required`, Claude avisa al usuario, y solo procede cuando este
  aprueba (la herramienta se vuelve a llamar con `confirm=true`).
- Las **acciones de estado** se limitan a una lista permitida por modelo
  (`action_post`, `button_draft`, `button_cancel`, …).
- Cada herramienta ejecutada queda en la **bitácora** (`Claude AI →
  Configuración → Bitácora`).

## Herramientas disponibles para Claude

`list_models`, `odoo_fields_get`, `odoo_name_search`, `odoo_search`,
`odoo_read`, `odoo_create`, `odoo_write`, `odoo_unlink`, `odoo_action`.

## Conector remoto (Claude.ai web / escritorio)

Permite usar Claude.ai (o la app de escritorio) y que Claude opere sobre **esta
misma Odoo**, sin instalar nada local. Reutiliza el mismo dispatcher y permisos
que el chat; las acciones quedan en la bitácora con `source=connector`.

**Requisito de infraestructura:** Odoo debe ser accesible por **HTTPS público**
(los servidores de Anthropic llaman al endpoint). Configura `web.base.url` o el
campo **URL pública** en Ajustes → Claude AI → Conector remoto.

**Puesta en marcha:**
1. Ajustes → Claude AI → Conector remoto → **Activar conector remoto** y fija la
   URL pública. Copia la **URL del conector**: `https://TU-ODOO/claude/mcp`.
2. En **Claude.ai → Settings → Connectors → Add custom connector** pega esa URL.
   Claude registra el cliente (OAuth 2.1 DCR), te redirige a Odoo para **iniciar
   sesión y autorizar**, y queda conectado.
3. Para **Claude Desktop o la API** (`mcp_servers`) sin OAuth: genera un **token
   estático** en Conector remoto → Tokens del conector y úsalo como Bearer.

**Endpoints expuestos:** `/claude/mcp` (MCP Streamable-HTTP, JSON-RPC 2.0) y el
proveedor OAuth 2.1 (`/.well-known/oauth-protected-resource`,
`/.well-known/oauth-authorization-server`, `/claude/oauth/register|authorize|token`).
Autenticación por OAuth 2.1 con PKCE o por token estático; rate-limit por token.

## Arquitectura

```
Fase 1 (chat):    claude.conversation.send_message() → claude.api (/v1/messages)
Fase 2 (conector): controllers/mcp.py  (/claude/mcp, OAuth 2.1)
        │                         │
        └────────────┬────────────┘
                     ▼
        claude.tool.dispatcher.execute_tool()   → NÚCLEO compartido
                     │  controla con
                     ▼
        claude.enabled.model + claude.request.log
```

## Pruebas

Pruebas unitarias incluidas (la llamada a Anthropic se simula, no requieren red):

```bash
odoo -d <db> -i ktx_claude_ai --test-enable --stop-after-init
```

- `tests/test_dispatcher.py`: permisos, CRUD, masivo, acciones de estado y
  confirmación.
- `tests/test_agent_loop.py`: bucle de *tool use* con la API mockeada.
- `tests/test_mcp_connector.py`: endpoint MCP (initialize / tools.list /
  tools.call / 401 sin token / conector desactivado).
- `tests/test_oauth_flow.py`: registro dinámico → consentimiento → token →
  refresh, con verificación PKCE y rechazo de redirect_uri no registrado.

## Mantenimiento y migración a futuras versiones de Odoo

El módulo está diseñado para migrar fácilmente:

- **Dependencias mínimas:** solo `base, base_setup, mail, web`; cero paquetes
  pip externos.
- **Sin monkeypatch:** solo ORM y controladores HTTP estándar.
- **APIs estables:** vistas `<list>`, ajustes `<app>/<setting>`, registries OWL,
  `@api.model_create_multi`, `_sql_constraints`.
- **Desacoplado de modelos concretos:** las herramientas y los permisos operan
  sobre nombres de modelo configurables (`claude.enabled.model`), no sobre
  modelos cableados; cambiar de versión no rompe la lógica.
- **Escalabilidad/higiene:** una tarea programada diaria (`ir.cron`) purga
  códigos/tokens OAuth expirados y la bitácora más antigua que los días de
  retención configurados.
- **Versionado:** patrón `19.0.x.y.z`. Para migrar a Odoo 20+, basta revisar
  cambios de la API de vistas/OWL y subir la serie de versión.

## Autor

KONTAXES — https://www.kontaxes.com · Soporte: admin@kontaxes.com
