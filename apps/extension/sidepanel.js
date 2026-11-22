/* SaylientAI side panel.
 *
 * Auto-analyze: on open, the panel asks the content script for the
 * conversation text and calls POST /v1/analyze then POST /v1/suggest
 * — no Analyze click is needed. While open, content changes
 * re-analyze automatically (debounced 800 ms, only if the text
 * changed, at most one API round per 3 seconds). If the user edits
 * the textarea, auto re-analysis never overwrites the edit; a
 * "New messages detected" affordance appears instead.
 *
 * Nothing is sent without redaction: the textarea always shows the
 * redacted text that is sent. Nothing is ever auto-sent or
 * auto-inserted: Copy needs a click, Insert needs two clicks.
 * All page-derived and API text is rendered with textContent only.
 */
(function () {
  'use strict';

  var TONES = ['polite', 'friendly', 'firm', 'formal'];
  var MAX_CHARS = 2000;
  var DEBOUNCE_MS = 800;
  var MIN_ROUND_GAP_MS = 3000;
  var INSERT_ARM_MS = 5000;
  var FEEDBACK_KEY = 'saylientFeedback';
  var PAUSED_KEY = 'saylientPaused';
  var THEME_KEY = 'saylientTheme';

  var redact = (typeof SaylientRedact !== 'undefined') ? SaylientRedact.redactText : function (s) { return s; };
  var extractLib = (typeof SaylientExtract !== 'undefined') ? SaylientExtract : null;
  var utilLib = (typeof SaylientUtil !== 'undefined') ? SaylientUtil : null;

  function $(id) { return document.getElementById(id); }

  var els = {};
  ['statusLine', 'extractedText', 'charCount', 'extractionHint', 'reanalyzeBtn',
   'clearBtn', 'newMessagesBtn', 'pauseToggle', 'goalInput', 'skeleton',
   'errorBox', 'errorMessage', 'retryBtn', 'emptyBox', 'resultsBox',
   'analysisLine', 'scoreValue', 'scenarioValue', 'strategyValue',
   'explanationText', 'engineLine', 'replyCards', 'regenerateBtn',
   'settingsDetails', 'apiBaseInput', 'saveApiBtn', 'apiSavedNote',
   'themeToggle', 'themeLabel'].forEach(function (id) { els[id] = $(id); });

  var state = {
    tabId: null,
    port: null,
    tone: 'polite',
    dirty: false,
    paused: false,
    inFlight: false,
    pendingRound: false,
    pendingAuto: false,
    lastSentNormalized: '',
    lastAnalyze: null,
    currentSuggestionId: null,
    apiBaseUrl: 'http://localhost:8000',
  };

  var roundThrottle = utilLib ? utilLib.createThrottle(MIN_ROUND_GAP_MS) : null;
  var lastRoundStartMs = 0;

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  function setStatus(message) {
    els.statusLine.textContent = message;
  }

  function updateCharCount() {
    els.charCount.textContent = els.extractedText.value.length + ' / ' + MAX_CHARS;
  }

  function show(el) { el.hidden = false; }
  function hide(el) { el.hidden = true; }

  function showSkeleton() {
    show(els.skeleton);
    hide(els.errorBox);
    hide(els.emptyBox);
    hide(els.resultsBox);
  }

  function hideSkeleton() {
    hide(els.skeleton);
  }

  function normalize(s) {
    return extractLib ? extractLib.normalizeText(s) : String(s || '').trim();
  }

  function goalValue() {
    var goal = els.goalInput.value.trim();
    return goal ? goal.slice(0, 300) : null;
  }

  function requestBody(text) {
    var body = { text: text, tone: state.tone };
    var goal = goalValue();
    if (goal) body.goal = goal;
    return body;
  }

  function sendRuntimeMessage(message) {
    return new Promise(function (resolve) {
      try {
        chrome.runtime.sendMessage(message, function (response) {
          if (chrome.runtime.lastError) resolve(null);
          else resolve(response || null);
        });
      } catch (e) {
        resolve(null);
      }
    });
  }

  function apiCall(endpoint, body) {
    return sendRuntimeMessage({ type: 'saylient-api', endpoint: endpoint, body: body });
  }

  function relayToTab(message) {
    if (state.tabId === null) return Promise.resolve(null);
    return sendRuntimeMessage({ type: 'saylient-relay', tabId: state.tabId, message: message });
  }

  function engineLine(source, llmStatus) {
    if (source === 'llm') {
      return 'Engine: LLM' + (llmStatus && llmStatus !== 'ok' ? ' (' + llmStatus + ')' : '');
    }
    if (source === 'rule_based') {
      return 'Engine: rule-based' + (llmStatus ? ' — LLM status: ' + llmStatus : '');
    }
    return 'Engine: ' + (source || 'unknown');
  }

  function errorEnvelopeMessage(data) {
    if (data && data.error && typeof data.error.message === 'string' && data.error.message.trim()) {
      return data.error.message.trim();
    }
    return null;
  }

  function showError(result, fallbackMessage) {
    hideSkeleton();
    hide(els.resultsBox);
    hide(els.emptyBox);
    var message = fallbackMessage;
    if (result && result.kind === 'network') {
      message = 'The API could not be reached. Check that the API is running and that the API base URL in Settings is correct.';
    } else if (result && result.status === 401) {
      message = 'Sign-in is not available in this build. The extension works without sign-in, but the API asked for one. Please try again later.';
    } else if (result && result.status === 429) {
      message = 'Too many requests. Please wait a little and try again. Auto-analyze has been paused.';
      setPaused(true);
    } else if (result && result.status === 503) {
      message = 'The suggestion service is unavailable right now (model unavailable). Please try again later.';
    } else if (result && (result.status === 400 || result.status === 422 || result.status === 413)) {
      message = errorEnvelopeMessage(result.data)
        || 'The text could not be processed. Please shorten it and try again.';
    } else if (result && result.status) {
      message = errorEnvelopeMessage(result.data)
        || ('The API returned an error (status ' + result.status + '). Please try again.');
    }
    els.errorMessage.textContent = message;
    show(els.errorBox);
    setStatus('Could not get suggestions.');
  }

  function showEmpty() {
    hideSkeleton();
    hide(els.errorBox);
    hide(els.resultsBox);
    show(els.emptyBox);
    setStatus('No conversation text found.');
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(
        function () { return true; },
        function () { return copyTextFallback(text); },
      );
    }
    return Promise.resolve(copyTextFallback(text));
  }

  function copyTextFallback(text) {
    try {
      var temp = document.createElement('textarea');
      temp.value = text;
      temp.setAttribute('readonly', '');
      temp.style.position = 'fixed';
      temp.style.opacity = '0';
      document.body.appendChild(temp);
      temp.select();
      var ok = document.execCommand('copy');
      document.body.removeChild(temp);
      return !!ok;
    } catch (e) {
      return false;
    }
  }

  function storeFeedback(suggestionId, tone, rating, reason) {
    return new Promise(function (resolve) {
      try {
        chrome.storage.local.get([FEEDBACK_KEY], function (stored) {
          var all = (stored && stored[FEEDBACK_KEY]) || {};
          var entry = all[suggestionId] || { suggestion_id: suggestionId, ratings: {} };
          entry.ratings[tone] = { rating: rating, reason: reason || '', at: Date.now() };
          all[suggestionId] = entry;
          var toSet = {};
          toSet[FEEDBACK_KEY] = all;
          chrome.storage.local.set(toSet, function () { resolve(true); });
        });
      } catch (e) {
        resolve(false);
      }
    });
  }

  function buildReplyCard(reply, suggestionId) {
    var card = document.createElement('article');
    card.className = 'reply-card';

    var heading = document.createElement('h3');
    heading.textContent = 'Tone: ' + reply.tone;
    card.appendChild(heading);

    var body = document.createElement('p');
    body.textContent = reply.text;
    card.appendChild(body);

    var actions = document.createElement('div');
    actions.className = 'reply-actions';

    var note = document.createElement('span');
    note.className = 'action-note';
    note.setAttribute('aria-live', 'polite');

    var copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.className = 'small-btn';
    copyBtn.textContent = 'Copy';
    copyBtn.addEventListener('click', function () {
      copyText(reply.text).then(function (ok) {
        note.textContent = ok ? 'Copied.' : 'Copy failed — select the text manually.';
      });
    });
    actions.appendChild(copyBtn);

    var insertBtn = document.createElement('button');
    insertBtn.type = 'button';
    insertBtn.className = 'small-btn';
    insertBtn.textContent = 'Insert';
    var armed = false;
    var armTimer = null;
    function disarm() {
      armed = false;
      insertBtn.textContent = 'Insert';
      insertBtn.classList.remove('btn-armed');
      if (armTimer !== null) { clearTimeout(armTimer); armTimer = null; }
    }
    insertBtn.addEventListener('click', function () {
      if (!armed) {
        armed = true;
        insertBtn.textContent = 'Click again to insert';
        insertBtn.classList.add('btn-armed');
        setStatus('Press Insert again within 5 seconds to insert this reply into the compose box. Nothing will be sent.');
        armTimer = setTimeout(disarm, INSERT_ARM_MS);
        return;
      }
      disarm();
      relayToTab({ type: 'saylient-insert', text: reply.text }).then(function (res) {
        var inner = res && res.response;
        if (inner && inner.ok) {
          note.textContent = 'Inserted into the compose box. Nothing was sent.';
        } else {
          note.textContent = 'Could not find a compose box on this page.';
        }
      });
    });
    actions.appendChild(insertBtn);
    actions.appendChild(note);
    card.appendChild(actions);

    var feedbackRow = document.createElement('div');
    feedbackRow.className = 'feedback-row';
    var fbLabel = document.createElement('span');
    fbLabel.className = 'fb-label';
    fbLabel.textContent = 'Was this helpful?';
    feedbackRow.appendChild(fbLabel);

    var reasonInput = document.createElement('input');
    reasonInput.type = 'text';
    reasonInput.maxLength = 300;
    reasonInput.placeholder = 'Reason (optional)';
    reasonInput.setAttribute('aria-label', 'Reason for feedback on the ' + reply.tone + ' reply (optional)');
    feedbackRow.appendChild(reasonInput);

    function feedbackButton(rating, label) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'small-btn';
      btn.textContent = label;
      btn.setAttribute('aria-pressed', 'false');
      btn.setAttribute('aria-label', 'Mark the ' + reply.tone + ' reply as ' + rating);
      btn.addEventListener('click', function () {
        storeFeedback(suggestionId, reply.tone, rating, reasonInput.value.trim()).then(function () {
          btn.setAttribute('aria-pressed', 'true');
          fbNote.textContent = 'Saved. Feedback is stored only in this browser.';
        });
      });
      return btn;
    }
    var upBtn = feedbackButton('up', 'Thumbs up');
    var downBtn = feedbackButton('down', 'Thumbs down');
    feedbackRow.appendChild(upBtn);
    feedbackRow.appendChild(downBtn);
    card.appendChild(feedbackRow);

    var fbNote = document.createElement('p');
    fbNote.className = 'feedback-note';
    fbNote.textContent = 'Feedback is stored only in this browser.';
    card.appendChild(fbNote);

    return card;
  }

  function renderResults(analyzeData, suggestData) {
    hideSkeleton();
    hide(els.errorBox);
    hide(els.emptyBox);

    var replies = suggestData && Array.isArray(suggestData.replies) ? suggestData.replies : [];
    if (replies.length === 0) {
      showError(null, 'The API returned no suggestions. Please try again.');
      return;
    }

    var score = Math.round(Number(suggestData.score));
    if (!Number.isFinite(score)) score = 0;
    score = Math.max(0, Math.min(100, score));
    els.scoreValue.textContent = String(score);
    els.scenarioValue.textContent = suggestData.scenario || '—';
    els.strategyValue.textContent = suggestData.strategy || '—';
    els.explanationText.textContent = suggestData.explanation || '';
    els.engineLine.textContent = engineLine(suggestData.source, suggestData.llm_status);

    var analysisParts = [];
    if (analyzeData) {
      if (analyzeData.face_threat) analysisParts.push('Face threat: ' + analyzeData.face_threat);
      if (analyzeData.detected_strategy) analysisParts.push('Detected strategy: ' + analyzeData.detected_strategy);
      if (Array.isArray(analyzeData.issues) && analyzeData.issues.length > 0) {
        analysisParts.push('Issues: ' + analyzeData.issues.join('; '));
      }
    }
    els.analysisLine.textContent = analysisParts.join(' · ');

    state.currentSuggestionId = suggestData.suggestion_id || null;
    var suggestionId = state.currentSuggestionId || 'local-' + Date.now();
    while (els.replyCards.firstChild) els.replyCards.removeChild(els.replyCards.firstChild);
    replies.forEach(function (reply) {
      var safeReply = {
        tone: TONES.indexOf(reply.tone) !== -1 ? reply.tone : 'polite',
        text: String(reply.text || ''),
      };
      els.replyCards.appendChild(buildReplyCard(safeReply, suggestionId));
    });

    show(els.resultsBox);
    setStatus('Suggestions ready.');
  }

  // One full API round: analyze, then suggest. Enforces the 3-second
  // minimum gap between rounds.
  function runRound() {
    if (state.inFlight) {
      state.pendingRound = true;
      return Promise.resolve();
    }
    var text = els.extractedText.value;
    if (!normalize(text)) {
      showEmpty();
      return Promise.resolve();
    }
    // What is sent is what is shown: redact before sending, and show
    // the redacted text in the textarea.
    var redacted = redact(text);
    if (redacted !== text) {
      els.extractedText.value = redacted;
      updateCharCount();
      text = redacted;
    }
    state.inFlight = true;
    showSkeleton();
    setStatus('Generating suggestions…');

    var waitForGap = Promise.resolve();
    if (roundThrottle) {
      waitForGap = (function () {
        function poll() {
          if (roundThrottle.allows(Date.now())) {
            roundThrottle.mark(Date.now());
            return Promise.resolve();
          }
          return sleep(100).then(poll);
        }
        return poll();
      })();
    } else {
      var now = Date.now();
      if (now - lastRoundStartMs < MIN_ROUND_GAP_MS) {
        waitForGap = sleep(MIN_ROUND_GAP_MS - (now - lastRoundStartMs));
      }
      lastRoundStartMs = now;
    }

    return waitForGap
      .then(function () {
        var body = requestBody(text);
        return apiCall('analyze', body);
      })
      .then(function (analyzeResult) {
        if (!analyzeResult || !analyzeResult.ok) {
          showError(analyzeResult, 'Could not analyze the conversation. Please try again.');
          return null;
        }
        state.lastAnalyze = analyzeResult.data;
        var body = requestBody(text);
        return apiCall('suggest', body).then(function (suggestResult) {
          if (!suggestResult || !suggestResult.ok) {
            showError(suggestResult, 'Could not get suggestions. Please try again.');
            return null;
          }
          state.lastSentNormalized = normalize(text);
          renderResults(state.lastAnalyze, suggestResult.data);
          return true;
        });
      })
      .catch(function () {
        showError({ kind: 'network', status: 0, data: null });
      })
      .then(function () {
        state.inFlight = false;
        if (state.pendingRound) {
          state.pendingRound = false;
          runRound();
        }
      });
  }

  // Suggest-only round (Regenerate): reuses the last analysis.
  function runSuggestOnly() {
    var text = els.extractedText.value;
    if (!normalize(text)) {
      showEmpty();
      return Promise.resolve();
    }
    if (!state.lastAnalyze) return runRound();
    var redacted = redact(text);
    if (redacted !== text) {
      els.extractedText.value = redacted;
      updateCharCount();
      text = redacted;
    }
    state.inFlight = true;
    showSkeleton();
    setStatus('Regenerating suggestions…');
    return apiCall('suggest', requestBody(text))
      .then(function (result) {
        if (!result || !result.ok) {
          showError(result, 'Could not get suggestions. Please try again.');
          return;
        }
        state.lastSentNormalized = normalize(text);
        renderResults(state.lastAnalyze, result.data);
      })
      .catch(function () {
        showError({ kind: 'network', status: 0, data: null });
      })
      .then(function () { state.inFlight = false; });
  }

  function extractFromTab() {
    return relayToTab({ type: 'saylient-extract' }).then(function (res) {
      if (!res || !res.ok || !res.response) return null;
      return res.response;
    });
  }

  function applyExtraction(result, hintText) {
    if (!result || !normalize(result.text)) return false;
    var redacted = redact(result.text);
    els.extractedText.value = redacted;
    updateCharCount();
    state.dirty = false;
    els.extractionHint.textContent = hintText || '';
    if (result.truncated) {
      els.extractionHint.textContent = (hintText ? hintText + ' ' : '') + 'Text was truncated to the most recent 2000 characters.';
    }
    return true;
  }

  function doAutoReextract() {
    return extractFromTab().then(function (result) {
      if (!result || !normalize(result.text)) return;
      var redacted = redact(result.text);
      if (!extractLib || !extractLib.normalizedChanged(state.lastSentNormalized, redacted)) return;
      if (state.dirty) {
        // Never overwrite the user's edit; offer the affordance.
        state.pendingAuto = true;
        show(els.newMessagesBtn);
        return;
      }
      applyExtraction(result, '');
      runRound();
    });
  }

  var debouncedAutoReextract = utilLib
    ? utilLib.debounce(function () { doAutoReextract(); }, DEBOUNCE_MS)
    : function () { doAutoReextract(); };

  function scheduleAutoReanalyze() {
    if (state.paused || state.dirty) {
      state.pendingAuto = true;
      show(els.newMessagesBtn);
      return;
    }
    debouncedAutoReextract();
  }

  function setPaused(value) {
    state.paused = !!value;
    els.pauseToggle.checked = state.paused;
    try {
      chrome.storage.session.set({ [PAUSED_KEY]: state.paused });
    } catch (e) { /* storage unavailable: pause still applies in memory */ }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    var isDark = theme === 'dark';
    els.themeToggle.setAttribute('aria-pressed', String(isDark));
    els.themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
    els.themeLabel.textContent = isDark ? 'Light' : 'Dark';
  }

  function preferredTheme() {
    try {
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
    } catch (e) { /* ignore */ }
    return 'light';
  }

  function initTheme() {
    var theme = preferredTheme();
    try {
      chrome.storage.local.get([THEME_KEY], function (stored) {
        if (stored && (stored[THEME_KEY] === 'dark' || stored[THEME_KEY] === 'light')) {
          theme = stored[THEME_KEY];
        }
        applyTheme(theme);
      });
    } catch (e) {
      applyTheme(theme);
    }
  }

  function loadSettings() {
    sendRuntimeMessage({ type: 'saylient-get-config' }).then(function (res) {
      if (res && res.apiBaseUrl) {
        state.apiBaseUrl = res.apiBaseUrl;
        els.apiBaseInput.value = res.apiBaseUrl;
      }
    });
    try {
      chrome.storage.session.get([PAUSED_KEY], function (stored) {
        if (stored && typeof stored[PAUSED_KEY] === 'boolean') {
          state.paused = stored[PAUSED_KEY];
          els.pauseToggle.checked = state.paused;
        }
      });
    } catch (e) { /* ignore */ }
  }

  function openPort() {
    if (state.tabId === null) return;
    try {
      state.port = chrome.tabs.connect(state.tabId, { name: 'saylient-panel' });
      state.port.onMessage.addListener(function (message) {
        if (message && message.type === 'saylient-content-changed') {
          scheduleAutoReanalyze();
        }
      });
      state.port.postMessage({ type: 'saylient-activate' });
    } catch (e) {
      state.port = null;
    }
  }

  function closePort() {
    if (state.port) {
      try { state.port.disconnect(); } catch (e) { /* ignore */ }
      state.port = null;
    }
  }

  function initialExtractAndAnalyze() {
    return extractFromTab().then(function (result) {
      if (!result) {
        // No content script on this page (e.g. a browser page): the
        // user can paste text manually and press Re-analyze.
        showEmpty();
        els.extractionHint.textContent = 'This page cannot be read by the extension. Paste text above, or open a conversation page.';
        setStatus('This page cannot be read. Paste text to get suggestions.');
        return;
      }
      var platformNote = '';
      if (result.platformName) {
        platformNote = result.platformKind === 'per-site'
          ? 'Read from ' + result.platformName + '.'
          : 'Read from ' + result.platformName + ' (generic text).';
      }
      if (!applyExtraction(result, platformNote)) {
        showEmpty();
        return;
      }
      runRound();
    });
  }

  function init() {
    updateCharCount();
    initTheme();
    loadSettings();

    if (typeof chrome === 'undefined' || !chrome.tabs || !chrome.runtime) {
      showError(null, 'Extension APIs are unavailable in this context.');
      return;
    }

    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      var tab = tabs && tabs[0];
      if (!tab || typeof tab.id !== 'number') {
        showEmpty();
        return;
      }
      state.tabId = tab.id;
      var url = tab.url || '';
      if (/^(chrome|about|edge|brave|opera):/.test(url)) {
        showEmpty();
        els.extractionHint.textContent = 'Browser pages cannot be read. Paste text above, or open a conversation page.';
        return;
      }
      openPort();
      initialExtractAndAnalyze();
    });

    window.addEventListener('pagehide', closePort);
    window.addEventListener('beforeunload', closePort);

    els.extractedText.addEventListener('input', function () {
      state.dirty = true;
      updateCharCount();
    });

    els.reanalyzeBtn.addEventListener('click', function () {
      hide(els.newMessagesBtn);
      state.pendingAuto = false;
      if (!normalize(els.extractedText.value)) {
        initialExtractAndAnalyze();
        return;
      }
      state.dirty = false;
      runRound();
    });

    els.newMessagesBtn.addEventListener('click', function () {
      hide(els.newMessagesBtn);
      state.pendingAuto = false;
      state.dirty = false;
      doAutoReextract();
    });

    els.clearBtn.addEventListener('click', function () {
      els.extractedText.value = '';
      updateCharCount();
      state.dirty = false;
      state.lastSentNormalized = '';
      state.pendingAuto = false;
      hide(els.newMessagesBtn);
      hide(els.resultsBox);
      hide(els.errorBox);
      hide(els.emptyBox);
      els.extractionHint.textContent = '';
      setStatus('Cleared. Paste text or press Re-analyze to read the page again.');
    });

    els.retryBtn.addEventListener('click', function () {
      if (!normalize(els.extractedText.value)) {
        initialExtractAndAnalyze();
        return;
      }
      runRound();
    });

    els.regenerateBtn.addEventListener('click', function () {
      runSuggestOnly();
    });

    els.pauseToggle.addEventListener('change', function () {
      setPaused(els.pauseToggle.checked);
      if (!state.paused && state.pendingAuto) {
        state.pendingAuto = false;
        hide(els.newMessagesBtn);
        doAutoReextract();
      }
      setStatus(state.paused ? 'Auto-analyze paused.' : 'Auto-analyze resumed.');
    });

    document.querySelectorAll('.tone').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var tone = btn.getAttribute('data-tone');
        if (TONES.indexOf(tone) === -1) return;
        state.tone = tone;
        document.querySelectorAll('.tone').forEach(function (b) {
          b.setAttribute('aria-pressed', String(b === btn));
        });
        if (normalize(els.extractedText.value)) {
          runRound();
        }
      });
    });

    els.themeToggle.addEventListener('click', function () {
      var current = document.documentElement.getAttribute('data-theme') || 'light';
      var next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      try {
        chrome.storage.local.set({ [THEME_KEY]: next });
      } catch (e) { /* ignore */ }
    });

    els.saveApiBtn.addEventListener('click', function () {
      var raw = els.apiBaseInput.value.trim();
      try {
        var url = new URL(raw);
        if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error('protocol');
      } catch (e) {
        els.apiSavedNote.textContent = 'Enter a valid http(s) URL.';
        return;
      }
      sendRuntimeMessage({ type: 'saylient-set-config', apiBaseUrl: raw }).then(function (res) {
        if (res && res.ok) {
          state.apiBaseUrl = res.apiBaseUrl;
          els.apiBaseInput.value = res.apiBaseUrl;
          els.apiSavedNote.textContent = 'Saved.';
        } else {
          els.apiSavedNote.textContent = 'Could not save the API URL.';
        }
      });
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && els.settingsDetails.open) {
        els.settingsDetails.open = false;
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
