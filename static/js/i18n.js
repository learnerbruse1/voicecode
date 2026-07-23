window.I18N = window.I18N || {};
const SUPPORTED_I18N_LANGUAGES = ["en", "zh", "ja"];

export async function ensureI18nCatalog(language) {
  const normalized = SUPPORTED_I18N_LANGUAGES.includes(language) ? language : "en";
  if (window.I18N[normalized]) return window.I18N[normalized];
  const response = await fetch(`/static/i18n/${normalized}.json`, {cache: "no-cache"});
  if (!response.ok) throw new Error(`Failed to load language catalog: ${normalized}`);
  const catalog = await response.json();
  if (!catalog || typeof catalog !== "object" || Array.isArray(catalog)) {
    throw new Error(`Invalid language catalog: ${normalized}`);
  }
  window.I18N[normalized] = catalog;
  return catalog;
}

export async function initializeI18n(language = "en") {
  await ensureI18nCatalog("en");
  if (language !== "en") await ensureI18nCatalog(language);
}

Object.assign(window, {ensureI18nCatalog, initializeI18n});
