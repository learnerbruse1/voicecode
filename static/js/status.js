async function pollModelStatus(force = false) {
  try {
    const resp = await fetch("/status");
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText || "Failed to read status");
    const state = data.model_state || {};
    if (state.error && (force || !shownModelErrors.has(state.error))) {
      shownModelErrors.add(state.error);
      showError(state.status === "ready" ? t("model_warning") : t("model_unavailable"), state.error);
    }
    if (state.status === "ready") { setStatus("connected", "connected"); return true; }
    if (state.status === "loading") { setStatus("processing", "loading_model"); return false; }
    if (state.error) { setStatus("error", "model_unavailable"); return true; }
    return false;
  } catch (e) {
    showError(t("failed_load_settings"), e.message || String(e));
    return true;
  }
}

async function updateStats() {
  try {
    const s = await fetch("/stats").then(r => r.json());
    const devLabel = s.device === "cuda" ? t("stats_gpu") : "CPU";
    const parts = [];
    parts.push(`${t("stats_inference")}: <b>${devLabel}</b> (${s.compute_type})`);
    parts.push(`${t("stats_model")}: ${s.model}`);
    parts.push(`${t("stats_cpu")}: ${s.cpu_percent}%`);
    parts.push(`${t("stats_ram")}: ${s.ram_mb}MB`);
    if (s.gpu) {
      if (s.gpu.util >= 0) parts.push(`${t("stats_gpu")}: ${s.gpu.util}% | ${t("stats_vram")}: ${s.gpu.mem_used}/${s.gpu.mem_total}MB`);
      if (s.gpu.name) parts.push(`${s.gpu.name}`);
    }
    perfEl.innerHTML = parts.join(" &nbsp;|&nbsp; ");
  } catch (e) {}
}
