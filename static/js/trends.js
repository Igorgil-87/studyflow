/* ═══════════════════════════════════════════════════════
   trends.js — Tendências Globais · multi-IA SSE pipeline
   ═══════════════════════════════════════════════════════ */

'use strict';

// ── helpers ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};

// ── state ─────────────────────────────────────────────────────────────────────
let eventSource = null;
let activeCat   = 'todos';
const renderedCards = [];   // legado (não usado no layout editorial)
let allTrends   = [];       // {category, trend} — fonte do layout editorial

// ── pipeline step map ─────────────────────────────────────────────────────────
const STEP_EL = {
  coleta:  'pipColeta',
  analise: 'pipAnalise',
  sintese: 'pipSintese',
};

const CAT_ICONS = {
  esportes: '⚽', games: '🎮', politica: '🏛', beleza: '💄', fitness: '💪', economia: '📈',
  ciencia: '🔬', cultura: '🎭', historia: '📜',
};

const CAT_LABELS = {
  esportes: 'Esportes', games: 'Games', politica: 'Política', beleza: 'Beleza', fitness: 'Mundo Fitness', economia: 'Economia',
  ciencia: 'Ciência', cultura: 'Cultura', historia: 'História',
};

// ── category progress dots ────────────────────────────────────────────────────
const catDots = {};

function initCatDots(cats) {
  const bar = $('catProgress');
  if (!bar) return;
  bar.innerHTML = '';
  cats.forEach(cat => {
    const dot = el('span', 'gt-cat-dot', `${CAT_ICONS[cat] || '•'} ${CAT_LABELS[cat] || cat}`);
    dot.dataset.cat = cat;
    bar.appendChild(dot);
    catDots[cat] = dot;
  });
}

function markCatDone(cat) {
  if (catDots[cat]) catDots[cat].classList.add('done');
}

// ── pipeline step update ─────────────────────────────────────────────────────
function setStep(step, status, detail) {
  const stepEl = $(STEP_EL[step]);
  if (!stepEl) return;
  stepEl.classList.remove('running', 'done', 'error');
  stepEl.classList.add(status);
  if (detail) {
    const d = stepEl.querySelector('.step-detail');
    if (d) d.textContent = detail;
  }
}

// ── trend card HTML ───────────────────────────────────────────────────────────
function scoreBar(label, value, cls) {
  const pct = Math.round((value / 10) * 100);
  return `
    <div class="gt-score-row">
      <span class="gt-score-label">${label}</span>
      <div class="gt-score-track">
        <div class="gt-score-fill ${cls}" style="width:${pct}%"></div>
      </div>
      <span class="gt-score-val">${value}</span>
    </div>`;
}

