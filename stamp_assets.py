"""
Carimba a versão nos links de CSS/JS do painel publicado.

O GitHub Pages manda `Cache-Control: max-age=600`. Sem carimbo, logo depois de
uma publicação o navegador pode juntar um `app.js` velho (em cache) com um
`data.json` novo — e uma seção do painel simplesmente não aparece. Com
`app.js?v=<versão>`, um index.html novo sempre puxa o par correspondente.

Uso:  python stamp_assets.py <pasta_publicada> <versao>
"""
from __future__ import annotations

import sys
from pathlib import Path

ARQUIVOS = ("styles.css", "app.js")


def stamp(pasta: Path, versao: str) -> Path:
    index = pasta / "index.html"
    html = index.read_text(encoding="utf-8")
    for nome in ARQUIVOS:
        html = html.replace(f'"{nome}"', f'"{nome}?v={versao}"')
    index.write_text(html, encoding="utf-8")
    return index


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("uso: python stamp_assets.py <pasta_publicada> <versao>")
    alvo = stamp(Path(sys.argv[1]), sys.argv[2])
    print(f"carimbado: {alvo} (v={sys.argv[2]})")
