/* ═══════════════════════════════════════════════════════════════════
   estudio.js — Módulo Estúdio (geração de vídeo via MoneyPrinterTurbo)

   Segue o mesmo contrato de eventos do youtuber.js:
     POST /api/estudio            → { job_id }
     GET  /api/stream/<job_id>    → SSE: progress | complete | error | end
   Nenhum código existente é alterado — arquivo 100% novo.
   ═══════════════════════════════════════════════════════════════════ */

'use strict';

/* ── refs ─────────────────────────────────────────────────────────── */
const estSubject       = document.getElementById('estSubject');
const estScript        = document.getElementById('estScript');
const estGerarBtn      = document.getElementById('estGerarBtn');
const estErrorBox      = document.getElementById('estErrorBox');
const estPipeline      = document.getElementById('estPipeline');
const estPipelineTitle = document.getElementById('estPipelineTitle');
const estPipelineError = document.getElementById('estPipelineError');
const estResult        = document.getElementById('estResult');
const estResultTitle   = document.getElementById('estResultTitle');
const estVideosGrid    = document.getElementById('estVideosGrid');
const estNewBtn        = document.getElementById('estNewBtn');
const estAdvToggleBtn  = document.getElementById('estAdvToggleBtn');
const estAdvBody       = document.getElementById('estAdvBody');
const estAspectDesc    = document.getElementById('estAspectDesc');

let estEventSource = null;
let estAspect = '9:16';
let estVoice  = 'pt-BR-AntonioNeural-Male';
let estCount  = 1;

/* ── toggles (mesmo padrão dos ps-toggle-group do youtuber) ───────── */
function wireToggleGroup(groupId, attr, onChange) {
  const group = document.getElementById(groupId);
  if (!group) return;
  group.querySelectorAll('.est-toggle-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      group.querySelectorAll('.est-toggle-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      onChange(btn.dataset[attr]);
    });
  });
}

wireToggleGroup('estAspectGroup', 'aspect', (v) => {
  estAspect = v;
  if (estAspectDesc) {
    estAspectDesc.textContent = v === '9:16'
      ? 'Ideal para Shorts, Reels e TikTok — 1080×1920'
      : 'Ideal para YouTube — 1920×1080';
  }
});
wireToggleGroup('estVoiceGroup', 'voice', (v) => { estVoice = v; });
wireToggleGroup('estCountGroup', 'count', (v) => { estCount = parseInt(v, 10) || 1; });

/* ── accordion avançado ───────────────────────────────────────────── */
if (estAdvToggleBtn) {
  estAdvToggleBtn.addEventListener('click', () => {
    const open = !estAdvBody.hidden;
    estAdvBody.hidden = open;
    estAdvToggleBtn.classList.toggle('open', !open);
  });
}

/* ── iniciar geração ──────────────────────────────────────────────── */
async function gerarVideo() {
  const subject = (estSubject?.value || '').trim();
  if (!subject) {
    showError(estErrorBox, 'Informe um tema para o vídeo.');
    return;
  }

  setLoading(true);
  if (estErrorBox)      estErrorBox.hidden = true;
  if (estPipelineError) estPipelineError.hidden = true;
  if (estPipelineTitle) estPipelineTitle.textContent = subject;

  try {
    const res = await fetch('/api/estudio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subject,
        script: (estScript?.value || '').trim(),
        aspect: estAspect,
        voice:  estVoice,
        count:  estCount,
      }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || 'Falha ao iniciar');

    if (estPipeline) estPipeline.hidden = false;
    if (estResult)   estResult.hidden   = true;

    document.querySelectorAll('#estPipeline .est-step')
      .forEach((s) => s.classList.remove('running', 'done'));
    document.querySelectorAll('#estPipeline .step-detail')
      .forEach((d) => { d.textContent = ''; });

    listenEstudioStream(body.job_id);

  } catch (e) {
    showError(estErrorBox, e.message);
    setLoading(false);
  }
}

if (estGerarBtn) estGerarBtn.addEventListener('click', gerarVideo);
if (estSubject) {
  estSubject.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') gerarVideo();
  });
}

