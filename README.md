# Radar GBOEX

Monitor de **notícias, dados e menções sobre a marca GBOEX** — o que a imprensa,
clientes, corretores e o público falam *sobre* o GBOEX (não o que o GBOEX publica).

Coleta de várias fontes → análise de sentimento → dashboard web.

```
Google News ┐
GDELT       ├─► coleta (Python) ─► sentimento ─► SQLite ─► data.json ─► 📊 dashboard
Reclame Aqui├
Redes (Apify)┘
```

---

## 1. Instalação

```bash
cd Radar_GBOEX
python -m pip install -r requirements.txt
cp .env.example .env        # (no Windows: copy .env.example .env)
```

Sem nenhuma chave o radar **já funciona** com as fontes gratuitas
(Google News, GDELT, site GBOEX). As chaves habilitam o resto — veja abaixo.

## 2. Rodar

```bash
python main.py              # coleta tudo que estiver configurado
python main.py --no-apify   # pula redes sociais (sem custo Apify)
python main.py --only google_news,gdelt
```

Depois, abra o painel:

```bash
python serve.py            # abre http://localhost:8000 no navegador
```

`main.py` acumula no banco (`radar.db`) e regenera `dashboard/data.json`.
Rodar de novo só adiciona o que é novo (deduplicação automática por URL).

---

## 3. Fontes e o que cada uma exige

| Collector       | Fonte                          | Chave? | Observação |
|-----------------|--------------------------------|--------|------------|
| `google_news`   | Google News RSS                | não    | espinha dorsal do radar de imprensa |
| `gdelt`         | GDELT DOC API                  | não    | secundária; cobertura BR limitada |
| `gboex_site`    | RSS do site GBOEX              | não    | **contexto** (publicações oficiais) |
| `reclame_aqui`  | Reclame Aqui                   | Apify* | API direta bloqueada por Cloudflare → usa Apify |
| `apify_social`  | Instagram, TikTok, X, YouTube, Reddit, Facebook | Apify | menções de terceiros |

\* Reclame Aqui: sem `APIFY_TOKEN` o collector é pulado. Com token, roda o actor
configurado em `config.APIFY_ACTORS["reclame_aqui"]`.

### Habilitar redes sociais (Apify)

1. Crie conta em <https://apify.com> (tem crédito grátis inicial).
2. Copie o token em **Settings → API tokens**.
3. No `.env`: `APIFY_TOKEN=apify_api_xxx`
4. Escolha as plataformas em `config.py` → `APIFY_ENABLED_PLATFORMS`.
5. Os actors usados ficam em `config.py` → `APIFY_ACTORS`. Pode trocar por
   qualquer actor equivalente do marketplace; a normalização de saída é tolerante.

Controle de custo: `APIFY_MAX_ITEMS` limita quantos itens por plataforma/rodada.

### Sentimento por IA (opcional)

Por padrão usa um analisador **léxico PT-BR embutido** (offline, sem custo).
Para maior precisão, preencha `ANTHROPIC_API_KEY` no `.env` — aí cada menção é
classificada pelo Claude (`SENTIMENT_MODEL`, padrão Haiku).

---

## 4. Ajustes rápidos (`config.py`)

- `QUERIES` — termos de busca. `NEGATIVE_FILTERS` — termos que descartam ruído.
- `LOOKBACK_DAYS` — janela de coleta (padrão 30 dias).
- `OWNED_DOMAINS` — domínios oficiais do GBOEX (marcados como contexto).
- Léxico de sentimento (termos positivos/negativos) em
  `radar/sentiment.py → _POS` / `_NEG`.

---

## 5. Rodar sozinho (agendamento)

O radar é um script; qualquer agendador serve.

### Opção A — n8n (recomendado)
Nó **Schedule Trigger** (ex.: a cada 6h) → nó **Execute Command**:
```
python C:\Users\Rodrigo\Desktop\Radar_GBOEX\main.py
```
Opcional: um segundo **Execute Command** publicando `dashboard/` num host, ou um
nó de e-mail lendo `data.json` para enviar resumo. (O `data.json` já traz KPIs
e a lista pronta.)

### Opção B — Agendador de Tarefas do Windows
Crie uma tarefa que executa, no diretório do projeto:
```
python main.py
```
a cada X horas. Deixe `serve.py` rodando à parte (ou publique o `dashboard/`).

### Opção C — cron (Linux/servidor)
```
0 */6 * * * cd /caminho/Radar_GBOEX && /usr/bin/python3 main.py
```

---

## 6. Estrutura

```
Radar_GBOEX/
├── main.py            # orquestrador: coleta → enriquece → grava → exporta
├── serve.py           # servidor local do dashboard
├── config.py          # palavras-chave, fontes, chaves, actors
├── .env               # segredos (não versionar)
├── radar/
│   ├── models.py      # Mention (modelo unificado)
│   ├── storage.py     # SQLite + deduplicação
│   ├── sentiment.py   # léxico PT-BR + IA opcional
│   ├── pipeline.py    # enriquecimento
│   ├── export.py      # agregações → data.json
│   └── collectors/    # google_news, gdelt, gboex_site, reclame_aqui, apify_social
├── dashboard/         # index.html, styles.css, app.js, data.json
└── radar.db           # banco (gerado)
```

## 7. Estado atual (validado com token real — jul/2026)

- ✅ Google News, site GBOEX: funcionando, sem chave. GDELT ~zero (marca nichada).
- ✅ Reclame Aqui via Apify (`blackfalcondata~reclameaqui-scraper`): nota 7,4/10,
  ~40 reclamações capturadas. Requer `APIFY_TOKEN`.
- ✅ Redes sociais (busca por termo `apify_social`): **todas testadas**. Só **Instagram**
  e **YouTube** trazem algo, e quase tudo é conta oficial. TikTok/X/Reddit/FB-busca = ~zero.
- ✅ **Facebook (`facebook.py`)**: comentários + avaliações da página oficial
  (`FACEBOOK_PAGE_URL`). ~32 menções de terceiros por rodada.
- ✅ **Comentários Instagram/YouTube (`social_comments.py`)**: perfil oficial → posts/
  vídeos → comentários. Instagram rende ~46 (foi de 4→46!); YouTube pouco (canal
  corporativo tem baixo engajamento). Config em `SOCIAL_COMMENTS`. Rode com
  `python main.py --only social_comments`.
- ✅ **Dashboard com separação por fonte**: painel "Por fonte" (clicável), filtro de
  fonte e coluna de fonte na tabela — cada menção com seu link original.

Total atual: **132 menções de terceiros** (Instagram 46 · Reclame Aqui 40 · Facebook 32
· Notícias 13 · YouTube 1).
- ✅ Sentimento léxico, dedup, filtro anti-ruído, dashboard: funcionando.

### Custo Apify (plano FREE ~US$5/mês)
Rodar Instagram+YouTube+Reclame Aqui a cada 6h consome crédito. Para produção:
rodar redes/RA 1x/dia (notícias podem ser de hora em hora, são grátis) ou migrar
para plano pago. Ajuste a frequência no agendador e `APIFY_MAX_ITEMS` no `config.py`.
