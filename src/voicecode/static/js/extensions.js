function extensionFieldId(extensionId, fieldName) {
  return `extension-${extensionId}-${fieldName}`;
}

function extensionFieldMarkup(extensionId, field, config) {
  const id = extensionFieldId(extensionId, field.name);
  const value = config[field.name] ?? field.default;
  const fieldKey = `extension_field_${field.name}`;
  const translatedLabel = t(fieldKey);
  const label = field.name === "enabled" ? t("field_enabled") : (translatedLabel === fieldKey ? field.name.replaceAll("_", " ") : translatedLabel);
  if (field.type === "boolean") {
    return `<label class="extension-field extension-toggle"><span>${htmlEscape(label)}</span><input id="${id}" data-field="${htmlEscape(field.name)}" data-type="boolean" type="checkbox" ${value ? "checked" : ""}></label>`;
  }
  if (field.type === "select") {
    const options = (field.choices || []).map(choice => `<option value="${htmlEscape(choice)}" ${choice === value ? "selected" : ""}>${htmlEscape(choice)}</option>`).join("");
    return `<label class="extension-field"><span>${htmlEscape(label)}</span><select id="${id}" data-field="${htmlEscape(field.name)}" data-type="select">${options}</select></label>`;
  }
  if (field.type === "multiselect") {
    const selected = new Set(Array.isArray(value) ? value : []);
    const options = (field.choices || []).map(choice => `<option value="${htmlEscape(choice)}" ${selected.has(choice) ? "selected" : ""}>${htmlEscape(choice)}</option>`).join("");
    return `<label class="extension-field"><span>${htmlEscape(label)}</span><select id="${id}" data-field="${htmlEscape(field.name)}" data-type="multiselect" multiple>${options}</select></label>`;
  }
  if (["integer", "number"].includes(field.type)) {
    const minimum = field.minimum === undefined ? "" : `min="${Number(field.minimum)}"`;
    const maximum = field.maximum === undefined ? "" : `max="${Number(field.maximum)}"`;
    const step = field.step === undefined ? (field.type === "integer" ? "1" : "any") : String(field.step);
    const help = field.help_key ? t(field.help_key) : "";
    const helpMarkup = help && help !== field.help_key ? `<small>${htmlEscape(help)}</small>` : "";
    return `<label class="extension-field"><span>${htmlEscape(label)}</span><input id="${id}" data-field="${htmlEscape(field.name)}" data-type="${field.type}" type="number" ${minimum} ${maximum} step="${step}" value="${Number(value || 0)}">${helpMarkup}</label>`;
  }
  const textValue = Array.isArray(value) ? value.join("\n") : String(value ?? "");
  return `<label class="extension-field"><span>${htmlEscape(label)}</span><textarea id="${id}" data-field="${htmlEscape(field.name)}" data-type="${field.type}">${htmlEscape(textValue)}</textarea></label>`;
}

function readExtensionConfig(card) {
  const config = {};
  card.querySelectorAll("[data-field]").forEach(input => {
    const field = input.dataset.field;
    const type = input.dataset.type;
    if (type === "boolean") config[field] = input.checked;
    else if (["integer", "number"].includes(type)) config[field] = Number(input.value);
    else if (type === "multiselect") config[field] = Array.from(input.selectedOptions).map(option => option.value);
    else if (type === "string_list") config[field] = input.value.split(/\r?\n|,/).map(item => item.trim()).filter(Boolean);
    else config[field] = input.value;
  });
  return config;
}

