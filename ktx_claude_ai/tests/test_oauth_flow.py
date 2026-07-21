# -*- coding: utf-8 -*-
import base64
import hashlib
import json
import re
from urllib.parse import parse_qs, urlencode, urlparse

from odoo.tests import HttpCase, tagged

REDIRECT_URI = "http://localhost:9999/callback"


@tagged("post_install", "-at_install")
class TestOauthFlow(HttpCase):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "ktx_claude_ai.connector_enabled", "True"
        )

    @staticmethod
    def _pkce(seed=b"verifier-seed-0123456789abcdef"):
        verifier = base64.urlsafe_b64encode(seed).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        return verifier, challenge

    def _register(self):
        reg = self.url_open(
            "/claude/oauth/register",
            data=json.dumps({
                "redirect_uris": [REDIRECT_URI],
                "client_name": "TestClient",
                "token_endpoint_auth_method": "none",
            }),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(reg.status_code, 201)
        return reg.json()["client_id"]

    def _get_code(self, client_id, challenge):
        self.authenticate("admin", "admin")
        params = {
            "response_type": "code", "client_id": client_id,
            "redirect_uri": REDIRECT_URI, "code_challenge": challenge,
            "code_challenge_method": "S256", "state": "xyz", "scope": "odoo",
        }
        page = self.url_open("/claude/oauth/authorize?" + urlencode(params))
        self.assertEqual(page.status_code, 200)
        self.assertIn("Autorizar", page.text)  # consent page, not the login form
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text)
        self.assertTrue(m, "csrf token not found in consent page")
        decision = dict(params)
        decision.update({"csrf_token": m.group(1), "decision": "allow"})
        resp = self.url_open(
            "/claude/oauth/authorize/decision", data=decision, allow_redirects=False
        )
        self.assertIn(resp.status_code, (302, 303))
        loc = resp.headers["Location"]
        return parse_qs(urlparse(loc).query)["code"][0]

    def test_full_flow_and_refresh(self):
        client_id = self._register()
        verifier, challenge = self._pkce()
        code = self._get_code(client_id, challenge)

        tok = self.url_open("/claude/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "code_verifier": verifier,
            "client_id": client_id,
        })
        self.assertEqual(tok.status_code, 200)
        tokens = tok.json()
        self.assertIn("access_token", tokens)
        self.assertEqual(tokens["token_type"], "Bearer")

        # The access token authenticates the MCP endpoint.
        r = self.url_open(
            "/claude/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + tokens["access_token"],
            },
        )
        self.assertEqual(r.status_code, 200)

        # Refresh rotates the tokens.
        ref = self.url_open("/claude/oauth/token", data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": client_id,
        })
        self.assertEqual(ref.status_code, 200)
        self.assertIn("access_token", ref.json())

    def test_bad_pkce_rejected(self):
        client_id = self._register()
        _verifier, challenge = self._pkce()
        code = self._get_code(client_id, challenge)
        tok = self.url_open("/claude/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT_URI, "code_verifier": "wrong-verifier",
            "client_id": client_id,
        })
        self.assertEqual(tok.status_code, 400)
        self.assertEqual(tok.json()["error"], "invalid_grant")

    def test_unregistered_redirect_uri_rejected(self):
        client_id = self._register()
        self.authenticate("admin", "admin")
        _verifier, challenge = self._pkce()
        params = {
            "response_type": "code", "client_id": client_id,
            "redirect_uri": "http://evil.example/callback",
            "code_challenge": challenge, "code_challenge_method": "S256",
        }
        page = self.url_open("/claude/oauth/authorize?" + urlencode(params))
        # Error page is shown; no code is issued.
        self.assertNotIn("Autorizar", page.text)
