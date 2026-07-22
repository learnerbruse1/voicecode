function renderHistoryEntries(entries) {
  if (!historyListEl) return;
  if (!entries.length) {
    historyListEl.innerHTML = `<div class="list-item"><p>${t("history_empty")}</p></div>`;
    return;
  }
  historyListEl.innerHTML = entries.slice().reverse().map(e => `
    <article class="list-item">
      <h4>${e.language || "auto"} / ${e.model || ""}</h4>
      <small>${e.created_at || ""}</small>
      <p>${String(e.text || "").replace(/[&<>]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[ch]))}</p>
    </article>`).join("");
}

async function loadHistoryPanel() {
  const r = await requestJSON("GET", "/history", {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (r.ok) renderHistoryEntries(r.entries || []);
}

async function loadDiagnosticsPanel() {
  const r = await requestJSON("GET", "/diagnostics", {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (diagnosticsOutputEl) diagnosticsOutputEl.textContent = r.ok ? JSON.stringify(r, null, 2) : (r.error || "Diagnostics unavailable");
}

async function loadExtensionsPanel() {
  const r = await requestJSON("GET", "/extensions", {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (!extensionsListEl) return;
  if (!r.ok) { extensionsListEl.innerHTML = `<div class="list-item"><p>${r.error || "Extensions unavailable"}</p></div>`; return; }
  extensionsListEl.innerHTML = (r.extensions || []).map(ext => {
    const state = ext.enabled ? t("enabled") : t("disabled");
    const available = ext.available ? t("available") : `${t("missing_deps")}: ${(ext.missing_dependencies || []).join(", ")}`;
    return `<article class="list-item"><h4>${ext.name} <small>${state}</small></h4><p>${ext.description || ""}</p><small>${available}</small><pre class="inline-code">${JSON.stringify(ext.config || {}, null, 2)}</pre></article>`;
  }).join("");
}

historyBtn.onclick = loadHistoryPanel;
clearHistoryBtn.onclick = async () => {
  const r = await requestJSON("POST", "/history/clear", {}, {errorTitle: t("request_failed")});
  if (r.ok) { showError(t("clear_history"), "Transcript history has been cleared."); loadHistoryPanel(); }
};
diagnosticsBtn.onclick = loadDiagnosticsPanel;
if (extensionsRefreshBtn) extensionsRefreshBtn.onclick = loadExtensionsPanel;