/* ── SSE (contrato idêntico ao dos outros módulos) ────────────────── */
function listenEstudioStream(jobId) {
  if (estEventSource) estEventSource.close();
  estEventSource = new EventSource(`/api/stream/${jobId}`);

  estEventSource.addEventListener('progress', (e) => {
    const { step, status, detail } = JSON.parse(e.data);
    updateEstStep(step, status, detail);
  });

  estEventSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data);
    renderEstVideos(data);
    setLoading(false);
  });

  estEventSource.addEventListener('pipeline_error', (e) => {
    try {
      showError(estPipelineError, JSON.parse(e.data).message);
    } catch { /* conexão fechada — ignora */ }
    setLoading(false);
  });

  estEventSource.addEventListener('end', () => estEventSource.close());
}

function updateEstStep(step, status, detail) {
  const el = document.querySelector(`#estPipeline .est-step[data-step="${step}"]`);
  if (!el) return;
  el.classList.remove('running', 'done');
  if (status === 'running') el.classList.add('running');
  if (status === 'done')    el.classList.add('done');
  const d = el.querySelector('.step-detail');
  if (d && detail) d.textContent = detail;
}

/* ── resultados ───────────────────────────────────────────────────── */
function renderEstVideos(data) {
  const videos  = data.videos || [];
  const subject = data.subject || '';

  if (estResultTitle) estResultTitle.textContent = subject;
  if (estVideosGrid)  estVideosGrid.innerHTML = '';

  const vertical = (data.aspect || estAspect) === '9:16';

  videos.forEach((src, i) => {
    const card = document.createElement('div');
    card.className = 'est-video-card';

    const video = document.createElement('video');
    video.src = src;
    video.controls = true;
    video.preload = 'metadata';
    video.style.width = '100%';
    video.style.borderRadius = 'var(--radius-sm)';
    video.style.aspectRatio = vertical ? '9 / 16' : '16 / 9';
    video.style.background = 'var(--bg-2)';
    video.style.objectFit = 'contain';

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-top:10px;gap:8px';

    const label = document.createElement('span');
    label.style.cssText = 'font-size:12px;color:var(--text-2)';
    label.textContent = videos.length > 1 ? `Variação ${i + 1}` : 'Vídeo final';

    const dl = document.createElement('a');
    dl.href = src;
    dl.download = '';
    dl.className = 'ghost-btn';
    dl.textContent = '↓ Baixar';

    row.appendChild(label);
    row.appendChild(dl);
    card.appendChild(video);
    card.appendChild(row);
    estVideosGrid.appendChild(card);
  });

  if (estResult) estResult.hidden = false;
}

/* ── novo vídeo ───────────────────────────────────────────────────── */
if (estNewBtn) {
  estNewBtn.addEventListener('click', () => {
    if (estResult)   estResult.hidden   = true;
    if (estPipeline) estPipeline.hidden = true;
    if (estSubject)  { estSubject.value = ''; estSubject.focus(); }
    if (estScript)   estScript.value = '';
  });
}

/* ── helpers ──────────────────────────────────────────────────────── */
function setLoading(on) {
  if (!estGerarBtn) return;
  estGerarBtn.disabled = on;
  const span = estGerarBtn.querySelector('span');
  if (span) span.textContent = on ? 'Produzindo…' : 'Gerar Vídeo';
}

function showError(box, msg) {
  if (!box) return;
  box.textContent = '⚠ ' + msg;
  box.hidden = false;
}

/* ═══════════════════════════════════════════════════════════════════
   ABAS — Vídeo / Imagens (adicionado, não mexe na lógica de vídeo acima)
   ═══════════════════════════════════════════════════════════════════ */
document.querySelectorAll('.est-tabs .ps-tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.est-tabs .ps-tab').forEach((t) => t.classList.remove('active'));
    document.querySelectorAll('#paneEstudio, #paneImagens').forEach((p) => { p.hidden = true; });
    tab.classList.add('active');
    const panel = document.getElementById(tab.dataset.panel);
    if (panel) panel.hidden = false;
  });
});

/* ═══════════════════════════════════════════════════════════════════
   MÓDULO CRIADOR · IMAGENS (Fooocus-API) — thumbnail / carrossel / capa
   ═══════════════════════════════════════════════════════════════════ */
const imgPrompt        = document.getElementById('imgPrompt');
const imgPromptSuggestions = document.getElementById('imgPromptSuggestions');

