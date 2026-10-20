"""
test_BE55_nginx_security_headers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tarea: SEC-6 · Cabeceras de seguridad en frontend/nginx.conf (parsea el archivo)

Verifica que:
  - hay nosniff, X-Frame-Options DENY, Referrer-Policy y Permissions-Policy, todas con `always`
  - la CSP existe (hoy en modo Report-Only) con default-src 'self', frame-ancestors 'none' y sin
    'unsafe-eval' ni comodines en script-src
  - los orígenes externos de la CSP son solo los que usa la app (Google Identity Services,
    Google Fonts y teselas de OpenStreetMap)
  - el bloque de estáticos, que define su propio add_header, repite nosniff (nginx no hereda)
  - no hay HSTS (el TLS termina fuera de este nginx) ni COOP distinto de same-origin-allow-popups
"""
import re
from pathlib import Path

CONF = (Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf").read_text(encoding="utf-8")
DIRECTIVES = re.findall(r'^\s*add_header\s+(\S+)\s+"([^"]*)"\s*(always)?\s*;', CONF, re.M)
HEADERS = {name.lower(): (value, always) for name, value, always in DIRECTIVES}


def csp():
    value = (HEADERS.get("content-security-policy") or HEADERS["content-security-policy-report-only"])[0]
    return {d.split()[0]: d.split()[1:] for d in (x.strip() for x in value.split(";")) if d}


def test_BE55_basic_headers_present_with_always():
    expected = {"x-content-type-options": "nosniff", "x-frame-options": "DENY",
                "referrer-policy": "strict-origin-when-cross-origin"}
    for name, value in expected.items():
        assert HEADERS[name] == (value, "always"), name
    assert HEADERS["permissions-policy"][1] == "always"
    assert "camera=()" in HEADERS["permissions-policy"][0]


def test_BE55_csp_present_and_strict_where_it_matters():
    policy = csp()
    assert HEADERS.get("content-security-policy", HEADERS.get("content-security-policy-report-only"))[1] == "always"
    assert policy["default-src"] == ["'self'"]
    assert policy["frame-ancestors"] == ["'none'"]
    assert policy["object-src"] == ["'none'"]
    script = policy["script-src"]
    assert "'unsafe-eval'" not in script and "'unsafe-inline'" not in script and "*" not in script


def test_BE55_csp_external_origins_are_only_the_ones_the_app_uses():
    allowed = {"https://accounts.google.com", "https://fonts.googleapis.com", "https://fonts.gstatic.com",
               "https://tile.openstreetmap.org"}
    for directive, sources in csp().items():
        for src in sources:
            if src.startswith("https://"):
                assert re.match(r"https://[^/]+", src).group(0) in allowed, f"{directive}: {src}"
    assert "https://accounts.google.com/gsi/client" in csp()["script-src"]
    assert "worker-src" in csp() and csp()["worker-src"] == ["blob:"]


def test_BE55_static_assets_block_repeats_nosniff():
    block = re.search(r"location ~\* [^{]*\{(.*?)\n    \}", CONF, re.S).group(1)
    assert "add_header" in block                      # define los suyos => nginx no hereda los del server
    assert re.search(r'add_header\s+X-Content-Type-Options\s+"nosniff"\s+always', block)


def test_BE55_no_hsts_and_safe_coop():
    assert "strict-transport-security" not in HEADERS
    coop = HEADERS.get("cross-origin-opener-policy")
    assert coop is None or coop[0] == "same-origin-allow-popups"