function renderExtensions(data) {
  if (!extensionsListEl) return;
  const extensions = data.extensions || [];
  if (!extensions.length) {
    extensionsListEl.innerHTML = `<div class="list-item"><p>${t("extensions_unavailable")}</p></div>`;
    return;
  }
  extensionsListEl.innerHTML = extensions.map(ext => {
    const stateKey = `extension_state_${ext.state || (ext.enabled ? "operational" : "disabled")}`;
    const state = t(stateKey);
    const readiness = ext.ready ? t("onboarding_ready") : t("onboarding_not_ready");
    const name = translatedEntity("extension", ext.id, "name", ext.name);
    const description = translatedEntity("extension", ext.id, "description", ext.description || "");
    const fields = (ext.config_schema || []).map(field => extensionFieldMarkup(ext.id, field, ext.config || {})).join("");
    const dependencyText = (ext.dependencies || []).length
      ? (ext.dependencies || []).map(dep => `${dep.name}: ${dep.installed ? t("available") : t("missing_deps")}`).join(" ? ")
      : t("extension_no_dependencies");
    const installButton = (ext.dependencies || []).some(dep => !dep.installed_in_voice_dep)
      ? `<button type="button" class="sm extension-install" data-extension-id="${htmlEscape(ext.id)}">${t("extension_install_dependencies")}</button>` : "";
    return `<article class="extension-card ${ext.enabled ? "enabled" : "disabled"}" data-extension-id="${htmlEscape(ext.id)}">
      <div class="extension-card-head"><div><h4>${htmlEscape(name)} <small>${htmlEscape(state)}</small></h4><p>${htmlEscape(description)}</p><small>${htmlEscape(readiness)} ? ${htmlEscape(dependencyText)}</small>${ext.status_message ? `<small class="extension-status-message">${htmlEscape(ext.status_message)}</small>` : ""}${ext.restart_required ? `<small class="extension-warning">${t("dependency_restart_required")}</small>` : ""}</div></div>
      <div class="extension-config-grid">${fields}</div>
      <div class="extension-actions">${installButton}<button type="button" class="sm primary extension-save" data-extension-id="${htmlEscape(ext.id)}">${t("extension_save")}</button></div>
    </article>`;
  }).join("");
  extensionsListEl.querySelectorAll(".extension-save").forEach(button => {
    button.onclick = () => saveExtension(button.dataset.extensionId);
  });
  extensionsListEl.querySelectorAll(".extension-install").forEach(button => {
    button.onclick = () => installExtensionDependencies(button.dataset.extensionId);
  });
}

export async function loadExtensionsPanel() {
  const result = await requestJSON("GET", "/extensions", {}, {suppressPopup: true});
  if (!result.ok) {
    if (extensionsListEl) extensionsListEl.innerHTML = `<div class="list-item"><p>${htmlEscape(result.error || t("extensions_unavailable"))}</p></div>`;
    return;
  }
  renderExtensions(result);
}

async function saveExtension(extensionId) {
  const card = extensionsListEl && extensionsListEl.querySelector(`[data-extension-id="${CSS.escape(extensionId)}"]`);
  if (!card) return;
  const result = await requestJSON("POST", `/extensions/${encodeURIComponent(extensionId)}`, {config: readExtensionConfig(card)}, {errorTitle: t("failed_save_settings")});
  if (!result.ok) return;
  showError(t("extension_save"), t("extension_saved"));
  await loadExtensionsPanel();
}

async function installExtensionDependencies(extensionId) {
  const result = await requestJSON("POST", `/extensions/${encodeURIComponent(extensionId)}/install`, {}, {errorTitle: t("dependency_install_failed"), timeout: 20000});
  if (!result.ok) return;
  if (!(result.tasks || []).length) {
    await loadExtensionsPanel();
    return;
  }
  showProgress(t("extension_install_dependencies"), t("extension_install_started"));
  try {
    for (const task of result.tasks) await waitForDependencyTask(task.id);
    await loadExtensionsPanel();
    await loadDependenciesPanel();
  } catch (error) {
    showError(t("dependency_install_failed"), error.message || String(error));
  } finally {
    hideProgress();
  }
}

if (extensionsRefreshBtn) extensionsRefreshBtn.onclick = loadExtensionsPanel;

Object.assign(window, {loadExtensionsPanel});
