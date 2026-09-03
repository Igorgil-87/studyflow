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
  const changed = activeCat !== cat;
  activeCat = cat;
  if (changed) _trackTrendUx('trend_filter_used');
  document.querySelectorAll('.gt-cat-btn').forEach(b => {
    const selected = b.dataset.cat === cat;
    b.classList.toggle('active', selected);
    b.setAttribute('aria-pressed', String(selected));
  });
  renderEditorial();
  updateTrendsHeader();
}

// ── Sprint 5: sistema único e escaneável de cards de tendência ────────────────
function renderEditorial() {
  const grid = $('gtTrendsGrid');
  if (!grid) return;
  let items = allTrends.slice();
  if (activeCat !== 'todos') items = items.filter(i => i.category === activeCat);
  items.sort((a, b) => (b.trend.oportunidade_score || 0) - (a.trend.oportunidade_score || 0));

  grid.className = 'ux-trend-list';
  grid.innerHTML = '';
  const filterEmpty = $('gtFilterEmpty');
  if (filterEmpty) filterEmpty.hidden = items.length > 0 || allTrends.length === 0;
  if (!items.length) return;

  items.forEach(({ category, trend }, index) => {
    grid.appendChild(buildOpportunityCard(category, trend, index === 0));
  });
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

function _sourceLinks(trend, detailed = false) {
  const links = (trend.links || []).filter(l => l && l.url).slice(0, detailed ? 8 : 4);
  if (!links.length) return '';
  return `<div class="ux-trend-sources${detailed ? ' is-detailed' : ''}">${links.map(l => {
    let host = ''; try { host = new URL(l.url).hostname.replace('www.', ''); } catch {}
    const label = (l.title && l.title.length > 3) ? l.title : (host || 'fonte');
    const source = l.source ? String(l.source).replace(/[_-]/g, ' ') : host;
    return `<a href="${escapeHtml(l.url)}" target="_blank" rel="noopener" data-trend-source-link="1"><span class="ux-source-name">${escapeHtml(source || 'Fonte')}</span><strong>${escapeHtml(label.length > 96 ? label.slice(0,96)+'…' : label)}</strong><span class="ux-source-host">${escapeHtml(host)}</span></a>`;
  }).join('')}</div>`;
}

function _trackTrendUx(event) {
  try {
    fetch('/api/ux/events', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({event, page:'trends'}), keepalive:true}).catch(()=>{});
  } catch { /* analytics nunca bloqueia a tarefa */ }
}

function _sensitiveTrendContext(category, trend) {
  const text = `${category || ''} ${trend.titulo || ''} ${trend.insight || ''} ${trend.angulo || ''}`.toLowerCase();
  const categoryReason = {
    politica: 'política e assuntos públicos',
    economia: 'economia e finanças',
    ciencia: 'ciência',
    fitness: 'saúde e bem-estar',
  }[category];
  const keywordGroups = [
    { reason: 'saúde e bem-estar', words: ['saúde','saude','médic','medic','doença','doenca','tratamento','vacina','nutrição','nutricao','suplement','diagnóstico','diagnostico'] },
    { reason: 'finanças', words: ['investimento','ações','acoes','bolsa','juros','crédito','credito','financiamento','bitcoin','cripto','renda fixa'] },
    { reason: 'segurança', words: ['segurança','seguranca','ataque','vulnerabilidade','malware','ransomware','ciber'] },
  ];
  const keywordReason = keywordGroups.find(g => g.words.some(w => text.includes(w)))?.reason;
  const reason = categoryReason || keywordReason;
  return reason ? { sensitive: true, reason } : { sensitive: false, reason: '' };
}

