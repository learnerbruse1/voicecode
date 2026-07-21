historyBtn.onclick = async () => {
  const r = await requestJSON("GET", "/history", {}, {errorTitle: t("request_failed")});
  if (!r.ok) return;
  const entries = r.entries || [];
  const body = entries.length ? entries.map(e => `[${e.created_at}] ${e.language || "auto"} / ${e.model || ""}\n${e.text}`).join("\n\n---\n\n") : t("history_empty");
  showError(t("history"), body);
};

clearHistoryBtn.onclick = async () => {
  const r = await requestJSON("POST", "/history/clear", {}, {errorTitle: t("request_failed")});
  if (r.ok) showError(t("clear_history"), "Transcript history has been cleared.");
};

diagnosticsBtn.onclick = async () => {
  const r = await requestJSON("GET", "/diagnostics", {}, {errorTitle: t("request_failed")});
  if (r.ok) showError(t("diagnostics"), JSON.stringify(r, null, 2));
};
