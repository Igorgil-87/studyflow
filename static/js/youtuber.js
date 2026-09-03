/* ═══════════════════════════════════════════════════════════
   Study Flow — Módulo Youtuber v2
   Tabs: Produção de Conteúdo | Inteligência e Pesquisa | Análise de Concorrência
   ═══════════════════════════════════════════════════════════ */

const $ = (sel) => document.querySelector(sel);

/* ── Tab switching ─────────────────────────────────────────── */
function switchTab(panelId) {
  document.querySelectorAll('.ps-tab').forEach((t) => t.classList.remove('active'));
  document.querySelectorAll('.ps-panel').forEach((p) => { p.hidden = true; });
  const tab   = document.querySelector(`.ps-tab[data-panel="${panelId}"]`);
  const panel = $(`#${panelId}`);
  if (tab)   tab.classList.add('active');
  if (panel) panel.hidden = false;
}

document.querySelectorAll('.ps-tab').forEach((tab) => {
  tab.addEventListener('click', () => { if (!tab.disabled) switchTab(tab.dataset.panel); });
});


/* ════════════════════════════════════════════════════════════
   PAINEL 1 — Produção de Conteúdo (Clips AI)
   ════════════════════════════════════════════════════════════ */

const videoUrlEl        = $('#videoUrl');
const nicheProducaoEl   = $('#nicheProducao');
const gerarClipsBtn     = $('#gerarClipsBtn');
const prodPipeline      = $('#prodPipeline');
const prodTimer         = $('#prodTimer');

let _prodTimerStart = null;
let _prodTimerInterval = null;

function _fmtElapsed(ms) {
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60).toString().padStart(2, '0');
  const s = (totalSec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function startProdTimer() {
  stopProdTimer();
  _prodTimerStart = Date.now();
  if (prodTimer) prodTimer.textContent = '00:00';
  _prodTimerInterval = setInterval(() => {
    if (!prodTimer || !_prodTimerStart) return;
    prodTimer.textContent = _fmtElapsed(Date.now() - _prodTimerStart);
  }, 1000);
}

// freeze=true trava o cronômetro no valor atual (fim do processamento);
// freeze=false só para e zera (ex: cancelamento).
function stopProdTimer(freeze) {
  if (_prodTimerInterval) clearInterval(_prodTimerInterval);
  _prodTimerInterval = null;
  if (freeze && prodTimer && _prodTimerStart) {
    prodTimer.textContent = _fmtElapsed(Date.now() - _prodTimerStart);
  }
  _prodTimerStart = null;
}
const prodResult        = $('#prodResult');
const prodErrorBox      = $('#prodErrorBox');
const prodPipelineError = $('#prodPipelineError');
const prodVideoTitle    = $('#prodVideoTitle');

let prodEventSource = null;

/* Content type + duração específica */
let contentType = 'shorts_45'; // preset de duração (clip_rules)

document.querySelectorAll('.ps-toggle-btn[data-ctype]').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.ps-toggle-btn[data-ctype]').forEach((b) => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
    btn.classList.add('active');
    btn.setAttribute('aria-pressed', 'true');
    const ctype = btn.dataset.ctype;
    const shortsInfo = $('#shortsInfo');
    const cortesInfo = $('#cortesInfo');
    if (ctype === 'shorts') {
      if (shortsInfo) shortsInfo.hidden = false;
      if (cortesInfo) cortesInfo.hidden = true;
      const active = document.querySelector('#shortsDurGroup .ps-toggle-btn.active');
      contentType = active?.dataset.dur || 'shorts_45';
    } else {
      if (shortsInfo) shortsInfo.hidden = true;
      if (cortesInfo) cortesInfo.hidden = false;
      const active = document.querySelector('#cortesDurGroup .ps-toggle-btn.active');
      contentType = active?.dataset.dur || 'corte_120';
    }
  });
});

// botões de duração específica (30/45/1:30 e 2/5/10/15 min)
document.querySelectorAll('.ps-toggle-btn[data-dur]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const group = btn.closest('.ps-toggle-group');
    group?.querySelectorAll('.ps-toggle-btn').forEach((b) => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
    btn.classList.add('active');
    btn.setAttribute('aria-pressed', 'true');
    contentType = btn.dataset.dur;
  });
});

/* Language toggle */
document.querySelectorAll('.ps-toggle-btn[data-lang]').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.ps-toggle-btn[data-lang]').forEach((b) => { b.classList.remove('active'); b.setAttribute('aria-pressed', 'false'); });
    btn.classList.add('active');
    btn.setAttribute('aria-pressed', 'true');
  });
});

/* Advanced settings accordion */
$('#advToggleBtn')?.addEventListener('click', () => {
  const body    = $('#advBody');
  const open    = !body.hidden;
  body.hidden   = open;
  $('#advToggleBtn')?.setAttribute('aria-expanded', String(!open));
  const chevron = $('#advToggleBtn')?.querySelector('.ps-accordion-chevron');
  if (chevron) chevron.style.transform = open ? '' : 'rotate(180deg)';
});

gerarClipsBtn?.addEventListener('click', startClipsGeneration);

