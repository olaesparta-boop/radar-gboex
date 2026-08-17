/* Radar GBOEX — dashboard front-end. Lê data.json e desenha o painel.
   Navegação por ABAS: "Geral" (visão consolidada) + uma aba por fonte,
   cada fonte com seu próprio dashboard. */

const COLORS = {
  positivo: "#2E6B4F", neutro: "#62706C", negativo: "#A23A33",
  accent: "#103A63", warn: "#C0892F",
};
const CHART_TICK = "#5E6B7C";   // texto dos eixos (tema claro)
const CHART_GRID = "#E7EAF0";   // linhas de grade (tema claro)
const CHANNEL_LABEL = {
  noticia: "Notícias", social: "Redes sociais", reclamacao: "Reclame Aqui",
  canal_proprio: "Canal próprio", indicador: "Indicador",
};
const SOURCE_LABEL = {
  google_news: "Google News", gdelt: "GDELT", gboex_site: "Site GBOEX",
  reclame_aqui: "Reclame Aqui", instagram: "Instagram", youtube: "YouTube",
  facebook: "Facebook", linkedin: "LinkedIn", twitter: "X / Twitter",
  reddit: "Reddit", tiktok: "TikTok",
};
const SOURCE_ICON = {
  google_news: "📰", gdelt: "🌐", gboex_site: "🏢", reclame_aqui: "📣",
  instagram: "📸", youtube: "▶️", facebook: "👥", linkedin: "💼",
  twitter: "🐦", reddit: "🟠", tiktok: "🎵",
};
const srcLabel = (s) => SOURCE_LABEL[s] || s;
const srcIcon = (s) => SOURCE_ICON[s] || "•";

let DATA = null;
let OV = null;                 // agregações da capa recalculadas por período
let charts = {};
let CURRENT_TAB = "overview"; // "overview" | <source>
let PERIOD_DAYS = 0;          // 0 = todo o histórico; senão janela em dias
const NOW = Date.now();

function withinPeriod(m) {
  if (!PERIOD_DAYS) return true;
  const t = Date.parse(m.published_at);
  if (isNaN(t)) return true;           // sem data válida: não esconder
  return (NOW - t) <= PERIOD_DAYS * 86400000;
}
function periodLabel() {
  return PERIOD_DAYS === 30 ? "últimos 30 dias"
    : PERIOD_DAYS === 90 ? "últimos 90 dias"
    : PERIOD_DAYS === 365 ? "últimos 12 meses"
    : "todo o histórico";
}
let OV_DATE = null;   // filtro de dia ativo na aba Geral (clique na timeline)
let OV_EXTERNAL = false; // capa: mostrar só menções de terceiros (clique nos KPIs)
let SRC_DATE = null;  // filtro de dia ativo na aba de fonte
let SRC_THEME = null; // filtro de tema ativo (aba Reclame Aqui)

/* remove acentos p/ casar palavras-chave com robustez */
function norm(s) {
  return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/* temas recorrentes das reclamações do Reclame Aqui (keywords sem acento) */
const RA_THEMES = [
  { key: "cancelamento", label: "Dificuldade de cancelamento",
    kws: ["cancel", "exclus", "excluir", "encerr", "rescis", "sair do plano"] },
  { key: "cobranca", label: "Cobrança / desconto indevido",
    kws: ["cobran", "desconto", "descontad", "debito", "indevid", "folha de pagamento", "boleto"] },
  { key: "venda", label: "Venda sem autorização / abordagem",
    kws: ["sem autoriza", "nao autoriz", "sem minha autoriza", "sem meu consentimento",
          "abordad", "representante", "enganad", "golpe", "induz", "ma-fe", "sem que eu"] },
  { key: "atendimento", label: "Sem retorno / atendimento",
    kws: ["retorno", "nao respond", "sem resposta", "ninguem", "nao consigo falar",
          "contato", "atendimento", "protocolo", "descaso", "sem posicionamento"] },
  { key: "beneficio", label: "Benefício / documentação / resgate",
    kws: ["document", "falec", "benefic", "peculio", "resgate", "indeniza", "pensao", "herdeir"] },
];
const matchTheme = (m, t) => {
  const s = norm(m.title + " " + (m.text || ""));
  return t.kws.some(k => s.includes(k));
};

/* busca o data.json publicado; se não der (arquivo único aberto offline),
   usa a cópia embutida por build_standalone.py */
async function fetchData() {
  try {
    const res = await fetch("data.json?_=" + Date.now());
    if (!res.ok) throw new Error(res.status);
    return await res.json();
  } catch (e) {
    if (window.RADAR_DATA) return window.RADAR_DATA;
    throw e;
  }
}

async function load() {
  try {
    DATA = await fetchData();
    render();
  } catch (e) {
    document.getElementById("main").innerHTML =
      `<div class="empty">Não foi possível carregar <code>data.json</code>.<br>
       Rode <code>python main.py</code> e depois recarregue.</div>`;
  }
}

function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleDateString("pt-BR",
      { day: "2-digit", month: "2-digit", year: "2-digit" });
  } catch { return iso?.slice(0, 10) || ""; }
}