function buildTrendCard(category, trend) {
  const card = el('div', 'gt-trend-card');
  card.dataset.cat = category;

  const hashtags = (trend.hashtags || [])
    .map(h => `<span class="gt-tag">#${h.replace(/^#/, '')}</span>`).join('');

  const podcasts = (trend.podcasts || [])
    .map(p => `<span class="gt-podcast-chip">🎙 ${p}</span>`).join('');

  const catIcon  = CAT_ICONS[category]  || '•';
  const catLabel = CAT_LABELS[category] || category;

  const links = (trend.links || []).filter(l => l && l.url).slice(0, 4);
  const linksHtml = links.length ? `
    <div class="gt-card-section">
      <div class="gt-card-section-label">FONTES</div>
      <div class="gt-sources">
        ${links.map(l => {
          let host = ''; try { host = new URL(l.url).hostname.replace('www.',''); } catch {}
          const label = (l.title && l.title.length > 3) ? l.title : (host || 'fonte');
          return `<a class="gt-source" href="${l.url}" target="_blank" rel="noopener" title="${(l.title||'').replace(/"/g,'')}">🔗 ${label.length > 48 ? label.slice(0,48)+'…' : label}</a>`;
        }).join('')}
      </div>
    </div>` : '';

  card.innerHTML = `
    <div class="gt-card-head">
      <span class="gt-cat-pill">${catIcon} ${catLabel}</span>
    </div>
    <h3 class="gt-card-title">${trend.titulo || ''}</h3>
    <p  class="gt-card-insight">${trend.insight || ''}</p>

    <div class="gt-card-section">
      <div class="gt-card-section-label">ÂNGULO PARA CRIADORES</div>
      <p class="gt-card-angulo">${trend.angulo || ''}</p>
    </div>

    <div class="gt-scores">
      ${scoreBar('Viral', trend.viral_score || 0, 'viral')}
      ${scoreBar('Oportunidade', trend.oportunidade_score || 0, 'oport')}
      ${scoreBar('Polêmica', trend.polemica_score || 0, 'polemica')}
    </div>

    ${hashtags ? `<div class="gt-tags">${hashtags}</div>` : ''}
    ${podcasts  ? `<div class="gt-podcasts">${podcasts}</div>` : ''}
    ${linksHtml}

    <button class="gt-create-btn" data-titulo="${encodeURIComponent(trend.titulo || '')}" data-cat="${encodeURIComponent(catLabel || '')}">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
      Criar conteúdo sobre isso
    </button>
  `;

  card.querySelector('.gt-create-btn').addEventListener('click', () => {
    const briefing = {
      titulo: trend.titulo || '',
      categoria: catLabel || '',
      insight: trend.insight || '',
      angulo: trend.angulo || '',
      hashtags: trend.hashtags || [],
      viral_score: trend.viral_score || 0,
      oportunidade_score: trend.oportunidade_score || 0,
      polemica_score: trend.polemica_score || 0,
    };
    try {
      localStorage.setItem('yt_trend_briefing', JSON.stringify(briefing));
      // compat com a versão anterior
      localStorage.setItem('yt_trend_topic', briefing.titulo);
      localStorage.setItem('yt_trend_niche', briefing.categoria);
    } catch { /* */ }
    window.location.href = '/youtuber';
  });

  return card;
}

// ── cross-theme card ──────────────────────────────────────────────────────────
function buildCrossCard(theme) {
  const cats = (theme.categorias || [])
    .map(c => `<span class="gt-cross-cat">${c}</span>`).join('');
  const card = el('div', 'gt-cross-card');
  card.innerHTML = `
    <div class="gt-cross-title">${theme.tema || ''}</div>
    <p class="gt-cross-exp">${theme.explicacao || ''}</p>
    ${cats ? `<div class="gt-cross-cats">${cats}</div>` : ''}
  `;
  return card;
}

// ── category filter ───────────────────────────────────────────────────────────
function applyFilter(cat) {
  activeCat = cat;
  document.querySelectorAll('.gt-cat-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.cat === cat);
  });
  renderEditorial();
  updateTrendsHeader();
}

// ── Layout editorial: hero + manchetes empilhadas (estilo jornal) ──
function renderEditorial() {
  const grid = $('gtTrendsGrid');
  if (!grid) return;
  let items = allTrends.slice();
  if (activeCat !== 'todos') items = items.filter(i => i.category === activeCat);
  items.sort((a, b) => (b.trend.viral_score || 0) - (a.trend.viral_score || 0));

  if (!items.length) { grid.innerHTML = ''; return; }

  const hero = items[0];
  const rest = items.slice(1);

  grid.className = 'nx-portal';
  grid.innerHTML = '';

  // manchete de destaque (largura total)
  grid.appendChild(buildHero(hero.category, hero.trend));

  // demais tendências em GRADE de cards (preenche a largura)
  if (rest.length) {
    const sec = el('section', 'nx-portal-section');
    sec.innerHTML = '<div class="nx-portal-head"><span class="nx-kicker-red">MAIS TENDÊNCIAS</span></div>';
    const cardGrid = el('div', 'nx-card-grid');
    rest.forEach(({ category, trend }) => cardGrid.appendChild(buildTrendNewsCard(category, trend)));
    sec.appendChild(cardGrid);
    grid.appendChild(sec);
  }
}

// card de tendência estilo "TREND INSIGHTS" (badge + thumb + título + métricas)
function buildTrendNewsCard(category, trend) {
  const card = el('article', 'ti-card');
  const icon = CAT_ICONS[category] || '•';
  const label = (CAT_LABELS[category] || category);
  const score = trend.viral_score || 0;

  // badge de status conforme o score (estilo do design system)
  let badge = '<span class="ti-badge ti-badge-hot">🔥 EM ALTA</span>';
  if (score >= 90) badge = '<span class="ti-badge ti-badge-live">● AO VIVO</span>';
  else if (score >= 75) badge = '<span class="ti-badge ti-badge-up">↗ SUBINDO</span>';
  else badge = '<span class="ti-badge ti-badge-new">☆ NOVO</span>';

  const insight = (trend.insight || '').slice(0, 120);
  card.innerHTML = `
    <div class="ti-card-thumb">
      ${badge}
      <span class="ti-card-thumb-emoji">${icon}</span>
    </div>
    <div class="ti-card-body">
      <h3 class="ti-card-title">${escapeHtml(trend.titulo || '')}</h3>
      <p class="ti-card-sub">${escapeHtml(insight)}${(trend.insight || '').length > 120 ? '…' : ''}</p>
      <div class="ti-card-meta">
        <span class="ti-card-source">${icon} ${escapeHtml(label)}</span>
        <span class="ti-card-score">🔥 ${score}</span>
      </div>
      ${_sourceLinks(trend)}
      <div class="ti-card-foot">
        <span class="ti-card-trend">↗ Em alta agora</span>
        <button class="ti-card-cta">Criar conteúdo</button>
      </div>
    </div>`;
  card.querySelector('.ti-card-cta').addEventListener('click', () => _goCreate(category, trend));
  card.querySelector('.ti-card-title').addEventListener('click', () => _goCreate(category, trend));
  return card;
}

function _briefingFromTrend(category, trend) {
  return {
    titulo: trend.titulo || '', categoria: CAT_LABELS[category] || category,
    insight: trend.insight || '', angulo: trend.angulo || '',
    hashtags: trend.hashtags || [], viral_score: trend.viral_score || 0,
    oportunidade_score: trend.oportunidade_score || 0,
    polemica_score: trend.polemica_score || 0,
  };
}

function _goCreate(category, trend) {
  try {
    const b = _briefingFromTrend(category, trend);
    localStorage.setItem('yt_trend_briefing', JSON.stringify(b));
    localStorage.setItem('yt_trend_topic', b.titulo);
    localStorage.setItem('yt_trend_niche', b.categoria);
  } catch { /* */ }
  window.location.href = '/youtuber';
}

function _sourceLinks(trend) {
  const links = (trend.links || []).filter(l => l && l.url).slice(0, 4);
  if (!links.length) return '';
  return `<div class="nx-sources">${links.map(l => {
    let host = ''; try { host = new URL(l.url).hostname.replace('www.', ''); } catch {}
    const label = (l.title && l.title.length > 3) ? l.title : (host || 'fonte');
    return `<a class="nx-source" href="${l.url}" target="_blank" rel="noopener">${escapeHtml(label.length > 46 ? label.slice(0,46)+'…' : label)}</a>`;
  }).join('')}</div>`;
}

function buildHero(category, trend) {
  const wrap = el('article', 'nx-hero');
  const icon = CAT_ICONS[category] || '•';
  const label = (CAT_LABELS[category] || category).toUpperCase();
  const score = trend.viral_score || 0;
  wrap.innerHTML = `
    <div class="nx-hero-kicker"><span class="nx-kicker-red">${icon} ${escapeHtml(label)}</span>
      <span class="nx-hero-badge">DESTAQUE</span></div>
    <h2 class="nx-hero-title">${escapeHtml(trend.titulo || '')}</h2>
    <p class="nx-hero-standfirst">${escapeHtml(trend.insight || '')}</p>
    ${trend.angulo ? `<p class="nx-hero-angle"><span class="nx-angle-tag">ÂNGULO</span> ${escapeHtml(trend.angulo)}</p>` : ''}
    <div class="nx-hero-meta">
      <span class="nx-metric"><b>${score}</b> viral</span>
      ${trend.oportunidade_score ? `<span class="nx-metric"><b>${trend.oportunidade_score}</b> oportunidade</span>` : ''}
      ${trend.polemica_score ? `<span class="nx-metric nx-metric-hot"><b>${trend.polemica_score}</b> polêmica</span>` : ''}
    </div>
    ${_sourceLinks(trend)}
    <button class="nx-cta">▶ Criar conteúdo sobre isso</button>`;
  wrap.querySelector('.nx-cta').addEventListener('click', () => _goCreate(category, trend));
  return wrap;
}

function buildHeadlineRow(category, trend) {
  const row = el('article', 'nx-headline');
  const icon = CAT_ICONS[category] || '•';
  const label = (CAT_LABELS[category] || category).toUpperCase();
  const score = trend.viral_score || 0;
  row.innerHTML = `
    <div class="nx-headline-main">
      <div class="nx-headline-kicker"><span class="nx-kicker-red">${icon} ${escapeHtml(label)}</span>
        <span class="nx-headline-score">${score} viral</span></div>
      <h3 class="nx-headline-title">${escapeHtml(trend.titulo || '')}</h3>
      <p class="nx-headline-sub">${escapeHtml(trend.insight || '')}</p>
      ${_sourceLinks(trend)}
    </div>
    <button class="nx-headline-cta" title="Criar conteúdo">＋</button>`;
  row.querySelector('.nx-headline-cta').addEventListener('click', () => _goCreate(category, trend));
  row.querySelector('.nx-headline-title').addEventListener('click', () => _goCreate(category, trend));
  return row;
}

function updateTrendsHeader() {
  const visible = allTrends.filter(
    c => activeCat === 'todos' || c.category === activeCat
  ).length;
  const labelEl = $('trendsHeaderLabel');
  const countEl = $('trendsHeaderCount');
  const headerEl = $('trendsHeader');
  if (!labelEl) return;
  if (activeCat === 'todos') {
    labelEl.textContent = 'TODAS AS CATEGORIAS';
  } else {
    labelEl.textContent = `${CAT_ICONS[activeCat] || ''} ${(CAT_LABELS[activeCat] || activeCat).toUpperCase()}`;
  }
  if (countEl) countEl.textContent = `${visible} tendência${visible !== 1 ? 's' : ''}`;
  if (headerEl) headerEl.hidden = visible === 0;
}

// ── show / hide sections ──────────────────────────────────────────────────────
function showPipeline() {
  $('gtPipeline').hidden = false;
  $('gtEmpty').hidden    = true;
  $('gtError').hidden    = true;
}

function showResults() {
  $('gtResults').hidden  = false;
  $('trendsHeader').hidden = false;
}

function showError(msg) {
  const box = $('gtError');
  box.textContent = msg;
  box.hidden = false;
  $('gtPipeline').hidden = true;
}

function resetUI() {
  // clear cards
  renderedCards.length = 0;
  allTrends = [];
  $('gtTrendsGrid').innerHTML = '';
  $('gtCrossGrid').innerHTML  = '';
  $('gtSummaryText').textContent = '';
  $('gtSummaryCard').hidden  = true;
  $('gtCrossThemes').hidden  = true;
  $('gtResults').hidden      = true;
  $('trendsHeader').hidden   = true;
  $('gtError').hidden        = true;
  $('gtEmpty').hidden        = true;

  // reset pipeline steps
  ['pipColeta', 'pipAnalise', 'pipSintese'].forEach(id => {
    const el = $(id);
    if (el) {
      el.classList.remove('running', 'done', 'error');
      const d = el.querySelector('.step-detail');
      if (d) d.textContent = '';
    }
  });

  Object.keys(catDots).forEach(k => delete catDots[k]);
}

// ── main pipeline start ───────────────────────────────────────────────────────
async function startAnalysis() {
  if (eventSource) eventSource.close();

  const btn   = $('analyzeBtn');
  const label = $('analyzeBtnLabel');
  btn.disabled = true;
  label.textContent = 'Analisando…';

  resetUI();
  showPipeline();

  // get selected cats from active filter (default: all)
  const cats = activeCat === 'todos'
    ? ['esportes', 'games', 'politica', 'ciencia', 'cultura', 'historia', 'beleza', 'fitness', 'economia']
    : [activeCat];

  initCatDots(cats);

  let jobId;
  try {
    const urlsRaw = ($('gtCrawlUrls')?.value || '').trim();
    const urls = urlsRaw ? urlsRaw.split(',').map((u) => u.trim()).filter(Boolean) : [];

    const res = await fetch('/api/trends/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ categories: cats, urls }),
    });
    const data = await res.json();
    if (!res.ok || !data.job_id) throw new Error(data.error || 'Erro ao iniciar análise');
    jobId = data.job_id;
  } catch (err) {
    showError(err.message);
    btn.disabled = false;
    label.textContent = 'Analisar Tendências Globais';
    return;
  }

  eventSource = new EventSource(`/api/stream/${jobId}`);

  eventSource.addEventListener('progress', e => {
    const d = JSON.parse(e.data);
    setStep(d.step, d.status, d.detail);
    if (d.step === 'analise' && d.status === 'running') showResults();
  });

  eventSource.addEventListener('category_ready', e => {
    const d = JSON.parse(e.data);
    const cat = d.category;
    const trends = d.trends || [];

    trends.forEach(trend => {
      allTrends.push({ category: cat, trend });
      if (trend.titulo) nxAddHeadline(CAT_ICONS[cat] || '•', trend.titulo);
    });

    markCatDone(cat);
    updateTrendsHeader();
    showResults();
    renderEditorial();
  });

  eventSource.addEventListener('complete', e => {
    const d = JSON.parse(e.data);

    // editorial summary
    if (d.summary) {
      $('gtSummaryText').textContent = d.summary;
      $('gtSummaryCard').hidden = false;
    }

    // cross-themes
    const themes = d.cross_themes || [];
    if (themes.length) {
      const grid = $('gtCrossGrid');
      themes.forEach(t => grid.appendChild(buildCrossCard(t)));
      $('gtCrossThemes').hidden = false;
    }

    // timestamp
    const ts = $('lastUpdated');
    if (ts) {
      const now = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
      ts.textContent = `Atualizado às ${now}`;
    }

    $('gtPipeline').hidden = true;
  });

  eventSource.addEventListener('pipeline_error', e => {
    let msg = 'Erro na análise de tendências';
    try { msg = JSON.parse(e.data).message || msg; } catch (_) {}
    showError(msg);
    btn.disabled = false;
    label.textContent = 'Analisar Tendências Globais';
    eventSource.close();
  });

  eventSource.addEventListener('end', () => {
    eventSource.close();
    btn.disabled = false;
    label.textContent = 'Atualizar Tendências';
  });

  // SSE connection error (network level)
  eventSource.onerror = () => {
    if (eventSource.readyState === EventSource.CLOSED) return;
    showError('Conexão SSE perdida. Tente novamente.');
    btn.disabled = false;
    label.textContent = 'Analisar Tendências Globais';
    eventSource.close();
  };
}

// ── init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  $('analyzeBtn')?.addEventListener('click', startAnalysis);

  document.querySelectorAll('.gt-cat-btn').forEach(btn => {
    btn.addEventListener('click', () => applyFilter(btn.dataset.cat));
  });

  // if navigated from youtuber with a trend topic pre-selected
  const topic = localStorage.getItem('yt_trend_preload');
  if (topic) {
    localStorage.removeItem('yt_trend_preload');
    // auto-start with no filter
    startAnalysis();
  }
});

/* ════════ Banner de canal de notícias: relógio + ticker ════════ */
(function () {
  // relógio ao vivo
  const clock = document.getElementById('nxClock');
  if (clock) {
    const tick = () => {
      clock.textContent = new Date().toLocaleTimeString('pt-BR', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    };
    tick();
    setInterval(tick, 1000);
  }
})();

let _nxHeadlines = [];
function nxAddHeadline(icon, titulo) {
  const t = (titulo || '').trim();
  if (!t || _nxHeadlines.includes(t)) return;
  _nxHeadlines.push(t);
  nxRenderTicker(icon, t, _nxHeadlines.length === 1);
}

function nxRenderTicker(icon, titulo, first) {
  const track = document.getElementById('nxTickerTrack');
  if (!track) return;
  if (first) track.innerHTML = ''; // limpa a mensagem inicial
  const item = document.createElement('span');
  item.className = 'nx-ticker-item';
  item.innerHTML = `<span class="nx-ticker-ico">${icon}</span> ${escapeHtml(titulo)}`;
  track.appendChild(item);
  // duplica o conteúdo p/ loop contínuo só quando há material suficiente
  if (_nxHeadlines.length >= 3 && !track.dataset.looped) {
    track.dataset.looped = '1';
    track.innerHTML = track.innerHTML + track.innerHTML;
  }
}

/* ════════ Faixa de cotações em tempo real (economia) ════════ */
async function nxLoadMarket() {
  const strip = document.getElementById('nxMarketStrip');
  const widgetBody = document.getElementById('mcMarketBody');
  try {
    const res = await fetch('/api/trends/economy');
    const data = await res.json();
    const quotes = data.quotes || [];
    if (!quotes.length) {
      if (strip) strip.innerHTML = '<span class="nx-market-item nx-market-loading">cotações indisponíveis</span>';
      if (widgetBody) widgetBody.innerHTML = '<div class="mc-market-loading">cotações indisponíveis</div>';
      return;
    }
    // faixa do topo (rolando)
    if (strip) {
      const render = quotes.map(q => {
        const cls = q.dir === 'up' ? 'up' : (q.dir === 'down' ? 'down' : 'flat');
        return `<span class="nx-market-item ${cls}">${escapeHtml(q.display || '')}</span>`;
      }).join('');
      strip.innerHTML = render + render;
    }
    // widget de mercado (lista vertical, estilo TradingView)
    if (widgetBody) {
      widgetBody.innerHTML = quotes.slice(0, 10).map(q => {
        const cls = q.dir === 'up' ? 'up' : (q.dir === 'down' ? 'down' : 'flat');
        const arrow = q.dir === 'up' ? '▲' : (q.dir === 'down' ? '▼' : '▬');
        const pct = Math.abs(q.pct || 0).toFixed(2).replace('.', ',');
        const val = (q.value >= 1000)
          ? Math.round(q.value).toLocaleString('pt-BR')
          : (q.value || 0).toFixed(2).replace('.', ',');
        return `<div class="mc-market-row">
          <span class="mc-market-name">${escapeHtml(q.label || '')}</span>
          <span class="mc-market-val">${q.is_stock ? '' : 'R$ '}${val}</span>
          <span class="mc-market-pct ${cls}">${arrow} ${pct}%</span>
        </div>`;
      }).join('');
    }
  } catch (e) {
    if (strip) strip.innerHTML = '<span class="nx-market-item nx-market-loading">cotações indisponíveis</span>';
    if (widgetBody) widgetBody.innerHTML = '<div class="mc-market-loading">cotações indisponíveis</div>';
  }
}
nxLoadMarket();
setInterval(nxLoadMarket, 60000); // atualiza a cada minuto

/* ════════ Widget de Clima (OpenWeather) ════════ */
async function nxLoadWeather() {
  const body = document.getElementById('mcWeatherBody');
  if (!body) return;
  try {
    const res = await fetch('/api/trends/weather');
    const data = await res.json();
    const w = data.weather;
    if (!w) {
      body.innerHTML = '<div class="mc-weather-empty">clima indisponível<br><span>configure OPENWEATHER_API_KEY</span></div>';
      return;
    }
    body.innerHTML = `
      <div class="mc-weather-main">
        <span class="mc-weather-emoji">${w.emoji}</span>
        <div class="mc-weather-temp">${w.temp}<span>°C</span></div>
      </div>
      <div class="mc-weather-city">${escapeHtml(w.city)}</div>
      <div class="mc-weather-desc">${escapeHtml(w.desc)}</div>
      <div class="mc-weather-stats">
        <span title="Sensação térmica">🌡 ${w.feels}°</span>
        <span title="Mínima / Máxima">↓${w.tmin}° ↑${w.tmax}°</span>
        <span title="Umidade">💧 ${w.humidity}%</span>
        <span title="Vento">💨 ${w.wind} km/h</span>
      </div>`;
  } catch (e) {
    body.innerHTML = '<div class="mc-weather-empty">clima indisponível</div>';
  }
}
nxLoadWeather();
setInterval(nxLoadWeather, 600000); // atualiza a cada 10 min

/* ════════ Widget GitHub em Alta ════════ */
async function nxLoadGithub() {
  const body = document.getElementById('mcGithubBody');
  if (!body) return;
  try {
    const res = await fetch('/api/trends/github');
    const data = await res.json();
    const repos = data.repos || [];
    if (!repos.length) {
      body.innerHTML = '<div class="mc-gh-loading">repositórios indisponíveis</div>';
      return;
    }
    body.innerHTML = repos.map((r, i) => {
      const stars = r.stars >= 1000 ? (r.stars / 1000).toFixed(1) + 'k' : r.stars;
      return `<a class="mc-gh-row" href="${escapeHtml(r.url)}" target="_blank" rel="noopener">
        <span class="mc-gh-rank">${i + 1}</span>
        <div class="mc-gh-info">
          <span class="mc-gh-name">${escapeHtml(r.name)}</span>
          <span class="mc-gh-desc">${escapeHtml(r.desc || 'sem descrição')}</span>
        </div>
        <div class="mc-gh-stats">
          ${r.lang ? `<span class="mc-gh-lang">${escapeHtml(r.lang)}</span>` : ''}
          <span class="mc-gh-stars">⭐ ${stars}</span>
        </div>
      </a>`;
    }).join('');
  } catch (e) {
    body.innerHTML = '<div class="mc-gh-loading">repositórios indisponíveis</div>';
  }
}
nxLoadGithub();
setInterval(nxLoadGithub, 1800000); // atualiza a cada 30 min

/* ════════ Widget Hacker News Top ════════ */
async function nxLoadHackerNews() {
  const body = document.getElementById('mcHnBody');
  if (!body) return;
  try {
    const res = await fetch('/api/trends/hackernews');
    const data = await res.json();
    const stories = data.stories || [];
    if (!stories.length) {
      body.innerHTML = '<div class="mc-hn-loading">histórias indisponíveis</div>';
      return;
    }
    body.innerHTML = stories.map((s, i) => `
      <a class="mc-hn-row" href="${escapeHtml(s.url)}" target="_blank" rel="noopener">
        <span class="mc-hn-rank">${i + 1}</span>
        <div class="mc-hn-info">
          <span class="mc-hn-title">${escapeHtml(s.title)}</span>
          <span class="mc-hn-meta">▲ ${s.score} · 💬 ${s.comments} · ${escapeHtml(s.domain)}</span>
        </div>
      </a>`).join('');
  } catch (e) {
    body.innerHTML = '<div class="mc-hn-loading">histórias indisponíveis</div>';
  }
}
nxLoadHackerNews();
setInterval(nxLoadHackerNews, 900000); // atualiza a cada 15 min

/* ════════ Widget NASA Foto do Dia ════════ */
async function nxLoadNasa() {
  const body = document.getElementById('mcNasaBody');
  if (!body) return;
  try {
    const res = await fetch('/api/trends/nasa');
    const data = await res.json();
    const a = data.apod;
    if (!a) {
      body.innerHTML = '<div class="mc-nasa-loading">imagem indisponível</div>';
      return;
    }
    const media = a.image
      ? `<a class="mc-nasa-imgwrap" href="${escapeHtml(a.hdurl || a.image)}" target="_blank" rel="noopener">
           <img class="mc-nasa-img" src="${escapeHtml(a.image)}" alt="${escapeHtml(a.title)}" loading="lazy">
           ${a.media_type === 'video' ? '<span class="mc-nasa-play">▶</span>' : ''}
         </a>`
      : '';
    body.innerHTML = `
      ${media}
      <div class="mc-nasa-info">
        <h4 class="mc-nasa-title">${escapeHtml(a.title)}</h4>
        <p class="mc-nasa-desc">${escapeHtml(a.explanation)}…</p>
        <span class="mc-nasa-credit">© ${escapeHtml(a.copyright)} · ${escapeHtml(a.date)}</span>
      </div>`;
  } catch (e) {
    body.innerHTML = '<div class="mc-nasa-loading">imagem indisponível</div>';
  }
}
nxLoadNasa();
setInterval(nxLoadNasa, 21600000); // atualiza a cada 6h (muda 1x/dia)

/* ════════════════ MISSION CONTROL — drag & drop + layout salvo ════════════════ */
(function () {
  const grid = document.querySelector('.mc-grid');
  if (!grid) return;

  const STORAGE_KEY = 'mc_layout';
  let dragEl = null;

  function widgets() {
    return Array.from(grid.querySelectorAll('.mc-widget'));
  }

  // aplica uma ordem (lista de data-wid) reposicionando os widgets no grid
  function applyOrder(order) {
    if (!Array.isArray(order)) return;
    order.forEach(wid => {
      const el = grid.querySelector(`.mc-widget[data-wid="${wid}"]`);
      if (el) grid.appendChild(el);   // reanexar = mover para o fim na ordem dada
    });
  }

  function currentOrder() {
    return widgets().map(w => w.dataset.wid).filter(Boolean);
  }

  // ── persistência (servidor + fallback local) ──
  async function loadLayout() {
    try {
      const res = await fetch('/api/trends/layout');
      const data = await res.json();
      if (data && Array.isArray(data.layout)) { applyOrder(data.layout); return; }
    } catch { /* usa fallback */ }
    try {
      const local = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (Array.isArray(local)) applyOrder(local);
    } catch { /* ignora */ }
  }

  let saveTimer = null;
  function saveLayout() {
    const order = currentOrder();
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(order)); } catch {}
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      fetch('/api/trends/layout', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ layout: order }),
      }).catch(() => { /* offline: já salvou local */ });
    }, 400);
  }

  // ── drag & drop (só pela alça) ──
  function onHandleDown(e) {
    const w = e.target.closest('.mc-widget');
    if (w) w.setAttribute('draggable', 'true');
  }
  function onHandleUp() {
    widgets().forEach(w => w.setAttribute('draggable', 'false'));
  }

  grid.addEventListener('mousedown', e => {
    if (e.target.classList.contains('mc-drag-handle')) onHandleDown(e);
  });
  document.addEventListener('mouseup', onHandleUp);

  grid.addEventListener('dragstart', e => {
    const w = e.target.closest('.mc-widget');
    if (!w || w.getAttribute('draggable') !== 'true') { e.preventDefault(); return; }
    dragEl = w;
    w.classList.add('mc-dragging');
    e.dataTransfer.effectAllowed = 'move';
  });

  grid.addEventListener('dragover', e => {
    e.preventDefault();
    if (!dragEl) return;
    const after = getDragAfter(e.clientY, e.clientX);
    if (after == null) grid.appendChild(dragEl);
    else grid.insertBefore(dragEl, after);
  });

  grid.addEventListener('dragend', () => {
    if (!dragEl) return;
    dragEl.classList.remove('mc-dragging');
    dragEl.setAttribute('draggable', 'false');
    dragEl = null;
    saveLayout();
  });

  // acha o widget após o qual soltar (considera grade 2D)
  function getDragAfter(y, x) {
    const els = widgets().filter(w => w !== dragEl);
    let closest = null, closestDist = Infinity;
    for (const el of els) {
      const box = el.getBoundingClientRect();
      const cx = box.left + box.width / 2;
      const cy = box.top + box.height / 2;
      // só considera quem está "depois" do cursor (abaixo ou à direita)
      if (cy - y > -box.height / 2) {
        const dist = Math.hypot(cx - x, cy - y);
        if (dist < closestDist) { closestDist = dist; closest = el; }
      }
    }
    return closest;
  }

  // botão de resetar layout (opcional via tecla)
  window.resetMissionControl = function () {
    localStorage.removeItem(STORAGE_KEY);
    fetch('/api/trends/layout', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ layout: [] }),
    }).catch(() => {});
    location.reload();
  };

  loadLayout();
})();
