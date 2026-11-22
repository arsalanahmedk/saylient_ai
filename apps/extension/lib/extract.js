/* SaylientAI extension — pure extraction logic (no chrome APIs).
 *
 * Operates on duck-typed document/window objects so the same code runs
 * against the real DOM (via content/extractor.js) and against a
 * hand-rolled fake DOM in Node tests. Nothing here reads the DOM on
 * load; every function runs only when the caller asks for extraction.
 *
 * Priority (EXTENSION_SPEC §3, amended): (1) user text selection,
 * (2) last 8 messages in known chat containers, (3) visible main text.
 * The tail of the text wins when truncating: the most recent words
 * are the ones that matter for a reply.
 */

(function (global) {
  'use strict';

  var MAX_EXTRACT_CHARS = 2000;
  var MAX_MESSAGES = 8;
  var TRUNCATION_MARKER = '\u2026 (truncated) ';

  // Per-site adapters for the 5 spec platforms only. Best effort: if a
  // layout changes, the selectors simply match nothing and extraction
  // falls back gracefully to visible text. No selectors are defined
  // for the other 9 claimed platforms — they use the generic fallback.
  var PLATFORMS = [
    {
      name: 'Gmail',
      domains: ['mail.google.com'],
      messageSelectors: ['.a3s.aiL', '.a3s'],
      textSelector: null,
      composeSelectors: [
        'div[aria-label="Message Body"]',
        '.Am.Al.editable',
        'div[contenteditable="true"][aria-label*="Message"]',
        '[contenteditable="true"].editable',
      ],
    },
    {
      name: 'LinkedIn',
      domains: ['linkedin.com'],
      messageSelectors: [
        '.msg-s-message-list__event',
        '.msg-s-event-listitem',
        '.msg-thread__message',
      ],
      textSelector: '.msg-s-event-listitem__body, .msg-s-message-list__event-body',
      composeSelectors: [
        '.msg-form__contenteditable',
        'div[contenteditable="true"][data-placeholder]',
        '.msg-form__textarea',
      ],
    },
    {
      name: 'Upwork',
      domains: ['upwork.com'],
      messageSelectors: [
        '[data-test="chat-message"]',
        '.up-chat-message',
        '.chat-message',
      ],
      textSelector: null,
      composeSelectors: [
        '[data-test="chat-input"]',
        'div[contenteditable="true"]',
        'textarea[placeholder]',
      ],
    },
    {
      name: 'Fiverr',
      domains: ['fiverr.com'],
      messageSelectors: [
        '[data-testid="message-bubble"]',
        '.msg-body',
        '.conversation-message',
        '.message-item',
      ],
      textSelector: null,
      composeSelectors: ['[contenteditable="true"]', 'textarea'],
    },
    {
      name: 'WhatsApp Web',
      domains: ['web.whatsapp.com'],
      messageSelectors: [
        '#main .message-in',
        '#main .message-out',
        '#main [data-testid="msg-container"]',
      ],
      textSelector: '.selectable-text, .copyable-text',
      composeSelectors: [
        '#main footer div[contenteditable="true"]',
        'div[contenteditable="true"][data-tab]',
        '#main [contenteditable="true"]',
      ],
    },
  ];

  // The other 9 claimed platforms: generic fallback only (selection,
  // then visible text). No per-site selectors, no per-site claims.
  var GENERIC_PLATFORMS = [
    { name: 'Instagram', domains: ['instagram.com'] },
    { name: 'Messenger', domains: ['messenger.com'] },
    { name: 'Telegram', domains: ['web.telegram.org', 'telegram.org'] },
    { name: 'Snapchat', domains: ['web.snapchat.com', 'snapchat.com'] },
    { name: 'TikTok', domains: ['tiktok.com'] },
    { name: 'Discord', domains: ['discord.com'] },
    { name: 'X', domains: ['x.com', 'twitter.com'] },
    { name: 'Slack', domains: ['slack.com'] },
    { name: 'Teams', domains: ['teams.microsoft.com', 'teams.live.com'] },
  ];

  function hostnameMatches(hostname, domain) {
    return hostname === domain || hostname.slice(-(domain.length + 1)) === '.' + domain;
  }

  function matchPlatform(hostname) {
    var host = String(hostname || '').toLowerCase();
    for (var i = 0; i < PLATFORMS.length; i++) {
      for (var j = 0; j < PLATFORMS[i].domains.length; j++) {
        if (hostnameMatches(host, PLATFORMS[i].domains[j])) {
          return { kind: 'per-site', name: PLATFORMS[i].name, config: PLATFORMS[i] };
        }
      }
    }
    for (var k = 0; k < GENERIC_PLATFORMS.length; k++) {
      for (var m = 0; m < GENERIC_PLATFORMS[k].domains.length; m++) {
        if (hostnameMatches(host, GENERIC_PLATFORMS[k].domains[m])) {
          return { kind: 'generic', name: GENERIC_PLATFORMS[k].name, config: null };
        }
      }
    }
    return { kind: 'unknown', name: null, config: null };
  }

  // Collapse runs of spaces/tabs, tidy spaces around newlines, drop
  // blank lines. Single newlines (message boundaries) are preserved.
  function normalizeText(text) {
    return String(text == null ? '' : text)
      .replace(/[ \t\r\f\v]+/g, ' ')
      .replace(/ *\n */g, '\n')
      .replace(/\n{2,}/g, '\n')
      .trim();
  }

  function normalizedChanged(prev, next) {
    return normalizeText(prev) !== normalizeText(next);
  }

  // Tail wins: keep the most recent characters, with an honest marker.
  function truncateTail(text, maxChars) {
    var max = maxChars || MAX_EXTRACT_CHARS;
    var normalized = normalizeText(text);
    if (normalized.length <= max) return { text: normalized, truncated: false };
    var tailLength = max - TRUNCATION_MARKER.length;
    if (tailLength <= 0) return { text: normalized.slice(-max), truncated: true };
    return { text: TRUNCATION_MARKER + normalized.slice(-tailLength), truncated: true };
  }

  function isVisibleNode(node, winLike) {
    if (!node) return false;
    if (node.hidden) return false;
    try {
      if (node.getAttribute && node.getAttribute('aria-hidden') === 'true') return false;
    } catch (e) { /* ignore */ }
    var style = node.style;
    if (style && (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse')) {
      return false;
    }
    if (winLike && typeof winLike.getComputedStyle === 'function') {
      try {
        var cs = winLike.getComputedStyle(node);
        if (cs && (cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse')) {
          return false;
        }
      } catch (e) { /* ignore: fall through to rect check */ }
    }
    if (typeof node.getBoundingClientRect === 'function') {
      try {
        var rect = node.getBoundingClientRect();
        if (rect && rect.width === 0 && rect.height === 0) return false;
      } catch (e) { /* ignore */ }
    } else if ('offsetParent' in node) {
      if (node.offsetParent === null && (node.tagName || '').toUpperCase() !== 'BODY') return false;
    }
    return true;
  }

  // Never read password or payment fields, scripts/styles, or hidden
  // subtrees. This is checked per node before any text is taken.
  function shouldSkipNode(node) {
    if (!node) return true;
    var tag = String(node.tagName || '').toUpperCase();
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEMPLATE') return true;
    if (tag === 'INPUT' || tag === 'TEXTAREA') {
      var type = String(node.type || '').toLowerCase();
      if (type === 'password') return true;
      var autocomplete = '';
      try {
        autocomplete = String(node.getAttribute ? node.getAttribute('autocomplete') || '' : '').toLowerCase();
      } catch (e) { /* ignore */ }
      if (autocomplete.indexOf('cc-') !== -1 || autocomplete === 'cc-number' || autocomplete === 'cc-csc') return true;
      var nameId = '';
      try {
        nameId = String((node.getAttribute && (node.getAttribute('name') || node.getAttribute('id'))) || '').toLowerCase();
      } catch (e) { /* ignore */ }
      if (/(card|cvv|cvc|password|passwd)/.test(nameId)) return true;
    }
    return false;
  }

  function nodeText(node, winLike) {
    if (shouldSkipNode(node) || !isVisibleNode(node, winLike)) return '';
    var raw = null;
    if (typeof node.innerText === 'string') raw = node.innerText;
    else if (typeof node.textContent === 'string') raw = node.textContent;
    else return '';
    return normalizeText(raw);
  }

  function messageNodeText(node, config, winLike) {
    if (config && config.textSelector && typeof node.querySelector === 'function') {
      var child = null;
      try {
        child = node.querySelector(config.textSelector);
      } catch (e) { /* ignore */ }
      if (child) {
        var childText = nodeText(child, winLike);
        if (childText) return childText;
      }
    }
    return nodeText(node, winLike);
  }

  function collectMessageTexts(nodes, config, winLike) {
    var texts = [];
    var list = nodes || [];
    for (var i = 0; i < list.length; i++) {
      var t = messageNodeText(list[i], config, winLike);
      if (t) texts.push(t);
    }
    return texts.slice(-MAX_MESSAGES);
  }

  function safeQueryAll(docLike, selector) {
    try {
      var nodes = docLike.querySelectorAll(selector);
      if (!nodes) return [];
      return Array.prototype.slice.call(nodes);
    } catch (e) {
      return [];
    }
  }

  function safeQuery(docLike, selector) {
    try {
      return docLike.querySelector(selector);
    } catch (e) {
      return null;
    }
  }

  function extractVisibleText(docLike, winLike) {
    var main = safeQuery(docLike, 'main');
    var mainText = main ? nodeText(main, winLike) : '';
    if (mainText) return mainText;
    var body = safeQuery(docLike, 'body') || docLike.body || null;
    return body ? nodeText(body, winLike) : '';
  }

  // The only entry point. `docLike` needs querySelector/querySelectorAll
  // (and optionally .body); `winLike` needs getSelection() (optional)
  // and getComputedStyle() (optional). Returns { text, source,
  // truncated, platform } where source is one of
  // 'selection' | 'messages' | 'visible' | 'empty'.
  function extractConversation(docLike, winLike, hostname) {
    var platform = matchPlatform(hostname || '');
    var selectionText = '';
    try {
      if (winLike && typeof winLike.getSelection === 'function') {
        var sel = winLike.getSelection();
        if (sel) selectionText = normalizeText(sel.toString ? sel.toString() : '');
      }
    } catch (e) { /* ignore */ }
    if (selectionText) {
      var selResult = truncateTail(selectionText);
      return { text: selResult.text, source: 'selection', truncated: selResult.truncated, platform: platform };
    }

    if (platform.config) {
      for (var i = 0; i < platform.config.messageSelectors.length; i++) {
        var nodes = safeQueryAll(docLike, platform.config.messageSelectors[i]);
        var messages = collectMessageTexts(nodes, platform.config, winLike);
        if (messages.length > 0) {
          var joined = truncateTail(messages.join('\n'));
          return { text: joined.text, source: 'messages', truncated: joined.truncated, platform: platform };
        }
      }
    }

    var visible = extractVisibleText(docLike, winLike);
    if (visible) {
      var visResult = truncateTail(visible);
      return { text: visResult.text, source: 'visible', truncated: visResult.truncated, platform: platform };
    }
    return { text: '', source: 'empty', truncated: false, platform: platform };
  }

  function composeSelectorsFor(hostname) {
    var platform = matchPlatform(hostname || '');
    if (platform.config) return platform.config.composeSelectors.slice();
    return ['div[contenteditable="true"]', 'textarea', 'input[type="text"]'];
  }

  var api = {
    MAX_EXTRACT_CHARS: MAX_EXTRACT_CHARS,
    MAX_MESSAGES: MAX_MESSAGES,
    TRUNCATION_MARKER: TRUNCATION_MARKER,
    PLATFORMS: PLATFORMS,
    GENERIC_PLATFORMS: GENERIC_PLATFORMS,
    matchPlatform: matchPlatform,
    normalizeText: normalizeText,
    normalizedChanged: normalizedChanged,
    truncateTail: truncateTail,
    isVisibleNode: isVisibleNode,
    shouldSkipNode: shouldSkipNode,
    nodeText: nodeText,
    collectMessageTexts: collectMessageTexts,
    extractVisibleText: extractVisibleText,
    extractConversation: extractConversation,
    composeSelectorsFor: composeSelectorsFor,
  };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.SaylientExtract = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
