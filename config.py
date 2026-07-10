"""
Configuração central do Radar GBOEX.

Tudo que é "ajustável" (palavras-chave, fontes, janelas de tempo, chaves)
mora aqui ou no arquivo .env. O resto do código lê deste módulo.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- carrega .env de forma leve (sem dependência externa) ---------------------
BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        # não sobrescreve variáveis já definidas no ambiente real
        os.environ.setdefault(key, val)


_load_dotenv(BASE_DIR / ".env")

# --- marca monitorada ---------------------------------------------------------
BRAND = "GBOEX"

# Termos de busca. "GBOEX" é distintivo o suficiente; termos genéricos como
# "Grêmio Beneficente" geram ruído (várias instituições usam esse nome) e foram
# removidos de propósito. Se quiser ampliar, use variações que contenham a sigla.
QUERIES = [
    "GBOEX",
]

# Filtro de relevância POSITIVO: uma menção só é aceita se o texto contiver
# algum destes termos (normalizados, sem acento). Barra falso-positivo mesmo
# quando a fonte devolve resultado só "parecido". GBOEX é a âncora.
REQUIRE_TERMS = [
    "gboex",
]

# Termos que, se aparecerem no texto, indicam que NÃO é sobre a marca
# (evita falso-positivo). Ajuste conforme aparecerem ruídos.
NEGATIVE_FILTERS = [
    "banco montepio",   # entidade portuguesa homônima de "montepio"
]

# Domínios dos canais PRÓPRIOS do GBOEX. Menções vindas daqui são marcadas
# como "canal_proprio" (contexto), não como voz de terceiros.
OWNED_DOMAINS = [
    "gboex.com.br",
    "gboex.com",
]

# --- janela de coleta ---------------------------------------------------------
LOOKBACK_DAYS = 30          # quão para trás cada coleta olha
REQUEST_TIMEOUT = 25        # segundos por requisição HTTP
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# --- chaves / segredos (via .env) ---------------------------------------------
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
SENTIMENT_MODEL = os.environ.get("SENTIMENT_MODEL", "claude-haiku-4-5-20251001").strip()

# --- Apify: quais actors rodar por plataforma ---------------------------------
# id do actor no formato "usuario~nome-do-actor". Você pode trocar por outros
# actors equivalentes do marketplace do Apify sem mudar o resto do código.
APIFY_ACTORS = {
    "instagram": "apify~instagram-hashtag-scraper",
    "tiktok":    "clockworks~tiktok-scraper",
    "twitter":   "apidojo~tweet-scraper",
    "youtube":   "streamers~youtube-scraper",
    "facebook":  "easyapi~facebook-posts-search-scraper",
    "reddit":    "trudax~reddit-scraper-lite",
    # fallback do Reclame Aqui (Cloudflare bloqueia a API direta):
    "reclame_aqui": "blackfalcondata~reclameaqui-scraper",
}

# shortname da empresa no Reclame Aqui (aparece na URL: /empresa/<shortname>/)
RECLAME_AQUI_SHORTNAME = "gboex"
# Plataformas ativas por padrão. Após testar todas (jul/2026), só Instagram e
# YouTube retornam menções reais ao GBOEX; TikTok/Facebook/X/Reddit deram ~zero.
# Para economizar crédito FREE do Apify, deixamos só as que funcionam.
# Reative qualquer uma incluindo o nome nesta lista.
APIFY_ENABLED_PLATFORMS = ["instagram", "youtube"]
# (testadas e sem retorno para GBOEX: "tiktok", "facebook", "twitter", "reddit")

# Handles/contas oficiais do GBOEX nas redes. Menções vindas destas contas são
# marcadas como canal_proprio (contexto), não como voz de terceiros.
OWNED_SOCIAL_HANDLES = [
    "gboex", "gboex_oficial", "gboexoficial", "gboexprevidencia",
]

# quantos itens no máximo por plataforma por rodada (controla custo no Apify)
APIFY_MAX_ITEMS = 40

# --- Instagram: radar ampliado (hashtags + marcações) --------------------------
# Além de #gboex, varre variações de hashtag e posts que MARCAM o perfil oficial
# (@gboex_oficial) — pega corretor/parceiro/cliente que cita a marca sem a hashtag
# exata. O contexto (hashtag/marcação da marca) já garante relevância, então aqui
# NÃO exigimos a palavra "gboex" no texto.
INSTAGRAM_HASHTAGS = ["gboex", "gboexoficial", "gboexprevidencia", "gboex113anos"]
INSTAGRAM_TAGGED = {
    "enabled": True,
    "profile": "gboex_oficial",              # sem @; perfil marcado nos posts
    "actor": "apify~instagram-tagged-scraper",
    "limit": 40,
}

# --- Facebook: página oficial + coleta de comentários/avaliações ---------------
# O FB não permite busca pública por palavra-chave; a voz de terceiros vem dos
# COMENTÁRIOS nos posts da página oficial e das AVALIAÇÕES da página.
FACEBOOK_PAGE_URL = "https://www.facebook.com/GBOEXoficial"
FACEBOOK_ACTORS = {
    "posts":    "apify~facebook-posts-scraper",
    "comments": "apify~facebook-comments-scraper",
    "reviews":  "apify~facebook-reviews-scraper",
}
FACEBOOK_POSTS_LIMIT = 15        # quantos posts recentes da página varrer
FACEBOOK_COMMENTS_LIMIT = 200    # teto de comentários no total
FACEBOOK_REVIEWS_LIMIT = 40      # teto de avaliações da página
FACEBOOK_ENABLED = True

# --- Comentários em Instagram / YouTube / demais redes -------------------------
# Mesma lógica do Facebook: perfil oficial -> posts/vídeos -> COMENTÁRIOS (voz de
# terceiros). É onde está o volume real de menções para uma marca nichada.
# Para adicionar TikTok/X etc., confirme o perfil oficial e replique um bloco.
SOCIAL_COMMENTS = {
    "instagram": {
        "enabled": True,
        "profile_url": "https://www.instagram.com/gboex_oficial/",
        "posts_actor": "apify~instagram-scraper",
        "comments_actor": "apify~instagram-comment-scraper",
        "posts_limit": 12,
        "comments_limit": 200,
    },
    "youtube": {
        "enabled": True,
        # busca vídeos da marca; filtramos os do canal oficial p/ pegar comentários
        "search": "GBOEX",
        "posts_actor": "streamers~youtube-scraper",
        "comments_actor": "streamers~youtube-comments-scraper",
        "posts_limit": 12,
        "comments_limit": 200,
    },
}

# --- LinkedIn: busca por menções à marca ---------------------------------------
# Diferente de Facebook/Instagram: no LinkedIn a página oficial do GBOEX quase não
# recebe comentários (testado jul/2026: ~3 em 15 posts). A voz real de terceiros
# vem de POSTS de outras pessoas/empresas que MENCIONAM "GBOEX" — funcionários,
# parceiros, ex-alunos, agências. Por isso usamos um actor de BUSCA por keyword.
# Actor sem cookie (harvestapi). Troque o id por equivalente do marketplace sem
# mexer no collector. Custa crédito Apify — mantenha a cadência econômica.
LINKEDIN = {
    "enabled": True,
    "search": "GBOEX",
    "company_url": "https://www.linkedin.com/company/gboex",
    "search_actor": "harvestapi~linkedin-post-search",
    "posts_limit": 40,
}

# Limite de posts por autor nas REDES SOCIAIS (evita um corretor/parceiro/loja
# inundar o radar). Vale só para channel="social"; notícias e RA não são limitados.
SOCIAL_MAX_PER_AUTHOR = 3

# --- armazenamento e saída ----------------------------------------------------
DB_PATH = BASE_DIR / "radar.db"
DASHBOARD_DIR = BASE_DIR / "dashboard"
DATA_JSON = DASHBOARD_DIR / "data.json"
