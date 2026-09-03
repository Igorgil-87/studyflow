/* ═══════════════════════════════════════════════════════════
   Study Flow — front-end logic
   ═══════════════════════════════════════════════════════════ */

const $ = (sel) => document.querySelector(sel);

const topicEl     = $('#topic');
const generateBtn = $('#generateBtn');
const composer    = $('#composer');
const pipeline    = $('#pipeline');
const result      = $('#result');
const errorBox    = $('#errorBox');
const videoCard   = $('#videoCard');

let eventSource = null;
let currentVideoMeta = null;
let currentCoursePayload = null;

/* ── Textarea auto-resize ─────────────────────────────────── */
topicEl.addEventListener('input', () => {
  topicEl.style.height = 'auto';
  topicEl.style.height = topicEl.scrollHeight + 'px';
});
topicEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) start();
});

/* ── Reset / Novo ─────────────────────────────────────────── */
$('#resetBtn').addEventListener('click', resetAll);
$('#newBtn').addEventListener('click', resetAll);

function resetAll() {
  if (eventSource) eventSource.close();
  pipeline.hidden = true;
  result.hidden = true;
  videoCard.hidden = true;
  errorBox.hidden = true;
  const vp = $('#videoPlayer');
  if (vp) { vp.hidden = true; $('#videoEl').src = ''; }
  const av = $('#aulasView');
  if (av) { av.innerHTML = ''; av.hidden = true; }
  composer.style.display = '';
  generateBtn.disabled = false;
  generateBtn.querySelector('.btn-label').textContent = 'Gerar curso';
  document.querySelectorAll('.step').forEach(s => s.className = 'step');
  document.querySelectorAll('.step-detail').forEach(d => d.textContent = '');
  topicEl.focus();
}

/* ── Start pipeline ───────────────────────────────────────── */
generateBtn.addEventListener('click', start);

async function start() {
  const topic = topicEl.value.trim();
  if (!topic) { topicEl.focus(); return; }

  generateBtn.disabled = true;
  generateBtn.querySelector('.btn-label').textContent = 'Gerando curso...';
  errorBox.hidden = true;

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic,
        flashcards: parseInt($('#flashcards').value),
        questions:  parseInt($('#questions').value),
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Falha ao iniciar');
    }

    const { job_id } = await res.json();
    pipeline.hidden = false;
    listenStream(job_id, topic);

  } catch (e) {
    showError(e.message);
    generateBtn.disabled = false;
    generateBtn.querySelector('.btn-label').textContent = 'Gerar curso';
  }
}

/* ── SSE stream ───────────────────────────────────────────── */
function listenStream(jobId, topic) {
  eventSource = new EventSource(`/api/stream/${jobId}`);

  eventSource.addEventListener('progress', (e) => {
    const { step, status, detail } = JSON.parse(e.data);
    updateStep(step, status, detail);
  });

  eventSource.addEventListener('video', (e) => {
    const v = JSON.parse(e.data);
    currentVideoMeta = v;
    videoCard.hidden = false;
    $('#videoTitle').textContent = v.titulo;
    $('#videoSub').textContent = `${v.canal} · ${v.duracao_minutos} min`;
  });

  eventSource.addEventListener('complete', (e) => {
    const payload = JSON.parse(e.data);
    const { quiz, roadmap, video_file, clips, video } = payload;
    if (video) currentVideoMeta = video;
    currentCoursePayload = { ...payload, topic, job_id: jobId };

    // YouTube volta ao fluxo completo original: o harness termina toda a
    // geração (vídeo, aulas/cortes, quiz, flashcards e roteiro) e entrega
    // o curso pronto nesta mesma experiência, sem etapa de aprovação.
    renderQuiz(quiz, topic);
    renderRoadmap(roadmap);
    renderVideo(video_file);
    if (clips && clips.length) renderClips(clips);
  });

  eventSource.addEventListener('pipeline_error', (e) => {
    try { showError(JSON.parse(e.data).message); } catch { /* conn closed */ }
  });

  eventSource.addEventListener('end', () => {
    eventSource.close();
  });
}

function updateStep(step, status, detail) {
  const el = document.querySelector(`.step[data-step="${step}"]`);
  if (!el) return;
  el.className = `step ${status}`;
  if (detail) el.querySelector('.step-detail').textContent = detail;
}

function showError(msg) {
  errorBox.hidden = false;
  errorBox.textContent = '⚠ ' + msg;
}

/* ── Render video player ──────────────────────────────────── */
function renderVideo(videoFile) {
  const player = $('#videoPlayer');
  const el = $('#videoEl');
  if (!videoFile) { player.hidden = true; return; }
  // videoFile vem como "videos/current_video.mp4" (relativo a /static)
  el.src = `/static/${videoFile}?t=${Date.now()}`;  // cache-bust
  player.hidden = false;
}

