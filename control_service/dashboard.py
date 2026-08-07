DASHBOARD_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Telemost Control Service</title>
  <style>
    :root { font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif; color: #20242d; background: #f4f6f8; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    body { min-height: 100vh; }
    .layout { display: grid; grid-template-columns: 250px 1fr; min-height: 100vh; }
    .sidebar { background: #111827; color: #f8fafc; padding: 24px 16px; }
    .brand { margin-bottom: 24px; }
    .brand strong { display: block; font-size: 18px; }
    .brand span { color: #aeb8c8; font-size: 13px; }
    .nav { display: grid; gap: 8px; }
    .nav button { width: 100%; text-align: left; background: transparent; color: #dbe4f0; border: 1px solid transparent; }
    .nav button.active { background: #243044; color: #fff; border-color: #3a4b68; }
    main { max-width: 1180px; width: 100%; margin: 0 auto; padding: 28px 18px 48px; }
    .page { display: none; }
    .page.active { display: block; }
    header { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 18px; }
    h1 { margin: 0; font-size: 30px; }
    h2 { margin: 0 0 12px; font-size: 20px; }
    .muted { color: #687080; font-size: 14px; }
    .panel, .metric, .node, .bot { background: #fff; border: 1px solid #dfe4ea; border-radius: 8px; box-shadow: 0 1px 2px rgba(20,31,45,.04); }
    .panel { padding: 16px; margin-bottom: 16px; }
    .quick-grid { display: grid; grid-template-columns: minmax(260px, 1.4fr) minmax(180px, .8fr) auto; gap: 10px; }
    .calendar-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
    .calendar-actions { display: flex; align-items: center; gap: 8px; }
    .calendar-actions input { width: 82px; }
    input, select, button { min-height: 38px; border-radius: 8px; font: inherit; }
    input, select, textarea { width: 100%; border: 1px solid #cbd3dc; padding: 8px 10px; background: white; }
    textarea { min-height: 74px; border-radius: 8px; font: inherit; resize: vertical; }
    button { border: 0; padding: 8px 13px; font-weight: 700; background: #1c71d8; color: white; cursor: pointer; }
    button:disabled { background: #aab4c0; cursor: not-allowed; }
    .summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
    .quick-extra-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }
    .calendar-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
    .metric { padding: 14px; }
    .metric strong { display: block; font-size: 28px; margin-top: 4px; }
    .nodes { display: grid; gap: 14px; }
    .node { padding: 16px; border-left: 7px solid #8b949e; }
    .node.online { border-left-color: #26a269; }
    .node.unavailable { border-left-color: #c01c28; }
    .node-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
    .node-title { font-weight: 760; font-size: 18px; }
    .bots { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }
    .bot { padding: 12px; border-left: 6px solid #26a269; }
    .bot.busy { border-left-color: #1c71d8; }
    .badge { display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; background: #dff5ea; color: #137144; }
    .badge.busy { background: #e1efff; color: #0b5cad; }
    .row { display: grid; grid-template-columns: 86px 1fr; gap: 6px 10px; font-size: 14px; margin-top: 8px; overflow-wrap: anywhere; }
    .calendar-table { width: 100%; border-collapse: collapse; font-size: 14px; }
    .calendar-table th, .calendar-table td { border-bottom: 1px solid #e4e8ee; padding: 9px 6px; text-align: left; vertical-align: top; }
    .calendar-table th { color: #687080; font-size: 12px; text-transform: uppercase; }
    .calendar-table td { overflow-wrap: anywhere; }
    .participants-cell { min-width: 220px; max-width: 340px; }
    .participants-cell details { max-width: 340px; }
    .participants-cell summary { cursor: pointer; font-weight: 700; }
    .participants-list { margin: 6px 0 0; padding-left: 16px; color: #3f4754; }
    .ok { color: #137144; font-weight: 760; }
    .warn { color: #9a6700; font-weight: 760; }
    .bad { color: #b42318; font-weight: 760; }
    .calendar-control-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
    .message { min-height: 20px; margin-top: 8px; font-size: 14px; }
    .error { color: #b42318; }
    @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } .sidebar { position: static; } .nav { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 760px) { header { display: block; } .summary, .quick-grid, .quick-extra-grid, .calendar-summary, .calendar-control-grid { grid-template-columns: 1fr; } .calendar-head, .calendar-actions { display: block; } .calendar-actions input, .calendar-actions button { margin-top: 8px; width: 100%; } .nav { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <div class="brand">
      <strong>Telemost Control</strong>
      <span>Единая панель управления</span>
    </div>
    <nav class="nav">
      <button type="button" class="active" data-page-target="bots-page">Пул ботов</button>
      <button type="button" data-page-target="calendar-page">Корпоративный календарь</button>
    </nav>
  </aside>

  <main>
    <section class="page active" id="bots-page">
      <header>
        <div>
          <h1>Пул ботов</h1>
          <div class="muted">Состояние всех bot-node и ручной запуск встреч</div>
        </div>
        <div class="muted" id="updated">Ожидание данных...</div>
      </header>

      <section class="panel">
        <h2>Быстрый запуск</h2>
        <form id="quick-form">
          <div class="quick-grid">
            <input name="meeting_url" type="url" placeholder="Ссылка на встречу" required>
            <input name="title" type="text" placeholder="Название, необязательно">
            <button type="submit">Запустить</button>
          </div>
          <div class="quick-extra-grid">
            <textarea name="agenda" placeholder="Повестка, необязательно. Например: ###Повестка: #1. Вопрос - 10:00 #2. Следующий вопрос###"></textarea>
            <textarea name="expected_participants" placeholder="Участники, необязательно. Например: Иван Иванов <ivan@example.com>, Максим Силаев - mv.silaev@razum.life"></textarea>
          </div>
          <div class="message" id="quick-message"></div>
        </form>
      </section>

      <section class="summary">
        <div class="metric"><span class="muted">Узлов</span><strong id="nodes-total">0</strong></div>
        <div class="metric"><span class="muted">Ботов</span><strong id="bots-total">0</strong></div>
        <div class="metric"><span class="muted">Свободны</span><strong id="bots-idle">0</strong></div>
        <div class="metric"><span class="muted">Заняты</span><strong id="bots-busy">0</strong></div>
      </section>

      <section class="nodes" id="nodes"></section>
    </section>

    <section class="page" id="calendar-page">
      <header>
        <div>
          <h1>Корпоративный календарь</h1>
          <div class="muted">Preview-режим: события только отображаются, боты не запускаются</div>
        </div>
      </header>

      <section class="panel">
        <div class="calendar-head">
          <div>
            <h2>Проверка доступных встреч</h2>
            <div class="muted">Сервис показывает только те календари, которые реально доступны аккаунту бота</div>
          </div>
          <div class="calendar-actions">
            <input id="calendar-days" type="number" min="1" max="14" value="2" title="Дней">
            <button type="button" id="calendar-preview-button">Показать встречи</button>
          </div>
        </div>
        <div class="calendar-summary">
          <div class="metric"><span class="muted">Календарей</span><strong id="calendar-total">0</strong></div>
          <div class="metric"><span class="muted">Событий</span><strong id="calendar-events">0</strong></div>
          <div class="metric"><span class="muted">Со ссылкой</span><strong id="calendar-telemost">0</strong></div>
        </div>
        <div class="message" id="calendar-message">Нажмите "Показать встречи", чтобы проверить ближайшие события.</div>
        <div style="overflow:auto;">
          <table class="calendar-table">
            <thead>
              <tr>
                <th>Начало</th>
                <th>Название</th>
                <th>Календарь</th>
                <th>Ссылка</th>
                <th>Участники</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody id="calendar-events-body"></tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="calendar-head">
          <div>
            <h2>Календарный контроль</h2>
            <div class="muted">Локальный список ближайших встреч и попыток автоматического запуска ботов</div>
          </div>
          <button type="button" id="calendar-control-refresh">Обновить</button>
        </div>
        <div class="calendar-control-grid">
          <div class="metric"><span class="muted">Встреч</span><strong id="control-events-total">0</strong></div>
          <div class="metric"><span class="muted">Со ссылкой</span><strong id="control-events-link">0</strong></div>
          <div class="metric"><span class="muted">К запуску</span><strong id="control-events-due">0</strong></div>
          <div class="metric"><span class="muted">Запущено</span><strong id="control-events-dispatched">0</strong></div>
          <div class="metric"><span class="muted">Ошибок</span><strong id="control-events-failed">0</strong></div>
        </div>
        <div class="message" id="calendar-control-message">Ожидание данных календарного контроля...</div>
        <div style="overflow:auto;">
          <table class="calendar-table">
            <thead>
              <tr>
                <th>Начало</th>
                <th>Название</th>
                <th>Календарь</th>
                <th>Статус</th>
                <th>Бот</th>
                <th>Попытка</th>
                <th>Ошибка</th>
              </tr>
            </thead>
            <tbody id="calendar-control-body"></tbody>
          </table>
        </div>
      </section>
    </section>
  </main>
</div>

<script>
const nodesEl = document.getElementById("nodes");
const updatedEl = document.getElementById("updated");
const quickForm = document.getElementById("quick-form");
const quickMessage = document.getElementById("quick-message");
const calendarButton = document.getElementById("calendar-preview-button");
const calendarDays = document.getElementById("calendar-days");
const calendarMessage = document.getElementById("calendar-message");
const calendarEventsBody = document.getElementById("calendar-events-body");
const calendarControlRefresh = document.getElementById("calendar-control-refresh");
const calendarControlMessage = document.getElementById("calendar-control-message");
const calendarControlBody = document.getElementById("calendar-control-body");
const navButtons = document.querySelectorAll("[data-page-target]");
const pages = document.querySelectorAll(".page");

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function render(data) {
  document.getElementById("nodes-total").textContent = data.summary.nodes_total;
  document.getElementById("bots-total").textContent = data.summary.bots_total;
  document.getElementById("bots-idle").textContent = data.summary.bots_idle;
  document.getElementById("bots-busy").textContent = data.summary.bots_busy;
  updatedEl.textContent = `Обновлено: ${new Date().toLocaleTimeString("ru-RU")}`;

  nodesEl.innerHTML = data.nodes.map(node => `
    <article class="node ${node.status}">
      <div class="node-head">
        <div>
          <div class="node-title">${esc(node.node_name)} <span class="muted">(${esc(node.node_id)})</span></div>
          <div class="muted">${esc(node.base_url || "")}</div>
          ${node.error ? `<div class="message error">${esc(node.error)}</div>` : ""}
        </div>
        <div class="badge ${node.status === "online" ? "" : "busy"}">${esc(node.status)}</div>
      </div>
      <div class="bots">
        ${(node.bots || []).map(bot => `
          <div class="bot ${bot.status}">
            <strong>${esc(bot.global_bot_id || bot.bot_id)}</strong>
            <span class="badge ${bot.status}">${esc(bot.status)}</span>
            <div class="row">
              <span class="muted">Встреча</span><span>${esc(bot.title || bot.session_id || "-")}</span>
              <span class="muted">Ссылка</span><span>${esc(bot.meeting_url || "-")}</span>
              <span class="muted">Старт</span><span>${esc(bot.started_at || "-")}</span>
            </div>
            ${bot.status === "idle" ? `
              <form class="bot-form" data-node-id="${esc(node.node_id)}" data-bot-id="${esc(bot.bot_id)}">
                <div class="row" style="grid-template-columns:1fr; margin-top:10px;">
                  <input name="meeting_url" type="url" placeholder="Ссылка на встречу" required>
                  <input name="title" type="text" placeholder="Название, необязательно">
                  <textarea name="agenda" placeholder="Повестка, необязательно"></textarea>
                  <textarea name="expected_participants" placeholder="Участники, необязательно"></textarea>
                  <button type="submit">Запустить на этом боте</button>
                  <div class="message"></div>
                </div>
              </form>
            ` : ""}
          </div>
        `).join("")}
      </div>
    </article>
  `).join("");

  for (const form of document.querySelectorAll(".bot-form")) {
    form.addEventListener("submit", submitSpecific);
  }
}

async function refresh() {
  try {
    const resp = await fetch("/api/v1/nodes/status", { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    render(await resp.json());
  } catch (e) {
    updatedEl.textContent = `Ошибка обновления: ${e.message}`;
  }
}

function payloadFrom(form) {
  const data = new FormData(form);
  return {
    meeting_url: String(data.get("meeting_url") || "").trim(),
    title: String(data.get("title") || "").trim() || null,
    agenda: String(data.get("agenda") || "").trim() || null,
    expected_participants: String(data.get("expected_participants") || "").trim() || null,
    source: "control_service"
  };
}

function showPage(pageId) {
  for (const page of pages) {
    page.classList.toggle("active", page.id === pageId);
  }
  for (const button of navButtons) {
    button.classList.toggle("active", button.dataset.pageTarget === pageId);
  }
}

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function renderParticipants(event) {
  const attendees = event.attendees || [];
  if (!attendees.length) return `<span class="muted">-</span>`;
  const rows = attendees.slice(0, 12).map(item => {
    const email = item.email ? ` <span class="muted">&lt;${esc(item.email)}&gt;</span>` : "";
    const role = item.role === "OPT-PARTICIPANT" ? "опц." : "обяз.";
    return `<li>${esc(item.name || "-")}${email} <span class="muted">${role}</span></li>`;
  }).join("");
  const tail = attendees.length > 12 ? `<li class="muted">... еще ${attendees.length - 12}</li>` : "";
  const required = Number(event.attendees_required_count || 0);
  const optional = Number(event.attendees_optional_count || 0);
  const label = optional ? `${attendees.length} (${required} обяз., ${optional} опц.)` : `${attendees.length}`;
  return `<details><summary>${esc(label)}</summary><ul class="participants-list">${rows}${tail}</ul></details>`;
}

function renderCalendarPreview(data) {
  document.getElementById("calendar-total").textContent = data.summary.calendars_total;
  document.getElementById("calendar-events").textContent = data.summary.events_total;
  document.getElementById("calendar-telemost").textContent = data.summary.events_with_telemost;

  const checkedAt = formatDateTime(data.checked_at);
  calendarMessage.className = "message";
  calendarMessage.textContent = `Проверено: ${checkedAt}. Диапазон: ${formatDateTime(data.range.start)} - ${formatDateTime(data.range.end)}.`;

  if (!data.events.length) {
    calendarEventsBody.innerHTML = `<tr><td colspan="6" class="muted">Событий за выбранный период не найдено.</td></tr>`;
    return;
  }

  calendarEventsBody.innerHTML = data.events.map(event => `
    <tr>
      <td>${esc(formatDateTime(event.starts_at))}</td>
      <td>${esc(event.title || "-")}</td>
      <td>${esc(event.calendar_source || "-")}</td>
      <td>${event.meeting_url ? `<a href="${esc(event.meeting_url)}" target="_blank" rel="noreferrer">${esc(event.meeting_url)}</a>` : `<span class="muted">-</span>`}</td>
      <td class="participants-cell">${renderParticipants(event)}</td>
      <td>${event.has_telemost_url ? `<span class="ok">готово</span>` : `<span class="warn">нет ссылки</span>`}</td>
    </tr>
  `).join("");
}

function statusLabel(status) {
  const labels = {
    upcoming: "ожидает",
    due: "пора запускать",
    missed_candidate: "проверка пропуска",
    dispatching: "запускается",
    dispatched: "запущено",
    failed: "ошибка",
    past_no_link: "прошло без ссылки"
  };
  return labels[status] || status || "-";
}

function statusClass(status) {
  if (status === "dispatched") return "ok";
  if (status === "failed") return "bad";
  if (status === "due" || status === "missed_candidate" || status === "dispatching") return "warn";
  return "muted";
}

function renderCalendarControl(data) {
  const summary = data.summary || {};
  document.getElementById("control-events-total").textContent = summary.events_total || 0;
  document.getElementById("control-events-link").textContent = summary.events_with_telemost || 0;
  document.getElementById("control-events-due").textContent = summary.due || 0;
  document.getElementById("control-events-dispatched").textContent = summary.dispatched || 0;
  document.getElementById("control-events-failed").textContent = summary.failed || 0;

  calendarControlMessage.className = "message";
  calendarControlMessage.textContent = `Файл обновлен: ${formatDateTime(data.generated_at)}. Диапазон: ${formatDateTime(data.range?.start)} - ${formatDateTime(data.range?.end)}.`;

  const events = data.events || [];
  if (!events.length) {
    calendarControlBody.innerHTML = `<tr><td colspan="7" class="muted">В локальном списке пока нет ближайших встреч.</td></tr>`;
    return;
  }

  calendarControlBody.innerHTML = events.map(event => `
    <tr>
      <td>${esc(formatDateTime(event.starts_at))}</td>
      <td>${event.meeting_url ? `<a href="${esc(event.meeting_url)}" target="_blank" rel="noreferrer">${esc(event.title || "-")}</a>` : esc(event.title || "-")}</td>
      <td>${esc(event.calendar_source || "-")}</td>
      <td><span class="${statusClass(event.status)}">${esc(statusLabel(event.status))}</span></td>
      <td>${esc([event.node_id, event.bot_id].filter(Boolean).join(":") || "-")}</td>
      <td>${esc(formatDateTime(event.last_attempt_at || event.dispatched_at))}</td>
      <td>${event.error ? `<span class="bad">${esc(event.error)}</span>` : `<span class="muted">-</span>`}</td>
    </tr>
  `).join("");
}

async function loadCalendarControl(forceRefresh = false) {
  try {
    const resp = await fetch(
      forceRefresh ? "/api/v1/calendar/upcoming/refresh" : "/api/v1/calendar/upcoming",
      {
        method: forceRefresh ? "POST" : "GET",
        cache: "no-store"
      }
    );
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    renderCalendarControl(data);
  } catch (e) {
    calendarControlMessage.className = "message error";
    calendarControlMessage.textContent = e.message;
  }
}

async function loadCalendarPreview() {
  const days = Math.max(1, Math.min(14, Number(calendarDays.value || 2)));
  calendarDays.value = days;
  calendarButton.disabled = true;
  calendarMessage.className = "message";
  calendarMessage.textContent = "Проверяю корпоративный календарь...";
  try {
    const resp = await fetch(`/api/v1/calendar/company/preview?days=${encodeURIComponent(days)}`, { cache: "no-store" });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    renderCalendarPreview(data);
  } catch (e) {
    calendarMessage.className = "message error";
    calendarMessage.textContent = e.message;
  } finally {
    calendarButton.disabled = false;
  }
}

async function submitQuick(event) {
  event.preventDefault();
  const button = quickForm.querySelector("button");
  button.disabled = true;
  quickMessage.className = "message";
  quickMessage.textContent = "Ищу свободного бота...";
  try {
    const resp = await fetch("/api/v1/meetings/quick", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloadFrom(quickForm))
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    quickMessage.textContent = `Задача ${data.task_id} отправлена на ${data.node_id}:${data.bot_id}`;
    quickForm.reset();
    await refresh();
  } catch (e) {
    quickMessage.className = "message error";
    quickMessage.textContent = e.message;
  } finally {
    button.disabled = false;
  }
}

async function submitSpecific(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const message = form.querySelector(".message");
  const button = form.querySelector("button");
  button.disabled = true;
  message.className = "message";
  message.textContent = "Отправляю...";
  try {
    const resp = await fetch(`/api/v1/nodes/${encodeURIComponent(form.dataset.nodeId)}/bots/${encodeURIComponent(form.dataset.botId)}/meetings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloadFrom(form))
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
    message.textContent = `Создана задача ${data.task_id}`;
    form.reset();
    await refresh();
  } catch (e) {
    message.className = "message error";
    message.textContent = e.message;
  } finally {
    button.disabled = false;
  }
}

quickForm.addEventListener("submit", submitQuick);
calendarButton.addEventListener("click", loadCalendarPreview);
calendarControlRefresh.addEventListener("click", () => loadCalendarControl(true));
for (const button of navButtons) {
  button.addEventListener("click", () => showPage(button.dataset.pageTarget));
}
refresh();
loadCalendarControl();
setInterval(refresh, 3000);
setInterval(loadCalendarControl, 10000);
</script>
</body>
</html>
"""
