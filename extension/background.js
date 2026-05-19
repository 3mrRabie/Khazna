/**
 * background.js — khazna Service Worker
 * ──────────────────────────────────────
 * Handles communication between the browser extension and the
 * khazna desktop app via Chrome Native Messaging + HTTP fallback.
 */

const HOST_NAME   = "com.khazna.bridge";
const HTTP_URL    = "http://127.0.0.1:27584";
const TIMEOUT_MS  = 5000;

// ── Transport Layer ───────────────────────────────────────────

/**
 * Send a request to the desktop app.
 * Tries native messaging first, falls back to HTTP POST.
 */
async function sendToDesktop(message) {
  try {
    return await sendNative(message);
  } catch (nativeErr) {
    console.warn("[khazna] Native messaging failed, trying HTTP:", nativeErr.message);
    try {
      return await sendHTTP(message);
    } catch (httpErr) {
      console.error("[khazna] HTTP fallback also failed:", httpErr.message);
      return { error: "connection_failed", detail: nativeErr.message };
    }
  }
}

/** Native messaging (primary transport). */
function sendNative(message) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("native_timeout")), TIMEOUT_MS);
    try {
      chrome.runtime.sendNativeMessage(HOST_NAME, message, (response) => {
        clearTimeout(timer);
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response || { error: "empty_response" });
        }
      });
    } catch (err) {
      clearTimeout(timer);
      reject(err);
    }
  });
}

/** HTTP fallback (for when native messaging manifest isn't installed). */
async function sendHTTP(message) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const resp = await fetch(HTTP_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message),
      signal: controller.signal,
    });
    return await resp.json();
  } finally {
    clearTimeout(timer);
  }
}

// ── API Methods ───────────────────────────────────────────────

async function getStatus() {
  return sendToDesktop({ command: "status" });
}

async function getLogins(url) {
  return sendToDesktop({ command: "get_logins", url });
}

// ── Message Router (popup & content scripts) ──────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.action) {
        case "status":
          sendResponse(await getStatus());
          break;

        case "get_logins":
          sendResponse(await getLogins(msg.url));
          break;

        case "search":
          sendResponse(await sendToDesktop({ command: "search", query: msg.query }));
          break;

        case "autofill": {
          // Forward credentials to the content script in the active tab
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab?.id) {
            chrome.tabs.sendMessage(tab.id, {
              action: "fill_credentials",
              username: msg.username,
              password: msg.password,
            }).catch(() => {});
          }
          sendResponse({ status: "ok" });
          break;
        }

        case "copy": {
          // Service workers can't access clipboard directly;
          // use offscreen document or forward to content script
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tab?.id) {
            chrome.tabs.sendMessage(tab.id, {
              action: "copy_to_clipboard",
              text: msg.text,
            }).catch(() => {});
          }
          sendResponse({ status: "ok" });
          break;
        }

        default:
          sendResponse({ error: "unknown_action" });
      }
    } catch (err) {
      sendResponse({ error: err.message });
    }
  })();
  return true; // keep channel open for async sendResponse
});

// ── Badge: show vault status on icon ──────────────────────────

async function updateBadge() {
  try {
    const status = await getStatus();
    if (status.error) {
      chrome.action.setBadgeText({ text: "!" });
      chrome.action.setBadgeBackgroundColor({ color: "#ff4444" });
    } else if (status.is_locked) {
      chrome.action.setBadgeText({ text: "🔒" });
      chrome.action.setBadgeBackgroundColor({ color: "#ff9800" });
    } else {
      chrome.action.setBadgeText({ text: "" });
    }
  } catch {
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#ff4444" });
  }
}

// Check status periodically using alarms instead of setInterval for MV3 compatibility
chrome.alarms.create("badge_update", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "badge_update") {
    updateBadge();
  }
});

updateBadge();
