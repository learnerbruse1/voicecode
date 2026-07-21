function showError(title, message) {
  errorTitle.textContent = title || t("operation_failed");
  errorMessage.textContent = message || t("operation_failed");
  errorModal.classList.add("show");
  errorModal.setAttribute("aria-hidden", "false");
  dbg(`${errorTitle.textContent}: ${errorMessage.textContent}`);
}

function closeError() {
  errorModal.classList.remove("show");
  errorModal.setAttribute("aria-hidden", "true");
}

errorClose.onclick = closeError;
errorModal.addEventListener("click", e => { if (e.target === errorModal) closeError(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeError(); });
errorCopy.onclick = () => navigator.clipboard?.writeText(`${errorTitle.textContent}\n${errorMessage.textContent}`).catch(() => {});
window.addEventListener("error", e => showError(t("unexpected_ui_error"), e.message || String(e.error || "Unknown error")));
window.addEventListener("unhandledrejection", e => showError(t("unexpected_async_error"), String(e.reason?.message || e.reason || "Unknown error")));