/* menções de terceiros no período (base de toda a análise reputacional) */
function externalMentions() {
  return DATA.mentions.filter(m =>
    !m.is_owned && m.channel !== "indicador" && withinPeriod(m));
}

/* recalcula, no navegador, as agregações da capa para o período selecionado */
function overviewData() {
  const ext = externalMentions();
  const g = aggregate(ext);
  const bsd = {};
  ext.forEach(m => {
    const d = bsd[m.source] || (bsd[m.source] =
      { total: 0, positivo: 0, neutro: 0, negativo: 0 });
    d.total++; d[m.sentiment] = (d[m.sentiment] || 0) + 1;
  });
  const by_source_detail = Object.fromEntries(
    Object.entries(bsd).sort((a, b) => b[1].total - a[1].total));
  const bySrc = {};
  ext.forEach(m => { const k = m.author || m.domain || m.source; bySrc[k] = (bySrc[k] || 0) + 1; });
  const top_sources = Object.entries(bySrc).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const sources = new Set(ext.map(m => m.author || m.domain || m.source)).size;
  return {
    kpis: {
      total_mentions: g.total, positivo: g.positivo, neutro: g.neutro, negativo: g.negativo,
      net_sentiment: g.net, sources, ra_score: DATA.kpis.ra_score,
    },
    by_sentiment: { positivo: g.positivo, neutro: g.neutro, negativo: g.negativo },
    by_source_detail, top_sources, timeline: g.timeline,
  };
}

function render() {
  document.getElementById("generated").textContent =
    "Atualizado em " + new Date(DATA.generated_at).toLocaleString("pt-BR");
  setupFilters(DATA);
  document.querySelectorAll("#period .pb-opt").forEach(btn => {
    btn.classList.toggle("on", +btn.dataset.days === PERIOD_DAYS);
    btn.onclick = () => {
      PERIOD_DAYS = +btn.dataset.days || 0;
      document.querySelectorAll("#period .pb-opt").forEach(b =>
        b.classList.toggle("on", b === btn));
      renderAll();
    };
  });
  renderAll();
}

function renderAll() {
  OV = overviewData();
  const plabel = periodLabel();
  document.getElementById("lb").textContent = plabel;
  document.querySelectorAll(".src-lb").forEach(el => el.textContent = plabel);

  buildTabs();
  renderKpis(OV.kpis);
  renderConsumo(DATA.consumo);
  renderTimeline(OV.timeline);
  renderSentiment(OV.by_sentiment);
  renderSourceBreakdown(OV.by_source_detail);
  renderSources(OV.top_sources);
  renderTable();

  // mantém a aba atual se a fonte ainda tiver dados no período
  const sources = Object.keys(OV.by_source_detail);
  if (CURRENT_TAB !== "overview" && !sources.includes(CURRENT_TAB)) CURRENT_TAB = "overview";
  switchTab(CURRENT_TAB);
}

/* ---------------- ABAS ---------------- */
function buildTabs() {
  const nav = document.getElementById("tabs");
  const detail = OV.by_source_detail || {};
  const tabs = [
    `<button class="tab" data-tab="overview">📊 Geral
       <span class="tab-n">${OV.kpis.total_mentions}</span></button>`,
  ];
  for (const [src, v] of Object.entries(detail)) {
    tabs.push(
      `<button class="tab" data-tab="${src}">${srcIcon(src)} ${srcLabel(src)}
         <span class="tab-n">${v.total}</span>
       </button>`);
  }
  nav.innerHTML = tabs.join("");
  nav.querySelectorAll(".tab").forEach(el =>
    el.addEventListener("click", () => switchTab(el.dataset.tab)));
}

