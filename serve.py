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


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """Evita que o navegador sirva app.js/styles.css antigos após uma edição."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()


def main() -> None:
    handler = partial(NoCacheHandler, directory=str(config.DASHBOARD_DIR))
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