async function startClipsGeneration() {
  const videoUrl = videoUrlEl?.value.trim();
  if (!videoUrl) { videoUrlEl?.focus(); return; }

  const niche = nicheProducaoEl?.value.trim() || 'geral';
  const numClipsRaw = document.querySelector('#numClips')?.value;
  const numClips = numClipsRaw ? parseInt(numClipsRaw, 10) : null;
  const gerarLegenda = document.getElementById('gerarLegenda')?.checked ?? true;
  const legendaIdioma = gerarLegenda ? (document.getElementById('legendaIdioma')?.value || null) : null;
  const adicionarFechamento = document.getElementById('adicionarFechamento')?.checked ?? true;

  setClipsLoading(true);
  if (prodErrorBox) prodErrorBox.hidden = true;

  if (prodVideoTitle) prodVideoTitle.textContent = videoUrl;

  try {
    const res = await fetch('/api/youtuber/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        niche, video_url: videoUrl, content_type: contentType, num_clips: numClips,
        gerar_legenda: gerarLegenda, idioma_legenda: legendaIdioma,
        adicionar_fechamento: adicionarFechamento,
      }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || 'Falha ao iniciar');

    if (prodPipeline) prodPipeline.hidden = false;
    if (prodResult)   prodResult.hidden   = true;

    document.querySelectorAll('#prodPipeline .ps-step-card')
      .forEach((s) => s.classList.remove('running', 'done'));
    document.querySelectorAll('#prodPipeline .step-detail')
      .forEach((d) => { d.textContent = ''; });

    startProdTimer();

    listenProdStream(body.job_id);

  } catch (e) {
    if (prodErrorBox) { prodErrorBox.textContent = '⚠ ' + e.message; prodErrorBox.hidden = false; }
    if (prodPipeline) prodPipeline.hidden = false;
    setClipsLoading(false);
  }
}

function setClipsLoading(on) {
  if (!gerarClipsBtn) return;
  gerarClipsBtn.disabled = on;
  const span = gerarClipsBtn.querySelector('span');
  if (span) span.textContent = on ? 'Processando…' : 'Gerar Clips';
}

function listenProdStream(jobId) {
  if (prodEventSource) prodEventSource.close();
  prodEventSource = new EventSource(`/api/stream/${jobId}`);

  prodEventSource.addEventListener('progress', (e) => {
    const { step, status, detail } = JSON.parse(e.data);
    updateProdStep(step, status, detail);
  });

  prodEventSource.addEventListener('complete', (e) => {
    const { clips } = JSON.parse(e.data);
    stopProdTimer(true);
    renderProdClips(clips);
    setClipsLoading(false);
  });

  prodEventSource.addEventListener('pipeline_error', (e) => {
    stopProdTimer(true);
    try {
      if (prodPipelineError) {
        prodPipelineError.textContent = '⚠ ' + JSON.parse(e.data).message;
        prodPipelineError.hidden = false;
      }
    } catch { /* conn close */ }
    setClipsLoading(false);
  });

  prodEventSource.addEventListener('end', () => prodEventSource.close());
}

function updateProdStep(step, status, detail) {
  const el = document.querySelector(`#prodPipeline .ps-step-card[data-step="${step}"]`);
  if (!el) return;
  el.classList.remove('running', 'done');
  if (status === 'running') el.classList.add('running');
  if (status === 'done')    el.classList.add('done');
  if (detail) {
    const d = el.querySelector('.step-detail');
    if (d) d.textContent = detail;
  }
}