function switchTab(tab) {
  CURRENT_TAB = tab;
  document.querySelectorAll("#tabs .tab").forEach(el =>
    el.classList.toggle("active", el.dataset.tab === tab));
  const isOverview = tab === "overview";
  document.getElementById("view-overview").hidden = !isOverview;
  document.getElementById("view-source").hidden = isOverview;
  if (!isOverview) renderSourceDashboard(tab);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------------- VISÃO GERAL ---------------- */
function kpi(label, value, cls = "", sub = "", act = "") {
  return `<div class="kpi ${cls}${act ? " kpi-click" : ""}"${act ? ` data-act="${act}" title="Ver menções"` : ""}>
    <div class="label">${label}</div>
    <div class="value">${value}</div>
    ${sub ? `<div class="sub">${sub}</div>` : ""}
  </div>`;
}

function renderKpis(k) {
  const html = [
    kpi("Menções (terceiros)", k.total_mentions, "", `${k.sources} fontes distintas`, "all"),
    kpi("Positivas", k.positivo, "pos", pct(k.positivo, k.total_mentions), "s:positivo"),
    kpi("Neutras", k.neutro, "", pct(k.neutro, k.total_mentions), "s:neutro"),
    kpi("Negativas", k.negativo, "neg", pct(k.negativo, k.total_mentions), "s:negativo"),
  ].join("");
  const box = document.getElementById("kpis");
  box.innerHTML = html;
  box.querySelectorAll(".kpi-click").forEach(el =>
    el.addEventListener("click", () => applyOverviewKpi(el.dataset.act)));
}

function applyOverviewKpi(act) {
  ["q", "fSource", "fChannel", "fSentiment"].forEach(id => document.getElementById(id).value = "");
  OV_DATE = null;
  OV_EXTERNAL = true; // os KPIs contam terceiros → a tabela reflete só terceiros
  if (act && act.startsWith("s:")) document.getElementById("fSentiment").value = act.slice(2);
  renderTable();
  focusTable("mentionsTable");
}

function renderTimeline(tl) {
  drawTimeline("timeline", "timelineChart", tl, (date, sentiment) => {
    OV_DATE = date;
    if (sentiment) document.getElementById("fSentiment").value = sentiment;
    renderTable();
    focusTable("mentionsTable");
  });
}

function renderSentiment(bs) {
  drawSentiment("sentiment", "sentimentChart", bs, (sentiment) => {
    document.getElementById("fSentiment").value = sentiment;
    renderTable();
    focusTable("mentionsTable");
  });
}

function focusTable(id) {
  document.getElementById(id).scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderSourceBreakdown(detail) {
  const box = document.getElementById("sourceBreakdown");
  const entries = Object.entries(detail);
  if (!entries.length) { box.innerHTML = `<p class="muted">sem dados</p>`; return; }
  const max = Math.max(...entries.map(([, v]) => v.total));
  box.innerHTML = entries.map(([src, v]) => {
    const p = (n) => v.total ? (n / v.total * 100).toFixed(1) : 0;
    const w = (v.total / max * 100).toFixed(1);
    return `
      <div class="src-row" data-src="${src}" title="Abrir dashboard de ${srcLabel(src)}">
        <div class="src-head">
          <span class="src-name">${srcIcon(src)} ${srcLabel(src)}</span>
          <span class="src-total">${v.total}</span>
        </div>
        <div class="src-bar" style="width:${w}%">
          <span style="width:${p(v.positivo)}%" class="b-pos"></span>
          <span style="width:${p(v.neutro)}%" class="b-neu"></span>
          <span style="width:${p(v.negativo)}%" class="b-neg"></span>
        </div>
      </div>`;
  }).join("");
  box.querySelectorAll(".src-row").forEach(el =>
    el.addEventListener("click", () => switchTab(el.dataset.src)));
}

function renderSources(top) {
  const ul = document.getElementById("sources");
  ul.innerHTML = top.length
    ? top.map(([name, n]) => `<li class="clickable" data-name="${esc(name || "")}" title="Filtrar por ${esc(name || "—")}"><span>${esc(name || "—")}</span><span class="n">${n}</span></li>`).join("")
    : `<li class="muted">sem dados</li>`;
  ul.querySelectorAll("li.clickable").forEach(el => el.addEventListener("click", () => {
    document.getElementById("q").value = el.dataset.name;
    renderTable();
    focusTable("mentionsTable");
  }));
}

/* ---------------- DASHBOARD POR FONTE ---------------- */
function aggregate(rows) {
  const g = { total: rows.length, positivo: 0, neutro: 0, negativo: 0 };
  const daily = {};
  const byAuthor = {};
  for (const m of rows) {
    g[m.sentiment] = (g[m.sentiment] || 0) + 1;
    const day = (m.published_at || "").slice(0, 10);
    (daily[day] ||= { total: 0, positivo: 0, neutro: 0, negativo: 0 });
    daily[day].total++;
    daily[day][m.sentiment] = (daily[day][m.sentiment] || 0) + 1;
    const a = m.author || m.domain || "—";
    byAuthor[a] = (byAuthor[a] || 0) + 1;
  }
  g.net = g.total ? Math.round(((g.positivo - g.negativo) / g.total) * 100 * 10) / 10 : 0;
  g.timeline = Object.keys(daily).sort().map(k => ({ date: k, ...daily[k] }));
  g.topAuthors = Object.entries(byAuthor).sort((a, b) => b[1] - a[1]).slice(0, 12);
  return g;
}

function renderSourceDashboard(src) {
  SRC_DATE = null; SRC_THEME = null; // cada fonte começa sem filtros de drill-down
  const rows = externalMentions().filter(m => m.source === src);
  const g = aggregate(rows);

  // hero
  const raScore = src === "reclame_aqui" && DATA.kpis.ra_score
    ? DATA.kpis.ra_score.replace("Reputação no Reclame Aqui: ", "") : null;
  document.getElementById("srcHero").innerHTML = `
    <div class="hero-icon">${srcIcon(src)}</div>
    <div class="hero-text">
      <h2>${srcLabel(src)}</h2>
      <p>${g.total} menção(ões) de terceiros · ${periodLabel()}</p>
    </div>
    ${raScore ? `<div class="hero-badge">${raScore}</div>` : ""}`;

  // kpis
  const skBox = document.getElementById("srcKpis");
  skBox.innerHTML = [
    kpi("Menções", g.total, "", "", "all"),
    kpi("Positivas", g.positivo, "pos", pct(g.positivo, g.total), "s:positivo"),
    kpi("Neutras", g.neutro, "", pct(g.neutro, g.total), "s:neutro"),
    kpi("Negativas", g.negativo, "neg", pct(g.negativo, g.total), "s:negativo"),
  ].join("");
  skBox.querySelectorAll(".kpi-click").forEach(el =>
    el.addEventListener("click", () => applySourceKpi(el.dataset.act)));

  drawTimeline("srcTimeline", "srcTimelineChart", g.timeline, (date, sentiment) => {
    SRC_DATE = date;
    if (sentiment) document.getElementById("srcFSentiment").value = sentiment;
    renderSourceTable(SRC_ROWS);
    focusTable("srcMentionsTitle");
  });
  drawSentiment("srcSentiment", "srcSentimentChart", g, (sentiment) => {
    document.getElementById("srcFSentiment").value = sentiment;
    renderSourceTable(SRC_ROWS);
    focusTable("srcMentionsTitle");
  });

  // top autores
  document.getElementById("srcTopTitle").textContent =
    src === "google_news" ? "Principais veículos" : "Principais autores/perfis";
  const topUl = document.getElementById("srcTop");
  topUl.innerHTML = g.topAuthors.length
    ? g.topAuthors.map(([name, n]) =>
      `<li class="clickable" data-name="${esc(name)}" title="Filtrar por ${esc(name)}"><span>${esc(name)}</span><span class="n">${n}</span></li>`).join("")
    : `<li class="muted">sem dados</li>`;
  topUl.querySelectorAll("li.clickable").forEach(el => el.addEventListener("click", () => {
    document.getElementById("srcQ").value = el.dataset.name;
    renderSourceTable(SRC_ROWS);
    focusTable("srcMentionsTitle");
  }));

  // destaques negativos (mais recentes)
  const negs = rows.filter(m => m.sentiment === "negativo")
    .sort((a, b) => (b.published_at || "").localeCompare(a.published_at || "")).slice(0, 6);
  document.getElementById("srcNeg").innerHTML = negs.length
    ? negs.map(m => `
      <div class="hl-item neg-item">
        <a href="${m.url}" target="_blank" rel="noopener">${esc(m.title)}</a>
        <div class="src">${fmtDate(m.published_at)} · ${esc(m.author || m.domain || "—")}</div>
      </div>`).join("")
    : `<p class="muted">Nenhuma menção negativa nesta fonte. 👍</p>`;

  // painel exclusivo do Reclame Aqui
  const raCard = document.getElementById("srcRAcard");
  if (src === "reclame_aqui") { raCard.hidden = false; renderRAProblems(rows); }
  else raCard.hidden = true;

  // tabela
  document.getElementById("srcMentionsTitle").textContent = `Menções — ${srcLabel(src)}`;
  setupSourceFilters(rows);
  renderSourceTable(rows);
}

function renderRAProblems(rows) {
  const total = rows.length;
  // taxa de resposta da empresa (prefixo [Respondida] / [Não respondida] no texto)
  let respondidas = 0, marcadas = 0;
  for (const m of rows) {
    const t = norm(m.text);
    if (t.includes("nao respondida")) marcadas++;
    else if (t.includes("respondida")) { respondidas++; marcadas++; }
  }
  const respRate = marcadas ? Math.round(respondidas / marcadas * 100) : null;
  const nota = DATA.kpis.ra_score
    ? DATA.kpis.ra_score.replace("Reputação no Reclame Aqui: ", "") : null;

  document.getElementById("raStats").innerHTML = [
    `<div class="ra-stat"><span class="v">${total}</span><span class="l">reclamações no período</span></div>`,
    respRate !== null ? `<div class="ra-stat"><span class="v">${respRate}%</span><span class="l">respondidas pela empresa</span></div>` : "",
    nota ? `<div class="ra-stat"><span class="v">${esc(nota)}</span><span class="l">reputação Reclame Aqui</span></div>` : "",
  ].join("");

  // conta por tema (uma reclamação pode entrar em mais de um tema)
  const counted = RA_THEMES.map(t => ({ ...t, n: rows.filter(m => matchTheme(m, t)).length }))
    .filter(t => t.n > 0).sort((a, b) => b.n - a.n);
  const max = counted.length ? Math.max(...counted.map(t => t.n)) : 0;

  const box = document.getElementById("raProblems");
  box.innerHTML = counted.length ? counted.map(t => `
    <div class="ra-row ${SRC_THEME === t.key ? "on" : ""}" data-theme="${t.key}" title="Filtrar por: ${t.label}">
      <div class="ra-label">${t.label}</div>
      <div class="ra-bar-wrap"><div class="ra-bar" style="width:${(t.n / max * 100).toFixed(1)}%"></div></div>
      <div class="ra-n">${t.n} <span class="muted">(${(t.n / total * 100).toFixed(0)}%)</span></div>
    </div>`).join("")
    : `<p class="muted">Sem reclamações categorizáveis no período.</p>`;

  box.querySelectorAll(".ra-row").forEach(el => el.addEventListener("click", () => {
    SRC_THEME = SRC_THEME === el.dataset.theme ? null : el.dataset.theme; // toggle
    renderRAProblems(SRC_ROWS);   // atualiza destaque ativo
    renderSourceTable(SRC_ROWS);
    focusTable("srcMentionsTitle");
  }));
}

function pct(n, total) { return total ? `${(n / total * 100).toFixed(0)}%` : "0%"; }

function applySourceKpi(act) {
  document.getElementById("srcQ").value = "";
  document.getElementById("srcFSentiment").value = "";
  SRC_DATE = null; SRC_THEME = null;
  if (!document.getElementById("srcRAcard").hidden) renderRAProblems(SRC_ROWS);
  if (act && act.startsWith("s:")) document.getElementById("srcFSentiment").value = act.slice(2);
  renderSourceTable(SRC_ROWS);
  focusTable("srcMentionsTitle");
}

let SRC_ROWS = [];
function setupSourceFilters(rows) {
  SRC_ROWS = rows;
  ["srcQ", "srcFSentiment"].forEach(id => {
    const el = document.getElementById(id);
    el.oninput = () => renderSourceTable(SRC_ROWS);
  });
  document.getElementById("srcClear").onclick = () => {
    document.getElementById("srcQ").value = "";
    document.getElementById("srcFSentiment").value = "";
    SRC_DATE = null; SRC_THEME = null;
    if (!document.getElementById("srcRAcard").hidden) renderRAProblems(SRC_ROWS);
    renderSourceTable(SRC_ROWS);
  };
}

function renderSourceTable(rows) {
  const q = document.getElementById("srcQ").value.toLowerCase();
  const se = document.getElementById("srcFSentiment").value;

  const theme = SRC_THEME ? RA_THEMES.find(t => t.key === SRC_THEME) : null;
  const filtered = rows.filter(m => {
    if (se && m.sentiment !== se) return false;
    if (SRC_DATE && (m.published_at || "").slice(0, 10) !== SRC_DATE) return false;
    if (theme && !matchTheme(m, theme)) return false;
    if (q && !((m.title + " " + (m.text || "") + " " + (m.author || "")).toLowerCase().includes(q))) return false;
    return true;
  }).sort((a, b) => (b.published_at || "").localeCompare(a.published_at || ""));

  document.getElementById("srcMentionsBody").innerHTML = filtered.slice(0, 500).map(m => `
    <tr>
      <td class="date">${fmtDate(m.published_at)}</td>
      <td>${esc(m.author || m.domain || "—")}</td>
      <td><a href="${m.url}" target="_blank" rel="noopener">${esc(m.title)}</a></td>
      <td><span class="s-${m.sentiment}" title="${m.sentiment}">●</span></td>
    </tr>`).join("") ||
    `<tr><td colspan="4" class="empty">Nenhuma menção com esses filtros.</td></tr>`;

  const bits = [];
  if (SRC_DATE) bits.push(`no dia ${fmtDate(SRC_DATE)}`);
  if (theme) bits.push(`tema "${theme.label}"`);
  const suffix = bits.length ? " · " + bits.join(" · ") : "";
  document.getElementById("srcTableInfo").innerHTML =
    `${filtered.length} menção(ões)${suffix} — exibindo até 500. Clique no título para abrir o link original.` +
    (SRC_DATE ? ` <button class="chip-clear" id="srcDateClear">✕ limpar dia</button>` : "") +
    (theme ? ` <button class="chip-clear" id="srcThemeClear">✕ limpar tema</button>` : "");
  if (SRC_DATE) document.getElementById("srcDateClear").onclick = () => { SRC_DATE = null; renderSourceTable(SRC_ROWS); };
  if (theme) document.getElementById("srcThemeClear").onclick = () => {
    SRC_THEME = null; renderRAProblems(SRC_ROWS); renderSourceTable(SRC_ROWS);
  };
}

/* ---------------- gráficos reutilizáveis (clicáveis) ---------------- */
const SENT_KEYS = ["positivo", "neutro", "negativo"];

function drawTimeline(key, canvasId, tl, onPick) {
  const ctx = document.getElementById(canvasId);
  charts[key]?.destroy();
  charts[key] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: tl.map(t => fmtDate(t.date)),
      datasets: [
        { label: "Positivo", data: tl.map(t => t.positivo), backgroundColor: COLORS.positivo, stack: "s" },
        { label: "Neutro", data: tl.map(t => t.neutro), backgroundColor: COLORS.neutro, stack: "s" },
        { label: "Negativo", data: tl.map(t => t.negativo), backgroundColor: COLORS.negativo, stack: "s" },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
      onClick: (e, els) => {
        if (!els.length || !onPick) return;
        const el = els[0];
        onPick(tl[el.index].date, SENT_KEYS[el.datasetIndex]);
      },
      plugins: {
        legend: { labels: { color: CHART_TICK, boxWidth: 12 } },
        tooltip: { footerColor: CHART_TICK, callbacks: { footer: () => "clique para ver as menções deste dia" } },
      },
      scales: {
        x: { stacked: true, ticks: { color: CHART_TICK, maxRotation: 0, autoSkip: true }, grid: { display: false } },
        y: { stacked: true, ticks: { color: CHART_TICK, precision: 0 }, grid: { color: CHART_GRID } },
      },
    },
  });
}

