/* SaylientAI content script (Manifest V3, declarative).
 *
 * Loaded (in order) after lib/redact.js, lib/extract.js and
 * lib/util.js, whose globals this file uses. It does NOT read the DOM
 * on load and starts no observer in the background: at load it only
 * registers chrome.runtime listeners. It reads page text only after
 * an explicit "saylient-extract" message from the open side panel,
 * and starts its MutationObserver only after "saylient-activate".
 * When the panel's port disconnects, the observer is disconnected.
 * Nothing runs when the panel is closed.
 *
 * It never reads input[type=password], payment fields or hidden
 * elements (see lib/extract.js), and it never sends a message: the
 * only write it performs is inserting text into a compose box after
 * an explicit, confirmed Insert click from the panel — never pressing
 * Enter, never clicking Send, never submitting anything.
 */
(function () {
  'use strict';

  var extractLib = typeof SaylientExtract !== 'undefined' ? SaylientExtract : null;

  var active = false;
  var observer = null;
  var panelPort = null;
  var changeTimer = null;
  var lastExtractedNormalized = '';

  function deactivate() {
    active = false;
    if (observer) {
      try { observer.disconnect(); } catch (e) { /* ignore */ }
      observer = null;
    }
    if (changeTimer !== null) {
      clearTimeout(changeTimer);
      changeTimer = null;
    }
  }

  function notifyChangeSoon() {
    // Coalesce mutation bursts into one notification. No DOM is read
    // here: the panel decides whether to re-extract.
    if (changeTimer !== null) return;
    changeTimer = setTimeout(function () {
      changeTimer = null;
      if (panelPort) {
        try { panelPort.postMessage({ type: 'saylient-content-changed' }); } catch (e) { /* ignore */ }
      }
    }, 300);
  }

  function activate() {
    if (active) return;
    active = true;
    if (typeof MutationObserver === 'undefined') return;
    if (!document.body) return;
    try {
      observer = new MutationObserver(function () {
        notifyChangeSoon();
      });
      observer.observe(document.body, {
        childList: true,
        characterData: true,
        subtree: true,
      });
    } catch (e) {
      observer = null;
    }
  }

  function extractNow() {
    if (!extractLib) return { text: '', source: 'empty', truncated: false, platform: null };
    var result = extractLib.extractConversation(document, window, window.location.hostname);
    lastExtractedNormalized = extractLib.normalizeText(result.text);
    return {
      text: result.text,
      source: result.source,
      truncated: result.truncated,
      platformName: result.platform ? result.platform.name : null,
      platformKind: result.platform ? result.platform.kind : 'unknown',
    };
  }

  function findComposeBox() {
    var selectors = extractLib
      ? extractLib.composeSelectorsFor(window.location.hostname)
      : ['div[contenteditable="true"]', 'textarea'];
    for (var i = 0; i < selectors.length; i++) {
      var nodes = null;
      try {
        nodes = document.querySelectorAll(selectors[i]);
      } catch (e) {
        continue;
      }
      for (var j = 0; j < nodes.length; j++) {
        var el = nodes[j];
        if (extractLib && !extractLib.isVisibleNode(el, window)) continue;
        if (extractLib && extractLib.shouldSkipNode(el)) continue;
        return el;
      }
    }
    return null;
  }

  // Insert text into the compose box only. Never submits, never
  // presses Enter, never clicks Send.
  function insertIntoComposeBox(text) {
    var box = findComposeBox();
    if (!box) return { ok: false, reason: 'no-compose-box' };
    try {
      box.focus({ preventScroll: false });
    } catch (e) {
      try { box.focus(); } catch (e2) { /* ignore */ }
    }
    var inserted = false;
    try {
      inserted = document.execCommand('insertText', false, text);
    } catch (e) {
      inserted = false;
    }
    if (!inserted) {
      try {
        var tag = String(box.tagName || '').toUpperCase();
        if (tag === 'TEXTAREA' || tag === 'INPUT') {
          var setter = null;
          try {
            var proto = tag === 'TEXTAREA'
              ? window.HTMLTextAreaElement.prototype
              : window.HTMLInputElement.prototype;
            var descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
            setter = descriptor && descriptor.set;
          } catch (e) { /* ignore */ }
          if (setter) setter.call(box, text);
          else box.value = text;
          box.dispatchEvent(new window.Event('input', { bubbles: true }));
          inserted = true;
        } else if (box.isContentEditable) {
          var selection = window.getSelection();
          if (selection && selection.rangeCount > 0) {
            var range = selection.getRangeAt(0);
            range.deleteContents();
            range.insertNode(document.createTextNode(text));
            range.collapse(false);
            selection.removeAllRanges();
            selection.addRange(range);
          } else {
            box.appendChild(document.createTextNode(text));
          }
          box.dispatchEvent(new window.InputEvent('input', { bubbles: true }));
          inserted = true;
        }
      } catch (e) {
        inserted = false;
      }
    }
    if (!inserted) return { ok: false, reason: 'insert-failed' };
    return { ok: true };
  }

  function handleExtractMessage(message, sendResponse) {
    if (!message || typeof message.type !== 'string') return false;
    if (message.type === 'saylient-extract') {
      var result = extractNow();
      sendResponse(result);
      return false;
    }
    if (message.type === 'saylient-activate') {
      activate();
      sendResponse({ ok: true });
      return false;
    }
    if (message.type === 'saylient-deactivate') {
      deactivate();
      sendResponse({ ok: true });
      return false;
    }
    if (message.type === 'saylient-insert') {
      var res = insertIntoComposeBox(String(message.text || ''));
      sendResponse(res);
      return false;
    }
    return false;
  }

  // The ONLY work done at load: register listeners. No DOM reads,
  // no observer, no extraction.
  if (typeof chrome !== 'undefined' && chrome.runtime) {
    chrome.runtime.onMessage.addListener(function (message, sender, sendResponse) {
      return handleExtractMessage(message, sendResponse);
    });

    chrome.runtime.onConnect.addListener(function (port) {
      if (!port || port.name !== 'saylient-panel') return;
      panelPort = port;
      port.onMessage.addListener(function (message) {
        if (!message || typeof message.type !== 'string') return;
        if (message.type === 'saylient-activate') {
          activate();
        } else if (message.type === 'saylient-deactivate') {
          deactivate();
        } else if (message.type === 'saylient-extract') {
          var result = extractNow();
          try {
            port.postMessage({
              type: 'saylient-extract-result',
              requestId: message.requestId || null,
              text: result.text,
              source: result.source,
              truncated: result.truncated,
              platformName: result.platformName,
              platformKind: result.platformKind,
            });
          } catch (e) { /* ignore */ }
        }
      });
      port.onDisconnect.addListener(function () {
        // Panel closed: stop observing immediately. Zero extraction
        // and zero API calls happen after this point.
        if (panelPort === port) panelPort = null;
        deactivate();
      });
    });
  }
})();
