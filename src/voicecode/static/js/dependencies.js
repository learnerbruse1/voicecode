var dependencyTaskState = {};

﻿function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
}

function translatedDependency(dep, field) {
  const safeId = String(dep.id || "").replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "");
  const key = `dependency_${safeId}_${field}`;
  const translated = t(key);
  return translated === key ? (dep[field] || "") : translated;
}

function renderDependencyProgress(dep, task) {
  const pct = task ? Math.max(0, Math.min(100, Number(task.progress || 0))) : 0;
  const message = task ? escapeHtml(task.message || task.status || "") : "";
  const visible = task && !["completed", "failed", "cancelled"].includes(task.status);
  return `<div class="dependency-progress ${visible ? "active" : ""}" aria-label="${escapeHtml(t("dependency_progress"))}"><div class="dependency-progress-bar" style="width:${pct}%"></div></div><small class="dependency-progress-text">${message}</small>`;
}

function dependencyActionLabel(dep) {
  if (dep.installed_in_voice_dep) return t("dependency_installed");
  if (dep.installed) return t("dependency_install_isolated");
  return t("dependency_install");
}

function reloadAfterDependencyChange() {
  try { window.sessionStorage.setItem("voicecode.activeView", "dependencies"); }
  catch (_) { /* ignore unavailable sessionStorage */ }
  window.setTimeout(() => window.location.reload(), 600);
}

function renderDependencies(data, taskByDependency = {}) {
  if (!dependenciesListEl) return;
  if (dependencyDirEl) dependencyDirEl.textContent = `${t("dependency_install_dir")}: ${data.install_dir || "VOICE_DEP"}`;
  const deps = data.dependencies || [];
  if (!deps.length) {
    dependenciesListEl.innerHTML = `<div class="list-item"><p>${t("dependencies_empty")}</p></div>`;
    return;
  }
  dependenciesListEl.innerHTML = deps.map(dep => {
    const task = taskByDependency[dep.id];
    const installed = dep.installed ? "installed" : "missing";
    const missing = (dep.missing_modules || []).join(", ");
    const features = (dep.feature_ids || []).join(", ");
    const busy = task && !["completed", "failed", "cancelled"].includes(task.status);
    const disabled = busy || dep.installed_in_voice_dep ? "disabled" : "";
    const uninstallVisible = dep.installed_in_voice_dep ? "" : "hidden";
    const cancelButton = busy ? `<button type="button" class="sm danger dependency-cancel-btn" data-task-id="${escapeHtml(task.id)}">${t("dependency_cancel")}</button>` : "";
    const installHint = dep.github_preferred ? t("dependency_github_preferred") : t("dependency_pypi_source");
    const depName = translatedDependency(dep, "name") || dep.name;
    const depDescription = translatedDependency(dep, "description") || dep.description;
    const depNotes = translatedDependency(dep, "notes") || dep.notes || installHint;
    return `<article class="dependency-card ${installed}" data-dependency-id="${escapeHtml(dep.id)}">
      <div class="dependency-main">
        <div>
          <h4>${escapeHtml(depName)} <small>${dep.installed ? t("available") : t("missing_deps")}</small></h4>
          <p>${escapeHtml(depDescription)}</p>
          <small>${escapeHtml(depNotes)}</small>
          ${features ? `<small>${t("dependency_features")}: ${escapeHtml(features)}</small>` : ""}
          ${missing ? `<small class="dependency-missing">${t("missing_deps")}: ${escapeHtml(missing)}</small>` : ""}
        </div>
        <div class="dependency-actions">
          <button type="button" class="sm dependency-install-btn" data-dependency-id="${escapeHtml(dep.id)}" ${disabled}>${dependencyActionLabel(dep)}</button>
          ${cancelButton}
          <button type="button" class="sm danger dependency-uninstall-btn ${uninstallVisible}" data-dependency-id="${escapeHtml(dep.id)}" data-confirm="false">${t("dependency_uninstall")}</button>
        </div>
      </div>
      ${renderDependencyProgress(dep, task)}
    </article>`;
  }).join("");

  dependenciesListEl.querySelectorAll(".dependency-install-btn").forEach(btn => {
    btn.onclick = () => startDependencyInstall(btn.dataset.dependencyId);
  });
  dependenciesListEl.querySelectorAll(".dependency-uninstall-btn").forEach(btn => {
    btn.onclick = () => uninstallDependency(btn);
  });
  dependenciesListEl.querySelectorAll(".dependency-cancel-btn").forEach(btn => {
    btn.onclick = () => cancelDependencyTask(btn.dataset.taskId);
  });
}

export async function loadDependenciesPanel(taskByDependency = null) {
  const [r, taskResult] = await Promise.all([
    requestJSON("GET", "/dependencies", {}, {errorTitle: t("request_failed"), suppressPopup: true}),
    taskByDependency ? Promise.resolve(null) : requestJSON("GET", "/dependencies/tasks", {}, {suppressPopup: true})
  ]);
  if (!dependenciesListEl) return;
  if (!r.ok) {
    dependenciesListEl.innerHTML = `<div class="list-item"><p>${escapeHtml(r.error || "Dependencies unavailable")}</p></div>`;
    return;
  }
  const taskMap = taskByDependency || dependencyTaskState;
  if (taskResult && taskResult.ok) {
    for (const task of taskResult.tasks || []) {
      if (!["completed", "failed", "cancelled"].includes(task.status) && !taskMap[task.dependency_id]) {
        taskMap[task.dependency_id] = task;
        dependencyTaskState[task.dependency_id] = task;
      }
    }
  }
  renderDependencies(r, taskMap);
}