function renderProdClips(clips) {
  setTimeout(() => {
    if (prodPipeline) prodPipeline.hidden = true;
    if (prodResult)   prodResult.hidden   = false;

    const titleEl = $('#prodResultTitle');
    if (titleEl) titleEl.textContent = videoUrlEl?.value.trim() || '';

    const view = $('#prodHighlightsView');
    if (!view) return;
    view.innerHTML = '';

    if (!clips || clips.length === 0) {
      view.innerHTML = '<p class="empty-msg">Nenhum clip disponível.</p>';
      return;
    }

    const typeLabel = {
      hook: 'Hook', insight: 'Insight', momento_emocional: 'Emocional',
      demonstracao: 'Demo', controversia: 'Polêmico', cta: 'CTA',
    };

    clips.forEach((clip, i) => {
      const score = clip.viral_score || 0;
      const tier  = (clip.tier || '').toUpperCase().trim();
      const tierClass = tier === 'S' ? 'tier-s' : tier === 'A' ? 'tier-a'
                      : tier === 'B' ? 'tier-b' : 'tier-c';

      const card = document.createElement('div');
      card.className = 'ps-viral-card';
      card.style.animationDelay = `${i * 0.07}s`;

      const tags = (clip.hashtags || [])
        .map((h) => `<span class="ps-hl-tag">#${escapeHtml(h)}</span>`).join('');

      const subbars = [
        ['Hook', clip.s_hook], ['Curiosidade', clip.s_curiosidade],
        ['Surpresa', clip.s_surpresa], ['Emoção', clip.s_emocao],
        ['Share', clip.s_share], ['Retenção', clip.s_retencao],
      ].map(([lbl, v]) => {
        const n = Number(v) || 0; const pct = Math.min(100, n * 10);
        return `<div class="ps-vbar"><span class="ps-vbar-l">${lbl}</span>
          <div class="ps-vbar-track"><div class="ps-vbar-fill" style="width:${pct}%"></div></div>
          <span class="ps-vbar-n">${n}</span></div>`;
      }).join('');

      const titulosAlt = (clip.titulos_alt || []).filter(Boolean);
      const titulosHtml = titulosAlt.length ? `
        <details class="ps-titles">
          <summary>💡 ${titulosAlt.length} títulos virais (clique p/ copiar)</summary>
          <ol>${titulosAlt.map((t) => `<li onclick="copyText(this)">${escapeHtml(t)}</li>`).join('')}</ol>
        </details>` : '';

      const thumbConcept = (clip.thumb_texto || clip.thumb_visual) ? `
        <div class="ps-thumb-concept">
          <div class="ps-concept-head">🎨 Conceito de thumbnail</div>
          ${clip.thumb_texto ? `<div class="ps-thumb-text">“${escapeHtml(clip.thumb_texto)}”</div>` : ''}
          <div class="ps-concept-grid">
            ${clip.thumb_emocao ? `<div><b>Emoção</b>${escapeHtml(clip.thumb_emocao)}</div>` : ''}
            ${clip.thumb_visual ? `<div><b>Visual</b>${escapeHtml(clip.thumb_visual)}</div>` : ''}
            ${clip.thumb_expressao ? `<div><b>Expressão</b>${escapeHtml(clip.thumb_expressao)}</div>` : ''}
            ${clip.thumb_contraste ? `<div><b>Contraste</b>${escapeHtml(clip.thumb_contraste)}</div>` : ''}
          </div>
        </div>` : '';

      const hookBlock = (clip.hook || clip.hook_otimizado) ? `
        <div class="ps-hooks">
          ${clip.hook ? `<div class="ps-hook-row"><span class="ps-hook-tag orig">Original</span>${escapeHtml(clip.hook)}</div>` : ''}
          ${clip.hook_otimizado ? `<div class="ps-hook-row"><span class="ps-hook-tag opt">Otimizado ⚡</span>${escapeHtml(clip.hook_otimizado)}</div>` : ''}
        </div>` : '';

      const analysisRows = [
        clip.retencao ? `<div><b>Retenção</b> ${escapeHtml(clip.retencao)}</div>` : '',
        clip.publico  ? `<div><b>Público</b> ${escapeHtml(clip.publico)}</div>` : '',
        clip.riscos   ? `<div><b>Riscos</b> ${escapeHtml(clip.riscos)}</div>` : '',
      ].join('');
      const analysis = analysisRows ? `<div class="ps-analysis">${analysisRows}</div>` : '';

      const rec = clip.recomendacao || '';
      const recClass = /n[aã]o/i.test(rec) ? 'rec-no' : 'rec-yes';

      card.innerHTML = `
        ${clip.arquivo
          ? `<video class="ps-hl-video" controls preload="metadata"
               src="/static/${escapeHtml(clip.arquivo)}?t=${Date.now()}"></video>`
          : `<div class="ps-hl-no-video">Clip indisponível</div>`}
        <div class="ps-hl-body">
          <div class="ps-viral-top">
            <div class="ps-tier ${tierClass}">${tier || '–'}</div>
            <div class="ps-viral-score">
              <div class="ps-viral-score-n">${score}</div>
              <div class="ps-viral-score-l">VIRAL SCORE /100</div>
            </div>
            ${rec ? `<div class="ps-rec ${recClass}">${escapeHtml(rec)}</div>` : ''}
          </div>
          <div class="ps-hl-title">${escapeHtml(clip.titulo)}</div>
          <div class="ps-hl-dur">${escapeHtml(clip.duracao || '')}</div>
          ${titulosHtml}
          <div class="ps-vbars">${subbars}</div>
          ${hookBlock}
          ${thumbConcept}
          ${clip.motivo ? `<p class="ps-hl-summary"><b>Por que viraliza:</b> ${escapeHtml(clip.motivo)}</p>` : ''}
          ${clip.descricao ? `
            <div class="ps-desc">
              <div class="ps-desc-head">📝 Descrição pronta (clique p/ copiar)</div>
              <div class="ps-desc-body" onclick="copyText(this)">${escapeHtml(clip.descricao)}</div>
            </div>` : ''}
          ${analysis}
          ${tags ? `<div class="ps-hl-tags">${tags}</div>` : ''}
          <div class="ps-card-actions">
            ${clip.arquivo && clip.legenda_queimada
              ? `<div class="ps-vert-status ps-vert-ok">✓ Vertical 9:16 com legenda pronto</div>`
              : clip.arquivo && clip.vertical_erro
              ? `<button class="ps-vert-btn" onclick="exportVertical('${escapeHtml(clip.arquivo)}', this)">📱 Tentar gerar vertical de novo</button>
                 <div class="ps-vert-status" style="color:#ff6b6b">${escapeHtml(clip.vertical_erro)}</div>`
              : ''}
            ${clip.arquivo
              ? `<button class="ps-yt-btn" data-i="${i}" onclick="publishClipToYouTube(${i}, this)">▶ Publicar no YouTube</button>
                 <div class="ps-yt-status" id="ps-yt-status-${i}"></div>`
              : ''}
            ${clip.arquivo
              ? `<button class="ps-ig-btn" data-i="${i}" onclick="publishClipToInstagram(${i}, this)">📷 Publicar no Instagram (Reels)</button>
                 <div class="ps-ig-status" id="ps-ig-status-${i}"></div>`
              : ''}
            ${clip.thumbnail
              ? `<a class="ps-thumb-btn" href="/static/${escapeHtml(clip.thumbnail)}?t=${Date.now()}" download>⬇ Baixar thumbnail</a>`
              : ''}
          </div>
        </div>`;
      view.appendChild(card);
    });
    lastProdClips = clips;
  }, 600);
}