/* ── Render quiz ──────────────────────────────────────────── */
function renderQuiz(quiz, topic) {
  setTimeout(() => {
    pipeline.hidden = true;
    composer.style.display = 'none';
    result.hidden = false;

    $('#resultTitle').textContent = quiz.tema || topic;

    // Flashcards
    const fcView = $('#flashcardsView');
    fcView.innerHTML = '';
    (quiz.flashcards || []).forEach((card) => {
      const div = document.createElement('div');
      div.className = 'flashcard';
      div.innerHTML = `
        <div class="fc-label">Flashcard</div>
        <div class="fc-front">${escapeHtml(card.frente)}</div>
        <div class="fc-back">${escapeHtml(card.verso)}</div>`;
      div.addEventListener('click', () => div.classList.toggle('flipped'));
      fcView.appendChild(div);
    });

    // Questões
    const qView = $('#questoesView');
    qView.innerHTML = '';
    (quiz.questoes || []).forEach((q, i) => {
      const wrap = document.createElement('div');
      wrap.className = 'question';
      const letters = ['a', 'b', 'c', 'd', 'e'];
      const opts = (q.alternativas || []).map((alt, idx) => {
        const key = letters[idx];
        const clean = alt.replace(/^[a-e]\)\s*/i, '');
        return `<div class="q-option" data-key="${key}">
                  <span class="opt-key">${key}</span>
                  <span>${escapeHtml(clean)}</span>
                </div>`;
      }).join('');

      wrap.innerHTML = `
        <div class="q-num">Questão ${i + 1}</div>
        <div class="q-text">${escapeHtml(q.enunciado)}</div>
        <div class="q-options">${opts}</div>
        <div class="q-explain">💡 ${escapeHtml(q.explicacao || '')}</div>`;

      const correct = (q.resposta_correta || '').trim().toLowerCase().charAt(0);
      wrap.querySelectorAll('.q-option').forEach((optEl) => {
        optEl.addEventListener('click', () => {
          if (wrap.dataset.answered) return;
          wrap.dataset.answered = '1';
          const picked = optEl.dataset.key;
          wrap.querySelectorAll('.q-option').forEach((o) => {
            if (o.dataset.key === correct) o.classList.add('correct');
            else if (o.dataset.key === picked) o.classList.add('wrong');
          });
          wrap.querySelector('.q-explain').classList.add('show');
        });
      });

      qView.appendChild(wrap);
    });
  }, 600);
}

/* ── Render roadmap ───────────────────────────────────────── */
function renderRoadmap(roadmap) {
  if (!roadmap) return;
  const view = $('#roteiroView');
  view.innerHTML = '';

  const header = document.createElement('div');
  header.className = 'roadmap-intro';
  const prereqs = (roadmap.pre_requisitos || []).map(p => `<span class="chip">${escapeHtml(p)}</span>`).join('');
  header.innerHTML = `
    <div class="roadmap-level">${escapeHtml(roadmap.nivel || '')}</div>
    <p class="roadmap-summary">${escapeHtml(roadmap.resumo || '')}</p>
    ${prereqs ? `<div class="roadmap-prereqs"><span class="prereq-label">Pré-requisitos</span>${prereqs}</div>` : ''}`;
  view.appendChild(header);

  (roadmap.modulos || []).forEach((mod, i) => {
    const topics = (mod.topicos || []).map(t => `<li>${escapeHtml(t)}</li>`).join('');
    const div = document.createElement('div');
    div.className = 'module';
    div.innerHTML = `
      <div class="module-head">
        <span class="module-num">${String(i + 1).padStart(2, '0')}</span>
        <div>
          <div class="module-title">${escapeHtml(mod.titulo)}</div>
          <div class="module-duration">${escapeHtml(mod.duracao_estimada || '')}</div>
        </div>
      </div>
      <p class="module-objective">${escapeHtml(mod.objetivo || '')}</p>
      <ul class="module-topics">${topics}</ul>
      <div class="module-practice"><span>Prática</span> ${escapeHtml(mod.pratica || '')}</div>`;
    view.appendChild(div);
  });

  const next = (roadmap.proximos_passos || []).map(p => `<li>${escapeHtml(p)}</li>`).join('');
  if (next) {
    const footer = document.createElement('div');
    footer.className = 'roadmap-next';
    footer.innerHTML = `<div class="next-label">Próximos passos</div><ul>${next}</ul>`;
    view.appendChild(footer);
  }
}

/* ── Tabs ─────────────────────────────────────────────────── */
document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const which = tab.dataset.tab;
    $('#flashcardsView').hidden = which !== 'flashcards';
    $('#questoesView').hidden   = which !== 'questoes';
    $('#roteiroView').hidden    = which !== 'roteiro';
    $('#aulasView').hidden      = which !== 'aulas';
  });
});

