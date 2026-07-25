function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!value) return "0 MB";
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`;
  return `${(value / 1024 ** 2).toFixed(1)} MB`;
}

function modelCacheSummary(cache) {
  if (cache?.partial) return `${t("model_cache_partial")} (${formatBytes(cache.size_bytes)})`;
  if (!cache || !cache.cached) return t("model_cache_missing");
  return `${t("model_cache_cached")} (${formatBytes(cache.size_bytes)})`;
}

function renderManagedModels(data) {
  if (!modelsListEl) return;
  if (modelsCacheDirEl) modelsCacheDirEl.textContent = `${t("model_cache_dir")}: ${data.cache_dir || "models"}`;
  const models = data.models || {};
  const cache = data.cache || {};
  const compatibility = data.compatibility || {};
  const current = data.current || "base";
  const configured = data.configured || current;
  const loaded = Boolean(data.model_loaded);
  const operationState = data.model_state || {};
  const operationActive = ["checking", "downloading", "loading"].includes(operationState.status);
  const operationInfo = operationActive ? modelOperationProgress(operationState, configured) : null;
  const operationCard = operationInfo ? `<article class="model-operation-card"><strong>${htmlEscape(operationInfo.title)}</strong><pre>${htmlEscape(operationInfo.detail)}</pre><div class="model-operation-track"><span style="width:${Math.max(0, Math.min(100, operationInfo.progress))}%"></span></div></article>` : "";
  modelsListEl.innerHTML = operationCard + Object.entries(models).map(([name, info]) => {
    const itemCache = cache[name] || {};
    const compat = compatibility[name] || {};
    const isCurrent = name === current;
    const isConfigured = name === configured;
    const vram = `${t("vram_min")}: ${compat.vram_min_gb || info.vram_min_gb || "?"}GB / ${t("vram_rec")}: ${compat.vram_recommended_gb || info.vram_recommended_gb || "?"}GB`;
    const reason = compat.reason ? `<small class="model-warning">${htmlEscape(compat.reason)}</small>` : "";
    const status = itemCache.partial ? "partial" : itemCache.cached ? "cached" : "missing";
    const active = isCurrent && loaded ? `<span class="model-badge active">${t("model_active")}</span>` : "";
    const selected = isConfigured && !(isCurrent && loaded) ? `<span class="model-badge">${t("model_selected")}</span>` : "";
    return `<article class="managed-model-card ${status}" data-model="${htmlEscape(name)}">
      <div class="managed-model-main">
        <div>
          <h4>${htmlEscape(name)} ${active}${selected}</h4>
          <p>${htmlEscape(info.description || t("model_description_default"))}</p>
          <small>${htmlEscape(info.size || "")} · ${htmlEscape(vram)}</small>
          <small>${htmlEscape(modelCacheSummary(itemCache))}</small>
          ${reason}
        </div>
        <div class="managed-model-actions">
          <button type="button" class="sm model-download-btn" data-model="${htmlEscape(name)}" ${operationActive ? "disabled" : ""}>${operationActive && operationState.target_model === name ? t("model_downloading") : itemCache.cached ? t("model_load") : t("model_download")}</button>
          <button type="button" class="sm danger model-delete-btn ${itemCache.cached ? "" : "hidden"}" data-model="${htmlEscape(name)}" data-confirm="false" ${isCurrent && loaded ? "disabled" : ""}>${t("model_delete_cache")}</button>
        </div>
      </div>
    </article>`;
  }).join("");
  modelsListEl.querySelectorAll(".model-download-btn").forEach(btn => { btn.onclick = () => downloadManagedModel(btn.dataset.model); });
  modelsListEl.querySelectorAll(".model-delete-btn").forEach(btn => { btn.onclick = () => deleteManagedModelCache(btn); });
}

async function loadModelsPanel() {
  const r = await requestJSON("GET", "/models", {}, {errorTitle: t("request_failed"), suppressPopup: true});
  if (!modelsListEl) return;
  if (!r.ok) { modelsListEl.innerHTML = `<div class="list-item"><p>${htmlEscape(r.error || t("models_unavailable"))}</p></div>`; return; }
  renderManagedModels(r);
}

async function waitForManagedModel(modelName, timeoutMs = 900000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const status = await requestJSON("GET", "/status", {}, {suppressPopup: true, timeout: 10000});
    if (!status.ok) throw Object.assign(new Error(status.error || t("request_failed")), {modelState: status});
    const state = status.model_state || {};
    const progressInfo = modelOperationProgress(state, modelName);
    updateProgress(progressInfo.detail, progressInfo.progress, progressInfo.title);
    if (state.status === "ready" && (state.target_model === modelName || status.model === modelName)) return status;
    if (state.status === "error") {
      throw Object.assign(new Error(state.user_message || state.error || t("model_unavailable")), {modelState: state});
    }
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  const timeoutState = {
    error_code: "model_client_wait_timeout",
    target_model: modelName,
    technical_details: t("request_timeout_detail"),
    suggestions: ["check_network", "retry", "use_smaller_model"],
  };
  throw Object.assign(new Error(t("request_timeout_detail")), {modelState: timeoutState});
}

async function downloadManagedModel(modelName) {
  if (!modelName) return;
  updateDownloadCenter(t("model_downloading"), `${t("model_download_detail")} ${modelName}`, null);
  const r = await requestJSON("POST", `/models/${encodeURIComponent(modelName)}/download`, {}, {errorTitle: t("model_download_failed"), timeout: 20000, suppressPopup: true});
  if (!r.ok) {
    showError(t("model_download_failed"), modelOperationErrorMessage(r));
    failDownloadCenter(t("model_download_failed"), modelOperationErrorMessage(r));
    await loadModelsPanel();
    return;
  }
  try {
    await waitForManagedModel(modelName);
    modelInfoCache = null;
    await pollModelStatus(true);
    await updateModelDescription(true);
    await loadModelsPanel();
    finishDownloadCenter(t("model_download_complete"));
  } catch (e) {
    const detail = modelOperationErrorMessage(e.modelState || {technical_details: e.message});
    showError(t("model_download_failed"), detail);
    failDownloadCenter(t("model_download_failed"), detail);
  }
}

async function deleteManagedModelCache(btn) {
  const modelName = btn.dataset.model;
  if (!modelName) return;
  if (btn.dataset.confirm !== "true") {
    btn.dataset.confirm = "true";
    btn.textContent = t("model_confirm_delete_cache");
    setTimeout(() => {
      if (btn.dataset.confirm === "true") {
        btn.dataset.confirm = "false";
        btn.textContent = t("model_delete_cache");
      }
    }, 5000);
    return;
  }
  const r = await requestJSON("DELETE", `/models/${encodeURIComponent(modelName)}/cache`, {confirm: true}, {errorTitle: t("model_delete_failed"), timeout: 60000});
  if (!r.ok) return;
  modelInfoCache = null;
  await loadModelsPanel();
  await updateModelDescription(true);
}

if (modelsRefreshBtn) modelsRefreshBtn.onclick = loadModelsPanel;