// guarda os clips renderizados para o botão de publicação
let lastProdClips = [];

function copyText(el) {
  const t = el.textContent || '';
  navigator.clipboard?.writeText(t).then(() => {
    const old = el.style.background;
    el.style.background = 'rgba(212,255,79,0.25)';
    setTimeout(() => { el.style.background = old; }, 500);
  });
}

async function publishClipToYouTube(i, btn) {
  const clip = (lastProdClips || [])[i];
  if (!clip || !clip.arquivo) return;
  const statusEl = document.getElementById(`ps-yt-status-${i}`);
  if (!confirm(`Publicar "${clip.titulo}" no seu canal do YouTube?`)) return;

  if (btn) { btn.disabled = true; btn.textContent = 'Enviando…'; }
  if (statusEl) { statusEl.textContent = 'Enviando para o YouTube…'; statusEl.style.color = ''; }

  try {
    const resp = await fetch('/api/youtuber/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        arquivo: clip.arquivo,
        titulo: clip.titulo,
        hook: clip.hook || '',
        hashtags: clip.hashtags || [],
        viral_score: clip.viral_score, tier: clip.tier,
        thumb_texto: clip.thumb_texto || '', thumb_emocao: clip.thumb_emocao || '',
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Falha ao publicar');
    if (statusEl) {
      statusEl.innerHTML = `Publicado (${data.privacy}): <a href="${data.url}" target="_blank">${data.url}</a>`;
      statusEl.style.color = '#d4ff4f';
    }
    if (btn) btn.textContent = '✓ Publicado';
  } catch (e) {
    if (statusEl) { statusEl.textContent = 'Erro: ' + e.message; statusEl.style.color = '#ff6b6b'; }
    if (btn) { btn.disabled = false; btn.textContent = '▶ Publicar no YouTube'; }
  }
}

async function publishClipToInstagram(i, btn) {
  const clip = (lastProdClips || [])[i];
  if (!clip || !clip.arquivo) return;
  const statusEl = document.getElementById(`ps-ig-status-${i}`);
  if (!confirm(`Publicar "${clip.titulo}" como Reels no Instagram?`)) return;

  if (btn) { btn.disabled = true; btn.textContent = 'Enviando…'; }
  if (statusEl) {
    statusEl.textContent = 'Subindo e processando no Instagram (pode levar 1-2 min)…';
    statusEl.style.color = '';
  }

  try {
    const resp = await fetch('/api/youtuber/publish_instagram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        arquivo: clip.arquivo,
        titulo: clip.titulo,
        hook: clip.hook || '',
        hashtags: clip.hashtags || [],
        viral_score: clip.viral_score, tier: clip.tier,
        thumb_texto: clip.thumb_texto || '', thumb_emocao: clip.thumb_emocao || '',
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || 'Falha ao publicar');
    if (statusEl) {
      statusEl.textContent = '✓ Publicado no Instagram';
      statusEl.style.color = '#d4ff4f';
    }
    if (btn) btn.textContent = '✓ Publicado';
  } catch (e) {
    if (statusEl) { statusEl.textContent = 'Erro: ' + e.message; statusEl.style.color = '#ff6b6b'; }
    if (btn) { btn.disabled = false; btn.textContent = '📷 Publicar no Instagram (Reels)'; }
  }
}

$('#prodCancelBtn')?.addEventListener('click', () => {
  if (prodEventSource) prodEventSource.close();
  stopProdTimer(false);
  if (prodPipeline) prodPipeline.hidden = true;
  setClipsLoading(false);
});

$('#prodNewBtn')?.addEventListener('click', () => {
  if (prodResult)   prodResult.hidden   = true;
  if (prodPipeline) prodPipeline.hidden = true;
  if (videoUrlEl)   videoUrlEl.value    = '';
  if (prodPipelineError) prodPipelineError.hidden = true;
  document.querySelectorAll('#prodPipeline .ps-step-card')
    .forEach((s) => s.classList.remove('running', 'done'));
  document.querySelectorAll('#prodPipeline .step-detail')
    .forEach((d) => { d.textContent = ''; });
  videoUrlEl?.focus();
});

function useVideoInProducao(url) {
  if (videoUrlEl) videoUrlEl.value = url;
  switchTab('paneProducao');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}


/* ════════════════════════════════════════════════════════════
   PAINEL 2 — Inteligência e Pesquisa (Trend Scanner)
   ════════════════════════════════════════════════════════════ */

let keywords = [];
const kwInput          = $('#kwInput');
const addKwBtn         = $('#addKwBtn');
const kwChips          = $('#kwChips');
const escanearBtn      = $('#escanearBtn');
const pesquisaResults  = $('#pesquisaResults');
const pesquisaErrorBox = $('#pesquisaErrorBox');

addKwBtn?.addEventListener('click', addKeyword);
kwInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') addKeyword(); });

function addKeyword() {
  const val = kwInput?.value.trim();
  if (!val || keywords.length >= 5 || keywords.includes(val)) return;
  keywords.push(val);
  if (kwInput) kwInput.value = '';
  renderKeywords();
}

function removeKeyword(kw) {
  keywords = keywords.filter((k) => k !== kw);
  renderKeywords();
}

function renderKeywords() {
  if (!kwChips) return;
  kwChips.innerHTML = '';
  keywords.forEach((kw) => {
    const chip = document.createElement('span');
    chip.className = 'ps-kw-chip';
    chip.innerHTML = `${escapeHtml(kw)}<button class="ps-kw-chip-del">×</button>`;
    chip.querySelector('.ps-kw-chip-del').addEventListener('click', () => removeKeyword(kw));
    kwChips.appendChild(chip);
  });
}

escanearBtn?.addEventListener('click', fetchTrends);

async function fetchTrends() {
  const kws   = keywords.length ? keywords.join(', ') : kwInput?.value.trim();
  const niche = kws;
  if (!niche) { kwInput?.focus(); return; }

  setScanLoading(true);
  if (pesquisaErrorBox) pesquisaErrorBox.hidden = true;

  try {
    const res = await fetch('/api/youtuber/trends', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ niche }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro ao buscar tendências');

    renderTrends(data);
    if (pesquisaResults) pesquisaResults.hidden = false;

  } catch (e) {
    if (pesquisaErrorBox) {
      pesquisaErrorBox.textContent = '⚠ ' + e.message;
      pesquisaErrorBox.hidden = false;
    }
  } finally {
    setScanLoading(false);
  }
}

function setScanLoading(on) {
  if (!escanearBtn) return;
  escanearBtn.disabled = on;
  const span = escanearBtn.querySelector('span');
  if (span) span.textContent = on ? 'Escaneando…' : 'Escanear Tendências';
}

function renderTrends(data) {
  /* Topics */
  const topics   = data.trending_topics || [];
  const topicsEl = $('#trendingTopics');
  const countEl  = $('#pesquisaTrendCount');

  if (countEl) countEl.textContent = `${topics.length} tópicos encontrados`;
  if (topicsEl) {
    topicsEl.innerHTML = '';
    topics.slice(0, 6).forEach((topic, i) => {
      const item = document.createElement('div');
      item.className = 'ps-trend-item';
      item.innerHTML = `
        <span class="ps-trend-rank">${i + 1}</span>
        <span class="ps-trend-name">${escapeHtml(topic)}</span>
        <span class="ps-trend-count">${Math.floor(50 + Math.random() * 500)}k</span>
        <span class="ps-trend-growth">↗ 1.000%</span>`;
      item.addEventListener('click', () => {
        if (kwInput) { kwInput.value = topic; }
        scanTopicVideos(topic);
      });
      topicsEl.appendChild(item);
    });
  }

  /* Reddit */
  const redditPosts = data.reddit_posts || [];
  const redditEl    = $('#redditPosts');
  const redditSec   = $('#redditSection');
  if (redditPosts.length && redditEl && redditSec) {
    redditEl.innerHTML = redditPosts.slice(0, 5).map((p) => `
      <div class="ps-reddit-item">
        <a class="ps-reddit-link" href="${escapeHtml(p.url)}"
           target="_blank" rel="noopener">${escapeHtml(p.titulo)}</a>
        <div class="ps-reddit-meta">↑ ${p.upvotes}</div>
      </div>`).join('');
    redditSec.hidden = false;
  } else if (redditSec) {
    redditSec.hidden = true;
  }

  /* Top videos */
  const videos    = data.top_videos || [];
  const videosEl  = $('#pesquisaVideosList');
  const videosSec = $('#pesquisaVideosSection');

  if (videos.length && videosEl && videosSec) {
    const maxViews = Math.max(...videos.map((v) => v.visualizacoes || 0), 1);
    videosEl.innerHTML = '';

    videos.forEach((v) => {
      const opp  = Math.round(60 + ((v.visualizacoes || 0) / maxViews) * 40);
      const dur  = v.duracao_minutos ? `${v.duracao_minutos}:00` : '';
      const card = document.createElement('div');
      card.className = 'ps-video-card';
      card.innerHTML = `
        <div class="ps-vid-thumb">
          ${v.thumbnail
            ? `<img src="${escapeHtml(v.thumbnail)}" alt="" loading="lazy">`
            : `<div class="ps-vid-no-thumb">▶</div>`}
          ${dur ? `<span class="ps-vid-dur">${escapeHtml(dur)}</span>` : ''}
          <div class="ps-vid-check">✓</div>
        </div>
        <div class="ps-vid-info">
          <div class="ps-vid-title">${escapeHtml(v.titulo)}</div>
          <div class="ps-vid-meta">
            ${escapeHtml(v.canal)}${v.visualizacoes ? ' · ' + formatViews(v.visualizacoes) : ''}
          </div>
          <div class="ps-opp-row">
            <span class="ps-opp-label">Oportunidade</span>
            <div class="ps-opp-track"><div class="ps-opp-fill" style="width:${opp}%"></div></div>
            <span class="ps-opp-val">${opp}</span>
          </div>
        </div>`;
      card.addEventListener('click', () => useVideoInProducao(v.url));
      videosEl.appendChild(card);
    });

    videosSec.hidden = false;
  } else if (videosSec) {
    videosSec.hidden = true;
  }
}

/* Seleciona um assunto da tendência → escaneia vídeos REALMENTE sobre o tema
   (relevância verificada por LLM) para o usuário escolher qual cortar. */
async function scanTopicVideos(topic, nicheOverride) {
  const niche = (nicheOverride && nicheOverride.trim())
    || (keywords.length ? keywords.join(', ') : (kwInput?.value.trim() || topic));
  const videosEl  = $('#pesquisaVideosList');
  const videosSec = $('#pesquisaVideosSection');
  if (!videosEl || !videosSec) return;

  videosSec.hidden = false;
  videosEl.innerHTML =
    `<p class="empty-msg">🔎 Escaneando vídeos sobre "${escapeHtml(topic)}" e verificando relevância…</p>`;
  videosSec.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  try {
    const res = await fetch('/api/youtuber/topic-videos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, niche }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro ao buscar vídeos');
    renderTopicVideos(topic, data);
  } catch (e) {
    videosEl.innerHTML = `<p class="empty-msg">⚠ ${escapeHtml(e.message)}</p>`;
  }
}

function renderTopicVideos(topic, data) {
  const videosEl = $('#pesquisaVideosList');
  if (!videosEl) return;
  const videos = data.videos || [];

  if (!videos.length) {
    videosEl.innerHTML =
      `<p class="empty-msg">${escapeHtml(data.reason || 'Nenhum vídeo relevante encontrado.')}</p>`;
    return;
  }

  videosEl.innerHTML = '';
  videos.forEach((v) => {
    const rel = (v.relevancia != null) ? Math.round(v.relevancia * 100) : null;
    const dur = v.duracao_minutos ? `${v.duracao_minutos} min` : '';
    const card = document.createElement('div');
    card.className = 'ps-video-card';
    card.innerHTML = `
      <div class="ps-vid-thumb"><div class="ps-vid-no-thumb">▶</div>
        ${dur ? `<span class="ps-vid-dur">${escapeHtml(dur)}</span>` : ''}</div>
      <div class="ps-vid-info">
        <div class="ps-vid-title">${escapeHtml(v.titulo)}</div>
        <div class="ps-vid-meta">${escapeHtml(v.canal || '')}</div>
        ${rel != null
          ? `<div class="ps-rel-badge" title="${escapeHtml(v.motivo || '')}">✓ Relevância ${rel}%</div>`
          : (data.filtered ? '' : '<div class="ps-rel-badge ps-rel-unverified">relevância não verificada</div>')}
        <button class="ps-use-vid-btn">Usar este vídeo</button>
      </div>`;
    card.querySelector('.ps-use-vid-btn').addEventListener('click', (ev) => {
      ev.stopPropagation();
      useVideoInProducao(v.url);
    });
    card.addEventListener('click', () => useVideoInProducao(v.url));
    videosEl.appendChild(card);
  });
}


/* ════════════════════════════════════════════════════════════
   PAINEL 3 — Análise de Concorrência (Monitor Outlier)
   ════════════════════════════════════════════════════════════ */

let competitors = [];
try { competitors = JSON.parse(localStorage.getItem('yt_competitors') || '[]'); } catch { /* */ }

const addCompInput   = $('#addCompInput');
const addCompBtn     = $('#addCompBtn');
const competitorList = $('#competitorList');
const compEmpty      = $('#compEmpty');
const compCount      = $('#compCount');
const analyzeBtn     = $('#analyzeBtn');
const analyzeCount   = $('#analyzeCount');

function saveCompetitors() {
  try { localStorage.setItem('yt_competitors', JSON.stringify(competitors)); } catch { /* */ }
}

function renderCompetitors() {
  if (!competitorList) return;

  competitorList.querySelectorAll('.ps-competitor-card').forEach((c) => c.remove());

  if (compCount)    compCount.textContent    = `${competitors.length}/5`;
  if (analyzeCount) analyzeCount.textContent = competitors.length;
  if (analyzeBtn)   analyzeBtn.disabled      = competitors.length === 0;
  if (compEmpty)    compEmpty.hidden         = competitors.length > 0;

  competitors.forEach((comp, i) => {
    const card    = document.createElement('div');
    card.className = 'ps-competitor-card';
    const display = comp.name || comp.handle || comp.url;
    const initial = display[0].toUpperCase();
    card.innerHTML = `
      <div class="ps-comp-avatar">${escapeHtml(initial)}</div>
      <div class="ps-comp-info">
        <div class="ps-comp-name">${escapeHtml(display)}</div>
        <div class="ps-comp-handle">${escapeHtml(comp.handle || comp.url)}</div>
      </div>
      <button class="ps-comp-remove" title="Remover">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/>
          <path d="M19 6l-1 14H6L5 6"/>
          <path d="M10 11v6"/><path d="M14 11v6"/>
          <path d="M9 6V4h6v2"/>
        </svg>
      </button>`;
    card.querySelector('.ps-comp-remove').addEventListener('click', () => {
      competitors.splice(i, 1);
      saveCompetitors();
      renderCompetitors();
    });
    if (compEmpty) competitorList.insertBefore(card, compEmpty);
    else competitorList.appendChild(card);
  });
}

addCompBtn?.addEventListener('click', addCompetitor);
addCompInput?.addEventListener('keydown', (e) => { if (e.key === 'Enter') addCompetitor(); });

function addCompetitor() {
  const val = addCompInput?.value.trim();
  if (!val || competitors.length >= 5) return;

  let name   = val;
  let handle = val;
  if (val.startsWith('@')) {
    handle = val;
    name   = val;
  } else if (val.includes('youtube.com')) {
    const parts = val.split('/').filter(Boolean);
    handle = parts[parts.length - 1] || val;
    name   = handle;
  }

  competitors.push({ name, handle, url: val });
  if (addCompInput) addCompInput.value = '';
  saveCompetitors();
  renderCompetitors();
}

analyzeBtn?.addEventListener('click', () => {
  alert('Análise de concorrentes em desenvolvimento. Em breve disponível!');
});

renderCompetitors();


/* ── Helpers ──────────────────────────────────────────────── */
function formatViews(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}k`;
  return `${n}`;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str ?? '';
  return div.innerHTML;
}

/* Focus initial field */
videoUrlEl?.focus();

/* ════════════════════════════════════════════════════════════
   Veio da tela de Trends ("Criar conteúdo sobre isso")?
   Lê o assunto, abre a aba de Pesquisa e já escaneia vídeos
   RELEVANTES sobre o tema (relevância verificada por LLM).
   ════════════════════════════════════════════════════════════ */
(function bootstrapTrendTopic() {
  let briefing = null;
  try {
    const raw = localStorage.getItem('yt_trend_briefing');
    if (raw) briefing = JSON.parse(raw);
  } catch { /* */ }
  if (!briefing || !briefing.titulo) return;
  try {
    localStorage.removeItem('yt_trend_briefing');
    localStorage.removeItem('yt_trend_topic');
    localStorage.removeItem('yt_trend_niche');
  } catch { /* */ }

  if (kwInput) kwInput.value = briefing.categoria || briefing.titulo;
  if (typeof nicheProducaoEl !== 'undefined' && nicheProducaoEl) {
    nicheProducaoEl.value = briefing.categoria || briefing.titulo;
  }
  switchTab('panePesquisa');
  setTimeout(() => enterFromTrend(briefing), 120);
})();

/* Renderiza o ASSUNTO COMPLETO escolhido + escaneia vídeos relevantes. */
async function enterFromTrend(briefing) {
  const panel = document.getElementById('panePesquisa');
  if (!panel) return;

  let box = document.getElementById('trendBriefingBox');
  if (!box) {
    box = document.createElement('div');
    box.id = 'trendBriefingBox';
    box.className = 'ps-card';
    box.style.marginBottom = '18px';
    panel.insertBefore(box, panel.firstChild);
  }

  const tags = (briefing.hashtags || [])
    .map((h) => `<span class="ps-hl-tag">#${escapeHtml(String(h).replace(/^#/, ''))}</span>`)
    .join('');
  const scores = `
    <div style="display:flex;gap:16px;margin:10px 0;font-size:12px;color:var(--ps-muted,#9b9a96)">
      <span>Viral <b style="color:#d4ff4f">${briefing.viral_score || 0}</b></span>
      <span>Oportunidade <b style="color:#64a0ff">${briefing.oportunidade_score || 0}</b></span>
      <span>Polêmica <b style="color:#ff6b6b">${briefing.polemica_score || 0}</b></span>
    </div>`;

  box.innerHTML = `
    <div class="ps-card-label">ASSUNTO ESCOLHIDO</div>
    <h3 style="margin:6px 0 4px;color:#f4f3f0;font-size:20px">${escapeHtml(briefing.titulo)}</h3>
    ${briefing.categoria ? `<span class="ps-rel-badge">${escapeHtml(briefing.categoria)}</span>` : ''}
    ${briefing.insight ? `<p style="color:#b9b8b4;font-size:14px;line-height:1.55;margin:10px 0">${escapeHtml(briefing.insight)}</p>` : ''}
    ${briefing.angulo ? `<div style="border-left:2px solid #d4ff4f;padding-left:12px;margin:10px 0;color:#cfcecb;font-size:13px;line-height:1.55"><b style="color:#9b9a96;font-size:11px;letter-spacing:1px">ÂNGULO PARA CRIADORES</b><br>${escapeHtml(briefing.angulo)}</div>` : ''}
    ${scores}
    ${tags ? `<div class="ps-hl-tags">${tags}</div>` : ''}
    <div id="trendVideos" style="margin-top:18px"><p class="empty-msg">🔎 Escaneando vídeos sobre este assunto e verificando relevância…</p></div>
  `;
  box.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Busca rica: título + principais hashtags (o "assunto completo")
  const query = [briefing.titulo, ...(briefing.hashtags || []).slice(0, 3)]
    .filter(Boolean).join(' ');

  try {
    const res = await fetch('/api/youtuber/topic-videos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: query, niche: briefing.categoria || '' }),
    });
    const data = await res.json();
    renderTrendVideos(data);
  } catch (e) {
    const el = document.getElementById('trendVideos');
    if (el) el.innerHTML = `<p class="empty-msg">⚠ ${escapeHtml(e.message)}</p>`;
  }
}

