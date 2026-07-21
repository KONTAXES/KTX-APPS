# -*- coding: utf-8 -*-
"""OAuth 2.1 authorization server for the Claude remote connector.

Implements the subset of RFC 9728 (protected-resource metadata), RFC 8414
(authorization-server metadata), RFC 7591 (dynamic client registration) and the
authorization-code + PKCE flow that Claude.ai uses to connect to a custom
(remote MCP) connector. End-user authentication and consent are layered on top
of Odoo's own login/session.
"""
import base64
import hashlib
import json
import logging
import secrets
import time
from datetime import timedelta
from urllib.parse import urlencode

from odoo import _, fields, http
from odoo.http import request

from ..models.claude_oauth import sha256
from .utils import base_url, json_response

_logger = logging.getLogger(__name__)

SCOPES = ["odoo"]


def _redirect_error(redirect_uri, state, error, description=None):
    params = {"error": error}
    if description:
        params["error_description"] = description
    if state:
        params["state"] = state
    sep = "&" if "?" in (redirect_uri or "") else "?"
    return request.redirect(redirect_uri + sep + urlencode(params), code=302, local=False)


def _token_error(error, status=400, description=None):
    body = {"error": error}
    if description:
        body["error_description"] = description
    return json_response(body, status=status)


class ClaudeOAuthController(http.Controller):

    # ------------------------------------------------------------- discovery
    @http.route(
        "/.well-known/oauth-protected-resource",
        type="http", auth="none", methods=["GET"], csrf=False, cors="*",
    )
    def protected_resource_metadata(self, **kw):
        base = base_url()
        return json_response({
            "resource": base + "/claude/mcp",
            "authorization_servers": [base],
            "bearer_methods_supported": ["header"],
            "scopes_supported": SCOPES,
        })

    @http.route(
        [
            "/.well-known/oauth-authorization-server",
            "/.well-known/oauth-authorization-server/claude/mcp",
            "/.well-known/openid-configuration",
        ],
        type="http", auth="none", methods=["GET"], csrf=False, cors="*",
    )
    def authorization_server_metadata(self, **kw):
        base = base_url()
        return json_response({
            "issuer": base,
            "authorization_endpoint": base + "/claude/oauth/authorize",
            "token_endpoint": base + "/claude/oauth/token",
            "registration_endpoint": base + "/claude/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": [
                "none", "client_secret_post", "client_secret_basic",
            ],
            "scopes_supported": SCOPES,
        })

    # ---------------------------------------------- dynamic client registration
    @http.route(
        "/claude/oauth/register",
        type="http", auth="none", methods=["POST"], csrf=False, cors="*",
    )
    def register(self, **kw):
        try:
            body = json.loads(request.httprequest.get_data(as_text=True) or "{}")
        except ValueError:
            return _token_error("invalid_client_metadata", description="Cuerpo JSON inválido.")
        result = request.env["claude.oauth.client"].sudo().register(body)
        if not result:
            return _token_error("invalid_redirect_uri", description="redirect_uris requerido.")
        client, secret = result
        resp = {
            "client_id": client.client_id,
            "client_id_issued_at": int(time.time()),
            "redirect_uris": client.get_redirect_uris(),
            "grant_types": (client.grant_types or "").split(","),
            "response_types": (client.response_types or "").split(","),
            "token_endpoint_auth_method": client.token_endpoint_auth_method,
            "scope": client.scope,
            "client_name": client.client_name,
        }
        if secret:
            resp["client_secret"] = secret
        return json_response(resp, status=201)

    # ----------------------------------------------------------- authorize (UI)
    @http.route(
        "/claude/oauth/authorize",
        type="http", auth="user", methods=["GET"], csrf=False,
    )
    def authorize(self, **params):
        client = request.env["claude.oauth.client"].sudo().search(
            [("client_id", "=", params.get("client_id"))], limit=1
        )
        redirect_uri = params.get("redirect_uri")
        # Cannot trust an unregistered client/redirect → show a safe error page.
        if not client or redirect_uri not in client.get_redirect_uris():
            return request.render(
                "ktx_claude_ai.oauth_error",
                {"error": _("Cliente o redirect_uri no válido.")},
            )
        # Personal client: only the registered user may authorize with it.
        if client.user_id and client.user_id.id != request.env.user.id:
            return request.render(
                "ktx_claude_ai.oauth_error",
                {"error": _(
                    "Este cliente OAuth es personal y solo puede usarlo "
                    "el usuario para el que fue creado."
                )},
            )
        if params.get("response_type") != "code":
            return _redirect_error(redirect_uri, params.get("state"), "unsupported_response_type")
        if params.get("code_challenge_method", "S256") != "S256" or not params.get("code_challenge"):
            return _redirect_error(
                redirect_uri, params.get("state"), "invalid_request",
                description="Se requiere PKCE con S256.",
            )
        return request.render("ktx_claude_ai.oauth_consent", {
            "client_name": client.client_name or client.client_id,
            "user_name": request.env.user.name,
            "params": params,
            "csrf_token": request.csrf_token(),
        })

    @http.route(
        "/claude/oauth/authorize/decision",
        type="http", auth="user", methods=["POST"], csrf=True,
    )
    def authorize_decision(self, **post):
        client = request.env["claude.oauth.client"].sudo().search(
            [("client_id", "=", post.get("client_id"))], limit=1
        )
        redirect_uri = post.get("redirect_uri")
        if not client or redirect_uri not in client.get_redirect_uris():
            return request.render(
                "ktx_claude_ai.oauth_error",
                {"error": _("Cliente o redirect_uri no válido.")},
            )
        if post.get("decision") != "allow":
            return _redirect_error(redirect_uri, post.get("state"), "access_denied")
        code_raw = secrets.token_urlsafe(32)
        request.env["claude.oauth.code"].sudo().create({
            "code": sha256(code_raw),
            "client_id": client.client_id,
            "user_id": request.env.user.id,
            "redirect_uri": redirect_uri,
            "code_challenge": post.get("code_challenge"),
            "code_challenge_method": post.get("code_challenge_method") or "S256",
            "scope": post.get("scope") or client.scope,
            "resource": post.get("resource"),
            "expires_at": fields.Datetime.now() + timedelta(seconds=120),
        })
        query = {"code": code_raw}
        if post.get("state"):
            query["state"] = post["state"]
        sep = "&" if "?" in redirect_uri else "?"
        return request.redirect(redirect_uri + sep + urlencode(query), code=302, local=False)

    # ---------------------------------------------------------------- token
    def _client_auth(self, post):
        """Resolve (client_id, client_secret) from body or HTTP Basic header."""
        client_id = post.get("client_id")
        client_secret = post.get("client_secret")
        auth = request.httprequest.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode()
                if ":" in decoded:
                    bid, bsecret = decoded.split(":", 1)
                    client_id = client_id or bid
                    client_secret = client_secret or bsecret
            except (ValueError, UnicodeDecodeError):
                pass
        return client_id, client_secret

    @http.route(
        "/claude/oauth/token",
        type="http", auth="none", methods=["POST"], csrf=False, cors="*",
    )
    def token(self, **post):
        grant_type = post.get("grant_type")
        client_id, client_secret = self._client_auth(post)
        Token = request.env["claude.oauth.token"].sudo()

        if grant_type == "authorization_code":
            code_rec = request.env["claude.oauth.code"].sudo().search(
                [("code", "=", sha256(post.get("code") or "")), ("used", "=", False)],
                limit=1,
            )
            if not code_rec or (code_rec.expires_at and code_rec.expires_at < fields.Datetime.now()):
                return _token_error("invalid_grant", description="Código inválido o expirado.")
            if code_rec.client_id != client_id:
                return _token_error("invalid_grant", description="client_id no coincide.")
            if post.get("redirect_uri") != code_rec.redirect_uri:
                return _token_error("invalid_grant", description="redirect_uri no coincide.")
            # PKCE verification (S256).
            verifier = post.get("code_verifier") or ""
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()
            ).rstrip(b"=").decode()
            if challenge != (code_rec.code_challenge or ""):
                return _token_error("invalid_grant", description="Falla la verificación PKCE.")
            # Confidential client secret check (if registered with one).
            client = request.env["claude.oauth.client"].sudo().search(
                [("client_id", "=", client_id)], limit=1
            )
            if client and client.client_secret:
                if not client_secret or sha256(client_secret) != client.client_secret:
                    return _token_error("invalid_client", status=401)
            code_rec.used = True
            access_raw, refresh_raw, ttl = Token._mint(
                client_id, code_rec.user_id, code_rec.scope, code_rec.resource
            )
            return json_response({
                "access_token": access_raw,
                "token_type": "Bearer",
                "expires_in": ttl,
                "refresh_token": refresh_raw,
                "scope": code_rec.scope or "odoo",
            })

        if grant_type == "refresh_token":
            res = Token._refresh(post.get("refresh_token"), client_id)
            if not res:
                return _token_error("invalid_grant", description="refresh_token inválido.")
            access_raw, refresh_raw, ttl = res
            return json_response({
                "access_token": access_raw,
                "token_type": "Bearer",
                "expires_in": ttl,
                "refresh_token": refresh_raw,
                "scope": "odoo",
            })

        return _token_error("unsupported_grant_type")
