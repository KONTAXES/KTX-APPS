# -*- coding: utf-8 -*-
{
    "name": "Login Studio - Personalizacion Avanzada de Login",
    "version": "19.0.1.1.0",
    "category": "Website",
    "summary": "Personaliza por completo el login de Odoo: temas, marca, fondos, tipografias y "
               "extensiones CSS/JS propias, con modo seguro anti-bloqueo",
    "description": """
Login Studio (KONTAXES)
========================
Reemplaza y personaliza a fondo las paginas de autenticacion de Odoo (login,
registro y recuperacion de contrasena), desactivando la apariencia por
defecto y sustituyendola por un tema propio, sin tocar el core de Odoo.

Motor de temas
--------------
- Plantillas base: Centrada, Split Screen, Pantalla Completa y Layout 100%
  personalizado (HTML propio) para casos donde el tema por defecto de Odoo
  debe desactivarse totalmente.
- Colores, tipografias (incluye fuentes propias .woff2), fondos solidos,
  degradados animados, imagenes y video de fondo subible directamente.
- Marca completa: logo, favicon y titulo de la pestana del navegador con el
  nombre del login, mas la frase "Accede al portal de: tu marca".
- Controles finos sin escribir CSS: ancho y sombra de la tarjeta, tamano del
  logo, color de enlaces, color de superposicion, glassmorphism, radios de
  borde, textos de bienvenida, pie de pagina, enlaces legales y control del
  dominio de la base de datos / "Powered by Odoo".
- Configuracion centralizada (solo administradores) dentro de Ajustes, con
  vista previa en vivo: un login predeterminado se aplica a todos los
  visitantes, y opcionalmente logins personales asignados a usuarios
  especificos los anulan solo para ellos, cada uno con su propio enlace de
  acceso corto y facil de recordar, que se mantiene al pasar a registro o
  recuperacion de contrasena.

Extensiones (CSS/JS/fuentes/imagenes) subibles
-----------------------------------------------
- Sube tus propios archivos (o un paquete .zip con varios) para anadir
  funcionalidad al login: animaciones, widgets, integraciones, tipografias.
- Cada archivo se sirve como recurso estatico independiente (nunca se
  ejecuta ni se interpreta en el servidor), por lo que un error de sintaxis
  en un archivo nunca interrumpe el formulario de login real.
- Control de alcance por pagina (login / registro / recuperar contrasena /
  todas), orden de carga, y punto de insercion (head / fin de body).
- Versionado automatico con checksum, publicacion controlada y "rollback"
  de un clic a la ultima version que funciono.
- "Modo seguro" de emergencia (parametro de sistema o `?ktx_safe=1`) que
  restaura instantaneamente el login 100% original de Odoo si algo falla.

Seguridad y gobierno
---------------------
- Solo el grupo de Ajustes Tecnicos puede administrar temas y extensiones.
- Validacion de extension, tipo MIME y tamano maximo por archivo.
- Confirmacion explicita de riesgo requerida antes de publicar JavaScript.
- Bitacora (chatter) de quien subio o publico cada archivo.

Pensado para crecer y migrar
------------------------------
- Toda la configuracion vive en modelos de Odoo (no en parametros sueltos),
  lo que facilita exportar/clonar temas entre bases y migrar a futuras
  versiones de Odoo con cambios minimos.
- Arquitectura extensible: otros modulos pueden anadir nuevos tipos de
  activos o variables de tema heredando los modelos existentes.

Nota: no instalar junto a otros modulos que tambien hereden
web.login_layout con el mismo objetivo (p. ej. auth_branding o
sc_login_animation); Login Studio esta pensado como reemplazo completo
de ese tipo de modulos, no como complemento.

Requiere el modulo Sitio Web (website): cuando esta instalado, Odoo
envuelve la pagina de login en el layout del sitio (navegacion, pie de
pagina) reemplazando por completo el layout base de login; Login Studio
se engancha despues de ese reemplazo para poder seguir aplicando el tema
en ese caso, que es la configuracion mas comun en instalaciones Enterprise.
    """,
    "author": "KONTAXES",
    "website": "https://www.kontaxes.com",
    "support": "soporte@kontaxes.com",
    "license": "OPL-1",
    "price": 0.0,
    "currency": "USD",
    "depends": ["web", "website", "auth_signup", "base_setup", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/ktx_login_asset_views.xml",
        "views/ktx_login_theme_import_wizard_views.xml",
        "views/ktx_login_theme_views.xml",
        "views/res_config_settings_views.xml",
        "views/preview_templates.xml",
        "views/login_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ktx_login_studio/static/src/js/ktx_login_studio_preview.js",
            "ktx_login_studio/static/src/xml/ktx_login_studio_preview.xml",
            "ktx_login_studio/static/src/css/ktx_login_studio_settings.css",
        ],
        "web.assets_frontend": [
            "ktx_login_studio/static/src/css/ktx_login_studio_frontend.css",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "images": [
        "static/description/banner.gif",
        "static/description/banner.png",
    ],
    "web_icon": "ktx_login_studio,static/description/icon.png",
}