/* ── Render clips (aulas) ─────────────────────────────────── */
function renderClips(clips) {
  const view = $('#aulasView');
  view.innerHTML = '';

  clips.forEach((clip, i) => {
    const div = document.createElement('div');
    div.className = 'clip-card';

    const videoHtml = clip.arquivo
      ? `<video class="clip-video" controls preload="metadata"
           src="/static/${clip.arquivo}?t=${Date.now()}"></video>`
      : `<div class="clip-no-video">Vídeo do trecho indisponível</div>`;

    div.innerHTML = `
      ${videoHtml}
      <div class="clip-info">
        <div class="clip-num">Aula ${String(i + 1).padStart(2, '0')}</div>
        <div class="clip-title">${escapeHtml(clip.titulo)}</div>
        <div class="clip-duration">${escapeHtml(clip.duracao)}</div>
        <p class="clip-summary">${escapeHtml(clip.resumo)}</p>
      </div>`;

    view.appendChild(div);
  });
}

/* ── Util ─────────────────────────────────────────────────── */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str ?? '';
  return div.innerHTML;
}

/* ── Salvar curso no catálogo ─────────────────────────────── */
const saveCourseBtn = document.getElementById('saveCourseBtn');
const saveCourseDialog = document.getElementById('saveCourseDialog');
const saveCourseConfirm = document.getElementById('saveCourseConfirm');
const saveCourseTitleInput = document.getElementById('saveCourseTitleInput');
const saveCourseAuthorInput = document.getElementById('saveCourseAuthorInput');
const saveCourseImageInput = document.getElementById('saveCourseImageInput');
const saveCourseImageFile = document.getElementById('saveCourseImageFile');
const saveCourseImage = document.getElementById('saveCourseImage');
const saveCourseFeedback = document.getElementById('saveCourseFeedback');

function youtubeThumb(meta) {
  if (meta?.thumbnail) return meta.thumbnail;
  const raw = meta?.video_id || (meta?.url || '').match(/[?&]v=([^&]+)/)?.[1] || '';
  return raw ? `https://i.ytimg.com/vi/${raw}/hqdefault.jpg` : '';
}

function syncSaveCoursePreview() {
  if (!saveCourseImage) return;
  const url = (saveCourseImageInput?.value || '').trim();
  if (url) {
    saveCourseImage.src = url;
    saveCourseImage.hidden = false;
  } else {
    saveCourseImage.removeAttribute('src');
    saveCourseImage.hidden = true;
  }
}

if (saveCourseBtn && saveCourseDialog) {
  saveCourseBtn.addEventListener('click', () => {
    if (!currentCoursePayload) return;
    const title = currentCoursePayload.quiz?.tema || currentCoursePayload.topic || currentVideoMeta?.titulo || 'Meu curso';
    const image = youtubeThumb(currentVideoMeta);
    saveCourseTitleInput.value = title;
    saveCourseAuthorInput.value = currentVideoMeta?.canal || 'StudyFlow';
    saveCourseImageInput.value = image;
    saveCourseFeedback.textContent = '';
    syncSaveCoursePreview();
    saveCourseDialog.showModal();
  });
  saveCourseImageInput?.addEventListener('input', syncSaveCoursePreview);
  saveCourseImageFile?.addEventListener('change', () => {
    const f = saveCourseImageFile.files?.[0];
    if (!f) return syncSaveCoursePreview();
    saveCourseImage.src = URL.createObjectURL(f);
    saveCourseImage.hidden = false;
  });
}

