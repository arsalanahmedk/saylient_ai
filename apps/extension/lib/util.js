/* SaylientAI extension — pure timing helpers (no chrome APIs, no DOM).
 * Shared by the side panel (debounce + 3-second round throttle) and the
 * content script (mutation coalescing). Unit-tested in Node.
 */

(function (global) {
  'use strict';

  // Call `fn` only after `waitMs` with no further call. Each call
  // resets the timer. Returns a function with a `.cancel()` method.
  function debounce(fn, waitMs) {
    var timer = null;
    function debounced() {
      var args = arguments;
      var self = this;
      if (timer !== null) clearTimeout(timer);
      timer = setTimeout(function () {
        timer = null;
        fn.apply(self, args);
      }, waitMs);
    }
    debounced.cancel = function () {
      if (timer !== null) {
        clearTimeout(timer);
        timer = null;
      }
    };
    return debounced;
  }

  // Minimum-gap gate: `allows(nowMs)` is true only when at least
  // `minGapMs` has passed since the last allowed call (or never).
  // The caller records the allowed call with `mark(nowMs)`.
  function createThrottle(minGapMs) {
    var lastAllowed = null;
    return {
      allows: function (nowMs) {
        if (lastAllowed === null) return true;
        return nowMs - lastAllowed >= minGapMs;
      },
      mark: function (nowMs) {
        lastAllowed = nowMs;
      },
      reset: function () {
        lastAllowed = null;
      },
    };
  }

  var api = { debounce: debounce, createThrottle: createThrottle };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.SaylientUtil = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
