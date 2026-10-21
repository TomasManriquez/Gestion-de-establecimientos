"""
Consentimiento inicial de la casilla remitente de Gmail (ADR-012 §4). Se ejecuta UNA vez.

Con la sesión de la casilla remitente (una cuenta aparte, NO personal) abierta en el navegador,
abre el flujo de consentimiento de Google con el scope mínimo `gmail.send` y, al terminar, imprime
el refresh token. Ese valor se guarda como secreto (`GMAIL_REFRESH_TOKEN` en el .env del servidor,
tratado como `JWT_SECRET`). El script NUNCA lo escribe en un archivo ni en el log.

Requisitos (checklist completo en Documentacion/07-operacion.md §9):
  - Cliente OAuth de tipo «Aplicación de escritorio», o web con `http://127.0.0.1:8765/` como URI de
    redirección autorizada. La pantalla de consentimiento debe ser de tipo *Internal*: con *External*
    en estado *Testing* Google caduca el refresh token a los 7 días.
  - GOOGLE_CLIENT_ID y GOOGLE_CLIENT_SECRET en el entorno.

Uso:
    cd backend
    GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... python scripts/gmail_consent.py
    python scripts/gmail_consent.py --no-browser      # imprime la URL en vez de abrir el navegador
"""
import argparse
import base64
import hashlib
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/gmail.send"      # el único scope: enviar, no leer
DEFAULT_PORT = 8765
TIMEOUT_SECONDS = 300


class ConsentError(Exception):
    pass


def make_pkce() -> Tuple[str, str]:
    """(code_verifier, code_challenge S256). El verifier no sale de este proceso."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_auth_url(client_id: str, redirect_uri: str, state: str, challenge: str) -> str:
    return AUTH_URL + "?" + urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": SCOPE,
        "access_type": "offline",          # para recibir refresh token
        "prompt": "consent",               # y recibirlo aunque ya se haya consentido antes
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
    })


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str, verifier: str,
                  transport: Optional[httpx.BaseTransport] = None) -> str:
    """Canjea el código por el refresh token. Lanza ConsentError sin incluir secretos en el mensaje."""
    with httpx.Client(timeout=20.0, transport=transport) as client:
        response = client.post(TOKEN_URL, data={
            "client_id": client_id, "client_secret": client_secret, "code": code,
            "redirect_uri": redirect_uri, "grant_type": "authorization_code", "code_verifier": verifier})
    if response.status_code != 200:
        try:
            reason = str(response.json().get("error", response.status_code))
        except ValueError:
            reason = str(response.status_code)
        raise ConsentError(f"Google rechazó el canje del código ({reason}). Repite el procedimiento desde el principio.")
    token = response.json().get("refresh_token")
    if not token:
        raise ConsentError(
            "Google no devolvió un refresh token (la cuenta ya había consentido). Revoca el acceso de esta aplicación en "
            "https://myaccount.google.com/permissions y vuelve a ejecutar el script.")
    return token


def wait_for_code(port: int, expected_state: str, timeout: int = TIMEOUT_SECONDS) -> str:
    """Levanta un servidor SOLO en 127.0.0.1 y espera la redirección de Google. Verifica `state`."""
    box: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            box["error"] = (query.get("error") or [None])[0]
            box["state"] = (query.get("state") or [None])[0]
            box["code"] = (query.get("code") or [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<p>Listo. Puedes cerrar esta pestaña y volver a la terminal.</p>".encode("utf-8"))

        def log_message(self, *args):          # sin log de peticiones: la URL lleva el código
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = timeout
    try:
        server.handle_request()
    finally:
        server.server_close()
    if not box:
        raise ConsentError("Se agotó el tiempo de espera sin recibir la respuesta de Google.")
    if box.get("error"):
        raise ConsentError(f"Google devolvió un error: {box['error']}")
    if not secrets.compare_digest(box.get("state") or "", expected_state):
        raise ConsentError("El parámetro `state` no coincide: se descarta la respuesta.")
    if not box.get("code"):
        raise ConsentError("La respuesta de Google no trae código de autorización.")
    return box["code"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"puerto de la redirección en 127.0.0.1 (por defecto {DEFAULT_PORT})")
    parser.add_argument("--no-browser", action="store_true", help="imprime la URL en vez de abrir el navegador")
    args = parser.parse_args(argv)

    client_id, client_secret = os.environ.get("GOOGLE_CLIENT_ID", "").strip(), os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        print("Falta GOOGLE_CLIENT_ID o GOOGLE_CLIENT_SECRET en el entorno.", file=sys.stderr)
        return 2
    redirect_uri = f"http://127.0.0.1:{args.port}/"
    verifier, challenge = make_pkce()
    state = secrets.token_urlsafe(24)
    url = build_auth_url(client_id, redirect_uri, state, challenge)

    print("Inicia sesión con la CASILLA REMITENTE (cuenta aparte, no personal) y acepta el permiso de enviar correo.")
    if args.no_browser or not webbrowser.open(url):
        print(f"\nAbre esta URL en el navegador:\n\n{url}\n")
    try:
        code = wait_for_code(args.port, state)
        token = exchange_code(client_id, client_secret, code, redirect_uri, verifier)
    except ConsentError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1
    print("\nGuarda este valor como secreto GMAIL_REFRESH_TOKEN en el .env del servidor (nunca en un archivo del repo):\n")
    print(token)
    print("\nTrátalo como JWT_SECRET: da permiso para enviar correo en nombre de la casilla.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
