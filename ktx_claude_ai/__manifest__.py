# -*- coding: utf-8 -*-
{
    "name": "Claude AI para Odoo",
    "version": "19.0.1.20.0",
    "category": "Productivity/Discuss",
    "summary": "Conecta Odoo directamente con Claude (Anthropic): chatea y crea, "
               "modifica, elimina, restablece a borrador o cambia de estado tus "
               "registros — individual o masivamente — desde lenguaje natural.",
    "description": """
Claude AI para Odoo
===================

Pega tu API key de Anthropic en Ajustes y conversa con Claude dentro de Odoo,
igual que los conectores de ChatGPT o Gemini — sin aplicaciones de terceros,
sin Claude de escritorio y sin instalación en terminal.

Claude puede, según lo que escribas en el chat y respetando los permisos del
usuario:

* Buscar y leer cualquier registro habilitado.
* Crear, modificar y eliminar registros (individual o masivamente).
* Restablecer a borrador, confirmar o cancelar documentos (account.move, etc.).
* Ejecutar acciones de cambio de estado permitidas.

Seguridad
---------
* Interruptor global y control por modelo y por operación
  (lectura/creación/escritura/eliminación/acción).
* Las operaciones se ejecutan con los permisos del usuario de Odoo (ACL y
  reglas de registro vigentes), no con sudo general.
* Las operaciones destructivas y masivas requieren confirmación.
* Bitácora de auditoría de cada herramienta ejecutada.
* Cada usuario tiene su propio chat privado: lo que conversa con Claude no es
  visible para los demás.

Acceso: un botón flotante de Claude en la barra superior abre un chat acoplado
desde cualquier pantalla de Odoo.

Sin dependencias externas de Python: usa ``requests`` (incluido en Odoo), por lo
que instala sin ``pip install`` en Odoo Online, Odoo.sh y on-premise.
    """,
    "author": "KONTAXES",
    "website": "https://www.kontaxes.com",
    "support": "admin@kontaxes.com",
    "maintainer": "KONTAXES",
    "license": "OPL-1",
    "price": 0.0,
    "currency": "USD",
    "depends": ["base", "base_setup", "mail", "web"],
    "data": [
        "security/claude_security.xml",
        "security/ir.model.access.csv",
        "wizard/claude_model_selection_wizard_views.xml",
        "views/claude_enabled_model_views.xml",
        "views/claude_request_log_views.xml",
        "views/claude_conversation_views.xml",
        "views/claude_connector_views.xml",
        "views/claude_connector_templates.xml",
        "views/res_config_settings_views.xml",
        "views/claude_menus.xml",
        "data/claude_enabled_model_data.xml",
        "data/claude_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ktx_claude_ai/static/src/js/claude_markdown.js",
            "ktx_claude_ai/static/src/js/claude_chat/claude_chat.scss",
            "ktx_claude_ai/static/src/js/claude_chat/claude_chat.js",
            "ktx_claude_ai/static/src/js/claude_chat/claude_chat.xml",
            "ktx_claude_ai/static/src/js/claude_systray/claude_systray.scss",
            "ktx_claude_ai/static/src/js/claude_systray/claude_systray.js",
            "ktx_claude_ai/static/src/js/claude_systray/claude_systray.xml",
        ],
    },
    "images": ["static/description/banner.png"],
    "post_init_hook": "post_init_hook",
    "post_migrate_hook": "post_migrate_hook",
    "application": True,
    "installable": True,
    "auto_install": False,
}