if (imgPromptSuggestions) {
  imgPromptSuggestions.querySelectorAll('.est-suggestion-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      if (imgPrompt) {
        imgPrompt.value = chip.dataset.suggestion || '';
        imgPrompt.focus();
      }
    });
  });
}
const imgGerarBtn      = document.getElementById('imgGerarBtn');
const imgBtnLabel      = document.getElementById('imgBtnLabel');
const imgErrorBox      = document.getElementById('imgErrorBox');
const imgPipeline      = document.getElementById('imgPipeline');
const imgPipelineTitle = document.getElementById('imgPipelineTitle');
const imgPipelineError = document.getElementById('imgPipelineError');
const imgResult        = document.getElementById('imgResult');
const imgResultTitle   = document.getElementById('imgResultTitle');
const imgGrid          = document.getElementById('imgGrid');
const imgNewBtn        = document.getElementById('imgNewBtn');
const imgResetBtn      = document.getElementById('imgResetBtn');
const imgPresetDesc    = document.getElementById('imgPresetDesc');
const imgEngineDesc    = document.getElementById('imgEngineDesc');
const imgReferenceInput = document.getElementById('imgReferenceInput');
const imgRefGallery    = document.getElementById('imgRefGallery');
const imgRefClear      = document.getElementById('imgRefClear');
const imgRefLabel      = document.getElementById('imgRefLabel');
const imgAiCopyToggle  = document.getElementById('imgAiCopyToggle');
const imgCopyFields    = document.getElementById('imgCopyFields');
const imgPilarSelect   = document.getElementById('imgPilarSelect');
const imgTopicInput    = document.getElementById('imgTopicInput');

let imgEventSource = null;
let imgPreset = 'thumbnail';
let imgEngine = 'openai';  // padrão: nuvem (mais rápido)
let lastGeneratedImages = [];  // [{ src, selected }, ...] — o que vai pro Instagram é só o que está selected:true
let imgReferences = [];  // [{ name, b64, dataUrl }, ...] — até 16 (limite da OpenAI)
const IMG_REF_MAX = 16;

const IMG_PRESET_DESCS = {
  thumbnail: 'Ideal para thumbnail de vídeo — proporção 16:9.',
  carrossel: 'Gera 4 imagens — um carrossel completo para o feed do Instagram (1:1).',
  capa: 'Paisagem, ideal para capa de curso no catálogo.',
};

const IMG_ENGINE_DESCS = {
  fooocus: 'Roda no seu Mac (GPU local) — grátis, mas pode levar minutos por imagem conforme a memória disponível.',
  openai: 'Roda na nuvem — rápido, com custo baixo por imagem (~$0,005–0,02).',
};

wireToggleGroup('imgPresetGroup', 'preset', (v) => {
  imgPreset = v;
  if (imgPresetDesc) imgPresetDesc.textContent = IMG_PRESET_DESCS[v] || '';
});

wireToggleGroup('imgEngineGroup', 'engine', (v) => {
  imgEngine = v;
  if (imgEngineDesc) imgEngineDesc.textContent = IMG_ENGINE_DESCS[v] || '';
});

// ── Imagem(ns) de referência (image-to-image, motor OpenAI, até 16) ──
function renderRefGallery() {
  if (!imgRefGallery) return;
  imgRefGallery.innerHTML = '';
  imgReferences.forEach((ref, i) => {
    const item = document.createElement('div');
    item.className = 'est-ref-item';
    item.innerHTML = `
      <img src="${ref.dataUrl}" alt="${ref.name}">
      <button type="button" class="est-ref-item-remove" data-idx="${i}" title="Remover" aria-label="Remover imagem de referência">×</button>
    `;
    imgRefGallery.appendChild(item);
  });
  imgRefGallery.querySelectorAll('.est-ref-item-remove').forEach((btn) => {
    btn.addEventListener('click', () => {
      imgReferences.splice(Number(btn.dataset.idx), 1);
      renderRefGallery();
      updateRefLabel();
    });
  });
}

function updateRefLabel() {
  if (!imgRefLabel) return;
  imgRefLabel.textContent = imgReferences.length
    ? `${imgReferences.length}/${IMG_REF_MAX} imagem(ns) de referência`
    : `Usar imagem(ns) de referência (opcional, motor Nuvem — até ${IMG_REF_MAX})`;
  if (imgRefClear) imgRefClear.hidden = imgReferences.length === 0;
}

