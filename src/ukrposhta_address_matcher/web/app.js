const state = {
  batches: [],
  currentBatch: null,
  currentRow: null,
  filter: "all",
  lastApplySummary: "",
};

const statusMap = {
  ai_assisted_verified: "Підтверджено з AI",
  verified_fuzzy: "Підтверджено нечітко",
  postcode_resolved: "Індекс знайдено",
  postcode_corrected: "Індекс виправлено",
  postcode_anchor_review: "Fallback на індекс",
  postcode_candidate_review: "Найближчий кандидат",
  forced_fill_review: "Примусове заповнення",
  unresolved_review: "Не розв'язано",
  po_box_review: "Абонскринька / відділення",
  operator_selected_candidate: "Кандидат обраний оператором",
  operator_manual_override: "Ручне редагування оператора",
  operator_marked_unresolved: "Позначено як нерозв'язне",
};

const warningMap = new Map([
  ["postcode does not align with parsed city/street/house", "Індекс не узгоджується з розпізнаними містом, вулицею або будинком"],
  ["ai fallback used for postcode rescue", "Використано AI для відновлення індексу"],
  ["ai fallback used for normalization", "Використано AI для нормалізації адреси"],
  ["nearest available house used", "Підібрано найближчий будинок"],
  ["classifier street unresolved; post office address used for resolved postcode", "Вулицю не підтверджено, використано адресу відділення для знайденого індексу"],
  ["resolved from nearest classifier address within postcode candidates", "Використано найближчу адресу з кандидатів класифікатора"],
  ["forced fill used due to missing street or house", "Використано примусове заповнення через відсутність вулиці або будинку"],
  ["po box mapped to post office address", "Абонентську скриньку зіставлено з адресою відділення"],
  ["po box preserved; post office address not resolved", "Абонентську скриньку збережено, адресу відділення не знайдено"],
]);

document.getElementById("upload-form").addEventListener("submit", onUpload);
document.getElementById("refresh-batches").addEventListener("click", loadBatches);
document.getElementById("download-auto").addEventListener("click", () => downloadCurrent("auto"));
document.getElementById("download-final").addEventListener("click", () => downloadCurrent("final"));
document.getElementById("download-log").addEventListener("click", () => downloadCurrent("review-log"));
document.getElementById("queue-filters").addEventListener("click", onFilterClick);

loadBatches();

async function loadBatches() {
  const response = await fetch("/api/batches");
  const payload = await response.json();
  state.batches = payload.items || [];
  renderRecentBatches();
}

async function onUpload(event) {
  event.preventDefault();
  const input = document.getElementById("file-input");
  const file = input.files[0];
  if (!file) {
    return;
  }
  const status = document.getElementById("upload-status");
  status.textContent = "Обробка файла триває. Це може зайняти трохи часу.";
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch("/api/batches", { method: "POST", body: formData });
  const payload = await response.json();
  if (!response.ok) {
    status.textContent = payload.error || "Не вдалося обробити файл.";
    return;
  }
  status.textContent = `Пакет ${payload.filename} створено.`;
  await loadBatches();
  await loadBatch(payload.batch_id);
}

async function loadBatch(batchId) {
  const response = await fetch(`/api/batches/${batchId}`);
  const payload = await response.json();
  if (!response.ok) {
    alert(payload.error || "Не вдалося завантажити пакет.");
    return;
  }
  state.currentBatch = payload;
  state.currentRow = null;
  state.lastApplySummary = "";
  renderSummary();
  renderQueue();
}

async function loadRow(lineNo) {
  if (!state.currentBatch) {
    return;
  }
  const response = await fetch(`/api/batches/${state.currentBatch.batch_id}/rows/${lineNo}`);
  const payload = await response.json();
  if (!response.ok) {
    alert(payload.error || "Не вдалося завантажити рядок.");
    return;
  }
  state.currentRow = payload;
  state.lastApplySummary = "";
  renderQueue();
  renderDetail();
}