function _trustNotice(context, sourceCount) {
  if (!context.sensitive) return '';
  const evidence = sourceCount
    ? `${sourceCount} ${sourceCount === 1 ? 'fonte verificável está disponível' : 'fontes verificáveis estão disponíveis'} nesta análise.`
    : 'Nenhuma fonte verificável foi retornada nesta análise.';
  return `<aside class="ux-trust-notice" aria-label="Atenção para verificação">
    <strong>Confira as fontes antes de publicar ou tomar decisões</strong>
    <p>Este assunto envolve ${escapeHtml(context.reason)}. A IA resume e interpreta os sinais disponíveis, mas pode deixar contexto importante de fora. ${escapeHtml(evidence)}</p>
    ${sourceCount ? '<button type="button" class="ux-trust-sources-link">Ver fontes</button>' : ''}
  </aside>`;
}

function _trendDetailModal(category, trend, potential) {
  const label = CAT_LABELS[category] || category;
  const icon = CAT_ICONS[category] || '•';
  const links = (trend.links || []).filter(l => l && l.url);
  const trustContext = _sensitiveTrendContext(category, trend);
  const overlay = el('div', 'ux-trend-modal-overlay');
  overlay.setAttribute('role', 'presentation');
  const modal = el('section', 'ux-trend-modal');
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.setAttribute('aria-labelledby', 'uxTrendModalTitle');
  modal.setAttribute('aria-describedby', 'uxTrendModalDescription');
  modal.innerHTML = `
    <div class="ux-trend-modal-head">
      <div><span class="ux-trend-category">${icon} ${escapeHtml(label)}</span><h2 id="uxTrendModalTitle">${escapeHtml(trend.titulo || 'Análise da tendência')}</h2></div>
      <button class="ux-trend-modal-close" type="button" aria-label="Fechar análise">×</button>
    </div>
    <div class="ux-trend-modal-body" id="uxTrendModalDescription">
      ${_trustNotice(trustContext, links.length)}
      <div class="ux-provenance-legend" aria-label="Como ler esta análise"><span class="is-source">↗ Fonte disponível</span><span>◇ Leitura da IA</span><span>✦ Ideia sugerida pela IA</span></div>
      <section class="ux-analysis-section">
        <span class="ux-analysis-kicker">Resumo</span>
        <div class="ux-analysis-meta">${potential ? `<span>Potencial: <strong>${escapeHtml(potential.label)}</strong> · estimativa da IA</span>` : ''}</div>
        <p>${escapeHtml(trend.insight || 'Não há síntese adicional disponível para esta tendência.')}</p>
        <span class="ux-content-origin is-ai">Síntese da IA</span>
      </section>
      <section class="ux-analysis-section">
        <span class="ux-analysis-kicker">Por que olhar para este assunto?</span>
        <p>${escapeHtml(trend.insight || 'Os dados atuais não trazem explicação suficiente para afirmar por que este tema está crescendo.')}</p>
        <span class="ux-content-origin is-ai">Leitura da IA com base nos sinais disponíveis</span>
      </section>
      <section class="ux-analysis-section">
        <span class="ux-analysis-kicker" id="uxTrendEvidenceHeading">Fontes para conferir</span>
        ${links.length ? `<p class="ux-analysis-help">Abra as fontes originais para conferir o contexto. O texto acima é uma síntese da IA, não uma citação das páginas.</p>${_sourceLinks(trend, true)}` : '<div class="ux-analysis-empty">Nenhuma fonte verificável foi retornada para esta tendência.</div>'}
        <span class="ux-content-origin is-source">Fontes originais disponíveis</span>
      </section>
      <section class="ux-analysis-section">
        <span class="ux-analysis-kicker">Uma forma de abordar</span>
        ${trend.angulo ? `<p>${escapeHtml(trend.angulo)}</p><span class="ux-content-origin is-creative">Ideia sugerida pela IA</span>` : '<div class="ux-analysis-empty">Nenhum ângulo de conteúdo foi gerado para esta tendência.</div>'}
      </section>
    </div>
    <div class="ux-trend-modal-actions">
      <button class="ux-btn-secondary ux-action ux-action-secondary ux-trend-modal-dismiss" data-action-level="secondary" type="button">Voltar às tendências</button>
      <button class="ux-btn-primary ux-action ux-action-primary ux-trend-modal-create" data-action-level="primary" type="button">Criar conteúdo com esta ideia <span aria-hidden="true">→</span></button>
    </div>`;
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  document.body.classList.add('ux-modal-open');
  _trackTrendUx('trend_opened');
  const previousFocus = document.activeElement;
  const close = () => { document.body.classList.remove('ux-modal-open'); overlay.remove(); if (previousFocus && previousFocus.focus) previousFocus.focus(); };
  modal.querySelector('.ux-trend-modal-close').addEventListener('click', close);
  modal.querySelector('.ux-trend-modal-dismiss').addEventListener('click', close);
  modal.querySelector('.ux-trend-modal-create').addEventListener('click', () => { _trackTrendUx('trend_create_content_clicked'); _goCreate(category, trend); });
  modal.querySelectorAll('[data-trend-source-link]').forEach(a => a.addEventListener('click', () => _trackTrendUx('trend_sources_opened')));
  const trustSourcesBtn = modal.querySelector('.ux-trust-sources-link');
  if (trustSourcesBtn) trustSourcesBtn.addEventListener('click', () => { modal.querySelector('#uxTrendEvidenceHeading')?.scrollIntoView({behavior:'smooth', block:'start'}); });
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  const onKey = e => {
    if (e.key === 'Escape') { document.removeEventListener('keydown', onKey); close(); return; }
    if (e.key === 'Tab') {
      const focusables = [...modal.querySelectorAll('button,a[href]')].filter(x => !x.disabled);
      if (!focusables.length) return;
      const first=focusables[0], last=focusables[focusables.length-1];
      if (e.shiftKey && document.activeElement===first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement===last) { e.preventDefault(); first.focus(); }
    }
  };
  document.addEventListener('keydown', onKey);
  modal.querySelector('.ux-trend-modal-close').focus();
}

