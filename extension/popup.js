/**
 * popup.js — khazna Extension Popup Logic
 * ────────────────────────────────────────
 * Handles vault status, credential listing, search,
 * autofill triggers, and copy actions.
 */

// ── DOM References ─────────────────────────────

const $ = (sel) => document.querySelector(sel);

const dom = {
  dot:        $("#status-dot"),
  offline:    $("#state-offline"),
  locked:     $("#state-locked"),
  unlocked:   $("#state-unlocked"),
  search:     $("#search"),
  list:       $("#logins-list"),
  empty:      $("#empty-state"),
  toast:      $("#toast"),
  footer:     $("#footer-text"),
};

let allLogins = [];
let currentUrl = "";

// ── Init ───────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  // Get current tab URL
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentUrl = tab?.url || "";
  } catch { /* ignore */ }

  await checkStatus();

  dom.search.addEventListener("input", () => filterLogins(dom.search.value));
});

// ── Status Check ───────────────────────────────

async function checkStatus() {
  try {
    const resp = await sendMessage({ action: "status" });

    if (resp.error) {
      showState("offline");
      return;
    }

    if (!resp.is_initialized) {
      showState("offline");
      dom.offline.querySelector(".state-title").textContent = "Vault not set up";
      dom.offline.querySelector(".state-sub").textContent = "Create a vault in the desktop app first.";
      return;
    }

    if (resp.is_locked) {
      showState("locked");
      return;
    }

    showState("unlocked");
    await loadLogins();

  } catch (err) {
    console.error("[khazna popup] status check failed:", err);
    showState("offline");
  }
}

// ── State Switching ────────────────────────────

function showState(state) {
  dom.offline.classList.add("hidden");
  dom.locked.classList.add("hidden");
  dom.unlocked.classList.add("hidden");

  switch (state) {
    case "offline":
      dom.dot.className = "dot dot-offline";
      dom.dot.title = "Disconnected";
      dom.offline.classList.remove("hidden");
      break;
    case "locked":
      dom.dot.className = "dot dot-locked";
      dom.dot.title = "Vault locked";
      dom.locked.classList.remove("hidden");
      break;
    case "unlocked":
      dom.dot.className = "dot dot-online";
      dom.dot.title = "Connected";
      dom.unlocked.classList.remove("hidden");
      break;
  }
}

// ── Load Credentials ───────────────────────────

async function loadLogins() {
  if (!currentUrl) {
    dom.empty.classList.remove("hidden");
    return;
  }

  try {
    const resp = await sendMessage({ action: "get_logins", url: currentUrl });

    if (resp.error) {
      if (resp.error === "locked") {
        showState("locked");
      }
      return;
    }

    allLogins = resp.logins || [];
    renderLogins(allLogins);

  } catch (err) {
    console.error("[khazna popup] load logins failed:", err);
  }
}

// ── Render ─────────────────────────────────────

function renderLogins(logins) {
  dom.list.innerHTML = "";

  if (logins.length === 0) {
    dom.empty.classList.remove("hidden");
    return;
  }

  dom.empty.classList.add("hidden");

  for (const login of logins) {
    const card = document.createElement("div");
    card.className = "login-card";

    const initial = (login.site_name || "?")[0];

    card.innerHTML = `
      <div class="login-favicon">${escapeHtml(initial)}</div>
      <div class="login-info">
        <div class="login-site">${escapeHtml(login.site_name || "Unknown")}</div>
        <div class="login-user">${escapeHtml(login.username || "—")}</div>
      </div>
      <div class="login-actions">
        <button class="btn-icon btn-fill" data-action="autofill" title="Autofill">
          ⚡
        </button>
        <button class="btn-icon" data-action="copy-user" title="Copy username">
          👤
        </button>
        <button class="btn-icon" data-action="copy-pass" title="Copy password">
          🔑
        </button>
      </div>
    `;

    // Event delegation for buttons
    card.querySelector('[data-action="autofill"]').addEventListener("click", () => {
      doAutofill(login.username, login.password);
    });

    card.querySelector('[data-action="copy-user"]').addEventListener("click", () => {
      copyText(login.username, "Username copied");
    });

    card.querySelector('[data-action="copy-pass"]').addEventListener("click", () => {
      copyText(login.password, "Password copied");
    });

    dom.list.appendChild(card);
  }
}

// ── Search / Filter ────────────────────────────

let searchTimer = null;

function filterLogins(query) {
  const q = query.toLowerCase().trim();
  if (!q) {
    renderLogins(allLogins);
    return;
  }
  
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async () => {
    try {
      const resp = await sendMessage({ action: "search", query: q });
      if (resp.error) return;
      renderLogins(resp.logins || []);
    } catch (err) {
      console.error(err);
    }
  }, 300);
}

// ── Actions ────────────────────────────────────

async function doAutofill(username, password) {
  await sendMessage({ action: "autofill", username, password });
  showToast("Credentials filled");
  // Close popup after brief delay
  setTimeout(() => window.close(), 600);
}

async function copyText(text, label) {
  try {
    await navigator.clipboard.writeText(text);
    showToast(label);
  } catch {
    // Fallback: ask content script
    await sendMessage({ action: "copy", text });
    showToast(label);
  }
}

// ── Toast ──────────────────────────────────────

let toastTimer = null;

function showToast(message) {
  dom.toast.textContent = message;
  dom.toast.classList.remove("hidden");
  // Force reflow for animation
  void dom.toast.offsetWidth;
  dom.toast.classList.add("visible");

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    dom.toast.classList.remove("visible");
    setTimeout(() => dom.toast.classList.add("hidden"), 200);
  }, 1800);
}

// ── Helpers ────────────────────────────────────

function sendMessage(msg) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(msg, (resp) => {
      resolve(resp || { error: "no_response" });
    });
  });
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
