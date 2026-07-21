# -*- coding: utf-8 -*-
"""Shared helpers for the Claude remote connector controllers."""
import json
import threading
import time

from odoo.http import request

# --------------------------------------------------------------- rate limiting
# In-memory sliding-window counter keyed by user id, protected by a lock so
# concurrent Odoo workers don't race. Mirrors the pattern in
# odoo_mcp_ai_agent/controllers/mcp_controller.py::_check_rate_limit.
_rl_lock = threading.Lock()
_rl_buckets = {}


def check_rate_limit(key, limit_per_minute):
    """Return True if the request is allowed. limit_per_minute=0 → unlimited."""
    if not limit_per_minute:
        return True
    now = time.monotonic()
    window_start = now - 60.0
    with _rl_lock:
        bucket = [t for t in _rl_buckets.get(key, []) if t > window_start]
        if len(bucket) >= limit_per_minute:
            _rl_buckets[key] = bucket
            return False
        bucket.append(now)
        _rl_buckets[key] = bucket
        return True


# ------------------------------------------------------------------- utilities
def base_url():
    """Public base URL of this Odoo for building OAuth/MCP metadata."""
    icp = request.env["ir.config_parameter"].sudo()
    url = (
        icp.get_param("ktx_claude_ai.connector_base_url")
        or icp.get_param("web.base.url")
        or ""
    ).rstrip("/")
    # Strip trailing /claude/mcp in case the user pasted the full connector
    # URL into the "URL pública" field instead of just the base domain.
    if url.endswith("/claude/mcp"):
        url = url[: -len("/claude/mcp")]
    return url


_CORS_HEADERS = [
    ("Access-Control-Allow-Origin", "*"),
    ("Access-Control-Allow-Headers", "Authorization, Content-Type, Mcp-Session-Id, MCP-Protocol-Version"),
    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
]


def json_response(data, status=200, headers=None):
    """Build a JSON HTTP response with permissive CORS headers."""
    payload = json.dumps(data, default=str)
    all_headers = [("Content-Type", "application/json")] + _CORS_HEADERS
    if headers:
        all_headers += headers
    return request.make_response(payload, headers=all_headers, status=status)


def extract_bearer():
    """Return the token from an ``Authorization: Bearer <token>`` header."""
    auth = request.httprequest.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def jsonrpc_result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def jsonrpc_error(req_id, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}