function renderTrendVideos(data) {
  const el = document.getElementById('trendVideos');
  if (!el) return;
  const vids = data.videos || [];
  if (!vids.length) {
    el.innerHTML = `<p class="empty-msg">${escapeHtml(data.reason || 'Nenhum vídeo relevante encontrado para este assunto.')}</p>`;
    return;
  }
  let html = '<div class="ps-card-label">VÍDEOS SOBRE O ASSUNTO</div>';
  vids.forEach((v) => {
    const rel = (v.relevancia != null) ? Math.round(v.relevancia * 100) : null;
    const dur = v.duracao_minutos ? `${v.duracao_minutos} min` : '';
    html += `
      <div class="ps-video-card" style="margin-top:10px">
        <div class="ps-vid-info">
          <div class="ps-vid-title">${escapeHtml(v.titulo)}</div>
          <div class="ps-vid-meta">${escapeHtml(v.canal || '')}${dur ? ' · ' + escapeHtml(dur) : ''}</div>
          ${rel != null ? `<div class="ps-rel-badge" title="${escapeHtml(v.motivo || '')}">✓ Relevância ${rel}%</div>` : ''}
          <button class="ps-use-vid-btn" data-url="${escapeHtml(v.url)}">Usar este vídeo no corte</button>
        </div>
      </div>`;
  });
  el.innerHTML = html;
  el.querySelectorAll('.ps-use-vid-btn').forEach((btn) => {
    btn.addEventListener('click', () => useVideoInProducao(btn.dataset.url));
  });
}

