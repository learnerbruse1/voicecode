const dialogFocusOrigins = new WeakMap();

export function dialogFocusableElements(dialog) {
  return Array.from(dialog.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter(element => !element.hidden && element.offsetParent !== null);
}

export function activateDialog(dialog, initialFocus = null) {
  if (!dialog || dialog.dataset.focusActive === "true") return;
  dialog.dataset.focusActive = "true";
  dialogFocusOrigins.set(dialog, document.activeElement);
  const appShell = document.querySelector(".app-shell");
  if (appShell) appShell.setAttribute("inert", "");
  document.body.classList.add("dialog-open");
  const target = initialFocus || dialogFocusableElements(dialog)[0] || dialog;
  if (!target.hasAttribute("tabindex") && target === dialog) target.setAttribute("tabindex", "-1");
  target.focus({preventScroll: true});
}

export function deactivateDialog(dialog) {
  if (!dialog || dialog.dataset.focusActive !== "true") return;
  dialog.dataset.focusActive = "false";
  const appShell = document.querySelector(".app-shell");
  if (appShell) appShell.removeAttribute("inert");
  document.body.classList.remove("dialog-open");
  const origin = dialogFocusOrigins.get(dialog);
  if (origin && typeof origin.focus === "function") origin.focus({preventScroll: true});
  dialogFocusOrigins.delete(dialog);
}

export function trapDialogFocus(event, dialog, onEscape = null) {
  if (!dialog || !dialog.classList.contains("show")) return;
  if (event.key === "Escape" && onEscape) {
    event.preventDefault();
    onEscape();
    return;
  }
  if (event.key !== "Tab") return;
  const elements = dialogFocusableElements(dialog);
  if (!elements.length) { event.preventDefault(); dialog.focus(); return; }
  const first = elements[0];
  const last = elements[elements.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

Object.assign(window, {activateDialog, deactivateDialog, trapDialogFocus});