if (imgReferenceInput) {
  imgReferenceInput.addEventListener('change', () => {
    const files = Array.from(imgReferenceInput.files || []);
    const remaining = IMG_REF_MAX - imgReferences.length;
    if (files.length > remaining) {
      showError(imgErrorBox, `Só cabem mais ${remaining} imagem(ns) de referência (máximo ${IMG_REF_MAX}).`);
    }
    files.slice(0, remaining).forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = String(reader.result);
        imgReferences.push({ name: file.name, b64: dataUrl.split(',')[1] || '', dataUrl });
        renderRefGallery();
        updateRefLabel();
      };
      reader.readAsDataURL(file);
    });
    imgReferenceInput.value = '';  // permite selecionar o mesmo arquivo de novo depois
  });
}
if (imgRefClear) {
  imgRefClear.addEventListener('click', () => {
    imgReferences = [];
    renderRefGallery();
    updateRefLabel();
  });
}

// ── Texto de impacto automático (Claude) ──
if (imgAiCopyToggle) {
  imgAiCopyToggle.addEventListener('change', () => {
    if (imgCopyFields) imgCopyFields.hidden = !imgAiCopyToggle.checked;
  });
}

async function gerarImagem() {
  const prompt = (imgPrompt?.value || '').trim();
  if (!prompt) {
    showError(imgErrorBox, 'Descreva a imagem que você quer gerar.');
    return;
  }
  if (imgReferences.length && imgEngine !== 'openai') {
    showError(imgErrorBox, 'Imagem de referência só funciona com o motor Nuvem (OpenAI). Troca o motor ou remove as referências.');
    return;
  }
  const aiCopy = !!(imgAiCopyToggle && imgAiCopyToggle.checked);
  if (aiCopy && imgPreset !== 'carrossel') {
    showError(imgErrorBox, 'Texto de impacto automático só funciona no preset Carrossel Instagram.');
    return;
  }

  imgGerarBtn.disabled = true;
  if (imgBtnLabel) imgBtnLabel.textContent = 'Gerando…';
  if (imgErrorBox) imgErrorBox.hidden = true;
  if (imgPipelineError) imgPipelineError.hidden = true;
  if (imgPipelineTitle) imgPipelineTitle.textContent = prompt;

  try {
    const payload = { prompt, preset: imgPreset, engine: imgEngine };
    if (imgReferences.length) payload.reference_images_b64 = imgReferences.map((r) => r.b64);
    if (aiCopy) {
      payload.ai_copy = true;
      payload.pilar = imgPilarSelect?.value || 'Cloud + IA';
      payload.topic = (imgTopicInput?.value || '').trim();
    }

    const res = await fetch('/api/imagem', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || 'Falha ao iniciar');

    if (imgPipeline) imgPipeline.hidden = false;
    // NÃO esconde imgResult — a galeria acumulada de gerações anteriores
    // continua visível enquanto a nova imagem é processada.

    document.querySelectorAll('#imgPipeline .est-step')
      .forEach((s) => s.classList.remove('running', 'done'));
    document.querySelectorAll('#imgPipeline .step-detail')
      .forEach((d) => { d.textContent = ''; });

    listenImagemStream(body.job_id);

  } catch (e) {
    showError(imgErrorBox, e.message);
    imgGerarBtn.disabled = false;
    if (imgBtnLabel) imgBtnLabel.textContent = 'Gerar Imagem';
  }
}

if (imgGerarBtn) imgGerarBtn.addEventListener('click', gerarImagem);
if (imgPrompt) {
  imgPrompt.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') gerarImagem();
  });
}

