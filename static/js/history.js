function htmlEscape(value) {
  return String(value || "").replace(/[&<>"]|'/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
}

function translatedEntity(prefix, id, field, fallback) {
  const key = `${prefix}_${String(id || "").replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "")}_${field}`;
  const translated = t(key);
  return translated === key ? (fallback || "") : translated;
}

function renderHistoryEntries(entries) {
  if (!historyListEl) return;
  if (!entries.length) {
    historyListEl.innerHTML = `<div class="list-item"><p>${t("history_empty")}</p></div>`;
    return;
  }
  historyListEl.innerHTML = entries.slice().reverse().map(e => `
    <article class="list-item">
      <h4>${htmlEscape(e.language || "auto")} / ${htmlEscape(e.model || "")}</h4>
      <small>${htmlEscape(e.created_at || "")}</small>
      <p>${htmlEscape(e.text || "")}</p>
    </article>`).join("");
}

async function loadHistoryPanel() {
  const r = await requestJSON("GET", "/history", {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (r.ok) renderHistoryEntries(r.entries || []);
}

async function loadDiagnosticsPanel() {
  const r = await requestJSON("GET", "/diagnostics", {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (diagnosticsOutputEl) diagnosticsOutputEl.textContent = r.ok ? JSON.stringify(r, null, 2) : (r.error || t("diagnostics_unavailable"));
}

async function loadExtensionsPanel() {
  const r = await requestJSON("GET", "/extensions", {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (!extensionsListEl) return;
  if (!r.ok) { extensionsListEl.innerHTML = `<div class="list-item"><p>${htmlEscape(r.error || t("extensions_unavailable"))}</p></div>`; return; }
  extensionsListEl.innerHTML = (r.extensions || []).map(ext => {
    const state = ext.enabled ? t("enabled") : t("disabled");
    const available = ext.available ? t("available") : `${t("missing_deps")}: ${(ext.missing_dependencies || []).join(", ")}`;
    const name = translatedEntity("extension", ext.id, "name", ext.name);
    const description = translatedEntity("extension", ext.id, "description", ext.description || "");
    return `<article class="list-item"><h4>${htmlEscape(name)} <small>${state}</small></h4><p>${htmlEscape(description)}</p><small>${htmlEscape(available)}</small><pre class="inline-code">${htmlEscape(JSON.stringify(ext.config || {}, null, 2))}</pre></article>`;
  }).join("");
}

historyBtn.onclick = loadHistoryPanel;
clearHistoryBtn.onclick = async () => {
  const r = await requestJSON("POST", "/history/clear", {}, {errorTitle: t("request_failed")});
  if (r.ok) { showError(t("clear_history"), t("history_cleared")); loadHistoryPanel(); }
};
diagnosticsBtn.onclick = loadDiagnosticsPanel;
if (extensionsRefreshBtn) extensionsRefreshBtn.onclick = loadExtensionsPanel;