function qualitativePotential(rawScore) {
  const score = Number(rawScore);
  if (!Number.isFinite(score) || score <= 0) return null;
  // O backend atual produz oportunidade_score por julgamento do LLM (1–10),
  // sem uma fórmula calibrada/validada. A UX evita expor falsa precisão.
  if (score >= 8) return { level: 'high', label: 'Alto' };
  if (score >= 5) return { level: 'medium', label: 'Médio' };
  return { level: 'low', label: 'Baixo' };
}

function buildOpportunityCard(category, trend, featured = false) {
  const card = el('article', `ux-trend-card${featured ? ' is-featured' : ''}`);
  card.dataset.cat = category;
  const icon = CAT_ICONS[category] || '•';
  const label = CAT_LABELS[category] || category;
  const potential = qualitativePotential(trend.oportunidade_score);
  const detailsId = `trend-detail-${Math.random().toString(36).slice(2, 10)}`;

  card.innerHTML = `
    <div class="ux-trend-card-top">
      <div class="ux-trend-card-context">
        <span class="ux-trend-category">${icon} ${escapeHtml(label)}</span>
        ${featured ? '<span class="ux-trend-featured">Destaque agora</span>' : ''}
      </div>
      ${potential ? `<div class="ux-trend-potential ux-trend-potential-${potential.level}" title="Estimativa qualitativa da IA a partir dos sinais disponíveis. Não é previsão de desempenho."><span>Potencial <button class="ux-potential-help" type="button" aria-label="Como o potencial é apresentado" title="Estimativa qualitativa da IA a partir dos sinais disponíveis. Não é previsão de desempenho.">?</button></span><strong>${potential.label}</strong><small>Estimativa da IA</small></div>` : ''}
    </div>

    <div class="ux-trend-card-copy">
      <h3>${escapeHtml(trend.titulo || '')}</h3>
      <p>${escapeHtml(trend.insight || 'Abra a análise para entender os sinais disponíveis sobre este assunto.')}</p>
    </div>

    <div class="ux-trend-card-actions">
      <button class="ux-btn-secondary ux-action ux-action-secondary ux-trend-analysis-btn" data-action-level="secondary" type="button" aria-expanded="false" aria-controls="${detailsId}">Ver análise</button>
      <button class="ux-btn-primary ux-action ux-action-primary ux-trend-create-btn" data-action-level="primary" type="button">Criar conteúdo <span aria-hidden="true">→</span></button>
    </div>

    `;

  const analysisBtn = card.querySelector('.ux-trend-analysis-btn');
  analysisBtn.removeAttribute('aria-controls');
  analysisBtn.removeAttribute('aria-expanded');
  analysisBtn.addEventListener('click', () => _trendDetailModal(category, trend, potential));
  card.querySelector('.ux-trend-create-btn').addEventListener('click', () => { _trackTrendUx('trend_create_content_clicked'); _goCreate(category, trend); });
  return card;
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
  $('gtPipeline').setAttribute('aria-busy', 'true');
  $('gtEmpty').hidden    = true;
  $('gtError').hidden    = true;
}