/* ════════ Busca por pessoa / podcast ════════ */
document.getElementById('personSearchBtn')?.addEventListener('click', async () => {
  const person = document.getElementById('personInput')?.value.trim() || '';
  const topic  = document.getElementById('personTopic')?.value.trim() || '';
  const prefer = document.getElementById('preferPodcast')?.checked ?? true;
  const out    = document.getElementById('personResults');
  const btn    = document.getElementById('personSearchBtn');
  if (!person && !topic) {
    if (out) out.innerHTML = '<p class="empty-msg">Informe uma pessoa ou um assunto.</p>';
    return;
  }
  btn.disabled = true; btn.textContent = 'Buscando…';
  if (out) out.innerHTML = '<p class="empty-msg">🎙 Buscando entrevistas e podcasts…</p>';
  try {
    const res = await fetch('/api/youtuber/people-search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ person, topic, prefer_podcast: prefer }),
    });
    const data = await res.json();
    renderPeopleVideos(data, out);
  } catch (e) {
    if (out) out.innerHTML = `<p class="empty-msg">⚠ ${escapeHtml(e.message)}</p>`;
  } finally {
    btn.disabled = false; btn.textContent = 'Buscar vídeos para cortar';
  }
});

function renderPeopleVideos(data, out) {
  if (!out) return;
  const vids = (data && data.videos) || [];
  if (!vids.length) {
    out.innerHTML = `<p class="empty-msg">${escapeHtml((data && data.reason) || 'Nenhum vídeo encontrado.')}</p>`;
    return;
  }
  let html = '<div class="ps-card-label" style="margin-bottom:8px">RESULTADOS (melhores para corte)</div>';
  vids.forEach((v) => {
    const rel = (v.relevancia != null) ? Math.round(v.relevancia * 100) : null;
    const dur = v.duracao_minutos ? `${v.duracao_minutos} min` : '';
    html += `
      <div class="ps-video-card" style="margin-top:10px">
        <div class="ps-vid-info">
          <div class="ps-vid-title">${escapeHtml(v.titulo || '')}</div>
          <div class="ps-vid-meta">${dur}${v.motivo ? ' · ' + escapeHtml(v.motivo) : ''}</div>
          ${rel != null ? `<div class="ps-rel-badge">✓ Match ${rel}%</div>` : ''}
          <button class="ps-use-vid-btn" data-url="${escapeHtml(v.url || '')}">Usar este vídeo no corte</button>
        </div>
      </div>`;
  });
  out.innerHTML = html;
  out.querySelectorAll('.ps-use-vid-btn').forEach((b) => {
    b.addEventListener('click', () => useVideoInProducao(b.dataset.url));
  });
}

