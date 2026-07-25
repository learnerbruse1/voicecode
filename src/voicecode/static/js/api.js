export function localApiToken() {
  const meta = document.querySelector('meta[name="voicecode-api-token"]');
  return meta ? meta.getAttribute("content") || "" : "";
}

function apiErrorDetails(data, fallback) {
  const lines = [data.user_message || data.error || fallback || t("request_failed")];
  if (data.technical_details && data.technical_details !== lines[0]) {
    lines.push("", `${t("technical_details")}: ${data.technical_details}`);
  }
  if (Array.isArray(data.suggestions) && data.suggestions.length) {
    const suggestions = data.suggestions.map(item => {
      const translated = t(`model_suggestion_${item}`);
      return translated === `model_suggestion_${item}` ? item.replaceAll("_", " ") : translated;
    });
    lines.push("", `${t("suggestions")}:`, ...suggestions.map(item => `? ${item}`));
  }
  if (data.request_id) lines.push("", `${t("request_id")}: ${data.request_id}`);
  return lines.join("\n");
}

export async function requestJSON(method, url, body = {}, opts = {}) {
  const controller = new AbortController();
  const timeout = opts.timeout || 30000;
  const timer = setTimeout(() => controller.abort(), timeout);
  if (opts.abortable) currentRequest = controller;
  const headers = {"Content-Type": "application/json"};
  const token = localApiToken();
  if (method !== "GET" && token) headers["X-VoiceCode-Token"] = token;
  try {
    const resp = await fetch(url, {
      method,
      headers,
      body: method === "GET" ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const message = apiErrorDetails(data, resp.statusText || t("request_failed"));
      if (!opts.suppressPopup) showError(opts.errorTitle || t("request_failed"), message);
      return {...data, ok: false, http_status: resp.status, error: data.error || message, display_error: message};
    }
    return {...data, ok: true, http_status: resp.status};
  } catch (e) {
    if (e.name === "AbortError") {
      const message = `${t("request_timeout_detail")}\n\n${method} ${url} ? ${timeout}ms`;
      if (!opts.silentAbort && !opts.suppressPopup) showError(opts.timeoutTitle || t("request_timeout"), message);
      return {ok: false, aborted: true, error: t("request_aborted"), display_error: message};
    }
    const message = `${t("network_error_detail")}\n\n${method} ${url}\n${e.message || String(e)}`;
    if (!opts.suppressPopup) showError(opts.networkTitle || t("network_error"), message);
    return {ok: false, error: "Network error", display_error: message};
  } finally {
    clearTimeout(timer);
    if (currentRequest === controller) currentRequest = null;
  }
}

Object.assign(window, {localApiToken, requestJSON});
