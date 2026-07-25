function showError(title, message) {
  errorTitle.textContent = title || t("operation_failed");
  errorMessage.textContent = message || t("operation_failed");
  errorModal.classList.add("show");
  errorModal.setAttribute("aria-hidden", "false");
  activateDialog(errorModal, errorClose);
  dbg(`${errorTitle.textContent}: ${errorMessage.textContent}`);
}

function closeError() {
  errorModal.classList.remove("show");
  errorModal.setAttribute("aria-hidden", "true");
  deactivateDialog(errorModal);
}

async function copyTextRobust(value) {
  const textValue = String(value || "");
  if (!textValue) return false;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(textValue);
      return true;
    }
  } catch (_) {}
  try {
    const area = document.createElement("textarea");
    area.value = textValue;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand("copy");
    area.remove();
    if (copied) return true;
  } catch (_) {}
  try {
    if (window.pywebview && pywebview.api && pywebview.api.copy_text) {
      return Boolean(await pywebview.api.copy_text(textValue));
    }
  } catch (_) {}
  return false;
}

errorClose.onclick = closeError;
errorModal.addEventListener("click", e => { if (e.target === errorModal) closeError(); });
document.addEventListener("keydown", e => trapDialogFocus(e, errorModal, closeError));
errorCopy.onclick = async () => {
  const original = errorCopy.textContent;
  const copied = await copyTextRobust(`${errorTitle.textContent}\n${errorMessage.textContent}`);
  errorCopy.textContent = copied ? t("copied") : t("copy_failed");
  setTimeout(() => { errorCopy.textContent = original; }, 1800);
};
window.addEventListener("error", e => showError(t("unexpected_ui_error"), e.message || String(e.error || "Unknown error")));
window.addEventListener("unhandledrejection", e => showError(t("unexpected_async_error"), String(e.reason?.message || e.reason || "Unknown error")));

if (errorOpenLogs) errorOpenLogs.onclick = async () => {
  try {
    const ok = window.pywebview && pywebview.api ? await pywebview.api.open_log_folder() : false;
    if (!ok) await copyTextRobust(errorMessage.textContent || "");
  } catch (_) {}
};

Object.assign(window, {showError, closeError, copyTextRobust});