function showResults() {
  $('gtResults').hidden  = false;
  $('trendsHeader').hidden = false;
}

function showError(msg) {
  const box = $('gtError');
  const message = $('gtErrorMessage');
  if (message) message.textContent = msg || 'Tente novamente em alguns instantes.';
  box.hidden = false;
  $('gtPipeline').hidden = true;
  box.focus?.();
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
  label.textContent = 'Buscando…';
  const emptyBtn = $('emptyAnalyzeBtn');
  if (emptyBtn) emptyBtn.disabled = true;

  resetUI();
  showPipeline();

  // get selected cats from active filter (default: all)
  const cats = activeCat === 'todos'
    ? ['esportes', 'games', 'politica', 'ciencia', 'cultura', 'historia', 'beleza', 'fitness', 'economia']
    : [activeCat];

  initCatDots(cats);
  const monitored = $('uxMonitoredCategories');
  if (monitored) monitored.textContent = String(cats.length);

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
    if (!res.ok || !data.job_id) throw new Error(data.error || 'Não foi possível iniciar a busca. Tente novamente.');
    jobId = data.job_id;
  } catch (err) {
    showError(err.message);
    btn.disabled = false;
    label.textContent = 'Buscar oportunidades';
    if (emptyBtn) emptyBtn.disabled = false;
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
    _trackTrendUx('trend_analysis_completed');

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
    $('gtPipeline').setAttribute('aria-busy', 'false');
  });

  eventSource.addEventListener('pipeline_error', e => {
    _trackTrendUx('trend_analysis_failed');
    let msg = 'Não foi possível concluir a busca de oportunidades.';
    try { msg = JSON.parse(e.data).message || msg; } catch (_) {}
    showError(msg);
    btn.disabled = false;
    label.textContent = 'Buscar oportunidades';
    if (emptyBtn) emptyBtn.disabled = false;
    eventSource.close();
  });

  eventSource.addEventListener('end', () => {
    eventSource.close();
    btn.disabled = false;
    label.textContent = 'Buscar novamente';
    if (emptyBtn) emptyBtn.disabled = false;
  });

  // SSE connection error (network level)
  eventSource.onerror = () => {
    if (eventSource.readyState === EventSource.CLOSED) return;
    _trackTrendUx('trend_analysis_failed');
    showError('A conexão com a análise foi interrompida. Tente novamente.');
    btn.disabled = false;
    label.textContent = 'Buscar oportunidades';
    if (emptyBtn) emptyBtn.disabled = false;
    eventSource.close();
  };
}

// ── init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  _trackTrendUx('trends_view');
  $('analyzeBtn')?.addEventListener('click', startAnalysis);
  $('emptyAnalyzeBtn')?.addEventListener('click', startAnalysis);
  $('gtRetryBtn')?.addEventListener('click', startAnalysis);

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

// Sprint 13: recovery action for a valid analysis with no results in the selected filter.
document.addEventListener('DOMContentLoaded', () => {
  const showAll = $('gtShowAllBtn');
  if (showAll) showAll.addEventListener('click', () => applyFilter('todos'));
});
