/* SaylientAI service worker (Manifest V3, type: module).
 *
 * Relays panel -> API fetches and panel <-> content-script messages.
 * It never reads page text itself and never logs message text: logs
 * carry only the endpoint name and the HTTP status.
 *
 * No sign-in: no Authorization header is ever sent. The API in this
 * build does not require auth; a 401 (not expected) is reported to
 * the panel, which shows a generic "sign-in is not available in this
 * build" state — never a fake login button.
 *
 * Fetch policy: 20 s timeout, one retry on a network timeout only.
 * HTTP errors (including 429) are never retried.
 */

const DEFAULT_API_BASE_URL = 'http://localhost:8000';
const FETCH_TIMEOUT_MS = 20000;
const CONFIG_KEY = 'saylientApiBaseUrl';

function normalizeBaseUrl(raw) {
  if (typeof raw !== 'string') return DEFAULT_API_BASE_URL;
  const trimmed = raw.trim().replace(/\/+$/, '');
  if (!trimmed) return DEFAULT_API_BASE_URL;
  try {
    const url = new URL(trimmed);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return DEFAULT_API_BASE_URL;
    return url.origin + (url.pathname === '/' ? '' : url.pathname);
  } catch {
    return DEFAULT_API_BASE_URL;
  }
}

async function getApiBaseUrl() {
  try {
    const stored = await chrome.storage.local.get([CONFIG_KEY]);
    return normalizeBaseUrl(stored[CONFIG_KEY]);
  } catch {
    return DEFAULT_API_BASE_URL;
  }
}

function isTimeoutError(error) {
  return error && (error.name === 'AbortError' || error.name === 'TimeoutError');
}

// One fetch attempt with a timeout. Returns { status, bodyText } or
// throws on a network failure (so the caller can decide on retry).
async function fetchOnce(url, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const bodyText = await response.text();
    return { status: response.status, bodyText };
  } finally {
    clearTimeout(timer);
  }
}

function parseBody(bodyText) {
  if (!bodyText) return null;
  try {
    return JSON.parse(bodyText);
  } catch {
    return null;
  }
}

// Call POST /v1/analyze or POST /v1/suggest. The response shape is
// always { ok, status, data } or { ok: false, kind, status, data }.
// `kind` is 'network' | 'http'. Message text is never logged.
async function callApi(endpoint, body) {
  const baseUrl = await getApiBaseUrl();
  const url = `${baseUrl}/v1/${endpoint}`;
  let attempt;
  try {
    attempt = await fetchOnce(url, body);
  } catch (error) {
    // Retry exactly once, only when the first attempt timed out.
    if (isTimeoutError(error)) {
      try {
        attempt = await fetchOnce(url, body);
      } catch (retryError) {
        console.warn('[saylient] api timeout after retry', endpoint);
        return { ok: false, kind: 'network', status: 0, data: null };
      }
    } else {
      console.warn('[saylient] api network error', endpoint);
      return { ok: false, kind: 'network', status: 0, data: null };
    }
  }
  console.info('[saylient] api response', endpoint, attempt.status);
  const data = parseBody(attempt.bodyText);
  if (attempt.status >= 200 && attempt.status < 300) {
    return { ok: true, status: attempt.status, data };
  }
  return { ok: false, kind: 'http', status: attempt.status, data };
}

async function openPanelForTab(tabId) {
  try {
    await chrome.sidePanel.open({ tabId });
  } catch (error) {
    console.warn('[saylient] sidePanel.open failed', error && error.message);
  }
}

async function getActiveTabId() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs && tabs[0] ? tabs[0].id : null;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message.type !== 'string') return false;

  if (message.type === 'saylient-api') {
    const endpoint = message.endpoint === 'analyze' || message.endpoint === 'suggest'
      ? message.endpoint
      : null;
    if (!endpoint || !message.body || typeof message.body !== 'object') {
      sendResponse({ ok: false, kind: 'http', status: 400, data: null });
      return false;
    }
    callApi(endpoint, message.body).then(sendResponse);
    return true; // async response
  }

  if (message.type === 'saylient-relay') {
    // Panel -> content script, forwarded through the worker.
    const tabId = message.tabId;
    const inner = message.message;
    if (typeof tabId !== 'number' || !inner || typeof inner.type !== 'string') {
      sendResponse({ ok: false, reason: 'bad-relay' });
      return false;
    }
    chrome.tabs.sendMessage(tabId, inner, (response) => {
      if (chrome.runtime.lastError) {
        sendResponse({ ok: false, reason: 'no-content-script' });
        return;
      }
      sendResponse({ ok: true, response: response || null });
    });
    return true; // async response
  }

  if (message.type === 'saylient-get-config') {
    getApiBaseUrl().then((apiBaseUrl) => sendResponse({ ok: true, apiBaseUrl }));
    return true;
  }

  if (message.type === 'saylient-set-config') {
    const apiBaseUrl = normalizeBaseUrl(message.apiBaseUrl);
    chrome.storage.local.set({ [CONFIG_KEY]: apiBaseUrl }).then(
      () => sendResponse({ ok: true, apiBaseUrl }),
      () => sendResponse({ ok: false }),
    );
    return true;
  }

  return false;
});

chrome.commands.onCommand.addListener(async (command) => {
  if (command !== 'open-saylient') return;
  const tabId = await getActiveTabId();
  if (tabId !== null) await openPanelForTab(tabId);
});

chrome.action.onClicked.addListener(async (tab) => {
  if (tab && typeof tab.id === 'number') await openPanelForTab(tab.id);
});

chrome.runtime.onInstalled.addListener(() => {
  // Toolbar click opens the panel; the command does the same.
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  }
});

if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
}
