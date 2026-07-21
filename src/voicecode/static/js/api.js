async function requestJSON(method, url, body = {}, opts = {}) {
  const controller = new AbortController();
  const timeout = opts.timeout || 30000;
  const timer = setTimeout(() => controller.abort(), timeout);
  if (opts.abortable) currentRequest = controller;
  try {
    const resp = await fetch(url, {
      method,
      headers: {"Content-Type": "application/json"},
      body: method === "GET" ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const message = data.error || resp.statusText || t("request_failed");
      if (!opts.suppressPopup) showError(opts.errorTitle || t("request_failed"), message);
      return {ok: false, http_status: resp.status, error: message};
    }
    return {...data, ok: true, http_status: resp.status};
  } catch (e) {
    if (e.name === "AbortError") {
      if (!opts.silentAbort) showError(opts.timeoutTitle || t("request_timeout"), t("request_timeout_detail"));
      return {ok: false, aborted: true, error: t("request_aborted")};
    }
    showError(opts.networkTitle || t("network_error"), t("network_error_detail"));
    return {ok: false, error: "Network error"};
  } finally {
    clearTimeout(timer);
    if (currentRequest === controller) currentRequest = null;
  }
}
