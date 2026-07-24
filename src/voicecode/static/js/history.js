function translatedEntity(prefix, id, field, fallback) {
  const key = `${prefix}_${String(id || "").replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "")}_${field}`;
  const translated = t(key);
  return translated === key ? (fallback || "") : translated;
}

function historyQueryParams() {
  const params = new URLSearchParams();
  const q = historySearchEl ? historySearchEl.value.trim() : "";
  const language = historyLanguageEl ? historyLanguageEl.value : "";
  if (q) params.set("q", q);
  if (language) params.set("language", language);
  return params;
}

function renderHistoryEntries(entries, total = entries.length) {
  if (!historyListEl) return;
  if (historySummaryEl) historySummaryEl.textContent = `${t("history_total")}: ${total}`;
  if (!entries.length) {
    historyListEl.innerHTML = `<div class="list-item"><p>${t("history_empty")}</p></div>`;
    return;
  }
  historyListEl.innerHTML = entries.slice().reverse().map(e => {
    const id = htmlEscape(e.id || "");
    const textValue = htmlEscape(e.text || "");
    return `<article class="list-item history-entry" data-history-id="${id}">
      <div class="history-entry-head"><div><h4>${htmlEscape(e.language || "auto")} / ${htmlEscape(e.model || "")}</h4><small>${htmlEscape(e.created_at || "")}</small></div><div class="button-row"><button class="sm history-copy-btn" type="button" data-history-id="${id}">${t("copy")}</button><button class="sm danger history-delete-btn" type="button" data-history-id="${id}" data-confirm="false">${t("delete")}</button></div></div>
      <p>${textValue}</p>
    </article>`;
  }).join("");
  historyListEl.querySelectorAll(".history-copy-btn").forEach(btn => { btn.onclick = () => copyHistoryEntry(btn.dataset.historyId); });
  historyListEl.querySelectorAll(".history-delete-btn").forEach(btn => { btn.onclick = () => deleteHistoryEntry(btn); });
}

async function loadHistoryPanel() {
  const params = historyQueryParams();
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const r = await requestJSON("GET", `/history${suffix}`, {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (r.ok) renderHistoryEntries(r.entries || [], r.total || 0);
}

async function copyHistoryEntry(entryId) {
  const article = historyListEl ? historyListEl.querySelector(`[data-history-id="${CSS.escape(entryId || "")}"]`) : null;
  const paragraph = article ? article.querySelector("p") : null;
  const value = paragraph ? paragraph.textContent || "" : "";
  if (!value.trim()) return;
  try {
    await navigator.clipboard.writeText(value);
    showError(t("copied"), t("history_entry_copied"));
  } catch (err) {
    showError(t("clipboard_failed"), err.message || t("clipboard_failed_detail"));
  }
}

async function deleteHistoryEntry(btn) {
  const entryId = btn.dataset.historyId;
  if (!entryId) return;
  if (btn.dataset.confirm !== "true") {
    btn.dataset.confirm = "true";
    btn.textContent = t("history_confirm_delete");
    setTimeout(() => {
      if (btn.dataset.confirm === "true") {
        btn.dataset.confirm = "false";
        btn.textContent = t("delete");
      }
    }, 5000);
    return;
  }
  const r = await requestJSON("DELETE", `/history/${encodeURIComponent(entryId)}`, {confirm: true}, {errorTitle: t("history_delete_failed")});
  if (r.ok) await loadHistoryPanel();
}

function exportHistory(format) {
  const params = historyQueryParams();
  params.set("format", format);
  window.location.href = `/history/export?${params.toString()}`;
}

async function loadDiagnosticsPanel() {
  const r = await requestJSON("GET", "/diagnostics", {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (diagnosticsOutputEl) diagnosticsOutputEl.textContent = r.ok ? JSON.stringify(r, null, 2) : (r.error || t("diagnostics_unavailable"));
}

let historySearchTimer = null;
if (historySearchEl) historySearchEl.oninput = () => { clearTimeout(historySearchTimer); historySearchTimer = setTimeout(loadHistoryPanel, 250); };
if (historyLanguageEl) historyLanguageEl.onchange = loadHistoryPanel;
historyBtn.onclick = loadHistoryPanel;
clearHistoryBtn.onclick = async () => {
  const r = await requestJSON("POST", "/history/clear", {}, {errorTitle: t("request_failed")});
  if (r.ok) { showError(t("clear_history"), t("history_cleared")); loadHistoryPanel(); }
};
if (historyExportJsonBtn) historyExportJsonBtn.onclick = () => exportHistory("json");
if (historyExportMdBtn) historyExportMdBtn.onclick = () => exportHistory("md");
if (historyExportTxtBtn) historyExportTxtBtn.onclick = () => exportHistory("txt");
diagnosticsBtn.onclick = loadDiagnosticsPanel;
if (diagnosticsExportBtn) diagnosticsExportBtn.onclick = () => { window.location.href = "/diagnostics/export"; };
