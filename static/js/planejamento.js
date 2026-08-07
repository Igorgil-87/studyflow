// planejamento.js — Módulo Planejamento (board + calendário sobre o mesmo dado)

const STATUSES = ["ideia", "roteiro", "gravacao", "edicao", "publicado"];
const STATUS_LABELS = {
  ideia: "Ideia", roteiro: "Roteiro", gravacao: "Gravação",
  edicao: "Edição", publicado: "Publicado",
};
const TIPO_ICONS = { video: "🎬", carrossel: "🖼️", post: "📝", outro: "📌" };

// ─────────────────────────── Módulos (Sprint 2) ───────────────────────
const MODULO_ICONS = { estudo: "📚", criador: "🎬", youtuber: "📹", geral: "📌" };
const MODULO_LABELS = { estudo: "Estudo", criador: "Criador", youtuber: "Youtuber", geral: "Geral" };
// cada módulo sabe montar sua própria URL de deep-link, a partir do
// campos_extra da atividade — é isso que faz o botão de ação abrir o
// módulo certo já com o contexto preenchido.
const MODULO_ACTION = {
  estudo: {
    label: "Estudar",
    url: (extra) => `/curso?tema=${encodeURIComponent(extra.materia || "")}`,
    disabled: (extra) => !extra.materia,
  },
  criador: {
    label: "Continuar produção",
    url: (extra) => `/estudio?tema=${encodeURIComponent(extra.pilar_conteudo || "")}`,
    disabled: (extra) => !extra.pilar_conteudo,
  },
  youtuber: {
    label: "Ver cortes",
    url: (extra) => `/youtuber?url=${encodeURIComponent(extra.url_video || "")}`,
    disabled: (extra) => !extra.url_video,
  },
  geral: null, // sem ação — card genérico, igual sempre foi
};

let atividades = [];
let currentAtividadeId = null; // null = criando nova
let calMonthCursor = new Date(); // mês exibido no calendário
let checklistState = []; // [{texto, feito}] do modal aberto

const boardEl = document.getElementById("planBoardView");
const agendaEl = document.getElementById("planAgendaView");
const calEl = document.getElementById("planCalendarView");
const calGrid = document.getElementById("planCalGrid");
const calTitle = document.getElementById("planCalTitle");
const errorBox = document.getElementById("planErrorBox");

function showError(msg) {
  if (!errorBox) return;
  errorBox.textContent = msg;
  errorBox.hidden = false;
  setTimeout(() => { errorBox.hidden = true; }, 5000);
}

// ─────────────────────────── API ───────────────────────────
async function fetchAtividades() {
  const res = await fetch("/api/planejamento/atividades");
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "Falha ao carregar atividades");
  atividades = body.atividades || [];
}

async function saveAtividade(payload) {
  const isEdit = !!currentAtividadeId;
  const url = isEdit
    ? `/api/planejamento/atividades/${currentAtividadeId}`
    : "/api/planejamento/atividades";
  const res = await fetch(url, {
    method: isEdit ? "PATCH" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "Falha ao salvar");
  return body.atividade;
}

async function deleteAtividadeApi(id) {
  const res = await fetch(`/api/planejamento/atividades/${id}`, { method: "DELETE" });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "Falha ao excluir");
}