async function cancelDependencyTask(taskId) {
  if (!taskId) return;
  const result = await requestJSON("POST", `/dependencies/tasks/${encodeURIComponent(taskId)}/cancel`, {}, {errorTitle: t("dependency_cancel_failed")});
  if (result.ok) await loadDependenciesPanel();
}

async function pollDependencyTask(taskId, dependencyId) {
  for (;;) {
    const r = await requestJSON("GET", `/dependencies/tasks/${encodeURIComponent(taskId)}`, {}, {suppressPopup: true, timeout: 10000});
    if (!r.ok) {
      showError(t("dependency_install_failed"), r.error || t("request_failed"));
      delete dependencyTaskState[dependencyId];
      await loadDependenciesPanel();
      return;
    }
    dependencyTaskState[dependencyId] = r.task;
    await loadDependenciesPanel(dependencyTaskState);
    if (["completed", "failed", "cancelled"].includes(r.task.status)) {
      if (r.task.status === "failed") showError(t("dependency_install_failed"), r.task.error || r.task.message || t("operation_failed"));
      if (r.task.status === "cancelled") showError(t("dependency_cancel"), t("dependency_cancelled"));
      if (r.task.status === "completed" && r.task.restart_required) showError(t("dependency_restart_required"), t("dependency_restart_required_detail"));
      delete dependencyTaskState[dependencyId];
      await loadDependenciesPanel();
      if (typeof loadExtensionsPanel === "function") await loadExtensionsPanel();
      if (typeof loadAudioDevices === "function") await loadAudioDevices();
      await pollModelStatus(true);
      return;
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

async function startDependencyInstall(dependencyId) {
  if (!dependencyId) return;
  const r = await requestJSON("POST", `/dependencies/${encodeURIComponent(dependencyId)}/install`, {}, {errorTitle: t("dependency_install_failed"), timeout: 20000});
  if (!r.ok || !r.task) return;
  await pollDependencyTask(r.task.id, dependencyId);
}

async function uninstallDependency(btn) {
  const dependencyId = btn.dataset.dependencyId;
  if (!dependencyId) return;
  if (btn.dataset.confirm !== "true") {
    btn.dataset.confirm = "true";
    btn.textContent = t("dependency_confirm_uninstall");
    setTimeout(() => {
      if (btn.dataset.confirm === "true") {
        btn.dataset.confirm = "false";
        btn.textContent = t("dependency_uninstall");
      }
    }, 5000);
    return;
  }
  const r = await requestJSON("POST", `/dependencies/${encodeURIComponent(dependencyId)}/uninstall`, {confirm: true}, {errorTitle: t("dependency_uninstall_failed"), timeout: 60000});
  if (!r.ok) return;
  await loadDependenciesPanel();
  if (typeof loadExtensionsPanel === "function") await loadExtensionsPanel();
  await pollModelStatus(true);
  reloadAfterDependencyChange();
}

export async function warnMissingDependenciesOnce() {
  if (shownDependencyWarning) return false;
  const onboardingVisible = document.getElementById("onboarding-overlay")?.classList.contains("show");
  if (onboardingVisible) return false;
  const r = await requestJSON("GET", "/dependencies", {}, {suppressPopup: true, timeout: 10000});
  if (!r.ok) return false;
  const missing = r.action_required_missing || [];
  if (!missing.length) return false;
  shownDependencyWarning = true;
  const names = missing.map(dep => `${dep.name}: ${(dep.missing_modules || []).join(", ")}`).join("\n");
  showError(t("dependency_missing_title"), `${t("dependency_missing_detail")}\n\n${names}\n\n${t("dependency_missing_action")}`);
}

if (dependenciesRefreshBtn) dependenciesRefreshBtn.onclick = () => loadDependenciesPanel();

export async function waitForDependencyTask(taskId, timeoutMs = 600000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const result = await requestJSON("GET", `/dependencies/tasks/${encodeURIComponent(taskId)}`, {}, {suppressPopup: true, timeout: 10000});
    if (!result.ok) throw new Error(result.error || t("request_failed"));
    const task = result.task || {};
    updateProgress(`${task.progress || 0}% ? ${task.message || task.status || ""}`);
    if (task.status === "completed") return task;
    if (task.status === "failed") throw new Error(task.error || task.message || t("dependency_install_failed"));
    if (task.status === "cancelled") throw new Error(t("dependency_cancelled"));
    await new Promise(resolve => setTimeout(resolve, 800));
  }
  throw new Error(t("request_timeout_detail"));
}


export async function resumeDependencyTasks() {
  const result = await requestJSON("GET", "/dependencies/tasks", {}, {suppressPopup: true});
  if (!result.ok) return;
  const active = (result.tasks || []).filter(task => !["completed", "failed", "cancelled"].includes(task.status));
  if (active.length) {
    await loadDependenciesPanel();
    for (const task of active) pollDependencyTask(task.id, task.dependency_id);
  }
}

const dependenciesInstallRequiredBtn = document.getElementById("dependencies-install-required");
if (dependenciesInstallRequiredBtn) dependenciesInstallRequiredBtn.onclick = async () => {
  const result = await requestJSON("POST", "/dependencies/install-required", {}, {errorTitle: t("dependency_install_failed"), timeout: 20000});
  if (!result.ok) return;
  if (!(result.tasks || []).length) { await loadDependenciesPanel(); return; }
  showProgress(t("dependency_install_all_required"), t("onboarding_installing"));
  try {
    for (const task of result.tasks) await waitForDependencyTask(task.id);
    await loadDependenciesPanel();
  } catch (error) {
    showError(t("dependency_install_failed"), error.message || String(error));
  } finally {
    hideProgress();
  }
};

Object.assign(window, {loadDependenciesPanel, warnMissingDependenciesOnce, waitForDependencyTask, resumeDependencyTasks});