/* ════════ Export Short 9:16 (1080×1920) ════════ */
async function exportVertical(arquivo, btn) {
  const status = btn.nextElementSibling;
  btn.disabled = true; const orig = btn.textContent;
  btn.textContent = '⏳ Gerando Short vertical…';
  if (status) status.textContent = 'Reenquadrando para 9:16 com fundo desfocado…';
  try {
    const res = await fetch('/api/youtuber/vertical', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ arquivo, mode: 'blur' }),
    });
    const data = await res.json();
    if (data.ok && data.arquivo) {
      if (status) {
        status.innerHTML = `✓ Short pronto! <a href="/static/${data.arquivo}?t=${Date.now()}" download style="color:#d4ff4f;text-decoration:underline">Baixar 1080×1920</a>`;
      }
      btn.textContent = '✓ Short 9:16 gerado';
    } else {
      if (status) status.textContent = '⚠ ' + (data.erro || 'falha ao gerar');
      btn.textContent = orig; btn.disabled = false;
    }
  } catch (e) {
    if (status) status.textContent = '⚠ ' + e.message;
    btn.textContent = orig; btn.disabled = false;
  }
}

// Pré-preenche a URL do vídeo se vier da URL da página (?url=...) — é
// assim que o card "Ver cortes" do Planejamento abre o Youtuber já com
// o vídeo certo.
(function prefillFromPlanejamento() {
  const params = new URLSearchParams(window.location.search);
  const url = params.get('url');
  const videoUrlEl = document.getElementById('videoUrl');
  if (url && videoUrlEl) {
    videoUrlEl.value = url;
  }
})();

// Legenda: mostra/esconde o seletor de idioma de tradução junto com o
// toggle liga/desliga da legenda.
(function () {
  const checkbox = document.getElementById('gerarLegenda');
  const wrap = document.getElementById('legendaIdiomaWrap');
  if (!checkbox || !wrap) return;
  const sync = () => { wrap.style.display = checkbox.checked ? '' : 'none'; };
  checkbox.addEventListener('change', sync);
  sync();
})();
