      (function () {
        'use strict';
        /* ============ API layer — real FastAPI backend ============
           The demo talks to the Saylient API (GET /health,
           POST /v1/suggest, POST /v1/analyze) configured in config.js
           (default http://localhost:8000, overridable with ?api=<url>).
           When the API answers, the demo always uses the real response;
           the built-in demo rewrite is only a fallback when the API is
           unreachable — never a broken error state. */
        var config = window.SAYLIENT_CONFIG || {};
        var apiBase = (config.apiBaseUrl || '').replace(/\/+$/, '');
        var apiTimeoutMs = config.apiTimeoutMs || 5000;
        try {
          var apiParam = new URLSearchParams(window.location.search).get('api');
          if (apiParam) { apiBase = apiParam.replace(/\/+$/, ''); }
        } catch (e) { /* URLSearchParams unavailable — ignore */ }
        var apiAvailable = false;
        var apiStatus = document.getElementById('apiStatus');
        function fetchWithTimeout(url, options, timeoutMs) {
          var controller = new AbortController();
          var timer = setTimeout(function () { controller.abort(); }, timeoutMs);
          var opts = options || {};
          opts.signal = controller.signal;
          return fetch(url, opts).finally(function () { clearTimeout(timer); });
        }
        function checkApi() {
          if (!apiBase) { return; }
          fetchWithTimeout(apiBase + '/health', {}, 3000).then(function (res) {
            if (!res.ok) { throw new Error('health ' + res.status); }
            return res.json();
          }).then(function (health) {
            apiAvailable = true;
            var extra = health.llm_enabled
              ? ' · live LLM (' + (health.llm_model || health.llm_provider) + ')'
              : ' · rule-based engine';
            if (apiStatus) { apiStatus.textContent = 'Connected to the Saylient API' + extra + '.'; }
          }).catch(function () {
            apiAvailable = false;
            if (apiStatus) { apiStatus.textContent = 'Demo mode — API not reachable, using the built-in demo.'; }
          });
        }
        checkApi();
        /* API tones are polite | friendly | firm | formal (docs/openapi.yaml).
           The UI's "Short" is a length preference, not a tone: request the
           polite reply and pick the shortest of the three replies instead. */
        var TONE_MAP = { professional: 'polite', friendly: 'friendly', firm: 'firm', short: 'polite' };
        function pickReply(data, tone) {
          var replies = data && data.replies;
          if (!Array.isArray(replies) || replies.length !== 3) { return null; }
          var valid = replies.filter(function (r) { return r && typeof r.text === 'string' && r.text.trim(); });
          if (valid.length !== 3) { return null; }
          if (tone === 'short') {
            return valid.slice().sort(function (a, b) { return a.text.length - b.text.length; })[0].text;
          }
          var match = valid.filter(function (r) { return r.tone === TONE_MAP[tone]; })[0];
          return match ? match.text : valid[0].text;
        }
        function suggestViaApi(text, tone) {
          return fetchWithTimeout(apiBase + '/v1/suggest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, tone: TONE_MAP[tone] }),
          }, apiTimeoutMs).then(function (res) {
            if (!res.ok) { throw new Error('suggest ' + res.status); }
            return res.json();
          });
        }
        function analyzeViaApi(text) {
          return fetchWithTimeout(apiBase + '/v1/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text }),
          }, apiTimeoutMs).then(function (res) {
            if (!res.ok) { throw new Error('analyze ' + res.status); }
            return res.json();
          });
        }

        var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        /* ============ App data ============ */
        var APPS = ['WhatsApp', 'Instagram', 'Messenger', 'Telegram', 'Snapchat', 'TikTok', 'Discord', 'X', 'Gmail', 'Slack', 'LinkedIn', 'Teams', 'Upwork', 'Fiverr'];

        var mqTrack = document.getElementById('mqTrack');
        if (mqTrack) {
          var html = '';
          for (var r = 0; r < 2; r++) {
            APPS.forEach(function (a) { html += '<span class="mq-chip neu-sm">' + a + '</span>'; });
          }
          mqTrack.innerHTML = html;
          if (reduced) { mqTrack.style.animation = 'none'; }
        }
        var appsRow = document.getElementById('appsRow');
        if (appsRow) {
          appsRow.innerHTML = APPS.map(function (a) { return '<span class="pill-chip neu-sm">' + a + '</span>'; }).join('');
        }
        var appsRowExt = document.getElementById('appsRowExt');
        if (appsRowExt) {
          appsRowExt.innerHTML = APPS.map(function (a) { return '<span class="pill-chip neu-sm">' + a + '</span>'; }).join('');
        }

        /* ============ Router ============ */
        var VIEWS = ['home', 'features', 'theory', 'about', 'extension', 'login'];
        function show(name, skipHash) {
          if (VIEWS.indexOf(name) === -1) { name = 'home'; }
          VIEWS.forEach(function (v) {
            var el = document.getElementById('view-' + v);
            if (el) { el.hidden = v !== name; }
          });
          document.querySelectorAll('.nav-link[data-nav]').forEach(function (b) {
            if (b.getAttribute('data-nav') === name) { b.setAttribute('aria-current', 'page'); }
            else { b.removeAttribute('aria-current'); }
          });
          window.scrollTo(0, 0);
          if (!skipHash) {
            try { history.replaceState(null, '', '#/' + name); } catch (e) {}
          }
          initReveals();
        }
        function scrollToId(id) {
          show('home');
          setTimeout(function () {
            var el = document.getElementById(id);
            if (el) { el.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' }); }
          }, 40);
        }
        document.addEventListener('click', function (e) {
          var navEl = e.target.closest('[data-nav]');
          if (navEl) {
            e.preventDefault();
            var mode = navEl.getAttribute('data-auth-mode');
            if (mode) { setAuthMode(mode); }
            show(navEl.getAttribute('data-nav'));
            return;
          }
          var scEl = e.target.closest('[data-scroll]');
          if (scEl) { e.preventDefault(); scrollToId(scEl.getAttribute('data-scroll')); }
        });
        var startHash = (location.hash || '').replace('#/', '').replace('#', '');
        if (VIEWS.indexOf(startHash) !== -1 && startHash !== 'home') { show(startHash, true); }

        /* ============ Rotating hero word ============ */
        var rotator = document.getElementById('rotator');
        var WORDS = ['Polished', 'Calmer', 'Clearer', 'Kinder'];
        if (rotator && !reduced) {
          var wi = 0;
          setInterval(function () {
            wi = (wi + 1) % WORDS.length;
            rotator.classList.remove('swap');
            void rotator.offsetWidth;
            rotator.textContent = WORDS[wi];
            rotator.classList.add('swap');
          }, 2600);
        }

        /* ============ Hero typewriter loop ============ */
        var DRAFT_TXT = 'hi, invoice #1048 is still unpaid. plz pay asap, its been 2 weeks';
        var OUTS = {
          professional: "Hello, I hope you're well. This is a polite reminder that invoice #1048, issued two weeks ago, is still outstanding. Could you please arrange payment at your earliest convenience? Thank you.",
          friendly: "Hi there! Just a friendly nudge — invoice #1048 from two weeks ago is still open. Whenever you get a moment, we'd really appreciate the payment. Thanks so much!",
          firm: 'Hello, invoice #1048 is now two weeks overdue. Please arrange payment promptly, and let us know once it has been settled. Thank you.',
          short: 'Hi — a quick reminder that invoice #1048 (two weeks old) is still unpaid. Please pay when you can. Thanks!'
        };
        var TONE_ORDER = ['professional', 'friendly', 'firm', 'short'];
        var typeDraft = document.getElementById('typeDraft');
        var typeOut = document.getElementById('typeOut');
        var draftCaret = document.getElementById('draftCaret');
        var outCaret = document.getElementById('outCaret');
        var mockTones = Array.prototype.slice.call(document.querySelectorAll('.mock-tone'));

        function setMockTone(tone) {
          mockTones.forEach(function (el) {
            el.classList.toggle('on', el.getAttribute('data-mtone') === tone);
          });
        }
        function typeInto(el, text, speed, done) {
          var i = 0;
          (function step() {
            if (i <= text.length) {
              el.textContent = text.slice(0, i);
              i++;
              setTimeout(step, speed);
            } else if (done) { done(); }
          })();
        }
        function heroLoop(idx) {
          var tone = TONE_ORDER[idx % TONE_ORDER.length];
          setMockTone(tone);
          typeOut.textContent = '';
          outCaret.style.display = 'none';
          draftCaret.style.display = '';
          typeInto(typeDraft, DRAFT_TXT, 34, function () {
            setTimeout(function () {
              draftCaret.style.display = 'none';
              outCaret.style.display = '';
              typeInto(typeOut, OUTS[tone], 13, function () {
                setTimeout(function () { heroLoop(idx + 1); }, 3600);
              });
            }, 650);
          });
        }
        if (typeDraft && typeOut) {
          if (reduced) {
            setMockTone('professional');
            typeDraft.textContent = DRAFT_TXT;
            typeOut.textContent = OUTS.professional;
            draftCaret.style.display = 'none';
          } else {
            heroLoop(0);
          }
        }

        /* ============ Reveal on scroll + counters ============ */
        var revealIO = null, countIO = null;
        function initReveals() {
          var pending = document.querySelectorAll('.reveal:not(.in)');
          if (reduced || !('IntersectionObserver' in window)) {
            pending.forEach(function (el) { el.classList.add('in'); });
          } else {
            if (!revealIO) {
              revealIO = new IntersectionObserver(function (entries) {
                entries.forEach(function (en) {
                  if (en.isIntersecting) { en.target.classList.add('in'); revealIO.unobserve(en.target); }
                });
              }, { threshold: 0.12 });
            }
            pending.forEach(function (el) { revealIO.observe(el); });
          }
          var counters = document.querySelectorAll('[data-count]:not([data-done])');
          counters.forEach(function (el) { el.setAttribute('data-done', '1'); });
          if (reduced || !('IntersectionObserver' in window)) {
            counters.forEach(function (el) { el.textContent = Number(el.getAttribute('data-count')).toLocaleString('en-US'); });
            return;
          }
          if (!countIO) {
            countIO = new IntersectionObserver(function (entries) {
              entries.forEach(function (en) {
                if (!en.isIntersecting) { return; }
                countIO.unobserve(en.target);
                var target = Number(en.target.getAttribute('data-count'));
                var t0 = null;
                function tick(ts) {
                  if (!t0) { t0 = ts; }
                  var p = Math.min((ts - t0) / 1300, 1);
                  en.target.textContent = Math.round(target * (1 - Math.pow(1 - p, 3))).toLocaleString('en-US');
                  if (p < 1) { requestAnimationFrame(tick); }
                }
                requestAnimationFrame(tick);
              });
            }, { threshold: 0.4 });
          }
          counters.forEach(function (el) { countIO.observe(el); });
        }
        initReveals();

        /* ============ Demo (unchanged behaviour) ============ */
        var draft = document.getElementById('draft');
        var charCount = document.getElementById('charCount');
        var polishBtn = document.getElementById('polishBtn');
        var outputText = document.getElementById('outputText');
        var copyBtn = document.getElementById('copyBtn');
        var copyNote = document.getElementById('copyNote');
        var outputMeta = document.getElementById('outputMeta');
        var toneBtns = Array.prototype.slice.call(document.querySelectorAll('.tone'));
        var currentTone = 'professional';
        var polished = '';

        var SAMPLE_KEY = 'invoice #1048';
        var SAMPLE = OUTS;

        function updateCount() { charCount.textContent = draft.value.length + ' / 2,000'; }
        draft.addEventListener('input', function () {
          updateCount();
          polished = '';
          copyBtn.disabled = true;
          copyNote.classList.remove('show');
          outputText.classList.add('placeholder');
          outputText.textContent = 'Your polished reply will appear here.';
          if (outputMeta) { outputMeta.hidden = true; outputMeta.textContent = ''; }
        });
        updateCount();

        toneBtns.forEach(function (btn) {
          btn.addEventListener('click', function () {
            currentTone = btn.getAttribute('data-tone');
            toneBtns.forEach(function (b) { b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); });
            if (polished) { runPolish(); }
          });
        });

        function clean(text) {
          var t = text.replace(/\s+/g, ' ').trim();
          t = t.replace(/\bplz\b/gi, 'please')
               .replace(/\basap\b/gi, 'as soon as possible')
               .replace(/\bu\b/gi, 'you')
               .replace(/\bthanks\b/gi, 'thank you');
          t = t.replace(/\bi\b/g, 'I');
          t = t.charAt(0).toUpperCase() + t.slice(1);
          if (!/[.!?]$/.test(t)) { t += '.'; }
          return t;
        }
        function genericRewrite(text, tone) {
          var body = clean(text);
          if (tone === 'friendly') { return 'Hi there! ' + body + ' Really appreciate it — thank you!'; }
          if (tone === 'firm') { return 'Hello, ' + body.charAt(0).toLowerCase() + body.slice(1) + ' Please confirm once this is done. Thank you.'; }
          if (tone === 'short') { return body; }
          return 'Hello, ' + body.charAt(0).toLowerCase() + body.slice(1) + ' Thank you.';
        }
        function demoRewrite(text, tone) {
          return text.toLowerCase().indexOf(SAMPLE_KEY) !== -1 ? SAMPLE[tone] : genericRewrite(text, tone);
        }
        function showResult(text, meta) {
          polished = text;
          outputText.classList.remove('placeholder');
          outputText.textContent = text;
          if (meta && outputMeta) { outputMeta.hidden = false; outputMeta.textContent = meta; }
          else if (outputMeta) { outputMeta.hidden = true; outputMeta.textContent = ''; }
          copyBtn.disabled = false;
        }
        function metaLine(data, analysis) {
          var parts = [];
          if (data && typeof data.score === 'number') { parts.push('Score ' + data.score + '/100'); }
          if (data && data.scenario) { parts.push('scenario: ' + data.scenario); }
          if (analysis && analysis.detected_strategy) { parts.push('strategy: ' + analysis.detected_strategy); }
          if (analysis && analysis.face_threat) { parts.push('face threat: ' + analysis.face_threat); }
          if (analysis && Array.isArray(analysis.issues) && analysis.issues.length) { parts.push('watch out: ' + analysis.issues.join(', ')); }
          if (data && data.source === 'llm') { parts.push('via live LLM'); }
          else if (data && data.source === 'rule_based') { parts.push('via rule-based engine'); }
          return parts.join(' · ');
        }
        var polishing = false;
        function runPolish() {
          var text = draft.value.trim();
          if (!text) {
            polished = '';
            outputText.classList.add('placeholder');
            outputText.textContent = 'Write a draft first, then polish it.';
            if (outputMeta) { outputMeta.hidden = true; outputMeta.textContent = ''; }
            copyBtn.disabled = true;
            return;
          }
          if (polishing) { return; }
          polishing = true;
          polishBtn.textContent = 'Polishing…';
          polishBtn.disabled = true;
          function finish() {
            polishBtn.textContent = 'Polish my reply';
            polishBtn.disabled = false;
            polishing = false;
          }
          if (apiAvailable) {
            suggestViaApi(text, currentTone).then(function (data) {
              var reply = pickReply(data, currentTone);
              if (!reply) { throw new Error('unexpected suggest response'); }
              showResult(reply, metaLine(data, null));
              finish();
              /* Enrich the meta line with the rule-engine analysis
                 (detected strategy, face threat, issues) — fire and
                 forget; the reply never waits on it. */
              analyzeViaApi(text).then(function (analysis) {
                if (polished) { showResult(polished, metaLine(data, analysis)); }
              }).catch(function () { /* analysis unavailable — keep the reply as is */ });
            }).catch(function () {
              /* API failed mid-session: fall back to the demo, never an error. */
              apiAvailable = false;
              if (apiStatus) { apiStatus.textContent = 'Demo mode — API stopped responding, using the built-in demo.'; }
              showResult(demoRewrite(text, currentTone), '');
              finish();
            });
          } else {
            /* Built-in demo, with the same short beat as the preview. */
            setTimeout(function () {
              showResult(demoRewrite(text, currentTone), '');
              finish();
            }, 450);
          }
        }
        polishBtn.addEventListener('click', runPolish);
        copyBtn.addEventListener('click', function () {
          if (!polished) { return; }
          function done() {
            copyNote.classList.add('show');
            setTimeout(function () { copyNote.classList.remove('show'); }, 2200);
          }
          function fallback() {
            var ta = document.createElement('textarea');
            ta.value = polished;
            ta.style.position = 'fixed'; ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); } catch (e) {}
            document.body.removeChild(ta);
            done();
          }
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(polished).then(done, fallback);
          } else { fallback(); }
        });

        /* ============ Theme toggle (dark / light, in-memory only) ============ */
        var themeToggle = document.getElementById('themeToggle');
        function currentTheme() {
          var t = document.documentElement.getAttribute('data-theme');
          if (t) { return t; }
          return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        }
        function applyTheme(theme) {
          document.documentElement.setAttribute('data-theme', theme);
          if (themeToggle) {
            var isDark = theme === 'dark';
            themeToggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
            themeToggle.setAttribute('aria-label', isDark ? 'Switch to light mode' : 'Switch to dark mode');
          }
        }
        applyTheme(currentTheme());
        if (themeToggle) {
          themeToggle.addEventListener('click', function () {
            applyTheme(currentTheme() === 'dark' ? 'light' : 'dark');
          });
        }

        /* ============ Auth (login / signup preview) ============ */
        var authForm = document.getElementById('authForm');
        var authTitle = document.getElementById('authTitle');
        var authSub = document.getElementById('authSub');
        var authSubmit = document.getElementById('authSubmit');
        var authSideTitle = document.getElementById('authSideTitle');
        var nameField = document.getElementById('nameField');
        var confirmField = document.getElementById('confirmField');
        var pwMeter = document.getElementById('pwMeter');
        var authRow = document.getElementById('authRow');
        var authNote = document.getElementById('authNote');
        var switchText = document.getElementById('switchText');
        var switchModeBtn = document.getElementById('switchMode');
        var authPass = document.getElementById('authPass');
        var authPassConfirm = document.getElementById('authPassConfirm');
        var confirmMsg = document.getElementById('confirmMsg');
        var authMode = 'login';
        var pwScore = 0;

        function setAuthMode(mode) {
          authMode = mode;
          var signup = mode === 'signup';
          authTitle.textContent = signup ? 'Create your account' : 'Log in to Saylient';
          authSub.textContent = signup ? 'Start free — set up in under a minute.' : 'Enter your details to open your workspace.';
          authSubmit.textContent = signup ? 'Create account' : 'Log in';
          authSideTitle.textContent = signup ? 'Your words, at their best.' : 'Welcome back to calmer conversations.';
          nameField.hidden = !signup;
          if (confirmField) { confirmField.hidden = !signup; }
          if (pwMeter) { pwMeter.hidden = !signup; }
          if (authPass) { authPass.setAttribute('autocomplete', signup ? 'new-password' : 'current-password'); }
          if (authPassConfirm) { authPassConfirm.required = signup; }
          authRow.style.display = signup ? 'none' : '';
          switchText.textContent = signup ? 'Already have an account?' : 'New to Saylient?';
          switchModeBtn.textContent = signup ? 'Log in' : 'Create an account';
          authNote.classList.remove('show');
          checkConfirm();
          if (authPass) { updatePwMeter(authPass.value); }
        }
        if (switchModeBtn) {
          switchModeBtn.addEventListener('click', function () {
            setAuthMode(authMode === 'login' ? 'signup' : 'login');
          });
        }
        function showAuthNote(msg) {
          authNote.textContent = msg;
          authNote.classList.add('show');
        }

        /* ---- NLP-style password strength ----
           Treats the password as natural language: counts recognisable words,
           rewards long passphrases, and penalises dictionary / common words,
           keyboard walks, sequences and repeats — not just symbol counting. */
        var COMMON_PW = ['password','password1','123456','12345678','123456789','qwerty','letmein','admin','welcome','iloveyou','monkey','dragon','football','sunshine','master','shadow','superman','saylient','saylient123'];
        var DICT_WORDS = ['password','welcome','hello','login','admin','user','love','god','secret','summer','winter','spring','autumn','orange','banana','monkey','dragon','tiger','lion','eagle','river','ocean','mountain','happy','smile','coffee','pizza','computer','internet','pakistan','india','london','paris','football','cricket','school','college','friend','family','house','water','light','night','dream','heart','stone','cloud','rain','snow','wind','fire','earth','star','moon','sun','king','queen','prince','baby','angel','sweet','honey'];
        var PW_WORDS = ['River','Mountain','Cloud','Tiger','Ocean','Forest','Lantern','Harbor','Meadow','Copper','Velvet','Juniper','Cedar','Falcon','Marble','Saffron','Willow','Ember','Compass','Breeze','Summit','Canyon','Lagoon','Orchid','Pepper','Quartz','Saddle','Timber','Umbra','Voyage','Walnut','Zephyr','Anchor','Beacon','Cinder','Delta','Elm','Flint','Garnet','Hazel','Ivory','Jasper','Kite','Linden','Mango','Nectar','Onyx','Pine','Quill','Rowan','Sage','Thyme','Umber','Violet','Wren','Yarrow','Zinc','Almond','Birch','Coral'];
        function splitWords(pw) {
          var spaced = pw.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[^A-Za-z]+/g, ' ');
          var parts = spaced.toLowerCase().split(/\s+/).filter(function (w) { return w.length >= 3; });
          return parts;
        }
        function analysePassword(pw) {
          if (!pw) { return { score: 0, bits: 0, words: 0, tip: 'NLP tip: a passphrase of 4+ real words — like a tiny sentence — is both stronger and easier to remember than random symbols.', checks: { len: false, words: false, mix: false, clean: false } }; }
          var lower = pw.toLowerCase();
          var pool = 0;
          if (/[a-z]/.test(pw)) { pool += 26; }
          if (/[A-Z]/.test(pw)) { pool += 26; }
          if (/[0-9]/.test(pw)) { pool += 10; }
          if (/[^A-Za-z0-9]/.test(pw)) { pool += 33; }
          var bits = pool ? Math.round(pw.length * (Math.log(pool) / Math.log(2))) : 0;
          var words = splitWords(pw);
          var wordCount = words.length;
          /* dictionary hits: whole split words, or a dict word buried in a short password */
          var dictHits = 0;
          words.forEach(function (w) { if (DICT_WORDS.indexOf(w) !== -1) { dictHits++; } });
          if (pw.length < 14) {
            DICT_WORDS.forEach(function (dw) { if (dw.length >= 5 && lower.indexOf(dw) !== -1 && words.indexOf(dw) === -1) { dictHits++; } });
          }
          var isCommon = COMMON_PW.indexOf(lower) !== -1 || COMMON_PW.indexOf(lower.replace(/[^a-z]/g, '')) !== -1;
          var hasRepeat = /(.)\1\1/.test(pw);
          var hasSeq = /abc|bcd|cde|def|efg|fgh|ghi|hij|ijk|jkl|klm|lmn|mno|nop|opq|pqr|qrs|rst|stu|tuv|uvw|vwx|wxy|xyz|012|123|234|345|456|567|678|789|890|qwerty|asdf|zxcv/i.test(pw);
          var mix = /[a-z]/.test(pw) && /[A-Z]/.test(pw) && /[0-9]/.test(pw) && /[^A-Za-z0-9]/.test(pw);
          var score = 0;
          if (pw.length >= 8) { score++; }
          if (pw.length >= 12) { score++; }
          if (mix || (wordCount >= 3 && pw.length >= 14)) { score++; }
          if (bits >= 65 || wordCount >= 4) { score++; }
          if (isCommon) { score = 0; }
          else if (hasSeq || hasRepeat) { score = Math.max(0, score - 1); }
          if (dictHits >= 1 && wordCount <= 2 && pw.length < 14) { score = Math.max(0, score - 1); }
          score = Math.min(4, Math.max(0, score));
          var tip = '';
          if (isCommon) { tip = 'This is one of the most common passwords — attackers try it first. Try a 4-word passphrase instead.'; }
          else if (hasSeq) { tip = 'Avoid sequences like “abc” or “123” — they are guessed in seconds. Real, unrelated words work better.'; }
          else if (hasRepeat) { tip = 'Repeated characters (“aaa”, “111”) add almost no strength. Add a different word instead.'; }
          else if (dictHits && wordCount <= 2) { tip = 'A single everyday word is easy to guess, even with numbers added. Combine 3–4 unrelated words.'; }
          else if (wordCount >= 4) { tip = 'Excellent — a multi-word passphrase. Length from real words beats short, complex strings.'; }
          else if (wordCount >= 3) { tip = 'Good passphrase shape. Add one more word, a number and a symbol to make it very strong.'; }
          else if (pw.length < 12) { tip = 'Make it longer with words you can picture — e.g. three objects from one room — rather than more symbols.'; }
          else { tip = 'Strong. Passphrases built from unrelated words stay memorable without getting weak.'; }
          return { score: score, bits: bits, words: wordCount, tip: tip, checks: { len: pw.length >= 12, words: wordCount >= 3, mix: !!mix, clean: !isCommon && !hasSeq && !hasRepeat } };
        }
        var pwBar = document.getElementById('pwBar');
        var pwLabel = document.getElementById('pwLabel');
        var pwEntropy = document.getElementById('pwEntropy');
        var pwTip = document.getElementById('pwTip');
        var PW_LABELS = ['Too weak', 'Weak', 'Fair', 'Strong', 'Very strong'];
        var PW_COLORS = ['#d64545', '#d64545', '#e08a1e', '#2E5A85', '#1e7d4f'];
        function updatePwMeter(pw) {
          var a = analysePassword(pw || '');
          pwScore = a.score;
          if (!pw) {
            if (pwBar) { pwBar.style.width = '0%'; }
            if (pwLabel) { pwLabel.textContent = 'Start typing a password'; }
            if (pwEntropy) { pwEntropy.textContent = ''; }
          } else {
            if (pwBar) { pwBar.style.width = Math.max(8, a.score * 25) + '%'; pwBar.style.background = PW_COLORS[a.score]; }
            if (pwLabel) { pwLabel.textContent = PW_LABELS[a.score]; }
            if (pwEntropy) { pwEntropy.textContent = '~' + a.bits + ' bits · ' + a.words + (a.words === 1 ? ' word' : ' words'); }
          }
          if (pwTip) { pwTip.textContent = a.tip; }
          document.querySelectorAll('#pwChecks li').forEach(function (li) {
            var key = li.getAttribute('data-check');
            li.classList.toggle('ok', !!a.checks[key]);
          });
        }
        function checkConfirm() {
          if (!confirmMsg || !authPass || !authPassConfirm) { return true; }
          if (authMode !== 'signup') { confirmMsg.className = 'field-msg'; confirmMsg.textContent = ''; authPassConfirm.classList.remove('match-ok', 'match-bad'); return true; }
          var a = authPass.value, b = authPassConfirm.value;
          if (!b) { confirmMsg.className = 'field-msg'; confirmMsg.textContent = ''; authPassConfirm.classList.remove('match-ok', 'match-bad'); return false; }
          if (a === b) {
            confirmMsg.className = 'field-msg show success';
            confirmMsg.textContent = 'Passwords match.';
            authPassConfirm.classList.add('match-ok'); authPassConfirm.classList.remove('match-bad');
            return true;
          }
          confirmMsg.className = 'field-msg show error';
          confirmMsg.textContent = 'Passwords do not match yet — check for a typo.';
          authPassConfirm.classList.add('match-bad'); authPassConfirm.classList.remove('match-ok');
          return false;
        }
        if (authPass) {
          authPass.addEventListener('input', function () { updatePwMeter(authPass.value); checkConfirm(); });
        }
        if (authPassConfirm) {
          authPassConfirm.addEventListener('input', checkConfirm);
        }
        /* Passphrase generator — NLP technique: random natural words */
        var genPassBtn = document.getElementById('genPassBtn');
        var pwSuggestion = document.getElementById('pwSuggestion');
        var pwSuggestionText = document.getElementById('pwSuggestionText');
        var usePassBtn = document.getElementById('usePassBtn');
        var suggestedPass = '';
        function generatePassphrase() {
          function pick() { return PW_WORDS[Math.floor(Math.random() * PW_WORDS.length)]; }
          var chosen = [];
          while (chosen.length < 4) { var w = pick(); if (chosen.indexOf(w) === -1) { chosen.push(w); } }
          var num = Math.floor(Math.random() * 90) + 10;
          var syms = ['!', '#', '*', '?', '@'];
          var sym = syms[Math.floor(Math.random() * syms.length)];
          return chosen.join('-') + num + sym;
        }
        if (genPassBtn) {
          genPassBtn.addEventListener('click', function () {
            suggestedPass = generatePassphrase();
            if (pwSuggestionText) { pwSuggestionText.textContent = suggestedPass; }
            if (pwSuggestion) { pwSuggestion.classList.add('show'); }
          });
        }
        if (usePassBtn) {
          usePassBtn.addEventListener('click', function () {
            if (!suggestedPass) { return; }
            authPass.value = suggestedPass;
            if (authPassConfirm) { authPassConfirm.value = suggestedPass; }
            authPass.type = 'text';
            if (authPassConfirm) { authPassConfirm.type = 'text'; }
            var eb = document.getElementById('eyeBtn');
            if (eb) { eb.setAttribute('aria-pressed', 'true'); eb.setAttribute('aria-label', 'Hide password'); }
            var ebc = document.getElementById('eyeBtnConfirm');
            if (ebc) { ebc.setAttribute('aria-pressed', 'true'); ebc.setAttribute('aria-label', 'Hide re-entered password'); }
            updatePwMeter(suggestedPass);
            checkConfirm();
          });
        }

        if (authForm) {
          authForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var email = document.getElementById('authEmail').value.trim();
            var pass = authPass.value;
            if (!email || !pass) {
              showAuthNote('Please enter your email and password first.');
              return;
            }
            if (authMode === 'signup') {
              if (!checkConfirm() || pass !== authPassConfirm.value) {
                showAuthNote('Your two passwords do not match — please re-enter the same password in both fields.');
                if (authPassConfirm) { authPassConfirm.focus(); }
                return;
              }
              if (pwScore < 2) {
                showAuthNote('That password is too weak. Try the passphrase generator above — 4 words + a number + a symbol.');
                authPass.focus();
                return;
              }
            }
            showAuthNote('This is a design preview — sign-in runs on the live Saylient app, so nothing was submitted here.');
          });
        }
        var googleBtn = document.getElementById('googleBtn');
        if (googleBtn) {
          googleBtn.addEventListener('click', function () {
            showAuthNote('This is a design preview — Google sign-in runs on the live Saylient app.');
          });
        }
        var forgotLink = document.getElementById('forgotLink');
        if (forgotLink) {
          forgotLink.addEventListener('click', function (e) {
            e.preventDefault();
            showAuthNote('Password reset lives on the live Saylient app — this preview does not send email.');
          });
        }
        function wireEye(btnId, input, hideLabel, showLabel) {
          var btn = document.getElementById(btnId);
          if (!btn || !input) { return; }
          btn.addEventListener('click', function () {
            var showPw = input.type === 'password';
            input.type = showPw ? 'text' : 'password';
            btn.setAttribute('aria-pressed', showPw ? 'true' : 'false');
            btn.setAttribute('aria-label', showPw ? hideLabel : showLabel);
          });
        }
        wireEye('eyeBtn', authPass, 'Hide password', 'Show password');
        wireEye('eyeBtnConfirm', authPassConfirm, 'Hide re-entered password', 'Show re-entered password');
      })();