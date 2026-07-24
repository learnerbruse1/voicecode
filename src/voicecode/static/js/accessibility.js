const dialogFocusOrigins = new WeakMap();
const activeDialogs = [];

export function dialogFocusableElements(dialog) {
  return Array.from(dialog.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter(element => !element.hidden && element.offsetParent !== null);
}

function focusDialogTarget(dialog, preferred = null) {
  const target = preferred || dialogFocusableElements(dialog)[0] || dialog;
  if (!target.hasAttribute("tabindex") && target === dialog) target.setAttribute("tabindex", "-1");
  target.focus({preventScroll: true});
}

function syncDialogState() {
  const hasActiveDialog = activeDialogs.length > 0;
  const appShell = document.querySelector(".app-shell");
  if (appShell) {
    if (hasActiveDialog) appShell.setAttribute("inert", "");
    else appShell.removeAttribute("inert");
  }
  document.body.classList.toggle("dialog-open", hasActiveDialog);
}

export function activateDialog(dialog, initialFocus = null) {
  if (!dialog) return;
  const existingIndex = activeDialogs.indexOf(dialog);
  if (existingIndex >= 0) activeDialogs.splice(existingIndex, 1);
  else dialogFocusOrigins.set(dialog, document.activeElement);
  dialog.dataset.focusActive = "true";
  activeDialogs.push(dialog);
  syncDialogState();
  focusDialogTarget(dialog, initialFocus);
}

export function deactivateDialog(dialog) {
  if (!dialog || dialog.dataset.focusActive !== "true") return;
  const index = activeDialogs.indexOf(dialog);
  if (index >= 0) activeDialogs.splice(index, 1);
  dialog.dataset.focusActive = "false";
  syncDialogState();

  const origin = dialogFocusOrigins.get(dialog);
  const topDialog = activeDialogs[activeDialogs.length - 1] || null;
  if (topDialog) {
    const preferred = origin && topDialog.contains(origin) ? origin : null;
    focusDialogTarget(topDialog, preferred);
  } else if (origin && typeof origin.focus === "function") {
    origin.focus({preventScroll: true});
  }
  dialogFocusOrigins.delete(dialog);
}

export function trapDialogFocus(event, dialog, onEscape = null) {
  if (!dialog || !dialog.classList.contains("show")) return;
  if (activeDialogs[activeDialogs.length - 1] !== dialog) return;
  if (event.key === "Escape" && onEscape) {
    event.preventDefault();
    onEscape();
    return;
  }
  if (event.key !== "Tab") return;
  const elements = dialogFocusableElements(dialog);
  if (!elements.length) { event.preventDefault(); focusDialogTarget(dialog); return; }
  const first = elements[0];
  const last = elements[elements.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

Object.assign(window, {activateDialog, deactivateDialog, trapDialogFocus});