function drawSentiment(key, canvasId, bs, onPick) {
  const ctx = document.getElementById(canvasId);
  charts[key]?.destroy();
  charts[key] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: SENT_KEYS.map(l => l[0].toUpperCase() + l.slice(1)),
      datasets: [{
        data: SENT_KEYS.map(l => bs[l] || 0),
        backgroundColor: SENT_KEYS.map(l => COLORS[l]), borderWidth: 0,
      }],
    },
    options: {
      cutout: "62%",
      onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
      onClick: (e, els) => {
        if (!els.length || !onPick) return;
        onPick(SENT_KEYS[els[0].index]);
      },
      plugins: {
        legend: { position: "bottom", labels: { color: CHART_TICK, boxWidth: 12, padding: 12 } },
        tooltip: { footerColor: CHART_TICK, callbacks: { footer: () => "clique para filtrar por este sentimento" } },
      },
    },
  });
}

/* ---------------- tabela geral + filtros ---------------- */
function setupFilters(d) {
  const srcSel = document.getElementById("fSource");
  srcSel.length = 1; // preserva "Todas as fontes"
  const srcCount = {};
  d.mentions.forEach(m => { srcCount[m.source] = (srcCount[m.source] || 0) + 1; });
  Object.keys(srcCount).sort((a, b) => srcCount[b] - srcCount[a]).forEach(s => {
    const o = document.createElement("option");
    o.value = s; o.textContent = `${srcLabel(s)} (${srcCount[s]})`;
    srcSel.appendChild(o);
  });
  const chSel = document.getElementById("fChannel");
  chSel.length = 1;
  [...new Set(d.mentions.map(m => m.channel))].forEach(c => {
    const o = document.createElement("option");
    o.value = c; o.textContent = CHANNEL_LABEL[c] || c;
    chSel.appendChild(o);
  });
  ["q", "fSource", "fChannel", "fSentiment"].forEach(id =>
    document.getElementById(id).oninput = renderTable);
  document.getElementById("refresh").onclick = onRefresh;
  document.getElementById("clearFilters").onclick = () => {
    ["q", "fSource", "fChannel", "fSentiment"].forEach(id => document.getElementById(id).value = "");
    OV_DATE = null; OV_EXTERNAL = false;
    renderTable();
  };
}