if (saveCourseConfirm) {
  saveCourseConfirm.addEventListener('click', async () => {
    if (!currentCoursePayload) return;
    const titulo = saveCourseTitleInput.value.trim();
    if (!titulo) { saveCourseTitleInput.focus(); return; }

    saveCourseConfirm.disabled = true;
    saveCourseConfirm.textContent = 'Salvando...';
    saveCourseFeedback.textContent = 'Copiando vídeos para sua biblioteca...';
    try {
      let imagem = saveCourseImageInput.value.trim();
      const coverFile = saveCourseImageFile?.files?.[0];
      if (coverFile) {
        const fd = new FormData(); fd.append('file', coverFile);
        const up = await fetch('/api/course-cover-upload', { method: 'POST', body: fd });
        const ud = await up.json();
        if (!up.ok) throw new Error(ud.error || 'Não foi possível enviar a capa.');
        imagem = ud.url || imagem;
      }
      const res = await fetch('/api/cursos-salvos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          titulo,
          autor: saveCourseAuthorInput.value.trim(),
          imagem,
          descricao: currentVideoMeta?.descricao || `Curso sobre ${titulo}`,
          source_url: currentVideoMeta?.url || '',
          duracao_minutos: currentVideoMeta?.duracao_minutos || 0,
          video_file: currentCoursePayload.video_file || '',
          clips: currentCoursePayload.clips || [],
          quiz: currentCoursePayload.quiz || {},
          roadmap: currentCoursePayload.roadmap || {}
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Não foi possível salvar o curso.');
      saveCourseFeedback.textContent = '✓ Curso salvo no Catálogo.';
      saveCourseBtn.textContent = '✓ Salvo no catálogo';
      saveCourseBtn.disabled = true;
      setTimeout(() => { window.location.href = `/curso-salvo/${data.curso.id}`; }, 600);
    } catch (err) {
      saveCourseFeedback.textContent = `⚠ ${err.message}`;
    } finally {
      saveCourseConfirm.disabled = false;
      saveCourseConfirm.textContent = 'Salvar no catálogo';
    }
  });
}

/* ── Material de apoio (PDF/PPTX/DOCX -> RAG do Curso) ───────
   Guardado com checagem de elemento porque este app.js também é usado
   em index.html, que não tem essa seção. */
const cxMaterialInput = document.getElementById('cxMaterialInput');
const cxMaterialLabel = document.getElementById('cxMaterialLabel');
const cxMaterialList  = document.getElementById('cxMaterialList');
const cxMaterialError = document.getElementById('cxMaterialError');

if (cxMaterialInput) {
  cxMaterialInput.addEventListener('change', async () => {
    const file = cxMaterialInput.files?.[0];
    if (!file) return;

    if (cxMaterialError) cxMaterialError.hidden = true;
    const originalLabel = cxMaterialLabel.textContent;
    cxMaterialLabel.textContent = `Adicionando ${file.name}...`;

    const formData = new FormData();
    formData.append('arquivo', file);

    try {
      const res = await fetch('/api/curso/material', { method: 'POST', body: formData });
      const body = await res.json();
      if (!res.ok || body.error) throw new Error(body.error || 'Não foi possível adicionar este material. Tente novamente.');

      const item = document.createElement('div');
      item.className = 'cx-material-item';
      item.innerHTML = `
        <span class="cx-material-item-name">📄 ${escapeHtml(body.arquivo)}</span>
        <span class="cx-material-item-meta">${body.chunks_indexados} trecho(s) pronto(s) para consulta</span>
      `;
      cxMaterialList.appendChild(item);
    } catch (err) {
      if (cxMaterialError) {
        cxMaterialError.textContent = err.message;
        cxMaterialError.hidden = false;
      }
    } finally {
      cxMaterialLabel.textContent = originalLabel;
      cxMaterialInput.value = '';
    }
  });
}

const cxMaterialUrl = document.getElementById('cxMaterialUrl');
const cxMaterialUrlBtn = document.getElementById('cxMaterialUrlBtn');

if (cxMaterialUrlBtn) {
  cxMaterialUrlBtn.addEventListener('click', async () => {
    const url = (cxMaterialUrl?.value || '').trim();
    if (!url) return;
    if (cxMaterialError) cxMaterialError.hidden = true;

    const originalBtnText = cxMaterialUrlBtn.textContent;
    cxMaterialUrlBtn.disabled = true;
    cxMaterialUrlBtn.textContent = 'Varrendo página...';

    try {
      const res = await fetch('/api/curso/material_url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const body = await res.json();
      if (!res.ok || body.error) throw new Error(body.error || 'Não foi possível adicionar este link. Tente novamente.');

      const item = document.createElement('div');
      item.className = 'cx-material-item';
      item.innerHTML = `
        <span class="cx-material-item-name">🔗 ${escapeHtml(body.url)}</span>
        <span class="cx-material-item-meta">${body.chunks_indexados} trecho(s) pronto(s) para consulta</span>
      `;
      cxMaterialList.appendChild(item);
      cxMaterialUrl.value = '';
    } catch (err) {
      if (cxMaterialError) {
        cxMaterialError.textContent = err.message;
        cxMaterialError.hidden = false;
      }
    } finally {
      cxMaterialUrlBtn.disabled = false;
      cxMaterialUrlBtn.textContent = originalBtnText;
    }
  });
}

topicEl.focus();

// Pré-preenche o tema se vier da URL (?tema=...) — é assim que o card
// "Estudar" do Planejamento abre o Curso já com o assunto certo.
(function prefillFromPlanejamento() {
  const params = new URLSearchParams(window.location.search);
  const tema = params.get('tema');
  if (tema && topicEl) {
    topicEl.value = tema;
    topicEl.style.height = 'auto';
    topicEl.style.height = topicEl.scrollHeight + 'px';
  }
})();
