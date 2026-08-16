"""
Gera `Radar_GBOEX_dashboard.html`: o painel inteiro em UM arquivo.

Embute CSS, JS e os dados (`data.json`) dentro do HTML, então o arquivo abre
sozinho — inclusive por duplo clique, sem servidor. Quando ele está publicado
no GitHub Pages, continua buscando o `data.json` do ar (dados mais novos); os
dados embutidos são o fallback offline.

Uso:  python build_standalone.py
"""
from __future__ import annotations

import json
from pathlib import Path

import config

BASE = Path(__file__).resolve().parent
DASH = BASE / "dashboard"
SAIDA = BASE / "Radar_GBOEX_dashboard.html"


def _js_safe(payload: str) -> str:
    """Impede que um `</script>` dentro do JSON feche a tag cedo demais."""
    return payload.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build() -> Path:
    html = (DASH / "index.html").read_text(encoding="utf-8")
    css = (DASH / "styles.css").read_text(encoding="utf-8")
    js = (DASH / "app.js").read_text(encoding="utf-8")
    dados = json.loads((config.DATA_JSON).read_text(encoding="utf-8"))

    html = html.replace(
        '<link rel="stylesheet" href="styles.css" />',
        f"<style>\n{css}\n</style>",
    )
    embutido = _js_safe(json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    html = html.replace(
        '<script src="app.js"></script>',
        f"<script>window.RADAR_DATA={embutido};</script>\n  <script>\n{js}\n</script>",
    )

    SAIDA.write_text(html, encoding="utf-8")
    return SAIDA


if __name__ == "__main__":
    caminho = build()
    kb = caminho.stat().st_size / 1024
    print(f"gerado: {caminho.name} ({kb:.0f} KB)")