async function patchStatus(id, status, posicao) {
  const res = await fetch(`/api/planejamento/atividades/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, posicao }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || "Falha ao mover");
  return body.atividade;
}

// ─────────────────────────── BOARD ───────────────────────────
function renderBoard() {
  boardEl.innerHTML = "";
  STATUSES.forEach((status) => {
    const col = document.createElement("div");
    col.className = "plan-col";
    col.dataset.status = status;

    const itens = atividades.filter((a) => a.status === status);
    col.innerHTML = `
      <div class="plan-col-head">
        <span>${STATUS_LABELS[status]}</span>
        <span class="plan-col-count">${itens.length}</span>
      </div>
      <div class="plan-col-body" data-status="${status}"></div>
    `;
    const body = col.querySelector(".plan-col-body");

    itens.forEach((a) => {
      const card = document.createElement("div");
      const modulo = a.modulo || "geral";
      card.className = `plan-card plan-card-${modulo}`;
      card.draggable = true;
      card.dataset.id = a.id;

      const checklist = a.checklist || [];
      const feitos = checklist.filter((c) => c.feito).length;
      const checklistBadge = checklist.length
        ? `<span class="plan-card-checklist">✓ ${feitos}/${checklist.length}</span>` : "";
      const dataBadge = a.data_pub
        ? `<span class="plan-card-date">${formatDateShort(a.data_pub)}${a.hora_inicio ? " · " + a.hora_inicio : ""}</span>` : "";

      // linha de info específica do módulo (matéria, pilar do conteúdo, ou plataforma)
      const extra = a.campos_extra || {};
      let moduloInfo = "";
      if (modulo === "estudo" && extra.materia) {
        moduloInfo = `<div class="plan-card-modulo-info">${escapeHtml(extra.materia)}${extra.tecnica ? " · " + escapeHtml(extra.tecnica) : ""}</div>`;
      } else if (modulo === "criador" && extra.pilar_conteudo) {
        moduloInfo = `<div class="plan-card-modulo-info">${escapeHtml(extra.pilar_conteudo)}</div>`;
      } else if (modulo === "youtuber" && extra.url_video) {
        moduloInfo = `<div class="plan-card-modulo-info">${escapeHtml(extra.plataforma || "youtube")}</div>`;
      }

      // botão de ação — só aparece se o módulo tiver ação E o campo necessário estiver preenchido
      const action = MODULO_ACTION[modulo];
      const actionBtn = (action && !action.disabled(extra))
        ? `<a href="${action.url(extra)}" class="plan-card-action" onclick="event.stopPropagation()">${action.label} →</a>`
        : "";

      card.innerHTML = `
        <div class="plan-card-top">
          <span class="plan-card-modulo-badge">${MODULO_ICONS[modulo]} ${MODULO_LABELS[modulo]}</span>
          ${a.pilar ? `<span class="plan-card-pilar">${escapeHtml(a.pilar)}</span>` : ""}
        </div>
        <div class="plan-card-titulo">${escapeHtml(a.titulo)}</div>
        ${moduloInfo}
        <div class="plan-card-bottom">${dataBadge}${checklistBadge}</div>
        ${actionBtn}
      `;
      card.addEventListener("click", () => openModal(a));
      card.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/plain", a.id);
        card.classList.add("dragging");
      });
      card.addEventListener("dragend", () => card.classList.remove("dragging"));
      body.appendChild(card);
    });

    body.addEventListener("dragover", (e) => {
      e.preventDefault();
      body.classList.add("plan-col-body-over");
    });
    body.addEventListener("dragleave", () => body.classList.remove("plan-col-body-over"));
    body.addEventListener("drop", async (e) => {
      e.preventDefault();
      body.classList.remove("plan-col-body-over");
      const id = e.dataTransfer.getData("text/plain");
      const atividade = atividades.find((x) => x.id === id);
      if (!atividade || atividade.status === status) return;
      try {
        const novaPos = atividades.filter((x) => x.status === status).length;
        await patchStatus(id, status, novaPos);
        await fetchAtividades();
        renderBoard();
        renderAlerts();
      } catch (err) {
        showError(err.message);
      }
    });

    boardEl.appendChild(col);
  });
}

// ─────────────────────────── CALENDÁRIO ───────────────────────────
function renderCalendar() {
  const year = calMonthCursor.getFullYear();
  const month = calMonthCursor.getMonth();
  const monthNames = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"];
  calTitle.textContent = `${monthNames[month]} ${year}`;

  const firstDay = new Date(year, month, 1);
  const startWeekday = firstDay.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const porDia = {};
  atividades.forEach((a) => {
    if (!a.data_pub) return;
    porDia[a.data_pub] = porDia[a.data_pub] || [];
    porDia[a.data_pub].push(a);
  });

  calGrid.innerHTML = "";
  ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"].forEach((d) => {
    const h = document.createElement("div");
    h.className = "plan-cal-dow";
    h.textContent = d;
    calGrid.appendChild(h);
  });

  for (let i = 0; i < startWeekday; i++) {
    calGrid.appendChild(Object.assign(document.createElement("div"), { className: "plan-cal-cell plan-cal-cell-empty" }));
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const cell = document.createElement("div");
    cell.className = "plan-cal-cell";
    const itens = porDia[dateStr] || [];
    cell.innerHTML = `<div class="plan-cal-daynum">${day}</div>`;
    itens.forEach((a) => {
      const chip = document.createElement("div");
      chip.className = "plan-cal-chip";
      chip.textContent = `${TIPO_ICONS[a.tipo] || "📌"} ${a.titulo}`;
      chip.addEventListener("click", () => openModal(a));
      cell.appendChild(chip);
    });
    calGrid.appendChild(cell);
  }
}

document.getElementById("planCalPrev").addEventListener("click", () => {
  calMonthCursor.setMonth(calMonthCursor.getMonth() - 1);
  renderCalendar();
});
document.getElementById("planCalNext").addEventListener("click", () => {
  calMonthCursor.setMonth(calMonthCursor.getMonth() + 1);
  renderCalendar();
});

// ─────────────────────────── AGENDA (por horário do dia) ──────────────
let agendaDayCursor = new Date(); // dia exibido na agenda

function toIsoDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function minutesToHhMm(totalMin) {
  const h = Math.floor(totalMin / 60) % 24;
  const m = totalMin % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function renderAgenda() {
  const dayNames = ["Domingo","Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira","Sexta-feira","Sábado"];
  const monthNames = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
    "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"];
  const isoHoje = toIsoDate(agendaDayCursor);
  const isToday = isoHoje === todayIso();

  document.getElementById("planAgendaTitle").textContent =
    `${dayNames[agendaDayCursor.getDay()]}, ${agendaDayCursor.getDate()} de ${monthNames[agendaDayCursor.getMonth()]}`
    + (isToday ? " · hoje" : "");

  const doDia = atividades.filter((a) => a.data_pub === isoHoje);
  const comHorario = doDia.filter((a) => a.hora_inicio).sort((a, b) => a.hora_inicio.localeCompare(b.hora_inicio));
  const semHorario = doDia.filter((a) => !a.hora_inicio);

  const list = document.getElementById("planAgendaList");
  list.innerHTML = "";

  if (doDia.length === 0) {
    list.innerHTML = '<div class="plan-agenda-empty">Nada planejado pra esse dia.</div>';
    return;
  }

  comHorario.forEach((a) => list.appendChild(buildAgendaItem(a)));

  if (semHorario.length) {
    const header = document.createElement("div");
    header.className = "plan-agenda-sem-horario-label";
    header.textContent = "Sem horário definido";
    list.appendChild(header);
    semHorario.forEach((a) => list.appendChild(buildAgendaItem(a)));
  }
}

function buildAgendaItem(a) {
  const modulo = a.modulo || "geral";
  const extra = a.campos_extra || {};
  const item = document.createElement("div");
  item.className = `plan-agenda-item plan-card-${modulo}`;

  let horarioLabel = "—";
  if (a.hora_inicio) {
    const [hh, mm] = a.hora_inicio.split(":").map(Number);
    const inicioMin = hh * 60 + mm;
    horarioLabel = a.duracao_min
      ? `${a.hora_inicio} – ${minutesToHhMm(inicioMin + a.duracao_min)}`
      : a.hora_inicio;
  }

  let moduloInfo = "";
  if (modulo === "estudo" && extra.materia) moduloInfo = escapeHtml(extra.materia) + (extra.tecnica ? " · " + escapeHtml(extra.tecnica) : "");
  else if (modulo === "criador" && extra.pilar_conteudo) moduloInfo = escapeHtml(extra.pilar_conteudo);
  else if (modulo === "youtuber" && extra.url_video) moduloInfo = escapeHtml(extra.plataforma || "youtube");

  const action = MODULO_ACTION[modulo];
  const actionBtn = (action && !action.disabled(extra))
    ? `<a href="${action.url(extra)}" class="plan-card-action" onclick="event.stopPropagation()">${action.label} →</a>`
    : "";

  item.innerHTML = `
    <div class="plan-agenda-time">${horarioLabel}${a.duracao_min ? `<span class="plan-agenda-dur">${a.duracao_min}min</span>` : ""}</div>
    <div class="plan-agenda-body">
      <div class="plan-card-top">
        <span class="plan-card-modulo-badge">${MODULO_ICONS[modulo]} ${MODULO_LABELS[modulo]}</span>
        ${a.status !== "publicado" ? `<span class="plan-agenda-status">${STATUS_LABELS[a.status]}</span>` : ""}
      </div>
      <div class="plan-card-titulo">${escapeHtml(a.titulo)}</div>
      ${moduloInfo ? `<div class="plan-card-modulo-info">${moduloInfo}</div>` : ""}
      ${actionBtn}
    </div>
  `;
  item.querySelector(".plan-agenda-body").addEventListener("click", (e) => {
    if (e.target.closest(".plan-card-action")) return;
    openModal(a);
  });
  return item;
}

document.getElementById("planAgendaPrev").addEventListener("click", () => {
  agendaDayCursor.setDate(agendaDayCursor.getDate() - 1);
  renderAgenda();
});
document.getElementById("planAgendaNext").addEventListener("click", () => {
  agendaDayCursor.setDate(agendaDayCursor.getDate() + 1);
  renderAgenda();
});
document.getElementById("planAgendaToday").addEventListener("click", () => {
  agendaDayCursor = new Date();
  renderAgenda();
});

// ─────────────────────────── RECOMENDADOR (Sprint 4) ───────────────────
// "O que eu faço agora?" — dado quanto tempo livre a pessoa tem, sugere a
// próxima atividade mais urgente que CABE nesse tempo. Prioridade: mais
// atrasada primeiro > vence hoje > vence em breve > sem data. Empate na
// urgência de data desempata pela mais curta (cabe melhor, "quick win").
// Atividade já publicada nunca é sugerida.
function scoreDias(a, hoje) {
  if (!a.data_pub) return 9999; // sem data = menos urgente, vai pro fim
  const diff = (new Date(a.data_pub) - new Date(hoje)) / 86400000;
  return diff; // negativo = atrasada (quanto mais negativo, mais atrasada)
}

function recommendNext(lista, availableMin) {
  const hoje = todayIso();
  const candidatos = lista.filter((a) =>
    a.status !== "publicado" &&
    (a.duracao_min == null || a.duracao_min <= availableMin)
  );
  if (!candidatos.length) return null;

  candidatos.sort((a, b) => {
    const da = scoreDias(a, hoje), db = scoreDias(b, hoje);
    if (da !== db) return da - db;
    const durA = a.duracao_min ?? 999;
    const durB = b.duracao_min ?? 999;
    return durA - durB;
  });
  return candidatos[0];
}

function describeUrgencia(a) {
  if (!a.data_pub) return "sem data definida";
  const hoje = todayIso();
  const dias = Math.round(scoreDias(a, hoje));
  if (dias < 0) return `atrasada há ${Math.abs(dias)} dia(s)`;
  if (dias === 0) return "vence hoje";
  if (dias === 1) return "vence amanhã";
  return `vence em ${dias} dias`;
}

document.getElementById("planRecommendBtn").addEventListener("click", () => {
  const min = Number(document.getElementById("planRecommendMin").value) || 0;
  const resultEl = document.getElementById("planRecommendResult");
  const sugestao = recommendNext(atividades, min);

  if (!sugestao) {
    resultEl.innerHTML = `<div class="plan-recommend-empty">Nada pendente cabe em ${min} min — ou já está tudo publicado, ou as próximas atividades são mais longas que isso.</div>`;
    resultEl.hidden = false;
    return;
  }

  const modulo = sugestao.modulo || "geral";
  const action = MODULO_ACTION[modulo];
  const extra = sugestao.campos_extra || {};
  const actionBtn = (action && !action.disabled(extra))
    ? `<a href="${action.url(extra)}" class="plan-card-action" onclick="event.stopPropagation()">${action.label} →</a>`
    : "";

  resultEl.innerHTML = `
    <div class="plan-recommend-card plan-card-${modulo}">
      <div class="plan-card-top">
        <span class="plan-card-modulo-badge">${MODULO_ICONS[modulo]} ${MODULO_LABELS[modulo]}</span>
        <span class="plan-agenda-status">${describeUrgencia(sugestao)}</span>
      </div>
      <div class="plan-card-titulo">${escapeHtml(sugestao.titulo)}</div>
      <div class="plan-card-modulo-info">${sugestao.duracao_min ? `~${sugestao.duracao_min} min` : "duração não estimada"}</div>
      ${actionBtn}
    </div>
  `;
  resultEl.querySelector(".plan-recommend-card").addEventListener("click", (e) => {
    if (e.target.closest(".plan-card-action")) return;
    openModal(sugestao);
  });
  resultEl.hidden = false;
});

// ─────────────────────────── VIEW SWITCH ───────────────────────────
document.querySelectorAll(".plan-view-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".plan-view-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const view = btn.dataset.view;
    boardEl.hidden = view !== "board";
    agendaEl.hidden = view !== "agenda";
    calEl.hidden = view !== "calendario";
    if (view === "calendario") renderCalendar();
    if (view === "agenda") renderAgenda();
  });
});

// ─────────────────────────── MODAL ───────────────────────────
const modal = document.getElementById("planModal");
const modalTitle = document.getElementById("planModalTitle");
const checklistWrap = document.getElementById("planChecklist");

let currentModulo = "geral";

function setModulo(modulo) {
  currentModulo = modulo;
  document.querySelectorAll(".plan-modulo-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.modulo === modulo);
  });
  document.getElementById("planFieldsEstudo").hidden = modulo !== "estudo";
  document.getElementById("planFieldsCriador").hidden = modulo !== "criador";
  document.getElementById("planFieldsYoutuber").hidden = modulo !== "youtuber";
}

document.querySelectorAll(".plan-modulo-btn").forEach((btn) => {
  btn.addEventListener("click", () => setModulo(btn.dataset.modulo));
});

function openModal(atividade) {
  currentAtividadeId = atividade ? atividade.id : null;
  modalTitle.textContent = atividade ? "Editar atividade" : "Nova atividade";
  document.getElementById("planTitulo").value = atividade?.titulo || "";
  document.getElementById("planDescricao").value = atividade?.descricao || "";
  document.getElementById("planTipo").value = atividade?.tipo || "video";
  document.getElementById("planStatus").value = atividade?.status || "ideia";
  document.getElementById("planPilar").value = atividade?.pilar || "";
  document.getElementById("planDataPub").value = atividade?.data_pub || "";
  document.getElementById("planHoraInicio").value = atividade?.hora_inicio || "";
  document.getElementById("planDuracaoMin").value = atividade?.duracao_min || "";
  document.getElementById("planDeleteBtn").hidden = !atividade;

  const extra = atividade?.campos_extra || {};
  document.getElementById("planEstudoMateria").value = extra.materia || "";
  document.getElementById("planEstudoTecnica").value = extra.tecnica || "Estudar teoria";
  document.getElementById("planCriadorTipo").value = extra.tipo_conteudo || "carrossel";
  document.getElementById("planCriadorPilar").value = extra.pilar_conteudo || "";
  document.getElementById("planYoutuberUrl").value = extra.url_video || "";
  document.getElementById("planYoutuberPlataforma").value = extra.plataforma || "youtube";
  setModulo(atividade?.modulo || "geral");

  checklistState = atividade?.checklist ? JSON.parse(JSON.stringify(atividade.checklist)) : [];
  renderChecklist();
  modal.hidden = false;
}

function closeModal() {
  modal.hidden = true;
  currentAtividadeId = null;
}

document.getElementById("planNovaBtn").addEventListener("click", () => openModal(null));
document.getElementById("planModalClose").addEventListener("click", closeModal);
modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

function renderChecklist() {
  checklistWrap.innerHTML = "";
  checklistState.forEach((item, i) => {
    const row = document.createElement("div");
    row.className = "plan-checklist-item";
    row.innerHTML = `
      <input type="checkbox" ${item.feito ? "checked" : ""} data-idx="${i}" class="plan-checklist-check">
      <input type="text" value="${escapeHtml(item.texto)}" data-idx="${i}" class="plan-checklist-text" placeholder="item da checklist">
      <button type="button" data-idx="${i}" class="plan-checklist-remove" title="Remover" aria-label="Remover item da checklist">×</button>
    `;
    checklistWrap.appendChild(row);
  });

  checklistWrap.querySelectorAll(".plan-checklist-check").forEach((el) => {
    el.addEventListener("change", () => { checklistState[el.dataset.idx].feito = el.checked; });
  });
  checklistWrap.querySelectorAll(".plan-checklist-text").forEach((el) => {
    el.addEventListener("input", () => { checklistState[el.dataset.idx].texto = el.value; });
  });
  checklistWrap.querySelectorAll(".plan-checklist-remove").forEach((el) => {
    el.addEventListener("click", () => {
      checklistState.splice(Number(el.dataset.idx), 1);
      renderChecklist();
    });
  });
}

document.getElementById("planChecklistAdd").addEventListener("click", () => {
  checklistState.push({ texto: "", feito: false });
  renderChecklist();
});

document.getElementById("planSaveBtn").addEventListener("click", async () => {
  const titulo = document.getElementById("planTitulo").value.trim();
  if (!titulo) { showError("Título é obrigatório."); return; }

  let campos_extra = {};
  if (currentModulo === "estudo") {
    campos_extra = {
      materia: document.getElementById("planEstudoMateria").value.trim(),
      tecnica: document.getElementById("planEstudoTecnica").value,
    };
  } else if (currentModulo === "criador") {
    campos_extra = {
      tipo_conteudo: document.getElementById("planCriadorTipo").value,
      pilar_conteudo: document.getElementById("planCriadorPilar").value.trim(),
    };
  } else if (currentModulo === "youtuber") {
    campos_extra = {
      url_video: document.getElementById("planYoutuberUrl").value.trim(),
      plataforma: document.getElementById("planYoutuberPlataforma").value,
    };
  }

  const payload = {
    titulo,
    descricao: document.getElementById("planDescricao").value.trim(),
    tipo: document.getElementById("planTipo").value,
    status: document.getElementById("planStatus").value,
    pilar: document.getElementById("planPilar").value.trim(),
    data_pub: document.getElementById("planDataPub").value || null,
    hora_inicio: document.getElementById("planHoraInicio").value || null,
    duracao_min: document.getElementById("planDuracaoMin").value
      ? Number(document.getElementById("planDuracaoMin").value) : null,
    modulo: currentModulo,
    campos_extra,
    checklist: checklistState.filter((c) => c.texto.trim()),
  };

  try {
    await saveAtividade(payload);
    closeModal();
    await fetchAtividades();
    renderBoard();
    renderAlerts();
    if (!calEl.hidden) renderCalendar();
  } catch (err) {
    showError(err.message);
  }
});

document.getElementById("planDeleteBtn").addEventListener("click", async () => {
  if (!currentAtividadeId) return;
  if (!confirm("Excluir essa atividade?")) return;
  try {
    await deleteAtividadeApi(currentAtividadeId);
    closeModal();
    await fetchAtividades();
    renderBoard();
    renderAlerts();
    if (!calEl.hidden) renderCalendar();
  } catch (err) {
    showError(err.message);
  }
});

// ─────────────────────────── HELPERS ───────────────────────────
function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s || "";
  return div.innerHTML;
}

function formatDateShort(isoDate) {
  const [y, m, d] = isoDate.split("-");
  return `${d}/${m}`;
}

// ─────────────────────────── ALERTAS ───────────────────────────
const alertsBtn = document.getElementById("planAlertsBtn");
const alertsPanel = document.getElementById("planAlertsPanel");
const alertsBadge = document.getElementById("planAlertsBadge");
const alertsList = document.getElementById("planAlertsList");

function todayIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function computeAlerts() {
  const hoje = todayIso();
  const em3dias = new Date();
  em3dias.setDate(em3dias.getDate() + 3);
  const limite = `${em3dias.getFullYear()}-${String(em3dias.getMonth() + 1).padStart(2, "0")}-${String(em3dias.getDate()).padStart(2, "0")}`;

  const pendentes = atividades.filter((a) => a.data_pub && a.status !== "publicado");
  const atrasadas = pendentes.filter((a) => a.data_pub < hoje);
  const vencendo = pendentes.filter((a) => a.data_pub >= hoje && a.data_pub <= limite);

  // atrasadas primeiro (mais urgente), depois as que vencem em breve — cada lista já ordenada por data
  atrasadas.sort((a, b) => a.data_pub.localeCompare(b.data_pub));
  vencendo.sort((a, b) => a.data_pub.localeCompare(b.data_pub));
  return { atrasadas, vencendo };
}

function renderAlerts() {
  const { atrasadas, vencendo } = computeAlerts();
  const total = atrasadas.length + vencendo.length;

  if (total === 0) {
    alertsBadge.hidden = true;
    alertsList.innerHTML = '<div class="plan-alerts-empty">Nenhum alerta — tudo em dia.</div>';
    return;
  }
  alertsBadge.hidden = false;
  alertsBadge.textContent = total > 9 ? "9+" : String(total);

  alertsList.innerHTML = "";
  atrasadas.forEach((a) => alertsList.appendChild(buildAlertItem(a, "overdue",
    `Atrasada desde ${formatDateShort(a.data_pub)}`)));
  vencendo.forEach((a) => alertsList.appendChild(buildAlertItem(a, "soon",
    a.data_pub === todayIso() ? "Publica hoje" : `Publica em ${formatDateShort(a.data_pub)}`)));
}

function buildAlertItem(atividade, kind, metaText) {
  const item = document.createElement("div");
  item.className = "plan-alerts-item";
  item.innerHTML = `
    <div class="plan-alerts-item-title">${TIPO_ICONS[atividade.tipo] || "📌"} ${escapeHtml(atividade.titulo)}</div>
    <div class="plan-alerts-item-meta ${kind}">${metaText} · ${STATUS_LABELS[atividade.status]}</div>
  `;
  item.addEventListener("click", () => {
    alertsPanel.hidden = true;
    openModal(atividade);
  });
  return item;
}

alertsBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  alertsPanel.hidden = !alertsPanel.hidden;
});
document.addEventListener("click", (e) => {
  if (!alertsPanel.hidden && !alertsPanel.contains(e.target) && e.target !== alertsBtn) {
    alertsPanel.hidden = true;
  }
});

// ─────────────────────────── INIT ───────────────────────────
(async function init() {
  try {
    await fetchAtividades();
    renderBoard();
    renderAlerts();
  } catch (err) {
    showError(err.message);
  }
})();
