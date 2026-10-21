"""
test_BE50_gmail_consent_script.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: US-14 · Script de consentimiento inicial de Gmail (ADR-012 §4)

Verifica que:
  - usa PKCE (S256) y el scope mínimo `gmail.send`, con access_type=offline y prompt=consent
  - descarta una respuesta cuyo `state` no coincide (CSRF) y escucha solo en 127.0.0.1
  - el canje envía el code_verifier y devuelve el refresh token; sin token o con error da un mensaje claro sin secretos
  - el script NUNCA escribe el token en un archivo ni lo manda a un log
"""
import base64
import hashlib
import importlib.util
import socket
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gmail_consent.py"
spec = importlib.util.spec_from_file_location("gmail_consent", SCRIPT)
consent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consent)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_BE50_pkce_challenge_is_s256_of_the_verifier():
    verifier, challenge = consent.make_pkce()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected and 43 <= len(verifier) <= 128 and "=" not in verifier + challenge
    assert consent.make_pkce()[0] != verifier


def test_BE50_auth_url_requests_only_gmail_send_offline_with_pkce():
    url = consent.build_auth_url("cid.apps.googleusercontent.com", "http://127.0.0.1:8765/", "st", "ch")
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert q["scope"] == "https://www.googleapis.com/auth/gmail.send"                  # ni lectura ni otros scopes
    assert (q["access_type"], q["prompt"], q["response_type"]) == ("offline", "consent", "code")
    assert (q["code_challenge"], q["code_challenge_method"], q["state"]) == ("ch", "S256", "st")
    assert q["redirect_uri"] == "http://127.0.0.1:8765/" and "client_secret" not in url


def respond(request_log, status=200, payload=None):
    def handler(request: httpx.Request):
        request_log.append(parse_qs(request.content.decode()))
        return httpx.Response(status, json=payload if payload is not None else {})
    return httpx.MockTransport(handler)


def test_BE50_exchange_sends_the_verifier_and_returns_the_refresh_token():
    log = []
    token = consent.exchange_code("cid", "csecret", "el-codigo", "http://127.0.0.1:8765/", "el-verifier",
                                  transport=respond(log, payload={"access_token": "ya29.x", "refresh_token": "1//el-refresh"}))
    assert token == "1//el-refresh"
    form = log[0]
    assert form["grant_type"] == ["authorization_code"] and form["code_verifier"] == ["el-verifier"] and form["code"] == ["el-codigo"]


def test_BE50_exchange_errors_are_clear_and_leak_nothing():
    with pytest.raises(consent.ConsentError) as e1:
        consent.exchange_code("cid", "csecret", "c", "http://127.0.0.1:8765/", "v",
                              transport=respond([], status=400, payload={"error": "invalid_grant", "error_description": "csecret"}))
    assert "invalid_grant" in str(e1.value) and "csecret" not in str(e1.value)
    with pytest.raises(consent.ConsentError) as e2:
        consent.exchange_code("cid", "csecret", "c", "http://127.0.0.1:8765/", "v", transport=respond([], payload={"access_token": "ya29.x"}))
    assert "permissions" in str(e2.value)                                              # explica cómo revocar y repetir


def serve_once(port, state, results):
    try:
        results["code"] = consent.wait_for_code(port, state, timeout=5)
    except consent.ConsentError as exc:
        results["error"] = str(exc)


def hit(port, query):
    for _ in range(50):                                                                # el servidor tarda en abrir el puerto
        try:
            return urlopen(f"http://127.0.0.1:{port}/?{query}", timeout=3).read()
        except OSError:
            time.sleep(0.05)
    raise AssertionError("el servidor local no respondió")


def test_BE50_callback_accepts_matching_state_and_closes():
    port, results = free_port(), {}
    t = threading.Thread(target=serve_once, args=(port, "estado-ok", results))
    t.start()
    assert b"Listo" in hit(port, "code=cod123&state=estado-ok")
    t.join(5)
    assert results == {"code": "cod123"}


@pytest.mark.parametrize("query,fragment", [
    ("code=cod123&state=otro", "state"), ("code=cod123", "state"), ("error=access_denied&state=estado-ok", "access_denied"),
    ("state=estado-ok", "código"),
])
def test_BE50_callback_rejects_bad_responses(query, fragment):
    port, results = free_port(), {}
    t = threading.Thread(target=serve_once, args=(port, "estado-ok", results))
    t.start()
    hit(port, query)
    t.join(5)
    assert "code" not in results and fragment in results["error"]


def test_BE50_server_listens_only_on_loopback_and_logs_nothing():
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'HTTPServer(("127.0.0.1", port), Handler)' in src and '"0.0.0.0"' not in src
    assert "def log_message(self, *args):" in src                                      # la URL lleva el código: sin log de peticiones


def test_BE50_script_never_writes_the_token_to_disk_or_logs():
    import ast
    src = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(src)
    builtin_open = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"]
    assert builtin_open == []                                                         # (webbrowser.open abre el navegador, no un archivo)
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not attrs & {"write_text", "write_bytes", "dump", "info", "debug", "warning", "error", "exception"}
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert "logging" not in imported and "shelve" not in imported and "pickle" not in imported
    assert src.count("print(token)") == 1                                             # el único lugar donde sale el token


def test_BE50_main_requires_client_credentials(monkeypatch, capsys):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    assert consent.main(["--no-browser"]) == 2
    assert "GOOGLE_CLIENT_ID" in capsys.readouterr().err
