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
    .sidebar { display: flex; flex-direction: column; background: #111827; color: #f8fafc; padding: 24px 16px; }
    .brand { margin-bottom: 24px; }
    .brand strong { display: block; font-size: 18px; }
    .brand span { color: #aeb8c8; font-size: 13px; }
    .nav { display: grid; gap: 8px; }
    .nav button { width: 100%; text-align: left; background: transparent; color: #dbe4f0; border: 1px solid transparent; }
    .nav button.active { background: #243044; color: #fff; border-color: #3a4b68; }
    .nav button.session-alert { background: #a51d2d; color: #fff; border-color: #ef6c72; }
    .nav button.session-alert.active { background: #c01c28; }
    .session-alert-mark { display: none; float: right; width: 22px; height: 22px; border-radius: 50%; background: #fff; color: #b42318; text-align: center; line-height: 22px; }
    .nav button.session-alert .session-alert-mark { display: inline-block; }
    .logout-link { margin-top: auto; padding: 12px; color: #aeb8c8; text-decoration: none; font-size: 14px; }
    .logout-link:hover { color: #fff; }
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
    .organizer-picker-row { margin-top: 10px; }
    .employee-picker { position: relative; }
    .employee-picker-trigger { width: 100%; display: flex; justify-content: space-between; align-items: center; text-align: left; color: #20242d; background: #fff; border: 1px solid #cbd3dc; font-weight: 400; }
    .employee-picker-trigger:hover { border-color: #8aa8cc; }
    .employee-picker-placeholder { color: #687080; }
    .employee-picker-menu { position: absolute; z-index: 80; top: calc(100% + 5px); left: 0; right: 0; padding: 8px; border: 1px solid #cbd3dc; border-radius: 9px; background: #fff; box-shadow: 0 12px 28px rgba(20,31,45,.18); }
    .employee-picker-search { margin-bottom: 7px; }
    .employee-picker-options { max-height: 300px; overflow-y: auto; display: grid; gap: 3px; }
    .employee-option { width: 100%; min-height: 50px; padding: 7px 9px; text-align: left; background: #fff; color: #20242d; border: 1px solid transparent; font-weight: 400; }
    .employee-option:hover, .employee-option.selected { background: #edf5ff; border-color: #b9d5f6; }
    .employee-option strong { display: block; font-size: 14px; }
    .employee-option small { display: block; margin-top: 2px; color: #687080; font-size: 12px; }
    .employee-option.clear { min-height: 40px; color: #687080; }
    .calendar-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
    .metric { padding: 14px; }
    .metric strong { display: block; font-size: 28px; margin-top: 4px; }
    .nodes { display: grid; gap: 14px; }
    .node { padding: 16px; border-left: 7px solid #8b949e; }
    .node.online { border-left-color: #26a269; }
    .node.unavailable { border-left-color: #c01c28; }
    .on-demand-machines { display: grid; gap: 12px; margin-bottom: 16px; }
    .on-demand-machine { padding: 16px; border: 1px solid #c4b5fd; border-left: 7px solid #7c3aed; border-radius: 8px; background: #faf7ff; box-shadow: 0 1px 2px rgba(76,29,149,.08); }
    .on-demand-machine.unavailable { border-left-color: #b45309; background: #fffbeb; }
    .on-demand-machine.degraded { border-left-color: #d97706; }
    .on-demand-machine.transitioning { border-left-color: #2563eb; background: #eff6ff; }
    .machine-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; margin-top: 12px; }
    .machine-actions .danger { background: #b42318; }
    .machine-actions .message { flex: 1; margin: 0; }
    .on-demand-machine-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
    .on-demand-machine-grid > div { padding: 10px; border: 1px solid #ddd6fe; border-radius: 7px; background: rgba(255,255,255,.75); }
    .node.on-demand { border-color: #c4b5fd; border-left-color: #7c3aed; background: #fcfaff; }
    .node.on-demand.unavailable { border-left-color: #b45309; background: #fffcf5; }
    .bot.on-demand { border-color: #ddd6fe; border-left-color: #8b5cf6; background: #faf7ff; }
    .bot.on-demand.busy { border-left-color: #4f46e5; }
    .bot.on-demand.unavailable { border-color: #f5d28c; border-left-color: #b45309; background: #fffbeb; }
    .on-demand-mark { display: inline-block; margin-left: 6px; padding: 3px 8px; border-radius: 999px; background: #ede9fe; color: #6d28d9; font-size: 11px; font-weight: 800; vertical-align: middle; }
    .node-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
    .node-title { font-weight: 760; font-size: 18px; }
    .bots { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }
    .bot { padding: 12px; border-left: 6px solid #26a269; }
    .bot.busy { border-left-color: #1c71d8; }
    .bot.single-participant-alert, .bot.on-demand.single-participant-alert { background: #fff1f2; border-color: #e5484d; border-left-color: #c01c28; box-shadow: 0 0 0 2px rgba(192,28,40,.12); }
    .single-participant-warning { color: #a51d2d; font-weight: 700; margin-top: 10px; }
    .badge { display: inline-block; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; background: #dff5ea; color: #137144; }
    .badge.busy { background: #e1efff; color: #0b5cad; }
    .badge.unavailable { background: #fff0d4; color: #8a4b08; }
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
    .analytics-summary { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
    .analytics-filters { display: grid; grid-template-columns: repeat(2, minmax(150px, .7fr)) minmax(220px, 1.3fr) minmax(160px, .7fr) auto; gap: 10px; align-items: end; }
    .analytics-filters label { display: grid; gap: 5px; color: #687080; font-size: 12px; }
    .organizer-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 8px; }
    .organizer-item { display: flex; justify-content: space-between; gap: 10px; padding: 10px; border: 1px solid #e4e8ee; border-radius: 8px; background: #f8fafc; }
    .daily-empty-summary { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; margin: 14px 0; }
    .empty-chart { height: 230px; display: flex; align-items: flex-end; gap: 4px; padding: 18px 4px 28px; border-bottom: 1px solid #dce3ec; overflow-x: auto; }
    .empty-chart-day { min-width: 24px; flex: 1 0 24px; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; position: relative; }
    .empty-chart-bar { width: 70%; min-height: 2px; border-radius: 5px 5px 0 0; background: #ef6c63; }
    .empty-chart-bar.no-data { height: 2px !important; background: #d9e0e9; }
    .empty-chart-label { position: absolute; bottom: -23px; font-size: 10px; color: #64748b; white-space: nowrap; }
    .message { min-height: 20px; margin-top: 8px; font-size: 14px; }
    .agenda-box { margin-top: 10px; padding: 10px; border: 1px solid #e4e8ee; border-radius: 8px; background: #f8fafc; }
    .agenda-form { display: grid; gap: 8px; margin-top: 8px; }
    .assignment-details { display: grid; gap: 14px; }
    .assignment-question { padding: 14px; border: 1px solid #dfe4ea; border-radius: 8px; background: #f8fafc; }
    .assignment-card { margin-top: 10px; padding: 12px; border-left: 4px solid #1c71d8; background: #fff; }
    .assignment-card.status-sent { border-left-color: #26a269; }
    .assignment-card.status-failed, .assignment-card.status-failed_user_resolution, .assignment-card.status-missing_due_date { border-left-color: #c01c28; }
    .assignment-card p { margin: 5px 0; white-space: pre-wrap; }
    .session-summary { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
    .session-status-line { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .session-auto-form { display: flex; gap: 14px; align-items: end; flex-wrap: wrap; }
    .session-auto-form label { display: grid; gap: 6px; }
    .session-auto-form input[type="number"] { width: 150px; }
    .session-auto-toggle { display: flex !important; grid-auto-flow: column; align-items: center; gap: 8px !important; min-height: 42px; }
    .discovery-subnav { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 18px; }
    .discovery-subnav button { background: #e8edf4; color: #27364a; }
    .discovery-subnav button.active { background: #1c71d8; color: #fff; }
    .discovery-section.hidden { display: none; }
    .discovery-status { display: flex; align-items: center; flex-wrap: wrap; gap: 11px; }
    .discovery-dot { width: 12px; height: 12px; border-radius: 50%; background: #8b949e; }
    .discovery-dot.running { background: #246fd6; animation: pulse 1.2s infinite; }
    .discovery-dot.completed { background: #26a269; }
    .discovery-dot.failed { background: #c01c28; }
    @keyframes pulse { 50% { opacity: .3; } }
    .discovery-progress { width: 100%; height: 12px; margin-top: 12px; }
    .discovery-summary { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
    .discovery-tabs, .discovery-meeting-filters, .discovery-control-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .discovery-tabs button, .discovery-meeting-filters button { background: #e8edf4; color: #27364a; }
    .discovery-tabs button.active, .discovery-meeting-filters button.active { background: #1c71d8; color: #fff; }
    .discovery-filters { display: grid; grid-template-columns: minmax(260px, 1fr); gap: 10px; margin: 12px 0; }
    .discovery-table-wrap { max-height: 650px; overflow: auto; }
    .discovery-day-row td { position: sticky; top: 36px; z-index: 1; background: #eef3fa; color: #27364a; font-size: 15px; font-weight: 800; }
    .discovery-mode-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
    .discovery-mode-card { min-height: 116px; padding: 15px; text-align: left; color: #27364a; background: #f6f8fb; border: 2px solid #dce2ea; }
    .discovery-mode-card strong { display: block; margin-bottom: 7px; font-size: 16px; }
    .discovery-mode-card span { color: #687080; font-weight: 400; font-size: 13px; }
    .discovery-mode-card.active { color: #124a91; background: #edf5ff; border-color: #246fd6; }
    .discovery-control-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .secondary { background: #e8edf4; color: #27364a; }
    .badge.no { background: #f0f2f5; color: #687080; }
    .badge.external { background: #fff0d4; color: #8a4b08; }
    .badge.fail { background: #fde7e7; color: #a61b1b; }
    .otp-panel { margin-top: 16px; padding: 16px; border: 1px solid #f0b6ba; border-radius: 8px; background: #fff7f7; }
    .otp-fields { display: flex; gap: 10px; margin: 14px 0; }
    .otp-fields input { width: 52px; height: 58px; text-align: center; font-size: 28px; font-weight: 760; }
    .hidden { display: none !important; }
    .error { color: #b42318; }
    @media (min-width: 901px) {
      .sidebar { position: sticky; top: 0; align-self: start; height: 100vh; overflow-y: auto; }
    }
    @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } .sidebar { position: static; } .nav { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 1100px) { .discovery-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
    @media (max-width: 760px) { header { display: block; } .summary, .quick-grid, .quick-extra-grid, .calendar-summary, .calendar-control-grid, .analytics-summary, .analytics-filters, .daily-empty-summary, .session-summary, .discovery-summary, .discovery-mode-grid, .on-demand-machine-grid { grid-template-columns: 1fr; } .calendar-head, .calendar-actions, .discovery-control-head { display: block; } .calendar-actions input, .calendar-actions button { margin-top: 8px; width: 100%; } .nav { grid-template-columns: 1fr; } .otp-fields { gap: 5px; } .otp-fields input { width: 42px; } }
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
      <button type="button" class="active" id="bots-nav-button" data-page-target="bots-page">Пул ботов <span class="session-alert-mark" aria-label="Есть встреча с одним участником дольше порога">!</span></button>
      <button type="button" data-page-target="calendar-page">Корпоративный календарь</button>
      <button type="button" data-page-target="analytics-page">Аналитика встреч</button>
      <button type="button" data-page-target="assignments-page">Поручения</button>
      <button type="button" id="session-nav-button" data-page-target="session-page">Состояние сессии <span class="session-alert-mark">!</span></button>
    </nav>
    <a class="logout-link" href="/auth/logout">Выйти из системы</a>
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
          <div class="organizer-picker-row">
            <div class="employee-picker" data-employee-picker>
              <input type="hidden" name="organizer" value="">
              <button type="button" class="employee-picker-trigger"><span class="employee-picker-label employee-picker-placeholder">Организатор, необязательно</span><span>⌄</span></button>
              <div class="employee-picker-menu hidden">
                <input type="search" class="employee-picker-search" placeholder="Поиск по ФИО или почте">
                <div class="employee-picker-options"><div class="muted">Нажмите, чтобы загрузить сотрудников</div></div>
              </div>
            </div>
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

      <section class="on-demand-machines hidden" id="on-demand-machines"></section>

      <section class="nodes" id="nodes"></section>
    </section>

    <section class="page" id="calendar-page">
      <header>
        <div>
          <h1>Корпоративный календарь</h1>
          <div class="muted">Все корпоративные встречи с Телемостом и управление участием Робота Вертера</div>
        </div>
      </header>
      <div class="discovery-subnav">
        <button type="button" class="active" data-discovery-page="control">Календарный контроль</button>
        <button type="button" data-discovery-page="meetings">Корпоративные встречи</button>
        <button type="button" data-discovery-page="management">Управление добавлением бота</button>
      </div>

      <div class="discovery-section" id="calendar-control-section">
        <section class="panel">
          <div class="calendar-head">
            <div>
              <h2>Проверка доступных встреч</h2>
              <div class="muted">Сервис показывает календари, доступные аккаунту бота через основной контур мониторинга</div>
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
          <div class="message" id="calendar-message">Нажмите «Показать встречи», чтобы проверить ближайшие события.</div>
          <div style="overflow:auto;">
            <table class="calendar-table">
              <thead><tr><th>Начало</th><th>Название</th><th>Календарь</th><th>Ссылка</th><th>Участники</th><th>Статус</th></tr></thead>
              <tbody id="calendar-events-body"></tbody>
            </table>
          </div>
        </section>
        <section class="panel">
          <div class="calendar-head">
            <div>
              <h2>Календарный контроль</h2>
              <div class="muted">Локальный список ближайших встреч, распределение по ботам и результаты запуска</div>
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
              <thead><tr><th>Начало</th><th>Название</th><th>Календарь</th><th>Статус</th><th>Бот</th><th>Попытка</th><th>Ошибка</th></tr></thead>
              <tbody id="calendar-control-body"></tbody>
            </table>
          </div>
        </section>
      </div>

      <div class="discovery-section hidden" id="discovery-meetings-section">
        <section class="panel">
          <div class="calendar-head">
            <div class="discovery-status"><span class="discovery-dot" id="discovery-dot"></span><strong id="discovery-status">Нет данных</strong><span class="muted" id="discovery-window"></span></div>
            <div><span class="muted" id="discovery-updated">Ожидание данных...</span> <button type="button" id="discovery-scan">Обновить сейчас</button></div>
          </div>
          <progress class="discovery-progress" id="discovery-progress" value="0" max="1"></progress>
          <div class="muted" id="discovery-progress-text"></div>
          <div class="muted" id="discovery-cache"></div>
          <div class="error" id="discovery-error"></div>
        </section>
        <section class="discovery-summary">
          <div class="metric"><span class="muted">Сотрудников</span><strong id="discovery-employees">0</strong></div>
          <div class="metric"><span class="muted">Прочитано календарей</span><strong id="discovery-scanned">0</strong></div>
          <div class="metric"><span class="muted">Событий до дедупликации</span><strong id="discovery-raw">0</strong></div>
          <div class="metric"><span class="muted">Уникальных событий</span><strong id="discovery-unique">0</strong></div>
          <div class="metric"><span class="muted">Удалено дублей</span><strong id="discovery-duplicates">0</strong></div>
          <div class="metric"><span class="muted">Встреч с Телемостом</span><strong id="discovery-telemost">0</strong></div>
        </section>
        <section class="panel">
          <div class="discovery-tabs"><button type="button" class="active" data-discovery-tab="events">Встречи с Телемостом</button><button type="button" data-discovery-tab="errors">Ошибки</button></div>
          <div class="discovery-filters">
            <div class="discovery-meeting-filters">
              <button type="button" class="active" data-discovery-filter="all">Все встречи</button>
              <button type="button" data-discovery-filter="participant">Бот участвует</button>
              <button type="button" data-discovery-filter="absent">Бот не участвует</button>
            </div>
            <input id="discovery-search" placeholder="Поиск по названию, организатору, участнику или ID">
          </div>
          <div class="discovery-table-wrap"><table class="calendar-table"><thead id="discovery-thead"></thead><tbody id="discovery-tbody"></tbody></table></div>
        </section>
      </div>

      <div class="discovery-section hidden" id="discovery-management-section">
        <section class="panel">
          <div class="discovery-control-head">
            <div><h2>Режим работы</h2><div class="muted">Автоматический режим сейчас не включён. Изменения календарей выполняются только после явного действия.</div></div>
            <div class="discovery-control-actions"><button type="button" class="secondary" id="discovery-run-management">Обработать сейчас</button></div>
          </div>
          <div class="discovery-mode-grid">
            <button type="button" class="discovery-mode-card" data-discovery-mode="off"><strong>Выключено</strong><span>Только сбор и отображение встреч. Календарь не изменяется.</span></button>
            <button type="button" class="discovery-mode-card" data-discovery-mode="preview"><strong>Предпросмотр</strong><span>Формируется очередь, но бот автоматически не добавляется.</span></button>
            <button type="button" class="discovery-mode-card" data-discovery-mode="automatic"><strong>Автоматически</strong><span>После каждого сканирования бот добавляется во все подходящие встречи.</span></button>
          </div>
          <div class="error" id="discovery-management-error"></div>
        </section>
        <section class="discovery-summary">
          <div class="metric"><span class="muted">Режим</span><strong id="discovery-management-mode">—</strong></div>
          <div class="metric"><span class="muted">Кандидатов</span><strong id="discovery-management-candidates">0</strong></div>
          <div class="metric"><span class="muted">Обработано</span><strong id="discovery-management-completed">0</strong></div>
          <div class="metric"><span class="muted">Ошибок</span><strong id="discovery-management-failed">0</strong></div>
          <div class="metric"><span class="muted">Исключено</span><strong id="discovery-management-excluded">0</strong></div>
          <div class="metric"><span class="muted">Последний цикл</span><strong id="discovery-management-cycle">—</strong></div>
        </section>
        <section class="panel">
          <h2>Очередь встреч</h2>
          <div class="muted" id="discovery-management-cycle-details"></div>
          <div class="discovery-filters"><input id="discovery-control-search" placeholder="Поиск по встрече, организатору или статусу"></div>
          <div class="discovery-table-wrap"><table class="calendar-table"><thead><tr><th>Время</th><th>Встреча</th><th>Управляющий аккаунт</th><th>Статус</th><th>Последний результат</th><th>Действия</th></tr></thead><tbody id="discovery-control-tbody"></tbody></table></div>
        </section>
        <section class="panel">
          <h2>Журнал действий</h2>
          <div class="discovery-table-wrap"><table class="calendar-table"><thead><tr><th>Время</th><th>Источник</th><th>Встреча</th><th>Результат</th><th>Этапы</th><th>Причина</th></tr></thead><tbody id="discovery-history-tbody"></tbody></table></div>
        </section>
      </div>
    </section>

    <section class="page" id="analytics-page">
      <header>
        <div>
          <h1>Аналитика встреч</h1>
          <div class="muted">Фактическая длительность и повестки завершённых встреч</div>
        </div>
        <button type="button" id="analytics-refresh">Обновить</button>
      </header>

      <section class="analytics-summary">
        <div class="metric"><span class="muted">Завершено встреч</span><strong id="analytics-total">0</strong></div>
        <div class="metric"><span class="muted">Средняя длительность</span><strong id="analytics-average">00:00</strong></div>
        <div class="metric"><span class="muted">С повесткой</span><strong id="analytics-agenda-count">0</strong></div>
        <div class="metric"><span class="muted">Доля с повесткой</span><strong id="analytics-agenda-percent">0%</strong></div>
        <div class="metric"><span class="muted">Пустые встречи</span><strong id="analytics-empty-count">0</strong></div>
      </section>

      <section class="panel">
        <h2>Доля пустых встреч по дням</h2>
        <div class="muted">В расчёт входят только проверенные встречи: пустые и непустые.</div>
        <div class="daily-empty-summary">
          <div class="metric"><span class="muted">Сегодня проверено</span><strong id="daily-empty-checked">0</strong></div>
          <div class="metric"><span class="muted">Сегодня пустых</span><strong id="daily-empty-count">0</strong></div>
          <div class="metric"><span class="muted">Доля сегодня</span><strong id="daily-empty-percent">—</strong></div>
          <div class="metric"><span class="muted">К предыдущему дню</span><strong id="daily-empty-change">—</strong></div>
          <div class="metric"><span class="muted">Среднее за 7 дней</span><strong id="daily-empty-average-7">—</strong></div>
          <div class="metric"><span class="muted">Среднее за 30 дней</span><strong id="daily-empty-average-30">—</strong></div>
        </div>
        <div class="empty-chart" id="daily-empty-chart"></div>
      </section>

      <section class="panel">
        <div class="analytics-filters">
          <label>Дата от<input type="date" id="analytics-date-from"></label>
          <label>Дата до<input type="date" id="analytics-date-to"></label>
          <label>Организатор<input type="search" id="analytics-organizer" placeholder="Имя или email"></label>
          <label>Повестка<select id="analytics-agenda"><option value="">Все встречи</option><option value="true">Есть</option><option value="false">Нет</option></select></label>
          <label>Пустая встреча<select id="analytics-empty"><option value="">Все встречи</option><option value="empty">Пустые</option><option value="not_empty">Непустые</option><option value="unknown">Ожидают проверки</option><option value="folder_not_found">Папка не найдена</option><option value="scan_missed">Проверка не выполнялась</option></select></label>
          <label>Папка на Яндекс Диске<select id="analytics-folder"><option value="">Все встречи</option><option value="true">Папка есть</option><option value="false">Папки нет</option></select></label>
          <button type="button" id="analytics-apply">Применить</button>
        </div>
        <div class="message" id="analytics-message">Загрузка аналитики...</div>
      </section>

      <section class="panel">
        <h2>Самые активные организаторы</h2>
        <div class="organizer-grid" id="analytics-organizers"></div>
      </section>

      <section class="panel">
        <h2>Завершённые встречи</h2>
        <div style="overflow:auto;">
          <table class="calendar-table">
            <thead><tr><th>Фактическое время</th><th>Название</th><th>Организатор</th><th>Длительность</th><th>Повестка</th><th>Проведение</th><th>Бот</th><th>Артефакты на Яндекс Диске</th></tr></thead>
            <tbody id="analytics-meetings-body"></tbody>
          </table>
        </div>
      </section>
    </section>

    <section class="page" id="assignments-page">
      <header>
        <div>
          <h1>Поручения</h1>
          <div class="muted">Подтверждённые поручения, полученные и сохранённые микросервисом интеграции</div>
        </div>
        <button type="button" id="assignments-refresh">Обновить</button>
      </header>
      <section class="panel">
        <div class="message" id="assignments-message">Загрузка поручений...</div>
        <div style="overflow:auto;">
          <table class="calendar-table">
            <thead><tr><th>Дата встречи</th><th>Название</th><th>Организатор</th><th>Получено</th><th>Вопросов</th><th>Поручений</th><th>Статус</th><th>Действия</th></tr></thead>
            <tbody id="assignments-meetings-body"></tbody>
          </table>
        </div>
      </section>
      <section class="panel hidden" id="assignment-details-panel">
        <div class="calendar-head">
          <div><h2 id="assignment-details-title">Поручения встречи</h2><div class="muted" id="assignment-details-meta"></div></div>
          <button type="button" class="secondary" id="assignment-details-close">Закрыть</button>
        </div>
        <div class="assignment-details" id="assignment-details"></div>
      </section>
    </section>

    <section class="page" id="session-page">
      <header>
        <div>
          <h1>Состояние сессии</h1>
          <div class="muted">Проверка и защищённое обновление авторизации Яндекса для ботов</div>
        </div>
        <button type="button" id="session-check-button">Проверить сейчас</button>
      </header>

      <section class="session-summary">
        <div class="metric"><span class="muted">Текущее состояние</span><strong id="session-status">неизвестно</strong></div>
        <div class="metric"><span class="muted">Последняя проверка</span><strong id="session-last-checked" style="font-size:18px;">—</strong></div>
        <div class="metric"><span class="muted">Последняя авторизация</span><strong id="session-last-authenticated" style="font-size:18px;">—</strong></div>
        <div class="metric"><span class="muted">Обновление сессии</span><strong id="session-last-updated" style="font-size:18px;">—</strong></div>
        <div class="metric"><span class="muted">Последняя доставка</span><strong id="session-last-delivered" style="font-size:18px;">—</strong></div>
      </section>

      <section class="panel">
        <h2 style="margin-top:0;">Автоматическая проверка</h2>
        <form id="session-auto-form" class="session-auto-form">
          <label class="session-auto-toggle">
            <input type="checkbox" id="session-auto-enabled">
            <span>Проверять сессию автоматически</span>
          </label>
          <label>
            <span class="muted">Интервал, секунд</span>
            <input type="number" id="session-auto-interval" min="10" max="86400" step="1" value="60" required>
          </label>
          <button type="submit" id="session-auto-save">Сохранить</button>
          <div>
            <span class="badge" id="session-auto-mode">загрузка...</span>
            <div class="muted" id="session-next-check" style="margin-top:6px;">Следующая проверка: —</div>
          </div>
        </form>
      </section>

      <section class="panel">
        <div class="session-status-line">
          <h2 style="margin:0;">Получатели сессии</h2>
          <span class="badge" id="session-delivery-status">ещё не отправлялась</span>
        </div>
        <div id="session-targets" class="organizer-grid" style="margin-top:12px;"></div>
        <div class="message" id="session-message">Загрузка состояния...</div>
      </section>

      <section class="otp-panel hidden" id="session-otp-panel">
        <h2>Введите одноразовый код</h2>
        <div class="muted">Яндекс запросил подтверждение входа. Введите шесть цифр кода.</div>
        <form id="session-otp-form">
          <div class="otp-fields" id="session-otp-fields">
            <input inputmode="numeric" autocomplete="one-time-code" maxlength="1" aria-label="Цифра 1">
            <input inputmode="numeric" maxlength="1" aria-label="Цифра 2">
            <input inputmode="numeric" maxlength="1" aria-label="Цифра 3">
            <input inputmode="numeric" maxlength="1" aria-label="Цифра 4">
            <input inputmode="numeric" maxlength="1" aria-label="Цифра 5">
            <input inputmode="numeric" maxlength="1" aria-label="Цифра 6">
          </div>
          <button type="submit" id="session-confirm-button">Подтвердить код</button>
        </form>
      </section>
    </section>
  </main>
</div>

<script>
const nodesEl = document.getElementById("nodes");
const onDemandMachinesEl = document.getElementById("on-demand-machines");
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
const analyticsMessage = document.getElementById("analytics-message");
const analyticsMeetingsBody = document.getElementById("analytics-meetings-body");
const assignmentsMessage = document.getElementById("assignments-message");
const assignmentsMeetingsBody = document.getElementById("assignments-meetings-body");
const assignmentDetailsPanel = document.getElementById("assignment-details-panel");
const assignmentDetails = document.getElementById("assignment-details");
const sessionNavButton = document.getElementById("session-nav-button");
const sessionCheckButton = document.getElementById("session-check-button");
const sessionMessage = document.getElementById("session-message");
const sessionOtpPanel = document.getElementById("session-otp-panel");
const sessionOtpForm = document.getElementById("session-otp-form");
const sessionOtpInputs = Array.from(document.querySelectorAll("#session-otp-fields input"));
const sessionAutoForm = document.getElementById("session-auto-form");
const sessionAutoEnabled = document.getElementById("session-auto-enabled");
const sessionAutoInterval = document.getElementById("session-auto-interval");
const navButtons = document.querySelectorAll("[data-page-target]");
const pages = document.querySelectorAll(".page");
let discoveryData = {};
let discoveryTab = "events";
let discoveryMeetingFilter = "all";
let latestOnDemandMachines = [];
let latestSessionState = null;
const botFormDrafts = new Map();

function botFormDraftKey(form) {
  return `${form.dataset.nodeId || ""}\u0000${form.dataset.botId || ""}`;
}

function captureBotFormDrafts() {
  let focusedField = null;
  for (const form of document.querySelectorAll(".bot-form")) {
    const values = {};
    for (const field of form.querySelectorAll("[name]")) values[field.name] = field.value;
    botFormDrafts.set(botFormDraftKey(form), values);
    if (form.contains(document.activeElement) && document.activeElement?.name) {
      focusedField = {
        key: botFormDraftKey(form),
        name: document.activeElement.name,
        selectionStart: document.activeElement.selectionStart,
        selectionEnd: document.activeElement.selectionEnd,
      };
    }
  }
  return focusedField;
}

function restoreBotFormDrafts(focusedField) {
  for (const form of document.querySelectorAll(".bot-form")) {
    const key = botFormDraftKey(form);
    const values = botFormDrafts.get(key);
    if (values) {
      for (const field of form.querySelectorAll("[name]")) {
        if (Object.prototype.hasOwnProperty.call(values, field.name)) field.value = values[field.name];
      }
    }
    form.addEventListener("input", () => {
      const current = {};
      for (const field of form.querySelectorAll("[name]")) current[field.name] = field.value;
      botFormDrafts.set(key, current);
    });
  }
  if (!focusedField) return;
  const form = Array.from(document.querySelectorAll(".bot-form"))
    .find(item => botFormDraftKey(item) === focusedField.key);
  const field = form?.elements?.namedItem(focusedField.name);
  if (!field) return;
  field.focus({preventScroll: true});
  if (typeof field.setSelectionRange === "function" && focusedField.selectionStart !== null) {
    field.setSelectionRange(focusedField.selectionStart, focusedField.selectionEnd);
  }
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

let employeeDirectory = [];
let employeeDirectoryPromise = null;

async function loadEmployeeDirectory() {
  if (employeeDirectory.length) return employeeDirectory;
  if (!employeeDirectoryPromise) {
    employeeDirectoryPromise = fetch("/api/v1/employees", {cache: "no-store"})
      .then(async response => {
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`);
        employeeDirectory = Array.isArray(payload.users) ? payload.users : [];
        return employeeDirectory;
      })
      .finally(() => { employeeDirectoryPromise = null; });
  }
  return employeeDirectoryPromise;
}

function employeePickerHtml() {
  return `<div class="employee-picker" data-employee-picker>
    <input type="hidden" name="organizer" value="">
    <button type="button" class="employee-picker-trigger"><span class="employee-picker-label employee-picker-placeholder">Организатор, необязательно</span><span>⌄</span></button>
    <div class="employee-picker-menu hidden">
      <input type="search" class="employee-picker-search" placeholder="Поиск по ФИО или почте">
      <div class="employee-picker-options"><div class="muted">Нажмите, чтобы загрузить сотрудников</div></div>
    </div>
  </div>`;
}

function setEmployeePickerValue(picker, email, fullName = "") {
  const hidden = picker.querySelector('input[name="organizer"]');
  const label = picker.querySelector(".employee-picker-label");
  const normalized = String(email || "").trim().toLowerCase();
  hidden.value = normalized;
  if (normalized) {
    const employee = employeeDirectory.find(item => String(item.email || "").toLowerCase() === normalized);
    label.textContent = fullName || employee?.full_name || normalized;
    label.classList.remove("employee-picker-placeholder");
  } else {
    label.textContent = "Организатор, необязательно";
    label.classList.add("employee-picker-placeholder");
  }
  hidden.dispatchEvent(new Event("input", {bubbles: true}));
}

function renderEmployeeOptions(picker, query = "") {
  const options = picker.querySelector(".employee-picker-options");
  const selected = picker.querySelector('input[name="organizer"]').value.toLowerCase();
  const needle = String(query || "").trim().toLowerCase();
  const users = employeeDirectory.filter(user => !needle || `${user.full_name || ""} ${user.email || ""} ${user.position || ""}`.toLowerCase().includes(needle));
  options.innerHTML = `<button type="button" class="employee-option clear" data-employee-email="">Без выбранного организатора</button>`
    + users.slice(0, 250).map(user => `<button type="button" class="employee-option ${String(user.email).toLowerCase() === selected ? "selected" : ""}" data-employee-email="${esc(user.email)}" data-employee-name="${esc(user.full_name)}"><strong>${esc(user.full_name || user.email)}</strong><small>${esc(user.email)}</small></button>`).join("")
    + (!users.length ? '<div class="muted" style="padding:8px">Сотрудники не найдены</div>' : "");
  options.querySelectorAll("[data-employee-email]").forEach(option => option.addEventListener("click", () => {
    setEmployeePickerValue(picker, option.dataset.employeeEmail, option.dataset.employeeName);
    picker.querySelector(".employee-picker-menu").classList.add("hidden");
  }));
}

function setupEmployeePickers(root = document) {
  root.querySelectorAll("[data-employee-picker]").forEach(picker => {
    if (picker.dataset.initialized) return;
    picker.dataset.initialized = "1";
    const trigger = picker.querySelector(".employee-picker-trigger");
    const menu = picker.querySelector(".employee-picker-menu");
    const search = picker.querySelector(".employee-picker-search");
    setEmployeePickerValue(picker, picker.querySelector('input[name="organizer"]').value);
    trigger.addEventListener("click", async () => {
      const shouldOpen = menu.classList.contains("hidden");
      document.querySelectorAll(".employee-picker-menu").forEach(item => item.classList.add("hidden"));
      if (!shouldOpen) return;
      menu.classList.remove("hidden");
      search.focus();
      picker.querySelector(".employee-picker-options").innerHTML = '<div class="muted" style="padding:8px">Загрузка сотрудников…</div>';
      try {
        await loadEmployeeDirectory();
        renderEmployeeOptions(picker, search.value);
      } catch (error) {
        picker.querySelector(".employee-picker-options").innerHTML = `<div class="error" style="padding:8px">Справочник временно недоступен. Встречу можно отправить без организатора.<br>${esc(error.message)}</div>`;
      }
    });
    search.addEventListener("input", () => renderEmployeeOptions(picker, search.value));
  });
}

document.addEventListener("click", event => {
  if (event.target.closest("[data-employee-picker]")) return;
  document.querySelectorAll(".employee-picker-menu").forEach(menu => menu.classList.add("hidden"));
});

function resetEmployeePicker(form) {
  const picker = form.querySelector("[data-employee-picker]");
  if (picker) setEmployeePickerValue(picker, "");
}

const agendaSubmissions = new Map();
function agendaSubmissionKey(nodeId, botId, sessionId) {
  return JSON.stringify([nodeId, botId, sessionId]);
}
function agendaFormKey(form) {
  return agendaSubmissionKey(form.dataset.nodeId, form.dataset.botId, form.dataset.sessionId);
}
function agendaFormHtml(node, bot) {
  const key = agendaSubmissionKey(node.node_id, bot.bot_id, bot.session_id);
  const state = agendaSubmissions.get(key) || {};
  if (state.accepted) return `<div class="muted">Повестка уже принята. Повторная передача отключена.</div>`;
  return `<form class="agenda-form" data-node-id="${esc(node.node_id)}" data-bot-id="${esc(bot.bot_id)}" data-session-id="${esc(bot.session_id)}">
    <textarea name="raw_agenda" maxlength="20000" placeholder="Введите повестку. Например: обсудим бюджет 10 минут, затем план запуска." ${state.pending ? "readonly" : ""}>${esc(state.text || "")}</textarea>
    <button type="submit" ${state.pending ? "disabled" : ""}>${state.pending ? "Обработка повестки…" : "Добавить повестку"}</button>
    <div class="agenda-message message ${esc(state.css || "")}" role="status">${esc(state.message || "")}</div>
  </form>`;
}
function captureAgendaSubmissions(data) {
  for (const form of document.querySelectorAll('.agenda-form')) {
    const key = agendaFormKey(form);
    const state = agendaSubmissions.get(key) || {};
    if (!state.pending && !state.accepted) state.text = form.elements.raw_agenda.value;
    agendaSubmissions.set(key, state);
  }
  for (const node of data.nodes) {
    if (node.status !== 'online') continue;
    const live = new Set((node.bots || []).filter(b => b.status !== 'idle' && b.session_id)
      .map(b => agendaSubmissionKey(node.node_id, b.bot_id, b.session_id)));
    for (const key of agendaSubmissions.keys()) {
      if (JSON.parse(key)[0] === node.node_id && !live.has(key)) agendaSubmissions.delete(key);
    }
  }
}

function agendaInfo(bot) {
  const agenda = bot.agenda_status || {};
  const active = Boolean(agenda.agenda_active || agenda.enabled && agenda.status === "active");
  if (bot.status === "idle") {
    return { active: false, text: "Повестка не требуется", css: "muted" };
  }
  if (active) {
    const source = agenda.source ? `, источник: ${agenda.source}` : "";
    const count = agenda.items_count || agenda.total || 0;
    return { active: true, text: `Повестка активна: ${count} пункт(ов)${source}`, css: "ok" };
  }
  return { active: false, text: "Повестка отсутствует", css: "warn" };
}

function agendaEditingActive() {
  const form = document.activeElement?.closest?.(".agenda-form");
  return form && !agendaSubmissions.get(agendaFormKey(form))?.pending;
}

function ec2StateLabel(state) {
  return ({running: "VM включена", pending: "VM запускается", stopping: "VM выключается", stopped: "VM выключена", error: "Ошибка AWS", not_configured: "Управление не настроено"})[state] || state || "Состояние неизвестно";
}

function nodeStateLabel(node) {
  return ({machine_stopped: "VM выключена", machine_stopping: "VM выключается", machine_starting: "VM запускается"})[node.availability_reason]
    || node.status;
}

function unavailableBotMessage(node) {
  return ({machine_stopped: "Бот временно недоступен до включения AWS VM", machine_stopping: "AWS VM выключается", machine_starting: "Бот запускается вместе с AWS VM"})[node.availability_reason]
    || "Бот временно недоступен";
}

function machineAutomationInfo(machine) {
  const automation = machine.automation || {};
  if (!automation.enabled) return '<div class="message warn">Автоматическое управление выключено</div>';
  const evaluation = automation.last_evaluation || {};
  const reasons = {
    capacity_sufficient: "постоянной мощности достаточно",
    aws_capacity_still_required: "AWS-мощность всё ещё требуется",
    persistent_capacity_below_calendar_demand: "не хватает постоянных ботов",
    awaiting_second_stop_confirmation: "ожидается второе подтверждение выключения",
    manual_start_hold: "действует защита после ручного включения",
    minimum_uptime: "не истекло минимальное время работы",
    action_cooldown: "защитная пауза между командами",
    calendar_stale: "календарные данные устарели",
    aws_bots_not_idle: "AWS-боты заняты или их состояние неизвестно",
    machine_not_stable: "ВМ находится в переходном состоянии",
    machine_transition_or_action_cooldown: "ожидание завершения операции AWS",
    final_safety_recheck_failed: "контрольная проверка запретила выключение",
  };
  const decision = ({start: "включение", stop: "выключение", wait: "ожидание", blocked: "защитная блокировка", none: "без действия"})[evaluation.decision]
    || "ожидание первого цикла";
  const detail = evaluation.checked_at
    ? `Встречи: ${esc(evaluation.maximum_concurrent_meetings ?? "—")} · свободны постоянные боты: ${esc(evaluation.free_persistent_bots ?? "—")} · требуется с резервом: ${esc(evaluation.required_capacity ?? "—")}`
    : "Первый цикл выполняется";
  const confirmation = Number(automation.stop_confirmations || 0) > 0
    ? ` · подтверждение выключения ${esc(automation.stop_confirmations)}/${esc(automation.stop_confirmations_required)}`
    : "";
  return `<div class="message muted"><strong>Автоматика:</strong> ${esc(decision)} — ${esc(reasons[evaluation.reason] || evaluation.reason || "нет данных")}${confirmation}<br>${detail}</div>`;
}

function machineControls(machine) {
  if (!machine.control_configured) {
    return `<div class="message warn">${esc(machine.ec2_error || "Управление EC2 не настроено")}</div>`;
  }
  const state = machine.ec2_state;
  const transition = state === "pending" || state === "stopping";
  const canStart = state === "stopped";
  const allBotsKnownIdle = Number(machine.nodes_online || 0) === Number(machine.nodes_total || 0)
    && Number(machine.bots_idle || 0) >= Number(machine.bots_capacity || 0);
  const canStop = state === "running" && Number(machine.bots_busy || 0) === 0 && allBotsKnownIdle;
  const busyHint = state === "running" && Number(machine.bots_busy || 0) > 0
    ? "Выключение заблокировано: есть активная встреча"
    : state === "running" && !allBotsKnownIdle
      ? "Выключение заблокировано: не все AWS-боты подтвердили состояние ожидания"
      : "";
  return `
    <div class="machine-actions">
      <div class="message ${machine.ec2_error ? "error" : "muted"}" data-machine-message>${esc(machine.ec2_error || busyHint)}</div>
      ${canStart ? '<button type="button" data-aws-action="start">Включить AWS VM</button>' : ""}
      ${state === "running" ? `<button type="button" class="danger" data-aws-action="stop" ${canStop ? "" : "disabled"}>Выключить AWS VM</button>` : ""}
      ${transition ? '<button type="button" disabled>Операция выполняется…</button>' : ""}
    </div>`;
}

const meetingExitRequests = new Map();
function meetingExitKey(nodeId, botId, sessionId) {
  return JSON.stringify([nodeId, botId, sessionId]);
}
function meetingExitControl(node, bot) {
  if (bot.status === "idle" || bot.status === "unavailable" || bot.configured_placeholder || !bot.session_id) return "";
  const state = meetingExitRequests.get(meetingExitKey(node.node_id, bot.bot_id, bot.session_id));
  return `<div style="margin-top:10px"><button type="button" class="danger" data-meeting-exit
    data-node-id="${esc(node.node_id)}" data-bot-id="${esc(bot.bot_id)}" data-session-id="${esc(bot.session_id)}"
    ${state?.pending ? "disabled" : ""}>${state?.pending ? "Выход запрошен…" : "Выйти со встречи"}</button>
    <div class="message ${state?.error ? "error" : "muted"}">${esc(state?.error || (state?.pending ? "Бот завершает участие и сохраняет запись" : ""))}</div></div>`;
}
async function leaveMeeting(button) {
  const {nodeId, botId, sessionId} = button.dataset;
  const key = meetingExitKey(nodeId, botId, sessionId);
  if (meetingExitRequests.get(key)?.pending) return;
  meetingExitRequests.set(key, {pending: true});
  button.disabled = true;
  button.textContent = "Выход запрошен…";
  try {
    const response = await fetch(`/api/v1/nodes/${encodeURIComponent(nodeId)}/bots/${encodeURIComponent(botId)}/leave`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({session_id: sessionId})
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`);
  } catch (error) {
    meetingExitRequests.set(key, {pending: false, error: error.message});
    button.disabled = false;
  }
  await refresh(true);
}

function participantMetricsInfo(bot) {
  const metrics = bot.participant_metrics || {};
  if (bot.status === "idle") {
    return {text: "не на встрече", css: "muted", details: ""};
  }
  const count = metrics.other_participants_count;
  if (metrics.valid && Number.isInteger(Number(count))) {
    const age = Number(metrics.last_valid_age_seconds);
    const details = Number.isFinite(age) ? ` · ${Math.max(0, age)} сек. назад` : "";
    return {
      text: `${Number(count)} чел. (без бота)`,
      css: "ok",
      details,
    };
  }
  if (count !== null && count !== undefined) {
    return {
      text: `${Number(count)} (последнее известное значение)`,
      css: "warn",
      details: metrics.error ? ` · ${metrics.error}` : "",
    };
  }
  return {
    text: metrics.status === "starting" ? "определяется…" : "данные недоступны",
    css: "warn",
    details: metrics.error ? ` · ${metrics.error}` : "",
  };
}

function audioActivityInfo(bot) {
  if (bot.status === "idle" || bot.status === "unavailable" || bot.configured_placeholder) return "";
  if (!bot.participant_metrics?.single_participant?.monitoring_active) return "";
  const state = bot.participant_metrics?.audio_activity;
  if (!state) return `<div class="muted">Накопление аудио: метрики пока недоступны</div>`;
  const formatDuration = value => {
    const seconds = Math.max(0, Math.floor(Number(value) || 0));
    return `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  };
  const duration = formatDuration(state.accumulated_seconds);
  const silence = formatDuration(state.silence_seconds);
  const percent = state.silence_percent == null ? "—" : `${state.silence_percent}%`;
  let details = "";
  if (state.status === "waiting_threshold") details = `начнётся после ${state.start_after_minutes} мин с одним участником`;
  else if (state.status === "waiting_monitor") details = "ожидание сервиса мониторинга";
  else if (state.status === "not_single_participant") details = "ожидание одного участника";
  else if (state.status === "waiting_audio") details = "ожидание аудиотелеметрии";
  else if (state.status === "stale") details = "пауза: нет достоверных аудиоданных";
  else details = state.currently_speaking == null ? "звуковая активность неизвестна" : (state.currently_speaking ? "сейчас звук" : "сейчас тишина");
  if (state.monitor_error) details = state.monitor_error;
  return `<div class="audio-activity-info" style="margin-top:10px"><strong>Накоплено аудио: ${esc(duration)}</strong><div>Время тишины: ${esc(silence)} · Доля тишины: ${esc(percent)}</div><div class="muted">${esc(details)}</div><div class="muted">Доля за весь период накопления · обновление ≈ 5 сек</div></div>`;
}

function singleParticipantAlert(bot) {
  return bot.status !== "idle" && bot.status !== "unavailable" && !bot.configured_placeholder
    && Boolean(bot.participant_metrics?.single_participant?.alert);
}
function singleParticipantInfo(bot) {
  const state = bot.participant_metrics?.single_participant;
  if (!state?.monitoring_active || bot.status === "idle" || bot.status === "unavailable") return "";
  const seconds = Number(state.monitoring_elapsed_seconds || 0);
  const duration = `${String(Math.floor(seconds / 3600)).padStart(2, "0")}:${String(Math.floor(seconds / 60) % 60).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
  return `<div class="${singleParticipantAlert(bot) ? "single-participant-warning" : "muted"}" role="status">${singleParticipantAlert(bot) ? "! " : ""}Мониторинг одного участника: ${esc(duration)}${state.enabled ? ` · оповещение через ${esc(state.threshold_minutes)} мин` : ""}</div>`;
}

function render(data) {
  captureAgendaSubmissions(data);
  const alertCount = data.nodes.reduce((total, node) => total + (node.bots || []).filter(singleParticipantAlert).length, 0);
  const poolNav = document.getElementById("bots-nav-button");
  poolNav.classList.toggle("session-alert", alertCount > 0);
  poolNav.title = alertCount ? `Встреч с одним участником дольше порога мониторинга: ${alertCount}` : "";
  const focusedBotField = captureBotFormDrafts();
  document.getElementById("nodes-total").textContent = data.summary.nodes_total;
  document.getElementById("bots-total").textContent = data.summary.bots_total;
  document.getElementById("bots-idle").textContent = data.summary.bots_idle;
  document.getElementById("bots-busy").textContent = data.summary.bots_busy;
  updatedEl.textContent = `Обновлено: ${new Date().toLocaleTimeString("ru-RU")}`;

  const machines = data.on_demand_machines || [];
  latestOnDemandMachines = machines;
  onDemandMachinesEl.classList.toggle("hidden", machines.length === 0);
  onDemandMachinesEl.innerHTML = machines.map(machine => `
    <article class="on-demand-machine ${esc(machine.status)}">
      <div class="node-head">
        <div>
          <div class="node-title">${esc(machine.machine_name)} <span class="on-demand-mark">НЕПОСТОЯННАЯ VM</span></div>
          <div class="muted">${esc(machine.provider || "Облачный узел")} · ${esc(machine.public_ip || "IP не указан")}</div>
        </div>
        <span class="badge ${machine.status === "online" ? "" : "busy"}">${esc(ec2StateLabel(machine.ec2_state))}</span>
      </div>
      <div class="on-demand-machine-grid">
        <div><span class="muted">Узлы онлайн</span><strong>${esc(machine.nodes_online)} / ${esc(machine.nodes_total)}</strong></div>
        <div><span class="muted">Ботов</span><strong>${esc(machine.bots_capacity)}</strong></div>
        <div><span class="muted">Свободны</span><strong>${esc(machine.bots_idle)}</strong></div>
        <div><span class="muted">Заняты</span><strong>${esc(machine.bots_busy)}</strong></div>
      </div>
      ${machineAutomationInfo(machine)}
      ${machineControls(machine)}
    </article>
  `).join("");

  nodesEl.innerHTML = data.nodes.map(node => `
    <article class="node ${node.status} ${node.configured_node?.lifecycle === "on_demand" ? "on-demand" : ""}">
      <div class="node-head">
        <div>
          <div class="node-title">${esc(node.node_name)} <span class="muted">(${esc(node.node_id)})</span>${node.configured_node?.lifecycle === "on_demand" ? '<span class="on-demand-mark">НЕПОСТОЯННАЯ VM</span>' : ""}</div>
          <div class="muted">${esc(node.base_url || "")}</div>
          ${node.error ? `<div class="message error">${esc(node.error)}</div>` : ""}
        </div>
        <div class="badge ${node.status === "online" ? "" : "unavailable"}">${esc(nodeStateLabel(node))}</div>
      </div>
      <div class="bots">
        ${(node.bots || []).map(bot => {
          const agenda = agendaInfo(bot);
          const participants = participantMetricsInfo(bot);
          const unavailable = Boolean(bot.configured_placeholder || bot.status === "unavailable");
          return `
          <div class="bot ${bot.status} ${node.configured_node?.lifecycle === "on_demand" ? "on-demand" : ""} ${singleParticipantAlert(bot) ? "single-participant-alert" : ""}">
            <strong>${esc(bot.global_bot_id || bot.bot_id)}</strong>
            <span class="badge ${bot.status}">${unavailable ? esc(nodeStateLabel(node)) : esc(bot.status)}</span>
            ${node.configured_node?.lifecycle === "on_demand" ? '<span class="on-demand-mark">AWS</span>' : ""}
            <div class="row">
              ${unavailable ? `<span class="muted">Состояние</span><span class="warn">${esc(unavailableBotMessage(node))}</span>` : `
              <span class="muted">Встреча</span><span>${esc(bot.title || bot.session_id || "-")}</span>
              <span class="muted">Ссылка</span><span>${esc(bot.meeting_url || "-")}</span>
              <span class="muted">Старт</span><span>${esc(bot.started_at || "-")}</span>
              <span class="muted">Участники сейчас</span><span class="${participants.css}">${esc(participants.text)}${esc(participants.details)}</span>
              <span class="muted">Повестка</span><span class="${agenda.css}">${esc(agenda.text)}</span>
              `}
            </div>
            ${singleParticipantInfo(bot)}
            ${audioActivityInfo(bot)}
            ${meetingExitControl(node, bot)}
            ${!unavailable && bot.status !== "idle" ? `
              <div class="agenda-box">
                ${agenda.active ? `<div class="muted">Новая повестка через дашборд не принимается: первая корректная повестка уже зафиксирована.</div>` : `
                  ${agendaFormHtml(node, bot)}
                `}
              </div>
            ` : ""}
            ${!unavailable && bot.status === "idle" ? `
              <form class="bot-form" data-node-id="${esc(node.node_id)}" data-bot-id="${esc(bot.bot_id)}">
                <div class="row" style="grid-template-columns:1fr; margin-top:10px;">
                  <input name="meeting_url" type="url" placeholder="Ссылка на встречу" required>
                  <input name="title" type="text" placeholder="Название, необязательно">
                  ${employeePickerHtml()}
                  <textarea name="agenda" placeholder="Повестка, необязательно"></textarea>
                  <textarea name="expected_participants" placeholder="Участники, необязательно"></textarea>
                  <button type="submit">Запустить на этом боте</button>
                  <div class="message"></div>
                </div>
              </form>
            ` : ""}
          </div>`;
        }).join("")}
      </div>
    </article>
  `).join("");

  for (const form of document.querySelectorAll(".bot-form")) {
    form.addEventListener("submit", submitSpecific);
  }
  for (const button of nodesEl.querySelectorAll("[data-meeting-exit]")) {
    button.addEventListener("click", () => leaveMeeting(button));
  }
  restoreBotFormDrafts(focusedBotField);
  setupEmployeePickers(nodesEl);
  for (const form of document.querySelectorAll(".agenda-form")) {
    form.addEventListener("submit", submitAgenda);
  }
  if (latestSessionState) renderSessionState(latestSessionState);
}

async function refresh(force = false) {
  if (!force && agendaEditingActive()) return;
  try {
    const resp = await fetch("/api/v1/nodes/status", { cache: "no-store" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    render(await resp.json());
  } catch (e) {
    updatedEl.textContent = `Ошибка обновления: ${e.message}`;
  }
}

async function controlAwsMachine(action, button) {
  const awsBotCapacity = latestOnDemandMachines[0]?.bots_capacity || 0;
  if (action === "stop" && !confirm(`Выключить AWS VM? Все ${awsBotCapacity} AWS-ботов станут временно недоступны.`)) return;
  const card = button.closest(".on-demand-machine");
  const message = card?.querySelector("[data-machine-message]");
  button.disabled = true;
  if (message) {
    message.className = "message muted";
    message.textContent = action === "start" ? "Отправляю команду включения…" : "Проверяю ботов и отправляю команду выключения…";
  }
  try {
    const response = await fetch(`/api/v1/aws-machine/${action}`, {method: "POST"});
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    if (message) message.textContent = `Команда принята: ${ec2StateLabel(payload.ec2_state)}`;
    await refresh(true);
  } catch (error) {
    if (message) {
      message.className = "message error";
      message.textContent = error.message;
    }
    button.disabled = false;
  }
}

function payloadFrom(form) {
  const data = new FormData(form);
  return {
    meeting_url: String(data.get("meeting_url") || "").trim(),
    title: String(data.get("title") || "").trim() || null,
    agenda: String(data.get("agenda") || "").trim() || null,
    expected_participants: String(data.get("expected_participants") || "").trim() || null,
    organizer: String(data.get("organizer") || "").trim().toLowerCase() || null,
    source: "control_service"
  };
}

function cohostResultText(cohost) {
  if (!cohost || cohost.status === "skipped") return "Организатор не выбран — бот останется без прав соорганизатора.";
  if (cohost.status === "completed") return cohost.reason === "already_cohost" ? "Бот уже является соорганизатором." : "Бот назначен соорганизатором.";
  if (cohost.status === "failed") return `Не удалось назначить бота соорганизатором: ${cohost.reason || "встреча не найдена у выбранного организатора"}.`;
  return `Назначение соорганизатора: ${cohost.status || "состояние неизвестно"}.`;
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

function personLabel(person) {
  if (!person) return "—";
  const name = String(person.name || "").trim();
  const email = String(person.email || "").trim();
  return name && email ? `${name} — ${email}` : name || email || "—";
}

const elmaStatusLabels = {
  received: "сохранено, не поставлено в очередь",
  pending: "ожидает отправки",
  sending: "отправляется",
  retrying: "ожидает повтора",
  sent: "отправлено в ELMA",
  failed_user_resolution: "email не найден в ELMA",
  missing_due_date: "не указан срок",
  failed: "ошибка отправки",
  processing: "обрабатывается",
  partial_failed: "отправлено частично",
};

function elmaStatusBadge(status) {
  const value = status || "received";
  const bad = ["failed", "failed_user_resolution", "missing_due_date", "partial_failed"].includes(value);
  const active = ["pending", "sending", "retrying", "processing"].includes(value);
  return `<span class="badge ${bad ? "fail" : active ? "busy" : ""}">${esc(elmaStatusLabels[value] || value)}</span>`;
}

async function loadAssignments() {
  assignmentsMessage.className = "message";
  assignmentsMessage.textContent = "Загрузка полученных поручений...";
  try {
    const response = await fetch("/api/v1/assignments/meetings?limit=1000", {cache: "no-store"});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
    const meetings = data.meetings || [];
    assignmentsMeetingsBody.innerHTML = meetings.map(meeting => `
      <tr>
        <td>${esc(formatDateTime(meeting.meeting_date))}</td>
        <td><strong>${esc(meeting.meeting_title)}</strong><div class="muted">${esc(meeting.meeting_id)}</div></td>
        <td>${esc(personLabel(meeting.organizer))}</td>
        <td>${esc(formatDateTime(meeting.received_at))}</td>
        <td>${esc(meeting.questions_count || 0)}</td>
        <td>${esc(meeting.assignments_count || 0)}</td>
        <td>${elmaStatusBadge(meeting.processing_status)}</td>
        <td><button type="button" data-assignment-request-id="${esc(meeting.request_id)}">Поручения</button></td>
      </tr>`).join("") || '<tr><td colspan="8" class="muted">Поручения пока не поступали.</td></tr>';
    assignmentsMessage.textContent = `Встреч с сохранёнными поручениями: ${meetings.length}.`;
  } catch (error) {
    assignmentsMessage.className = "message error";
    assignmentsMessage.textContent = error.message;
  }
}

async function showAssignmentDetails(requestId) {
  assignmentDetailsPanel.classList.remove("hidden");
  assignmentDetails.innerHTML = '<div class="muted">Загрузка...</div>';
  try {
    const response = await fetch(`/api/v1/assignments/meetings/${encodeURIComponent(requestId)}`, {cache: "no-store"});
    const meeting = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof meeting.detail === "string" ? meeting.detail : `HTTP ${response.status}`);
    document.getElementById("assignment-details-title").textContent = meeting.meeting_title || "Поручения встречи";
    document.getElementById("assignment-details-meta").innerHTML = `${esc(formatDateTime(meeting.meeting_date))} · ${esc(personLabel(meeting.organizer))} · <a href="${esc(meeting.protocol_url)}" target="_blank" rel="noopener">Протокол</a>`;
    assignmentDetails.innerHTML = (meeting.questions || []).map(question => `
      <article class="assignment-question">
        <strong>Вопрос ${esc(question.question_number)}. ${esc(question.question)}</strong>
        ${(question.assignments || []).map(assignment => `
          <div class="assignment-card status-${esc(assignment.elma_status || "received")}">
            <p><strong>${esc(assignment.text)}</strong></p>
            ${assignment.description ? `<p>${esc(assignment.description)}</p>` : ""}
            <p><span class="muted">Срок:</span> ${esc(assignment.due_date || "не указан")}</p>
            <p><span class="muted">Исполнители:</span> ${esc((assignment.assignees || []).map(personLabel).join(", ") || "—")}</p>
            <p><span class="muted">Поручил:</span> ${esc(personLabel(assignment.given_by))}</p>
            <p><span class="muted">ELMA:</span> ${elmaStatusBadge(assignment.elma_status)}</p>
            ${assignment.elma_object_id ? `<p><span class="muted">ELMA ID:</span> ${esc(assignment.elma_object_id)}</p>` : ""}
            <p><span class="muted">Попыток:</span> ${esc(assignment.elma_attempts || 0)}</p>
            ${assignment.elma_sent_at ? `<p><span class="muted">Отправлено:</span> ${esc(formatDateTime(assignment.elma_sent_at))}</p>` : ""}
            ${assignment.elma_next_retry_at ? `<p><span class="muted">Следующая попытка:</span> ${esc(formatDateTime(assignment.elma_next_retry_at))}</p>` : ""}
            ${assignment.elma_last_error ? `<div class="message error">${esc(assignment.elma_last_error)}</div>` : ""}
            <div class="muted">ID: ${esc(assignment.assignment_id)}</div>
            ${["failed", "failed_user_resolution", "missing_due_date"].includes(assignment.elma_status) ? `<button type="button" data-elma-retry="${esc(assignment.assignment_id)}">Повторить отправку</button>` : ""}
          </div>`).join("")}
      </article>`).join("") || '<div class="muted">В этой встрече нет поручений.</div>';
    assignmentDetailsPanel.scrollIntoView({behavior: "smooth", block: "start"});
  } catch (error) {
    assignmentDetails.innerHTML = `<div class="message error">${esc(error.message)}</div>`;
  }
}

async function retryElmaAssignment(assignmentId) {
  const response = await fetch(`/api/v1/assignments/${encodeURIComponent(assignmentId)}/retry`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: "{}",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${response.status}`);
  await loadAssignments();
  return data;
}

const sessionStatusLabels = {
  unknown: "не проверялась",
  valid: "валидна",
  restored: "обновлена",
  session_file_missing: "файл сессии отсутствует",
  session_file_invalid: "файл сессии повреждён",
  awaiting_confirmation: "ожидается код",
  confirmation_interrupted: "подтверждение прервано",
  invalid_credentials_not_configured: "нет учётных данных",
  login_form_not_ready: "форма входа недоступна",
  wrong_account_or_unexpected_page: "невалидна",
  saved_session_validation_failed: "проверка не пройдена",
  network_or_page_error: "ошибка проверки",
  confirmation_rejected_or_expired: "код отклонён"
};

function sessionIsAlert(state) {
  return !["unknown", "valid", "restored"].includes(state.status || "unknown");
}

function formatSessionDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU", {
    timeZone: "Europe/Astrakhan",
    dateStyle: "short",
    timeStyle: "medium"
  });
}

function renderSessionState(state) {
  latestSessionState = state;
  const status = state.status || "unknown";
  const alert = sessionIsAlert(state);
  sessionNavButton.classList.toggle("session-alert", alert);
  const statusElement = document.getElementById("session-status");
  statusElement.textContent = sessionStatusLabels[status] || status;
  statusElement.className = alert ? "bad" : (status === "unknown" ? "muted" : "ok");
  document.getElementById("session-last-checked").textContent = formatSessionDateTime(state.last_checked_at);
  document.getElementById("session-last-authenticated").textContent = formatSessionDateTime(state.last_authenticated_at);
  document.getElementById("session-last-updated").textContent = formatSessionDateTime(state.last_session_updated_at);
  document.getElementById("session-last-delivered").textContent = formatSessionDateTime(state.last_delivered_at);
  sessionAutoEnabled.checked = Boolean(state.automatic_check_enabled);
  if (document.activeElement !== sessionAutoInterval) {
    sessionAutoInterval.value = state.automatic_check_interval_seconds || 60;
  }
  const automaticMode = document.getElementById("session-auto-mode");
  automaticMode.textContent = state.automatic_check_enabled ? "автопроверка включена" : "автопроверка выключена";
  automaticMode.className = `badge ${state.automatic_check_enabled ? "" : "busy"}`;
  document.getElementById("session-next-check").textContent = state.automatic_check_enabled
    ? `Следующая проверка: ${formatSessionDateTime(state.next_automatic_check_at)}`
    : "Следующая проверка: приостановлена";
  const delivery = document.getElementById("session-delivery-status");
  delivery.textContent = state.delivery_status === "delivered" ? "доставлено" : (state.delivery_status === "failed" ? "ошибка доставки" : "ещё не отправлялась");
  delivery.className = `badge ${state.delivery_status === "failed" ? "busy" : ""}`;
  const targets = state.targets || [];
  document.getElementById("session-targets").innerHTML = targets.map(target => {
    const awsTarget = String(target.target_id || "").startsWith("telemost-aws-");
    const awsMachine = latestOnDemandMachines.find(machine => machine.machine_id === "telemost-aws-1");
    const waiting = target.status === "skipped_unavailable" || (awsTarget && awsMachine && awsMachine.status !== "online");
    const statusText = waiting ? "ожидает включения" : (target.status || "настроен");
    const statusClass = target.status === "delivered" ? "ok" : (waiting ? "warn" : (target.status ? "bad" : "muted"));
    const awsMark = String(target.target_id || "").startsWith("telemost-aws-")
      ? '<span class="on-demand-mark">НЕПОСТОЯННАЯ VM</span>'
      : "";
    return `
      <div class="organizer-item">
        <div>
          <strong>ВМ №${esc(target.vm_number || "—")} · ${esc(target.ip_address || "IP не указан")}</strong>${awsMark}
          <div class="muted">${esc(target.bot_id || target.target_id || "бот не указан")}</div>
        </div>
        <span class="${statusClass}">${esc(statusText)}</span>
      </div>`;
  }).join("") || '<div class="muted">Получатели пока не настроены.</div>';
  const otpWasHidden = sessionOtpPanel.classList.contains("hidden");
  sessionOtpPanel.classList.toggle("hidden", !state.awaiting_confirmation);
  if (state.awaiting_confirmation && otpWasHidden) sessionOtpInputs[0].focus();
  sessionMessage.className = `message ${alert ? "error" : ""}`;
  sessionMessage.textContent = state.error || (state.awaiting_confirmation
    ? "Авторизация остановлена на этапе подтверждения. Введите одноразовый код."
    : "Отображается результат последней проверки сессии.");
}

async function loadSessionState() {
  try {
    const response = await fetch("/api/v1/session-state", { cache: "no-store" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderSessionState(data);
  } catch (error) {
    sessionNavButton.classList.add("session-alert");
    sessionMessage.className = "message error";
    sessionMessage.textContent = error.message;
  }
}

async function runSessionCheck() {
  sessionCheckButton.disabled = true;
  sessionMessage.className = "message";
  sessionMessage.textContent = "Проверяю сессию и при необходимости выполняю авторизацию...";
  try {
    const response = await fetch("/api/v1/session-state/check", { method: "POST" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    await loadSessionState();
  } catch (error) {
    sessionMessage.className = "message error";
    sessionMessage.textContent = error.message;
  } finally {
    sessionCheckButton.disabled = false;
  }
}

async function configureAutomaticSessionCheck(event) {
  event.preventDefault();
  const interval = Number(sessionAutoInterval.value);
  if (!Number.isInteger(interval) || interval < 10 || interval > 86400) {
    sessionMessage.className = "message error";
    sessionMessage.textContent = "Интервал должен быть целым числом от 10 до 86400 секунд.";
    return;
  }
  const button = document.getElementById("session-auto-save");
  button.disabled = true;
  try {
    const response = await fetch("/api/v1/session-state/automatic-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: sessionAutoEnabled.checked, interval_seconds: interval })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderSessionState(data);
    sessionMessage.className = "message";
    sessionMessage.textContent = sessionAutoEnabled.checked
      ? `Автоматическая проверка включена с интервалом ${interval} секунд.`
      : "Автоматическая проверка приостановлена. Ручная проверка остаётся доступной.";
  } catch (error) {
    sessionMessage.className = "message error";
    sessionMessage.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function submitSessionCode(event) {
  event.preventDefault();
  const code = sessionOtpInputs.map(input => input.value).join("");
  if (!/^[0-9]{6}$/.test(code)) {
    sessionMessage.className = "message error";
    sessionMessage.textContent = "Введите все шесть цифр одноразового кода.";
    return;
  }
  const button = document.getElementById("session-confirm-button");
  button.disabled = true;
  try {
    const response = await fetch("/api/v1/session-state/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    sessionOtpInputs.forEach(input => { input.value = ""; });
    await loadSessionState();
  } catch (error) {
    sessionMessage.className = "message error";
    sessionMessage.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

sessionOtpInputs.forEach((input, index) => {
  input.addEventListener("input", () => {
    input.value = input.value.replace(/[^0-9]/g, "").slice(-1);
    if (input.value && index < sessionOtpInputs.length - 1) sessionOtpInputs[index + 1].focus();
  });
  input.addEventListener("keydown", event => {
    if (event.key === "Backspace" && !input.value && index > 0) sessionOtpInputs[index - 1].focus();
  });
  input.addEventListener("paste", event => {
    const digits = event.clipboardData.getData("text").replace(/[^0-9]/g, "").slice(0, 6);
    if (!digits) return;
    event.preventDefault();
    sessionOtpInputs.forEach((item, digitIndex) => { item.value = digits[digitIndex] || ""; });
    sessionOtpInputs[Math.min(digits.length, 6) - 1].focus();
  });
});

function formatDuration(seconds) {
  const value = Math.max(0, Number(seconds || 0));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const rest = Math.floor(value % 60);
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function formatPercent(value) {
  return value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}%`;
}

function renderDailyEmpty(data) {
  const current = data.current_day || {};
  document.getElementById("daily-empty-checked").textContent = current.checked_meetings || 0;
  document.getElementById("daily-empty-count").textContent = current.empty_meetings || 0;
  document.getElementById("daily-empty-percent").textContent = formatPercent(current.empty_percentage);
  const change = data.change_from_previous_day_percentage_points;
  document.getElementById("daily-empty-change").textContent = change === null || change === undefined
    ? "—"
    : `${change > 0 ? "+" : ""}${Number(change).toFixed(1)} п.п.`;
  document.getElementById("daily-empty-average-7").textContent = formatPercent(data.average_daily_empty_percentage_7_days);
  document.getElementById("daily-empty-average-30").textContent = formatPercent(data.average_daily_empty_percentage_30_days);
  const daily = data.daily || [];
  document.getElementById("daily-empty-chart").innerHTML = daily.map(item => {
    const value = item.empty_percentage;
    const hasData = value !== null && value !== undefined;
    const height = hasData ? Math.max(2, Math.min(100, Number(value))) : 2;
    const date = new Date(`${item.meeting_date}T00:00:00`);
    const label = date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
    const title = hasData
      ? `${label}: ${Number(value).toFixed(1)}% (${item.empty_meetings}/${item.checked_meetings})`
      : `${label}: нет проверенных встреч`;
    return `<div class="empty-chart-day" title="${esc(title)}"><div class="empty-chart-bar ${hasData ? "" : "no-data"}" style="height:${height}%"></div><span class="empty-chart-label">${esc(label)}</span></div>`;
  }).join("");
}

function analyticsParams(includeOrganizer = true) {
  const params = new URLSearchParams();
  const from = document.getElementById("analytics-date-from").value;
  const to = document.getElementById("analytics-date-to").value;
  const organizer = document.getElementById("analytics-organizer").value.trim();
  const agenda = document.getElementById("analytics-agenda").value;
  const emptyStatus = document.getElementById("analytics-empty").value;
  const folderExists = document.getElementById("analytics-folder").value;
  if (from) params.set("date_from", from);
  if (to) params.set("date_to", to);
  if (includeOrganizer && organizer) params.set("organizer", organizer);
  if (includeOrganizer && agenda) params.set("agenda_present", agenda);
  if (includeOrganizer && emptyStatus) params.set("disk_empty_status", emptyStatus);
  if (includeOrganizer && folderExists) params.set("disk_folder_exists", folderExists);
  return params;
}

async function loadAnalytics(runCollector = false) {
  analyticsMessage.className = "message";
  analyticsMessage.textContent = runCollector ? "Собираю задачи bot-node и проверяю Яндекс Диск..." : "Загрузка аналитики...";
  try {
    if (runCollector) {
      const refreshResponse = await fetch("/api/v1/analytics/refresh", { method: "POST" });
      const refreshData = await refreshResponse.json().catch(() => ({}));
      if (!refreshResponse.ok) throw new Error(refreshData.detail || `HTTP ${refreshResponse.status}`);
    }
    const summaryParams = analyticsParams(false);
    const meetingParams = analyticsParams(true);
    const [summaryResponse, meetingsResponse, dailyResponse] = await Promise.all([
      fetch(`/api/v1/analytics/summary?${summaryParams}`, { cache: "no-store" }),
      fetch(`/api/v1/analytics/meetings?${meetingParams}`, { cache: "no-store" }),
      fetch("/api/v1/analytics/daily-empty?days=30", { cache: "no-store" })
    ]);
    const summary = await summaryResponse.json().catch(() => ({}));
    const meetingsData = await meetingsResponse.json().catch(() => ({}));
    const dailyData = await dailyResponse.json().catch(() => ({}));
    if (!summaryResponse.ok) throw new Error(summary.detail || `HTTP ${summaryResponse.status}`);
    if (!meetingsResponse.ok) throw new Error(meetingsData.detail || `HTTP ${meetingsResponse.status}`);
    if (!dailyResponse.ok) throw new Error(dailyData.detail || `HTTP ${dailyResponse.status}`);

    document.getElementById("analytics-total").textContent = summary.total_meetings || 0;
    document.getElementById("analytics-average").textContent = formatDuration(summary.average_actual_duration_seconds);
    document.getElementById("analytics-agenda-count").textContent = summary.agenda_meetings || 0;
    document.getElementById("analytics-agenda-percent").textContent = `${summary.agenda_percentage || 0}%`;
    document.getElementById("analytics-empty-count").textContent = summary.empty_meetings || 0;
    renderDailyEmpty(dailyData);
    const organizers = summary.top_organizers || [];
    document.getElementById("analytics-organizers").innerHTML = organizers.map(item => `
      <div class="organizer-item"><div><strong>${esc(item.organizer_name || item.organizer_email || "Не указан")}</strong><div class="muted">${esc(item.organizer_email || "")}</div></div><strong>${esc(item.meetings_count || 0)}</strong></div>
    `).join("") || '<div class="muted">Организаторы пока не найдены.</div>';

    const meetings = meetingsData.meetings || [];
    analyticsMeetingsBody.innerHTML = meetings.map(meeting => {
      const agenda = meeting.agenda_present
        ? `<span class="ok">есть · ${esc(meeting.agenda_items_count || 0)} пункт(ов)</span><div class="muted">${esc(meeting.agenda_source || "")}</div>`
        : '<span class="muted">нет</span>';
      const emptyLabels = {
        empty: '<span class="warn">пустая</span>',
        not_empty: '<span class="ok">не пустая</span>',
        folder_not_found: '<span class="error">папка не найдена</span>',
        scan_missed: '<span class="muted">проверка не выполнялась</span>',
        unknown: '<span class="muted">ожидает проверки</span>'
      };
      const emptyState = emptyLabels[meeting.disk_empty_status] || emptyLabels.unknown;
      const folderState = meeting.disk_folder_exists === true
        ? `<span class="ok" title="${esc(meeting.disk_folder_path || "")}">папка есть</span>`
        : meeting.disk_folder_exists === false
          ? '<span class="error">папки нет</span>'
          : '<span class="muted">—</span>';
      const folderChecked = meeting.disk_checked_at
        ? `<div class="muted">проверено ${esc(formatDateTime(meeting.disk_checked_at))}</div>`
        : "";
      return `<tr><td>${esc(formatDateTime(meeting.actual_start_at))}<div class="muted">до ${esc(formatDateTime(meeting.actual_end_at))}</div></td><td><strong>${esc(meeting.title || "Без названия")}</strong></td><td>${esc(meeting.organizer_name || "—")}<div class="muted">${esc(meeting.organizer_email || "")}</div></td><td><strong>${esc(formatDuration(meeting.actual_duration_seconds))}</strong></td><td>${agenda}</td><td>${emptyState}<div class="muted">${esc(meeting.disk_checked_at ? `проверено ${formatDateTime(meeting.disk_checked_at)}` : "")}</div></td><td>${esc([meeting.node_id, meeting.bot_id].filter(Boolean).join(":") || "—")}</td><td>${folderState}${folderChecked}</td></tr>`;
    }).join("") || '<tr><td colspan="8" class="muted">За выбранный период завершённых встреч нет.</td></tr>';
    analyticsMessage.textContent = `Показано встреч: ${meetings.length}. Все расчёты выполнены по фактическому времени бота.`;
  } catch (error) {
    analyticsMessage.className = "message error";
    analyticsMessage.textContent = error.message;
  }
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
  calendarMessage.className = "message";
  calendarMessage.textContent = `Проверено: ${formatDateTime(data.checked_at)}. Диапазон: ${formatDateTime(data.range.start)} - ${formatDateTime(data.range.end)}.`;
  if (!data.events.length) {
    calendarEventsBody.innerHTML = '<tr><td colspan="6" class="muted">Событий за выбранный период не найдено.</td></tr>';
    return;
  }
  calendarEventsBody.innerHTML = data.events.map(event => `
    <tr>
      <td>${esc(formatDateTime(event.starts_at))}</td>
      <td>${esc(event.title || "-")}</td>
      <td>${esc(event.calendar_source || "-")}</td>
      <td>${event.meeting_url ? `<a href="${esc(event.meeting_url)}" target="_blank" rel="noreferrer">${esc(event.meeting_url)}</a>` : '<span class="muted">-</span>'}</td>
      <td class="participants-cell">${renderParticipants(event)}</td>
      <td>${event.has_telemost_url ? '<span class="ok">готово</span>' : '<span class="warn">нет ссылки</span>'}</td>
    </tr>
  `).join("");
}

function statusLabel(status) {
  const labels = {upcoming: "ожидает", due: "пора запускать", missed_candidate: "проверка пропуска", dispatching: "запускается", dispatched: "запущено", failed: "ошибка", past_no_link: "прошло без ссылки"};
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
    calendarControlBody.innerHTML = '<tr><td colspan="7" class="muted">В локальном списке пока нет ближайших встреч.</td></tr>';
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
      <td>${event.error ? `<span class="bad">${esc(event.error)}</span>` : '<span class="muted">-</span>'}</td>
    </tr>
  `).join("");
}

async function loadCalendarControl(forceRefresh = false) {
  try {
    const response = await fetch(forceRefresh ? "/api/v1/calendar/upcoming/refresh" : "/api/v1/calendar/upcoming", {method: forceRefresh ? "POST" : "GET", cache: "no-store"});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderCalendarControl(data);
  } catch (error) {
    calendarControlMessage.className = "message error";
    calendarControlMessage.textContent = error.message;
  }
}

async function loadCalendarPreview() {
  const days = Math.max(1, Math.min(14, Number(calendarDays.value || 2)));
  calendarDays.value = days;
  calendarButton.disabled = true;
  calendarMessage.className = "message";
  calendarMessage.textContent = "Проверяю корпоративный календарь...";
  try {
    const response = await fetch(`/api/v1/calendar/company/preview?days=${encodeURIComponent(days)}`, {cache: "no-store"});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    renderCalendarPreview(data);
  } catch (error) {
    calendarMessage.className = "message error";
    calendarMessage.textContent = error.message;
  } finally {
    calendarButton.disabled = false;
  }
}

const discoveryModeLabels = {off: "Выключено", preview: "Предпросмотр", automatic: "Автоматически"};
const discoveryStatusLabels = {eligible: "Ожидает", already_participant: "Бот участвует", participation_unknown: "Участие неизвестно", event_finished: "Встреча завершена", external_or_unknown_organizer: "Нет корпоративного организатора", missing_event_id: "Нет ID события", missing_conference_id: "Нет ID Телемоста", excluded: "Исключено", running: "Выполняется", completed: "Готово", failed: "Ошибка", skipped: "Пропущено"};
const discoverySourceLabels = {scheduled_scan: "Часовой скан", automatic_scan: "Автоматически", manual_batch: "Ручной пакет", manual_event: "Вручную"};

function discoveryStatusBadge(status) {
  const css = status === "completed" || status === "already_participant" ? "" : status === "failed" ? "fail" : status === "eligible" || status === "running" ? "external" : "no";
  return `<span class="badge ${css}">${esc(discoveryStatusLabels[status] || status || "—")}</span>`;
}

function renderDiscoveryMeetings() {
  const rowsSource = discoveryTab === "events" ? (discoveryData.available_events || []) : (discoveryData.errors || []);
  const query = document.getElementById("discovery-search").value.toLowerCase();
  let rows = rowsSource.filter(row => JSON.stringify(row).toLowerCase().includes(query));
  const head = document.getElementById("discovery-thead");
  const body = document.getElementById("discovery-tbody");
  if (discoveryTab === "events") {
    rows = rows.filter(row => Boolean(row.telemost_url));
    if (discoveryMeetingFilter === "participant") rows = rows.filter(row => row.bot_participant === true);
    if (discoveryMeetingFilter === "absent") rows = rows.filter(row => row.bot_participant === false);
    rows.sort((a, b) => String(a.start || "").localeCompare(String(b.start || ""), "ru") || String(a.summary || "").localeCompare(String(b.summary || ""), "ru"));
    head.innerHTML = "<tr><th>Время</th><th>Название</th><th>Организатор</th><th>Бот</th><th>Телемост</th><th>Найдено у</th><th>ID</th></tr>";
    let lastDay = "";
    let html = "";
    for (const row of rows) {
      const day = String(row.start || "").slice(0, 10);
      const startTime = String(row.start || "").slice(11, 16);
      const endTime = String(row.end || "").slice(11, 16);
      if (day !== lastDay) {
        const label = new Date(`${day}T00:00:00`).toLocaleDateString("ru-RU", {weekday: "long", day: "numeric", month: "long", year: "numeric"});
        html += `<tr class="discovery-day-row"><td colspan="7">${esc(label.charAt(0).toUpperCase() + label.slice(1))}</td></tr>`;
        lastDay = day;
      }
      const botBadge = row.bot_participant === true ? '<span class="badge">участвует</span>' : row.bot_participant === false ? '<span class="badge no">не участвует</span>' : '<span class="badge external">неизвестно</span>';
      const organizerCss = row.organizer_type === "external" ? "external" : "";
      html += `<tr><td><strong>${esc(startTime || "—")}</strong><div class="muted">${esc(endTime || "—")}</div></td><td><strong>${esc(row.summary)}</strong></td><td>${esc(row.organizer || "—")}<div><span class="badge ${organizerCss}">${esc(row.organizer_type || "unknown")}</span></div></td><td>${botBadge}</td><td><a href="${esc(row.telemost_url)}" target="_blank" rel="noreferrer">открыть</a></td><td>${esc(row.seen_by_count || 0)}</td><td>${esc(row.event_id || row.ical_uid || "—")}<div class="muted">${esc(row.recurrence_id || "")}</div></td></tr>`;
    }
    body.innerHTML = html;
  } else {
    head.innerHTML = "<tr><th>Область</th><th>Сотрудник</th><th>HTTP</th><th>Ошибка</th></tr>";
    body.innerHTML = rows.map(row => `<tr><td>${esc(row.scope)}</td><td>${esc(row.email || "—")}</td><td>${esc(row.status || "—")}</td><td>${esc(row.message)}</td></tr>`).join("");
  }
  if (!rows.length) body.innerHTML = '<tr><td class="muted" colspan="7">Нет данных для отображения</td></tr>';
}

function renderDiscoveryManagement() {
  const management = discoveryData.management || {};
  const cycle = management.last_cycle || {};
  const queue = management.queue || [];
  const history = management.history || [];
  const scan = discoveryData.scan || {};
  const candidates = queue.filter(item => item.eligible).length;
  document.getElementById("discovery-management-mode").textContent = discoveryModeLabels[management.mode] || "Выключено";
  document.getElementById("discovery-management-candidates").textContent = candidates;
  document.getElementById("discovery-management-completed").textContent = cycle.completed || 0;
  document.getElementById("discovery-management-failed").textContent = cycle.failed || 0;
  document.getElementById("discovery-management-excluded").textContent = (management.excluded_keys || []).length;
  document.getElementById("discovery-management-cycle").textContent = discoveryStatusLabels[cycle.status] || cycle.status || "—";
  document.getElementById("discovery-management-cycle-details").textContent = `Последний цикл: ${formatDateTime(cycle.started_at)} · источник: ${discoverySourceLabels[cycle.source] || cycle.source || "—"} · попыток: ${cycle.attempted || 0} · завершено: ${cycle.completed || 0} · ошибок: ${cycle.failed || 0}`;
  document.querySelectorAll("[data-discovery-mode]").forEach(button => button.classList.toggle("active", button.dataset.discoveryMode === (management.mode || "off")));
  document.getElementById("discovery-run-management").disabled = Boolean(management.running) || scan.status === "running" || candidates === 0;
  const query = document.getElementById("discovery-control-search").value.toLowerCase();
  const rows = [...queue].filter(row => JSON.stringify(row).toLowerCase().includes(query)).sort((a, b) => String(a.start || "").localeCompare(String(b.start || ""), "ru"));
  document.getElementById("discovery-control-tbody").innerHTML = rows.map(row => {
    const last = row.last_result || {};
    const stages = last.status ? `Календарь: ${last.calendar_participant ? "да" : "нет"}; Телемост: ${last.telemost_cohost ? "да" : "нет"}` : "—";
    let actions = "";
    if (row.excluded) actions = `<button class="secondary" data-discovery-action="include" data-key="${esc(row.key)}">Вернуть</button>`;
    else if (row.eligible || row.action_status === "failed") actions = `<button data-discovery-action="add" data-key="${esc(row.key)}">${row.action_status === "failed" ? "Повторить" : "Добавить сейчас"}</button> <button class="secondary" data-discovery-action="exclude" data-key="${esc(row.key)}">Исключить</button>`;
    else if (row.action_status !== "already_participant") actions = `<button class="secondary" data-discovery-action="exclude" data-key="${esc(row.key)}">Исключить</button>`;
    return `<tr><td><strong>${esc(String(row.start || "").slice(0, 16).replace("T", " "))}</strong><div class="muted">${esc(String(row.end || "").slice(11, 16))}</div></td><td><strong>${esc(row.summary)}</strong><div><a href="${esc(row.telemost_url)}" target="_blank" rel="noreferrer">Телемост</a></div></td><td>${esc(row.management_email || "—")}</td><td>${discoveryStatusBadge(row.action_status)}</td><td>${esc(stages)}${last.reason ? `<div class="error">${esc(last.reason)}</div>` : ""}</td><td>${actions || "—"}</td></tr>`;
  }).join("") || '<tr><td class="muted" colspan="6">Очередь пока не сформирована</td></tr>';
  document.getElementById("discovery-history-tbody").innerHTML = [...history].reverse().slice(0, 100).map(row => `<tr><td>${esc(formatDateTime(row.at))}</td><td>${esc(discoverySourceLabels[row.source] || row.source || "—")}</td><td><strong>${esc(row.summary)}</strong></td><td>${discoveryStatusBadge(row.status)}</td><td>Календарь: ${row.calendar_participant ? "да" : "нет"}<br>Телемост: ${row.telemost_cohost ? "да" : "нет"}</td><td>${esc(row.reason || "—")}</td></tr>`).join("") || '<tr><td class="muted" colspan="6">Действий ещё не было</td></tr>';
}

function renderDiscovery() {
  const summary = discoveryData.summary || {};
  const scan = discoveryData.scan || {};
  const cache = discoveryData.employee_cache || {};
  document.getElementById("discovery-employees").textContent = summary.employees_cached || 0;
  document.getElementById("discovery-scanned").textContent = `${summary.employees_scanned || 0}${summary.employees_failed ? ` / ошибок ${summary.employees_failed}` : ""}`;
  document.getElementById("discovery-raw").textContent = summary.raw_events || 0;
  document.getElementById("discovery-unique").textContent = summary.unique_events || 0;
  document.getElementById("discovery-duplicates").textContent = summary.duplicates_removed || 0;
  document.getElementById("discovery-telemost").textContent = summary.telemost_events || 0;
  document.querySelectorAll("[data-discovery-filter]").forEach(button => {
    const counts = {all: summary.telemost_events || 0, participant: summary.bot_participant_events || 0, absent: summary.bot_absent_events || 0};
    const labels = {all: "Все встречи", participant: "Бот участвует", absent: "Бот не участвует"};
    button.textContent = `${labels[button.dataset.discoveryFilter]} · ${counts[button.dataset.discoveryFilter]}`;
  });
  document.getElementById("discovery-dot").className = `discovery-dot ${scan.status || ""}`;
  const scanLabels = {running: "Сканирование выполняется", completed: "Сканирование завершено", failed: "Ошибка сканирования"};
  document.getElementById("discovery-status").textContent = scanLabels[scan.status] || "Нет данных";
  document.getElementById("discovery-window").textContent = scan.window_from ? `Период: ${formatDateTime(scan.window_from)} — ${formatDateTime(scan.window_to)}` : "";
  const progress = document.getElementById("discovery-progress");
  progress.max = scan.progress_total || 1;
  progress.value = scan.progress_current || 0;
  document.getElementById("discovery-progress-text").textContent = `${scan.stage || "—"}: ${scan.progress_current || 0} из ${scan.progress_total || 0}. Следующий запуск: ${formatDateTime(scan.next_scan_at)}`;
  document.getElementById("discovery-cache").textContent = cache.refreshed_at ? `Кэш сотрудников: ${cache.employees_count || cache.items?.length || 0}, обновлён ${formatDateTime(cache.refreshed_at)}, действует до ${formatDateTime(cache.expires_at)}${cache.status === "stale" ? " (используется резервный устаревший кэш)" : ""}` : "Кэш сотрудников ещё не сформирован";
  document.getElementById("discovery-error").textContent = scan.error || "";
  document.getElementById("discovery-scan").disabled = scan.status === "running";
  document.getElementById("discovery-updated").textContent = `Обновлено: ${new Date().toLocaleTimeString("ru-RU")}`;
  renderDiscoveryMeetings();
  renderDiscoveryManagement();
}

async function discoveryApi(path, options = {}) {
  const response = await fetch(`/api/v1/calendar-discovery${path}`, {headers: {"Content-Type": "application/json", ...(options.headers || {})}, ...options});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail || `HTTP ${response.status}`));
  return payload;
}

async function loadDiscovery() {
  try {
    discoveryData = await discoveryApi("/status", {cache: "no-store"});
    renderDiscovery();
  } catch (error) {
    document.getElementById("discovery-error").textContent = `Не удалось получить состояние: ${error.message}`;
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
    quickMessage.textContent = `Задача ${data.task_id} отправлена на ${data.node_id}:${data.bot_id}. ${cohostResultText(data.cohost)}`;
    quickForm.reset();
    resetEmployeePicker(quickForm);
    await refresh();
  } catch (e) {
    quickMessage.className = "message error";
    quickMessage.textContent = e.message;
  } finally {
    button.disabled = false;
  }
}

async function submitAgenda(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const key = agendaFormKey(form);
  const state = agendaSubmissions.get(key) || {};
  if (state.pending || state.accepted) return;
  state.text = form.elements.raw_agenda.value;
  if (!state.text.trim()) {
    state.message = "Укажите повестку.";
    state.css = "error";
    agendaSubmissions.set(key, state);
    form.querySelector('.agenda-message').textContent = state.message;
    return;
  }
  Object.assign(state, {pending:true, css:"", message:"Проверяю формат и обрабатываю повестку…"});
  agendaSubmissions.set(key, state);
  form.querySelector('button').disabled = true;
  form.elements.raw_agenda.readOnly = true;
  form.querySelector('.agenda-message').textContent = state.message;
  try {
    const resp = await fetch(`/api/v1/nodes/${encodeURIComponent(form.dataset.nodeId)}/bots/${encodeURIComponent(form.dataset.botId)}/agenda/normalize-activate`, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({raw_agenda:state.text.trim(), session_id:form.dataset.sessionId})
    });
    const data = await resp.json().catch(() => ({}));
    if (!agendaSubmissions.has(key)) return;
    if (!resp.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Ошибка передачи повестки (HTTP ${resp.status}).`);
    state.css = "error";
    if (data.status === "agenda_activated" || data.status === "already_active") {
      state.accepted = true;
      state.text = "";
      state.css = "ok";
      state.message = "Повестка принята. Повторная передача отключена.";
    } else if (data.status === "meeting_ended") {
      agendaSubmissions.delete(key);
    } else {
      state.message = data.error || "Не удалось передать повестку. Попробуйте ещё раз.";
    }
  } catch (error) {
    if (agendaSubmissions.has(key)) {
      state.css = "error";
      state.message = error.message || "Ошибка связи. Повторите отправку.";
    }
  } finally {
    state.pending = false;
    await refresh(true);
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
    message.textContent = `Создана задача ${data.task_id}. ${cohostResultText(data.cohost)}`;
    botFormDrafts.delete(botFormDraftKey(form));
    form.reset();
    resetEmployeePicker(form);
    await refresh();
  } catch (e) {
    message.className = "message error";
    message.textContent = e.message;
  } finally {
    button.disabled = false;
  }
}

quickForm.addEventListener("submit", submitQuick);
setupEmployeePickers();
calendarButton.addEventListener("click", loadCalendarPreview);
calendarControlRefresh.addEventListener("click", () => loadCalendarControl(true));
for (const button of navButtons) {
  button.addEventListener("click", () => {
    showPage(button.dataset.pageTarget);
    if (button.dataset.pageTarget === "calendar-page") {
      loadCalendarControl();
      loadDiscovery();
    }
    if (button.dataset.pageTarget === "analytics-page") loadAnalytics(false);
    if (button.dataset.pageTarget === "assignments-page") loadAssignments();
    if (button.dataset.pageTarget === "session-page") loadSessionState();
  });
}
document.querySelectorAll("[data-discovery-page]").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("[data-discovery-page]").forEach(item => item.classList.toggle("active", item === button));
  document.getElementById("calendar-control-section").classList.toggle("hidden", button.dataset.discoveryPage !== "control");
  document.getElementById("discovery-meetings-section").classList.toggle("hidden", button.dataset.discoveryPage !== "meetings");
  document.getElementById("discovery-management-section").classList.toggle("hidden", button.dataset.discoveryPage !== "management");
  if (button.dataset.discoveryPage === "control") loadCalendarControl();
  else loadDiscovery();
}));
document.querySelectorAll("[data-discovery-tab]").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("[data-discovery-tab]").forEach(item => item.classList.toggle("active", item === button));
  discoveryTab = button.dataset.discoveryTab;
  renderDiscoveryMeetings();
}));
document.querySelectorAll("[data-discovery-filter]").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll("[data-discovery-filter]").forEach(item => item.classList.toggle("active", item === button));
  discoveryMeetingFilter = button.dataset.discoveryFilter;
  renderDiscoveryMeetings();
}));
document.querySelectorAll("[data-discovery-mode]").forEach(button => button.addEventListener("click", async () => {
  const mode = button.dataset.discoveryMode;
  const current = (discoveryData.management || {}).mode || "off";
  if (mode === current) return;
  if (mode === "automatic" && !confirm(`Включить автоматический режим? После следующего сканирования сервис сможет изменить ${(discoveryData.management?.queue || []).filter(item => item.eligible).length} встреч.`)) return;
  try {
    document.getElementById("discovery-management-error").textContent = "";
    await discoveryApi("/management/mode", {method: "PUT", body: JSON.stringify({mode})});
    await loadDiscovery();
  } catch (error) {
    document.getElementById("discovery-management-error").textContent = error.message;
  }
}));
document.getElementById("discovery-scan").addEventListener("click", async () => {
  try {
    await discoveryApi("/scan", {method: "POST"});
    await loadDiscovery();
  } catch (error) {
    document.getElementById("discovery-error").textContent = error.message;
  }
});
document.getElementById("discovery-run-management").addEventListener("click", async () => {
  const count = (discoveryData.management?.queue || []).filter(item => item.eligible).length;
  if (!confirm(`Добавить бота участником и соорганизатором в ${count} встреч сейчас?`)) return;
  try {
    document.getElementById("discovery-management-error").textContent = "";
    await discoveryApi("/management/run", {method: "POST"});
    await loadDiscovery();
  } catch (error) {
    document.getElementById("discovery-management-error").textContent = error.message;
  }
});
document.getElementById("discovery-control-tbody").addEventListener("click", async event => {
  const button = event.target.closest("[data-discovery-action]");
  if (!button) return;
  const action = button.dataset.discoveryAction;
  if (action === "add" && !confirm("Добавить бота участником и соорганизатором этой встречи?")) return;
  try {
    button.disabled = true;
    document.getElementById("discovery-management-error").textContent = "";
    await discoveryApi(`/management/${action === "add" ? "event" : action}`, {method: "POST", body: JSON.stringify({event_key: button.dataset.key})});
    await loadDiscovery();
  } catch (error) {
    document.getElementById("discovery-management-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
document.getElementById("discovery-search").addEventListener("input", renderDiscoveryMeetings);
document.getElementById("discovery-control-search").addEventListener("input", renderDiscoveryManagement);
document.getElementById("analytics-apply").addEventListener("click", () => loadAnalytics(false));
document.getElementById("analytics-refresh").addEventListener("click", () => loadAnalytics(true));
document.getElementById("assignments-refresh").addEventListener("click", loadAssignments);
assignmentsMeetingsBody.addEventListener("click", event => {
  const button = event.target.closest("[data-assignment-request-id]");
  if (button) showAssignmentDetails(button.dataset.assignmentRequestId);
});
assignmentDetails.addEventListener("click", async event => {
  const button = event.target.closest("[data-elma-retry]");
  if (!button) return;
  button.disabled = true;
  try {
    await retryElmaAssignment(button.dataset.elmaRetry);
    button.textContent = "Поставлено в очередь";
  } catch (error) {
    button.disabled = false;
    button.textContent = `Ошибка: ${error.message}`;
  }
});
document.getElementById("assignment-details-close").addEventListener("click", () => assignmentDetailsPanel.classList.add("hidden"));
sessionCheckButton.addEventListener("click", runSessionCheck);
sessionOtpForm.addEventListener("submit", submitSessionCode);
sessionAutoForm.addEventListener("submit", configureAutomaticSessionCheck);
onDemandMachinesEl.addEventListener("click", event => {
  const button = event.target.closest("[data-aws-action]");
  if (button) controlAwsMachine(button.dataset.awsAction, button);
});
refresh();
loadCalendarControl();
loadDiscovery();
loadSessionState();
setInterval(refresh, 3000);
setInterval(loadCalendarControl, 10000);
setInterval(loadDiscovery, 5000);
setInterval(loadSessionState, 10000);
</script>
</body>
</html>
"""
