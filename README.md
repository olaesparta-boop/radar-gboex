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

## 2.1 Painel publicado (GitHub Pages) — e a coleta na nuvem

O dashboard fica no ar, **público**, em:

**<https://olaesparta-boop.github.io/radar-gboex/>**
(versão em arquivo único: `.../Radar_GBOEX_dashboard.html`)

Você **não precisa** rodar nada na sua máquina para o painel se manter vivo:
a coleta roda no próprio GitHub, pelo workflow `.github/workflows/coleta.yml`.

| Quando | O que acontece |
|--------|----------------|
| Toda segunda-feira às 08h (BRT) | coleta **completa** (todas as fontes, usa a verba): o GitHub roda `main.py`, grava `radar.db` + `dashboard/data.json` no repositório e republica o painel |
| Todos os outros dias, 08h (BRT) | coleta **grátis** — só Google News, GDELT e site GBOEX; mantém o painel com movimento diário sem tocar na verba |
| Botão **↻ Atualizar** no painel | dispara essa mesma coleta na hora e recarrega o painel quando ela termina (2 a 6 min) |
| Aba **Actions → Coleta Radar GBOEX → Run workflow** | mesma coisa, pelo site do GitHub |

Rodar `python main.py` no seu computador continua funcionando; para mandar o
resultado ao ar, `git add radar.db dashboard/data.json && git commit && git push`
— mas dê um `git pull` antes, porque o robô também escreve nesses arquivos.

### Ligar o botão "Atualizar"

O painel é um site estático: sozinho ele não coleta nada, quem coleta é o
Actions. Para o botão poder acionar o Actions, cada navegador precisa de um
token seu (fica só no `localStorage` daquele navegador, nunca no repositório):

1. No painel, clique na engrenagem **⚙** ao lado de *Atualizar*.
2. Gere um token **fine-grained** em
   <https://github.com/settings/personal-access-tokens/new>:
   *Repository access* → **Only select repositories → radar-gboex**;
   *Permissions → Repository permissions* → **Actions: Read and write**.
3. Cole no campo, salve. Pronto — o **↻ Atualizar** passa a coletar de verdade.

Sem token salvo, o botão apenas rebusca o `data.json` publicado (o que a coleta
semanal deixou). Na engrenagem há também a opção **"só fontes grátis"**, que
coleta apenas notícias e não consome nada da verba.

### Chaves da coleta na nuvem (segredos do repositório)

O `.env` não vai para o GitHub. As chaves precisam ser cadastradas uma vez em
*Settings → Secrets and variables → Actions*, ou pelo terminal:

```bash
gh secret set -f .env -R olaesparta-boop/radar-gboex
```

(feito em 16/08/2026 — `APIFY_TOKEN`, `ANTHROPIC_API_KEY` e `SENTIMENT_MODEL`
já estão cadastrados; refaça o comando se trocar alguma chave no `.env`.)

Sem `APIFY_TOKEN` cadastrado, a coleta na nuvem funciona só com as fontes
grátis (Google News, GDELT, site GBOEX) — Reclame Aqui e redes ficam de fora.

> ⚠️ O site é público e o `data.json` (assim como o `radar.db`, agora versionado
> para servir de memória entre as execuções na nuvem) contém o texto das
> reclamações e os perfis/autores das menções. Se isso precisar deixar de ser
> aberto, o caminho é tornar o repositório privado (Pages privado exige plano
> pago) ou migrar a hospedagem para um serviço com proteção por senha.

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

**Em produção isso já está resolvido pelo GitHub Actions** (seção 2.1): os dois
agendamentos estão no `.github/workflows/coleta.yml` — o `cron` de segunda roda
a coleta completa, o dos demais dias roda só as fontes grátis. Para incluir
outro dia na completa, mova-o de um `cron` para o outro (ex.: quinta = tirar o
`4` do segundo e usar `0 11 * * 1,4` no primeiro), lembrando que cada coleta
completa consome verba. As opções abaixo valem se você quiser rodar a coleta na
sua própria máquina/servidor.

### Opção A — n8n
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
├── build_standalone.py# gera o painel em arquivo único (CSS/JS/dados embutidos)
├── config.py          # palavras-chave, fontes, chaves, actors
├── .env               # segredos (não versionar)
├── .github/workflows/
│   └── coleta.yml     # coleta diária + botão "Atualizar" + publicação no Pages
├── radar/
│   ├── models.py      # Mention (modelo unificado)
│   ├── storage.py     # SQLite + deduplicação
│   ├── sentiment.py   # léxico PT-BR + IA opcional
│   ├── pipeline.py    # enriquecimento
│   ├── export.py      # agregações → data.json
│   └── collectors/    # google_news, gdelt, gboex_site, reclame_aqui, apify_social
├── dashboard/         # index.html, styles.css, app.js, data.json
└── radar.db           # banco (versionado: é a memória entre as coletas na nuvem)
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

### Verba das coletas pagas e o mapa de consumo
O radar tem uma **verba própria por ciclo**: `RADAR_BUDGET_USD` no `config.py`
(hoje **US$ 5**). É o quanto as fontes pagas (redes sociais e Reclame Aqui)
podem consumir por ciclo — o saldo da conta do provedor **não** entra aqui nem
no painel, que é público.

Uma coleta completa custa ≈ US$ 1,90 (medido em 17/08/2026). Por isso a
divisão: **completa só às segundas** (~US$ 8/ciclo caberia mal em US$ 5) e
**grátis nos outros dias**, que não consome nada. Quando a verba do ciclo
acaba, a coleta **continua rodando só com as fontes grátis** até o ciclo virar
(`BUDGET_ENFORCE = False` desliga esse freio).

O painel mostra isso como **Mapa de consumo** (abaixo dos KPIs, aba Geral):
**só a barra**, sem nenhum valor em dinheiro — proporção da verba consumida no
ciclo, o estado em palavra (Folga / Atenção / Verba esgotada) e quantas coletas
completas ainda cabem. A medição acontece na coleta (`radar/apify_usage.py`), o
gasto de cada rodada fica na tabela `run_costs` do `radar.db` e o `data.json`
publicado leva apenas `pct_usado`. Sem `APIFY_TOKEN` não há medição e o mapa
não aparece.

> Os valores em dólar aparecem só para quem roda `python main.py` na própria
> máquina; no log do GitHub Actions (que é público) sai a porcentagem.

Para gastar menos: modo **"só fontes grátis"** na ⚙ do painel, `APIFY_MAX_ITEMS`
menor ou tirar collectors caros de `PAID_COLLECTORS`/`config.py`.
