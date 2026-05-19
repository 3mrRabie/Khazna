/**
 * content.js — khazna Content Script
 * ───────────────────────────────────
 * Detects login forms, injects autofill triggers,
 * handles credential filling, and detects form submissions.
 */

(() => {
  "use strict";

  // Avoid double-injection
  if (window.__khazna_injected) return;
  window.__khazna_injected = true;

  // ── Constants ─────────────────────────────────────────────

  const FIELD_SELECTORS = {
    password: 'input[type="password"]',
    username: [
      'input[type="email"]',
      'input[type="text"][name*="user" i]',
      'input[type="text"][name*="login" i]',
      'input[type="text"][name*="email" i]',
      'input[type="text"][id*="user" i]',
      'input[type="text"][id*="login" i]',
      'input[type="text"][id*="email" i]',
      'input[type="text"][autocomplete="username"]',
      'input[type="text"][autocomplete="email"]',
      'input[type="text"][name*="account" i]',
    ].join(", "),
  };

  // ── Form Detection ────────────────────────────────────────

  function findLoginForms() {
    const passwordFields = document.querySelectorAll(FIELD_SELECTORS.password);
    const forms = [];

    for (const pwField of passwordFields) {
      if (pwField.closest("[data-khazna-processed]")) continue;

      // Find the closest form or container
      const form = pwField.closest("form") || pwField.parentElement;
      if (!form) continue;

      // Find the associated username field
      let usernameField = form.querySelector(FIELD_SELECTORS.username);

      // Fallback: look for the text input immediately before the password field
      if (!usernameField) {
        const container = form || document.body;
        const allInputs = Array.from(container.querySelectorAll('input:not([type="hidden"]):not([type="submit"])'));
        const pwIdx = allInputs.indexOf(pwField);
        if (pwIdx > 0) {
          const prev = allInputs[pwIdx - 1];
          if (prev.type === "text" || prev.type === "email") {
            usernameField = prev;
          }
        }
      }

      form.setAttribute("data-khazna-processed", "true");
      forms.push({ form, usernameField, passwordField: pwField });
    }

    return forms;
  }

  // ── Autofill Badge ────────────────────────────────────────

  function injectBadge(field) {
    if (field.dataset.khaznaBadge) return;
    field.dataset.khaznaBadge = "true";

    const badge = document.createElement("div");
    badge.className = "khazna-autofill-badge";
    badge.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#00d4ff" stroke-width="2">
      <path d="M12 2L3 7v5c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z"/>
      <circle cx="12" cy="12" r="2"/>
      <path d="M12 14v3"/>
    </svg>`;
    badge.title = "Autofill with khazna";

    // Position relative to the field
    const wrapper = document.createElement("div");
    wrapper.style.cssText = "position:relative;display:inline-block;width:100%;";

    field.parentNode.insertBefore(wrapper, field);
    wrapper.appendChild(field);
    wrapper.appendChild(badge);

    // Style the badge
    const style = document.createElement("style");
    style.textContent = `
      .khazna-autofill-badge {
        position: absolute;
        right: 8px;
        top: 50%;
        transform: translateY(-50%);
        width: 24px;
        height: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        border-radius: 4px;
        z-index: 999999;
        opacity: 0.6;
        transition: opacity 0.2s, background 0.2s;
      }
      .khazna-autofill-badge:hover {
        opacity: 1;
        background: rgba(0, 212, 255, 0.12);
      }
    `;
    if (!document.querySelector("#khazna-badge-styles")) {
      style.id = "khazna-badge-styles";
      document.head.appendChild(style);
    }

    badge.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      requestAutofill(badge);
    });
  }

  // ── Request autofill from desktop app ─────────────────────

  function requestAutofill(badgeElement) {
    chrome.runtime.sendMessage(
      { action: "get_logins", url: window.location.href },
      (response) => {
        if (!response || response.error) return;
        const logins = response.logins || [];
        if (logins.length === 1) {
          fillCredentials(logins[0].username, logins[0].password);
        } else if (logins.length > 1) {
          showSelector(badgeElement, logins);
        }
      }
    );
  }

  function showSelector(badge, logins) {
    // Remove any existing selector
    document.querySelectorAll('.khazna-selector').forEach(e => e.remove());
    
    const rect = badge.getBoundingClientRect();
    const selector = document.createElement("div");
    selector.className = "khazna-selector";
    selector.style.cssText = `
      position: absolute;
      top: ${rect.bottom + window.scrollY + 5}px;
      left: ${rect.right + window.scrollX - 200}px;
      width: 200px;
      max-height: 250px;
      overflow-y: auto;
      background: #0d1220;
      border: 1px solid #1e293b;
      border-radius: 6px;
      z-index: 1000000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #f1f5f9;
      padding: 4px;
    `;
    
    logins.forEach(login => {
      const item = document.createElement("div");
      item.style.cssText = `
        padding: 8px 12px;
        cursor: pointer;
        font-size: 13px;
        border-radius: 4px;
        display: flex;
        flex-direction: column;
        transition: background 0.1s;
      `;
      item.innerHTML = `
        <span style="font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
          ${login.site_name || "Unknown"}
        </span>
        <span style="font-size:11px; color:#94a3b8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
          ${login.username || "—"}
        </span>
      `;
      item.onmouseover = () => item.style.background = "#1e293b";
      item.onmouseout = () => item.style.background = "transparent";
      item.onclick = (e) => {
        e.stopPropagation();
        fillCredentials(login.username, login.password);
        selector.remove();
      };
      selector.appendChild(item);
    });
    
    document.body.appendChild(selector);
    
    // Close on outside click
    setTimeout(() => {
      const closer = (e) => {
        if (!selector.contains(e.target)) {
          selector.remove();
          document.removeEventListener("click", closer);
        }
      };
      document.addEventListener("click", closer);
    }, 10);
  }

  // ── Fill credentials into detected fields ─────────────────

  function fillCredentials(username, password) {
    const forms = findLoginForms();
    // Also check previously processed forms
    const allPwFields = document.querySelectorAll(FIELD_SELECTORS.password);

    for (const pwField of allPwFields) {
      const form = pwField.closest("form") || pwField.parentElement;
      let userField = form?.querySelector(FIELD_SELECTORS.username);

      // Fallback: find text input before password
      if (!userField && form) {
        const container = form || document.body;
        const inputs = Array.from(container.querySelectorAll('input:not([type="hidden"]):not([type="submit"])'));
        const idx = inputs.indexOf(pwField);
        if (idx > 0 && (inputs[idx-1].type === "text" || inputs[idx-1].type === "email")) {
          userField = inputs[idx - 1];
        }
      }

      if (userField && username) {
        setFieldValue(userField, username);
      }
      setFieldValue(pwField, password);
    }
  }

  /**
   * Set a field's value in a way that triggers React/Vue/Angular change detection.
   */
  function setFieldValue(field, value) {
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value"
    )?.set;

    if (nativeSetter) {
      nativeSetter.call(field, value);
    } else {
      field.value = value;
    }

    field.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
    field.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    field.dispatchEvent(new Event("blur", { bubbles: true, composed: true }));
  }

  // ── Message Listener (from background/popup) ──────────────

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "fill_credentials") {
      fillCredentials(msg.username, msg.password);
      sendResponse({ status: "ok" });
    }
    if (msg.action === "copy_to_clipboard") {
      navigator.clipboard.writeText(msg.text).catch(() => {
        // Fallback: textarea method
        const ta = document.createElement("textarea");
        ta.value = msg.text;
        ta.style.cssText = "position:fixed;left:-9999px;";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
      });
      sendResponse({ status: "ok" });
    }
    return true; // keep channel open for async responses
  });

  // ── Initialize + SPA Observer ─────────────────────────────

  function scanPage() {
    const forms = findLoginForms();
    for (const { passwordField } of forms) {
      injectBadge(passwordField);
    }
  }

  // Initial scan
  scanPage();

  // Watch for dynamically added forms (SPA support)
  let scanTimer = null;
  const observer = new MutationObserver((mutations) => {
    let shouldScan = false;
    for (const m of mutations) {
      if (m.addedNodes.length > 0) { shouldScan = true; break; }
    }
    if (shouldScan) {
      clearTimeout(scanTimer);
      scanTimer = setTimeout(scanPage, 100);
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });
})();