async function submitDecision(payload) {
  if (!state.currentBatch || !state.currentRow) {
    return;
  }
  const response = await fetch(
    `/api/batches/${state.currentBatch.batch_id}/rows/${state.currentRow.line_no}/decision`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  const detail = await response.json();
  if (!response.ok) {
    alert(detail.error || "Не вдалося зберегти рішення.");
    return;
  }
  await loadBatch(state.currentBatch.batch_id);
  state.currentRow = detail;
  const applied = detail.applied_to_similar_line_nos || [];
  state.lastApplySummary = applied.length
    ? `Рішення додатково застосовано до ${applied.length} схожих рядків: ${applied.join(", ")}.`
    : "Рішення збережено.";
  renderDetail();
}

function onFilterClick(event) {
  const button = event.target.closest("button[data-filter]");
  if (!button) {
    return;
  }
  state.filter = button.dataset.filter;
  for (const item of document.querySelectorAll(".filter")) {
    item.classList.toggle("active", item === button);
  }
  renderQueue();
}

function renderRecentBatches() {
  const container = document.getElementById("recent-batches");
  if (!state.batches.length) {
    container.className = "recent-list empty-state";
    container.textContent = "Ще немає пакетів.";
    return;
  }
  container.className = "recent-list";
  container.innerHTML = state.batches
    .map(
      (item) => `
        <div class="recent-item">
          <strong>${escapeHtml(item.filename)}</strong>
          <div class="badge-row">
            <span class="badge auto_accept">Авто: ${item.summary.auto_accept}</span>
            <span class="badge review">Review: ${item.summary.review}</span>
            <span class="badge hard_stop">Hard Stop: ${item.summary.hard_stop}</span>
          </div>
          <p class="muted">Створено: ${formatDate(item.created_at)}. Очікують рішення: ${item.summary.pending_review}</p>
          <button onclick="loadBatch('${item.batch_id}')">Відкрити пакет</button>
        </div>
      `
    )
    .join("");
}

function renderSummary() {
  const container = document.getElementById("batch-summary");
  const autoButton = document.getElementById("download-auto");
  const finalButton = document.getElementById("download-final");
  const logButton = document.getElementById("download-log");
  if (!state.currentBatch) {
    container.className = "empty-state";
    container.textContent = "Оберіть пакет або завантажте новий файл.";
    autoButton.disabled = true;
    finalButton.disabled = true;
    logButton.disabled = true;
    return;
  }
  const { summary, filename, created_at, stats } = state.currentBatch;
  autoButton.disabled = false;
  logButton.disabled = false;
  finalButton.disabled = summary.pending_review > 0;
  container.className = "";
  container.innerHTML = `
    <p><strong>${escapeHtml(filename)}</strong></p>
    <p class="muted">Створено: ${formatDate(created_at)}. Унікальних запитів: ${stats.unique_requests}. HTTP до класифікатора: ${stats.classifier_http_requests}.</p>
    <div class="summary-grid">
      <div class="summary-card"><span>Рядків</span><strong>${summary.rows}</strong></div>
      <div class="summary-card"><span>Автоматично</span><strong>${summary.auto_accept}</strong></div>
      <div class="summary-card"><span>Review</span><strong>${summary.review}</strong></div>
      <div class="summary-card"><span>Hard Stop</span><strong>${summary.hard_stop}</strong></div>
      <div class="summary-card"><span>Без рішення</span><strong>${summary.pending_review}</strong></div>
    </div>
  `;
}

function renderQueue() {
  const container = document.getElementById("queue-list");
  if (!state.currentBatch) {
    container.className = "queue-list empty-state";
    container.textContent = "Немає активної черги.";
    return;
  }
  const rows = state.currentBatch.rows.filter(matchesFilter);
  if (!rows.length) {
    container.className = "queue-list empty-state";
    container.textContent = "Для цього фільтра рядків немає.";
    return;
  }
  container.className = "queue-list";
  container.innerHTML = rows
    .map((row) => {
      const active = state.currentRow && row.line_no === state.currentRow.line_no;
      return `
        <div class="queue-item ${active ? "active" : ""}" onclick="loadRow(${row.line_no})">
          <strong>Рядок ${row.line_no}</strong>
          <div class="badge-row">
            <span class="badge ${row.routing.queue}">${translateQueue(row.routing.queue)}</span>
            ${row.decision ? '<span class="badge auto_accept">Є рішення</span>' : ""}
          </div>
          <p>${escapeHtml(truncate(row.original_address, 100))}</p>
          <p class="muted">${escapeHtml(translateStatus(row.auto_result.status))} • ${row.auto_result.structured_address.postcode}</p>
        </div>
      `;
    })
    .join("");
}

function renderDetail() {
  const container = document.getElementById("row-detail");
  if (!state.currentRow) {
    container.className = "detail-view empty-state";
    container.textContent = "Оберіть рядок у черзі.";
    return;
  }
  const row = state.currentRow;
  const suggested = row.auto_result.structured_address;
  const finalAddress = row.decision ? row.decision.final_address : suggested;
  const warnings = (row.auto_result.warnings || []).map(translateWarning);
  const reasons = row.routing.reasons || [];
  const similarRows = row.similar_rows || [];
  container.className = "detail-view";
  container.innerHTML = `
    <div class="detail-section">
      <div class="badge-row">
        <span class="badge ${row.routing.queue}">${translateQueue(row.routing.queue)}</span>
        <span class="badge review">${translateStatus(row.auto_result.status)}</span>
      </div>
      <h3>Оригінал</h3>
      <p><strong>Рядок:</strong> ${row.line_no}</p>
      <p><strong>Вхідний індекс:</strong> ${escapeHtml(row.input_postcode || "—")}</p>
      <p>${escapeHtml(row.original_address)}</p>
    </div>

    <div class="detail-section">
      <h3>Розпізнані компоненти</h3>
      ${renderAddressGrid(row.parsed_address)}
    </div>

    <div class="detail-section">
      <h3>Запропонований результат</h3>
      ${renderAddressGrid(suggested)}
      <ul class="reason-list">
        ${reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
      </ul>
      ${warnings.length ? `<ul class="warning-list">${warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    </div>

    <div class="detail-section">
      <h3>Кандидати класифікатора</h3>
      ${renderCandidates(row.candidates || [])}
    </div>

    <div class="detail-section">
      <h3>Рішення оператора</h3>
      ${state.lastApplySummary ? `<p class="notice">${escapeHtml(state.lastApplySummary)}</p>` : ""}
      <div class="manual-actions">
        <button onclick='acceptSuggested()'>Підтвердити запропоноване</button>
        <button class="secondary" onclick='markUnresolved()'>Позначити нерозв'язним</button>
      </div>
      ${
        similarRows.length
          ? `
            <label class="checkbox-line">
              <input id="apply-similar" type="checkbox">
              Застосувати це рішення до ${similarRows.length} схожих рядків без рішення
            </label>
          `
          : `<p class="muted">Для цього рядка зараз немає схожих нерозв'язаних рядків.</p>`
      }
      <form id="manual-form" onsubmit="submitManual(event)">
        ${renderManualForm(finalAddress)}
      </form>
    </div>
  `;
}

function renderAddressGrid(address) {
  return `
    <div class="kv-grid">
      <div><span>Індекс</span>${escapeHtml(address.postcode || "—")}</div>
      <div><span>Область</span>${escapeHtml(address.region || "—")}</div>
      <div><span>Район</span>${escapeHtml(address.district || "—")}</div>
      <div><span>Місто</span>${escapeHtml(address.city || "—")}</div>
      <div><span>Вулиця</span>${escapeHtml(address.street || "—")}</div>
      <div><span>Будинок</span>${escapeHtml(address.houseNumber || "—")}</div>
      <div><span>Квартира</span>${escapeHtml(address.apartmentNumber || "—")}</div>
    </div>
  `;
}

function renderCandidates(candidates) {
  if (!candidates.length) {
    return '<p class="muted">Для цього рядка додаткових кандидатів не знайдено.</p>';
  }
  return candidates
    .map((candidate, index) => {
      const encodedAddress = encodeURIComponent(JSON.stringify(candidate.address));
      return `
        <div class="candidate-card">
          <p><strong>${index + 1}. ${translateCandidateSource(candidate.source)}</strong></p>
          ${renderAddressGrid(candidate.address)}
          <p class="muted">Score: ${candidate.score}. ${escapeHtml(candidate.note || "")}</p>
          <button class="secondary" onclick="chooseCandidateFromEncoded('${escapeAttribute(encodedAddress)}')">Обрати цей варіант</button>
        </div>
      `;
    })
    .join("");
}

function renderManualForm(address) {
  return `
    <div class="manual-grid">
      ${renderInput("postcode", "Індекс", address.postcode)}
      ${renderInput("region", "Область", address.region)}
      ${renderInput("district", "Район", address.district)}
      ${renderInput("city", "Місто", address.city)}
      ${renderInput("street", "Вулиця", address.street)}
      ${renderInput("houseNumber", "Будинок", address.houseNumber)}
      ${renderInput("apartmentNumber", "Квартира", address.apartmentNumber)}
      ${renderInput("reasonCode", "Код причини", state.currentRow.decision?.reason_code || "")}
      ${renderInput("comment", "Коментар", state.currentRow.decision?.comment || "")}
    </div>
    <div class="manual-actions">
      <button type="submit">Зберегти ручне рішення</button>
    </div>
  `;
}

function renderInput(name, label, value) {
  return `
    <label>
      <span>${label}</span>
      <input name="${name}" value="${escapeAttribute(value || "")}">
    </label>
  `;
}

function chooseCandidate(address) {
  submitDecision({
    action: "select_candidate",
    final_address: address,
    reason_code: "selected_candidate",
    comment: "",
    apply_to_similar: getApplyToSimilarFlag(),
  });
}

function chooseCandidateFromEncoded(value) {
  chooseCandidate(JSON.parse(decodeURIComponent(value)));
}

function acceptSuggested() {
  submitDecision({
    action: "accept_suggested",
    reason_code: "accepted_suggested",
    comment: "",
    apply_to_similar: getApplyToSimilarFlag(),
  });
}

function markUnresolved() {
  submitDecision({
    action: "mark_unresolved",
    reason_code: "marked_unresolved",
    comment: "",
    apply_to_similar: getApplyToSimilarFlag(),
  });
}

function submitManual(event) {
  event.preventDefault();
  const form = event.target;
  const data = new FormData(form);
  submitDecision({
    action: "manual_override",
    reason_code: data.get("reasonCode") || "",
    comment: data.get("comment") || "",
    apply_to_similar: getApplyToSimilarFlag(),
    final_address: {
      postcode: data.get("postcode") || "",
      region: data.get("region") || "",
      district: data.get("district") || "",
      city: data.get("city") || "",
      street: data.get("street") || "",
      houseNumber: data.get("houseNumber") || "",
      apartmentNumber: data.get("apartmentNumber") || "",
    },
  });
}

function getApplyToSimilarFlag() {
  const checkbox = document.getElementById("apply-similar");
  return Boolean(checkbox && checkbox.checked);
}

function matchesFilter(row) {
  if (state.filter === "all") {
    return true;
  }
  if (state.filter === "pending") {
    return row.routing.needs_review && !row.decision;
  }
  return row.routing.queue === state.filter;
}

function downloadCurrent(kind) {
  if (!state.currentBatch) {
    return;
  }
  window.location.href = `/api/batches/${state.currentBatch.batch_id}/export/${kind}`;
}

function translateQueue(queue) {
  return (
    {
      auto_accept: "Автоматично",
      review: "Потрібен review",
      hard_stop: "Hard Stop",
    }[queue] || queue
  );
}

function translateStatus(status) {
  return statusMap[status] || status;
}

function translateCandidateSource(source) {
  return (
    {
      address_by_postcode: "Кандидат за індексом",
      post_office: "Адреса відділення",
    }[source] || source
  );
}

function translateWarning(value) {
  return warningMap.get(value) || value;
}

function truncate(value, length) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function formatDate(value) {
  return new Date(value).toLocaleString("uk-UA");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

window.loadBatch = loadBatch;
window.loadRow = loadRow;
window.chooseCandidate = chooseCandidate;
window.chooseCandidateFromEncoded = chooseCandidateFromEncoded;
window.acceptSuggested = acceptSuggested;
window.markUnresolved = markUnresolved;
window.submitManual = submitManual;