function listenImagemStream(jobId) {
  if (imgEventSource) imgEventSource.close();
  imgEventSource = new EventSource(`/api/stream/${jobId}`);

  imgEventSource.addEventListener('progress', (e) => {
    const { step, status, detail } = JSON.parse(e.data);
    const el = document.querySelector(`#imgPipeline .est-step[data-step="${step}"]`);
    if (!el) return;
    el.classList.remove('running', 'done');
    if (status === 'running') el.classList.add('running');
    if (status === 'done')    el.classList.add('done');
    const d = el.querySelector('.step-detail');
    if (d && detail) d.textContent = detail;
  });

  imgEventSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data);
    renderImagens(data);
    imgGerarBtn.disabled = false;
    if (imgBtnLabel) imgBtnLabel.textContent = 'Gerar Imagem';
  });

  imgEventSource.addEventListener('pipeline_error', (e) => {
    try {
      showError(imgPipelineError, JSON.parse(e.data).message);
    } catch { /* conexão fechada — ignora */ }
    imgGerarBtn.disabled = false;
    if (imgBtnLabel) imgBtnLabel.textContent = 'Gerar Imagem';
  });

  imgEventSource.addEventListener('end', () => imgEventSource.close());
}

function updateSelectionCount() {
  const total = lastGeneratedImages.length;
  const selected = lastGeneratedImages.filter((i) => i.selected).length;
  if (igSelectionCount) {
    igSelectionCount.textContent = total
      ? `${selected}/${total} selecionada(s) pra publicar`
      : '';
  }
  if (igPublishBtn) igPublishBtn.disabled = selected === 0;
}

function renderImagens(data) {
  const images = data.images || [];
  const prompt = data.prompt || '';
  const startIndex = lastGeneratedImages.length;
  // ACUMULA entre gerações (não sobrescreve) — cada imagem nova entra
  // pré-selecionada (checkbox marcado), pra manter o "1 clique publica"
  // já funcionando por padrão; o usuário desmarca o que não quiser.
  images.forEach((src) => lastGeneratedImages.push({ src, selected: true }));

  if (imgResultTitle) imgResultTitle.textContent = prompt;
  // imgGrid NÃO é limpo aqui — cada geração soma cards novos aos que já
  // existem, até o usuário clicar em "Resetar tudo".

  images.forEach((src, i) => {
    const globalIdx = startIndex + i;
    const card = document.createElement('div');
    card.className = 'est-video-card est-img-card';

    const imgWrap = document.createElement('div');
    imgWrap.style.cssText = 'position:relative';

    const img = document.createElement('img');
    img.src = src;
    img.style.width = '100%';
    img.style.borderRadius = '10px';
    img.style.display = 'block';

    // checkbox moderno (toggle), sobreposto no canto da imagem — marca/
    // desmarca se essa imagem entra na publicação do carrossel
    const checkLabel = document.createElement('label');
    checkLabel.className = 'est-img-select';
    checkLabel.title = 'Incluir na publicação';
    const checkInput = document.createElement('input');
    checkInput.type = 'checkbox';
    checkInput.checked = true;
    checkInput.addEventListener('change', () => {
      lastGeneratedImages[globalIdx].selected = checkInput.checked;
      card.classList.toggle('est-img-card-off', !checkInput.checked);
      updateSelectionCount();
    });
    const checkMark = document.createElement('span');
    checkMark.className = 'est-img-select-mark';
    checkLabel.appendChild(checkInput);
    checkLabel.appendChild(checkMark);

    imgWrap.appendChild(img);
    imgWrap.appendChild(checkLabel);

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-top:10px;gap:8px';

    const label = document.createElement('span');
    label.style.cssText = 'font-size:12px;color:var(--text-2)';
    label.textContent = `Slide ${globalIdx + 1}`;

    const dl = document.createElement('a');
    dl.href = src;
    dl.download = '';
    dl.className = 'ghost-btn';
    dl.textContent = '↓ Baixar';

    row.appendChild(label);
    row.appendChild(dl);
    card.appendChild(imgWrap);
    card.appendChild(row);
    imgGrid.appendChild(card);
  });

  if (imgResult) imgResult.hidden = false;
  updateSelectionCount();

  // fluxo "1 clique gera → 1 clique publica": se veio legenda pronta
  // (texto de impacto ligado), preenche sozinho e leva o influencer
  // direto pro botão de publicar — sem precisar escrever nada na mão.
  if (data.caption && igCaption) {
    igCaption.value = data.caption;
  }
  if (data.caption && imgPreset === 'carrossel') {
    requestAnimationFrame(() => {
      igPublishBtn?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      igPublishBtn?.focus();
    });
  }
}