function renderTable() {
  const q = document.getElementById("q").value.toLowerCase();
  const src = document.getElementById("fSource").value;
  const ch = document.getElementById("fChannel").value;
  const se = document.getElementById("fSentiment").value;

  const rows = DATA.mentions.filter(m => {
    if (!withinPeriod(m)) return false;
    if (OV_EXTERNAL && (m.is_owned || m.channel === "indicador")) return false;
    if (src && m.source !== src) return false;
    if (ch && m.channel !== ch) return false;
    if (se && m.sentiment !== se) return false;
    if (OV_DATE && (m.published_at || "").slice(0, 10) !== OV_DATE) return false;
    if (q && !((m.title + " " + (m.text || "") + " " + (m.author || "")).toLowerCase().includes(q))) return false;
    return true;
  });

  const body = document.getElementById("mentionsBody");
  body.innerHTML = rows.slice(0, 500).map(m => `
    <tr>
      <td class="date">${fmtDate(m.published_at)}</td>
      <td><span class="tag src-tag">${srcIcon(m.source)} ${srcLabel(m.source)}</span></td>
      <td>${esc(m.author || m.domain || "—")}${m.is_owned ? ' <span class="muted">(oficial)</span>' : ""}</td>
      <td><a href="${m.url}" target="_blank" rel="noopener">${esc(m.title)}</a></td>
      <td><span class="s-${m.sentiment}" title="${m.sentiment}">●</span></td>
    </tr>`).join("") ||
    `<tr><td colspan="5" class="empty">Nenhuma menção com esses filtros.</td></tr>`;

  const parts = [];
  if (OV_EXTERNAL) parts.push("de terceiros");
  if (src) parts.push(`de ${srcLabel(src)}`);
  if (OV_DATE) parts.push(`no dia ${fmtDate(OV_DATE)}`);
  const label = parts.length ? " " + parts.join(" ") : "";
  document.getElementById("tableInfo").innerHTML =
    `${rows.length} menção(ões)${label} — exibindo até 500. Clique no título para abrir o link original.` +
    (OV_DATE ? ` <button class="chip-clear" id="ovDateClear">✕ limpar dia</button>` : "");
  if (OV_DATE) document.getElementById("ovDateClear").onclick = () => { OV_DATE = null; renderTable(); };
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* ---------------- mapa de consumo ----------------
   Verba reservada às coletas pagas (redes sociais e Reclame Aqui) e quanto
   dela o ciclo já consumiu. Medido na hora da coleta e lido do data.json. */
const usd = (v) => "US$ " + Number(v).toLocaleString("pt-BR",
  { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const diaMes = (iso) => new Date(iso).toLocaleDateString("pt-BR",
  { day: "2-digit", month: "2-digit" });

function renderConsumo(c) {
  const box = document.getElementById("consumoMeter");
  if (!box) return;
  if (!c || !c.orcamento_usd) { box.innerHTML = ""; return; }

  const usadoPct = Math.min(100, (c.gasto_usd / c.orcamento_usd) * 100);
  /* estado: cor + palavra (nunca só cor) */
  const estado = c.freado || usadoPct >= 100 ? { cls: "crit", txt: "Verba esgotada" }
    : usadoPct >= 85 ? { cls: "crit", txt: "No limite" }
      : usadoPct >= 60 ? { cls: "warn", txt: "Atenção" }
        : { cls: "ok", txt: "Folga" };

  const renova = c.ciclo_fim ? ` · renova em ${diaMes(c.ciclo_fim)}` : "";
  /* a barra mostra o CONSUMIDO — dito em texto para não depender da cor */
  let rodape = "A barra mostra o consumo do ciclo.";
  if (c.freado) {
    rodape += " Verba do ciclo esgotada: as coletas seguem só com as fontes grátis" +
      (c.ciclo_fim ? ` até ${diaMes(c.ciclo_fim)}.` : ".");
  } else if (c.custo_coleta_usd) {
    rodape += ` Última coleta completa: ≈ ${usd(c.custo_coleta_usd)}` +
      (c.coletas_restantes
        ? ` — cabem cerca de ${c.coletas_restantes} coleta${c.coletas_restantes > 1 ? "s" : ""} até o fim do ciclo.`
        : " — sem verba para outra coleta completa neste ciclo.");
  }

  box.innerHTML = `
    <div class="meter-card">
      <div class="meter-head">
        <span class="meter-label">Mapa de consumo
          <span class="hint">(verba das coletas em redes sociais e Reclame Aqui)</span></span>
        <span class="meter-state m-${estado.cls}">● ${estado.txt}</span>
      </div>
      <div class="meter-nums">
        <span><strong class="meter-hero">${usd(c.restante_usd)}</strong> disponíveis</span>
        <span class="meter-right">${usd(c.gasto_usd)} de ${usd(c.orcamento_usd)} usados${renova}</span>
      </div>
      <div class="meter-track" role="img"
           aria-label="${usadoPct.toFixed(0)}% da verba do ciclo consumida">
        <div class="meter-fill m-${estado.cls}" style="width:${usadoPct.toFixed(1)}%"></div>
      </div>
      <p class="meter-foot">${esc(rodape)}</p>
    </div>`;
}

/* =======================================================================
   COLETA REMOTA — o botão "Atualizar" dispara o workflow do GitHub Actions
   ("Coleta Radar GBOEX"), espera a coleta terminar e recarrega o painel.
   Sem token salvo, o botão apenas rebusca o data.json publicado.
   ======================================================================= */
const GH = {
  owner: "olaesparta-boop",
  repo: "radar-gboex",
  workflow: "coleta.yml",
  ref: "main",
};
const GH_TOKEN_KEY = "radar_gboex_gh_token";
const GH_MODE_KEY = "radar_gboex_modo";

const ghToken = () => localStorage.getItem(GH_TOKEN_KEY) || "";
const ghModoGratis = () => localStorage.getItem(GH_MODE_KEY) === "gratis";
/* a coleta remota só faz sentido no painel publicado: rodando local, o
   data.json que o navegador lê é o do seu computador, não o do GitHub */
const podeColetar = () => !!ghToken() && /github\.io$/.test(location.hostname);

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function status(msg, { erro = false, girando = false } = {}) {
  const el = document.getElementById("refreshStatus");
  if (!el) return;
  if (!msg) { el.hidden = true; el.innerHTML = ""; return; }
  el.hidden = false;
  el.className = "rf-status" + (erro ? " err" : "");
  el.innerHTML = (girando ? '<span class="spin"></span>' : "") + esc(msg);
}

async function ghApi(caminho, opcoes = {}) {
  const res = await fetch("https://api.github.com" + caminho, {
    ...opcoes,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: "Bearer " + ghToken(),
      "X-GitHub-Api-Version": "2022-11-28",
      ...(opcoes.body ? { "Content-Type": "application/json" } : {}),
      ...(opcoes.headers || {}),
    },
  });
  if (res.status === 401) throw new Error("Token inválido ou expirado.");
  if (res.status === 403) throw new Error("Token sem permissão de Actions neste repositório.");
  if (res.status === 404) throw new Error("Repositório/workflow não encontrado para este token.");
  if (!res.ok && res.status !== 204) {
    let detalhe = "";
    try { detalhe = (await res.json()).message || ""; } catch { /* sem corpo */ }
    throw new Error(`GitHub respondeu ${res.status}${detalhe ? ": " + detalhe : ""}.`);
  }
  return res.status === 204 ? null : res.json();
}

/* dispara o workflow e devolve a execução criada (a API do dispatch não
   retorna o id, então procuramos a execução mais nova depois do disparo) */
async function dispararColeta() {
  const base = `/repos/${GH.owner}/${GH.repo}`;
  const marco = Date.now() - 60000;   // margem p/ relógio do GitHub

  await ghApi(`${base}/actions/workflows/${GH.workflow}/dispatches`, {
    method: "POST",
    body: JSON.stringify({
      ref: GH.ref,
      inputs: { modo: ghModoGratis() ? "gratis" : "completa" },
    }),
  });

  for (let i = 0; i < 15; i++) {
    await sleep(4000);
    const r = await ghApi(`${base}/actions/workflows/${GH.workflow}/runs?event=workflow_dispatch&per_page=5`);
    const run = (r.workflow_runs || []).find(w => Date.parse(w.created_at) >= marco);
    if (run) return run;
    status("Coleta na fila…", { girando: true });
  }
  throw new Error("A coleta foi pedida, mas a execução não apareceu. Veja a aba Actions.");
}

async function esperarFim(runId) {
  const base = `/repos/${GH.owner}/${GH.repo}`;
  const inicio = Date.now();
  while (Date.now() - inicio < 20 * 60000) {
    const run = await ghApi(`${base}/actions/runs/${runId}`);
    if (run.status === "completed") return run;
    const min = Math.floor((Date.now() - inicio) / 60000);
    const seg = Math.floor(((Date.now() - inicio) % 60000) / 1000);
    status(`Coletando menções… ${min}:${String(seg).padStart(2, "0")}`, { girando: true });
    await sleep(6000);
  }
  throw new Error("A coleta passou de 20 minutos. Acompanhe pela aba Actions.");
}

/* o GitHub Pages leva ~1 min para republicar: esperamos o data.json mudar */
async function esperarPublicacao(geradoAntes) {
  const limite = Date.now() + 5 * 60000;
  while (Date.now() < limite) {
    try {
      const novo = await fetchData();
      if (novo.generated_at !== geradoAntes) { DATA = novo; render(); return true; }
    } catch { /* publicação em andamento */ }
    status("Publicando o painel…", { girando: true });
    await sleep(8000);
  }
  return false;
}

let coletando = false;

async function onRefresh() {
  if (coletando) return;
  const btn = document.getElementById("refresh");

  if (!podeColetar()) {
    status("Buscando dados…", { girando: true });
    await load();
    status("");
    if (!ghToken() && /github\.io$/.test(location.hostname)) {
      status("Só recarreguei os dados publicados. Configure em ⚙ para coletar na hora.");
      setTimeout(() => status(""), 9000);
    }
    return;
  }

  coletando = true;
  btn.disabled = true;
  const geradoAntes = DATA?.generated_at;
  try {
    status("Pedindo uma coleta nova…", { girando: true });
    const run = await dispararColeta();
    const fim = await esperarFim(run.id);
    if (fim.conclusion !== "success") {
      throw new Error(`A coleta terminou como "${fim.conclusion}". Veja o log na aba Actions.`);
    }
    status("Coleta pronta, publicando…", { girando: true });
    const ok = await esperarPublicacao(geradoAntes);
    status(ok ? "Painel atualizado ✓" : "Coleta feita, mas o painel ainda não republicou. Tente Atualizar em 1 min.",
      { erro: !ok });
    setTimeout(() => status(""), 9000);
  } catch (e) {
    status(e.message || "Falha ao atualizar.", { erro: true });
  } finally {
    coletando = false;
    btn.disabled = false;
  }
}

function setupColetaRemota() {
  const modal = document.getElementById("ghModal");
  if (!modal) return;
  const input = document.getElementById("ghTokenInput");
  const gratis = document.getElementById("ghFree");
  const abrir = () => {
    input.value = ghToken();
    gratis.checked = ghModoGratis();
    modal.hidden = false;
  };
  const fechar = () => { modal.hidden = true; };

  document.getElementById("ghConfig").onclick = abrir;
  document.getElementById("ghClose").onclick = fechar;
  modal.onclick = (e) => { if (e.target === modal) fechar(); };
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") fechar(); });

  document.getElementById("ghSave").onclick = () => {
    const t = input.value.trim();
    if (t) localStorage.setItem(GH_TOKEN_KEY, t); else localStorage.removeItem(GH_TOKEN_KEY);
    localStorage.setItem(GH_MODE_KEY, gratis.checked ? "gratis" : "completa");
    fechar();
    status(t ? "Coleta remota ativada. Use ↻ Atualizar." : "Token removido.");
    setTimeout(() => status(""), 6000);
  };
  document.getElementById("ghForget").onclick = () => {
    localStorage.removeItem(GH_TOKEN_KEY);
    input.value = "";
    fechar();
    status("Token removido.");
    setTimeout(() => status(""), 6000);
  };

  document.getElementById("refresh").title = podeColetar()
    ? "Disparar uma coleta nova no GitHub e recarregar o painel"
    : "Recarregar os dados publicados (configure em ⚙ para coletar na hora)";
}

setupColetaRemota();
load();
