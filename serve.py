"""
Servidor local do dashboard.

Serve a pasta dashboard/ em http://localhost:8000 e abre o navegador.
Necessário porque o painel carrega data.json via fetch() (o protocolo file://
bloqueia isso). Rode `python main.py` antes para gerar/atualizar os dados.
"""
from __future__ import annotations

import http.server
import socketserver
import webbrowser
from functools import partial

import config

PORT = 8000


def main() -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler,
                      directory=str(config.DASHBOARD_DIR))
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        url = f"http://localhost:{PORT}/index.html"
        print(f"Dashboard em {url}  (Ctrl+C para parar)")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nEncerrado.")


if __name__ == "__main__":
    main()