if (imgNewBtn) {
  imgNewBtn.addEventListener('click', () => {
    // Só limpa o campo de prompt pra digitar o próximo — a galeria
    // acumulada (imgGrid / lastGeneratedImages) fica intacta.
    if (imgPipeline) imgPipeline.hidden = true;
    if (imgPrompt)   { imgPrompt.value = ''; imgPrompt.focus(); }
  });
}

if (imgResetBtn) {
  imgResetBtn.addEventListener('click', () => {
    lastGeneratedImages = [];
    if (imgGrid)     imgGrid.innerHTML = '';
    if (imgResult)   imgResult.hidden   = true;
    if (imgPipeline) imgPipeline.hidden = true;
    if (igCaption)   igCaption.value    = '';
    if (imgPrompt)   { imgPrompt.value = ''; imgPrompt.focus(); }
    updateSelectionCount();
  });
}

/* ═══════════════════════════════════════════════════════════════════
   PUBLICAR NO INSTAGRAM (carrossel a partir das últimas imagens geradas)
   ═══════════════════════════════════════════════════════════════════ */
const igCaption        = document.getElementById('igCaption');
const igPublishBtn     = document.getElementById('igPublishBtn');
const igPublishBtnLabel = document.getElementById('igPublishBtnLabel');
const igPublishStatus  = document.getElementById('igPublishStatus');
const igErrorBox       = document.getElementById('igErrorBox');
const igSelectionCount = document.getElementById('igSelectionCount');

let igEventSource = null;

async function publicarInstagram() {
  const selecionadas = lastGeneratedImages.filter((i) => i.selected).map((i) => i.src);
  if (!selecionadas.length) {
    showError(igErrorBox, 'Selecione pelo menos uma imagem pra publicar.');
    return;
  }

  igPublishBtn.disabled = true;
  if (igPublishBtnLabel) igPublishBtnLabel.textContent = 'Publicando…';
  if (igErrorBox) igErrorBox.hidden = true;
  if (igPublishStatus) { igPublishStatus.hidden = false; igPublishStatus.textContent = 'Iniciando...'; }

  try {
    const res = await fetch('/api/instagram/publicar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ images: selecionadas, caption: (igCaption?.value || '').trim() }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || 'Falha ao iniciar publicação');

    listenInstagramStream(body.job_id);
  } catch (e) {
    showError(igErrorBox, e.message);
    igPublishBtn.disabled = false;
    if (igPublishBtnLabel) igPublishBtnLabel.textContent = 'Publicar carrossel';
    if (igPublishStatus) igPublishStatus.hidden = true;
  }
}

if (igPublishBtn) igPublishBtn.addEventListener('click', publicarInstagram);

function listenInstagramStream(jobId) {
  if (igEventSource) igEventSource.close();
  igEventSource = new EventSource(`/api/stream/${jobId}`);

  igEventSource.addEventListener('progress', (e) => {
    const { step, status, detail } = JSON.parse(e.data);
    if (igPublishStatus) igPublishStatus.textContent = detail || step;
  });

  igEventSource.addEventListener('complete', () => {
    if (igPublishStatus) igPublishStatus.textContent = '✓ Publicado no Instagram!';
    igPublishBtn.disabled = false;
    if (igPublishBtnLabel) igPublishBtnLabel.textContent = 'Publicar carrossel';
  });

  igEventSource.addEventListener('pipeline_error', (e) => {
    try {
      showError(igErrorBox, JSON.parse(e.data).message);
    } catch { /* conexão fechada — ignora */ }
    if (igPublishStatus) igPublishStatus.hidden = true;
    igPublishBtn.disabled = false;
    if (igPublishBtnLabel) igPublishBtnLabel.textContent = 'Publicar carrossel';
  });

  igEventSource.addEventListener('end', () => igEventSource.close());
}

// Pré-preenche o tema/tópico se vier da URL (?tema=...) — é assim que o
// card "Continuar produção" do Planejamento abre o Estúdio já com o
// assunto do carrossel/conteúdo certo.
(function prefillFromPlanejamento() {
  const params = new URLSearchParams(window.location.search);
  const tema = params.get('tema');
  const topicInput = document.getElementById('imgTopicInput');
  if (tema && topicInput) {
    topicInput.value = tema;
  }
})();
