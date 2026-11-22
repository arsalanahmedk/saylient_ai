/* SaylientAI extension — client-side PII redactor (pure module).
 *
 * No chrome APIs, no DOM, no network. Safe to unit-test in Node and to
 * load as a classic script in the side panel and in content scripts.
 * The panel shows the redacted text, so what is sent is what is shown.
 *
 * Order matters: IBAN and CNIC first (their shapes overlap generic
 * digit runs), then email, then card numbers (Luhn-checked, so phone
 * numbers and order numbers are not masked as cards), then phones.
 */

(function (global) {
  'use strict';

  var EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
  var CNIC_RE = /\b\d{5}-\d{7}-\d\b/g;
  // IBAN: 2-letter country code + 2 check digits + 4..30 alphanumerics,
  // optionally space-grouped. Length is checked in the replacer.
  var IBAN_RE = /\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){1,7}(?:[ ]?[A-Z0-9]{1,3})?\b/g;
  // Grouped card: 4-4-4-4 (Visa/Mastercard) or 4-6-5 (Amex).
  var CARD_GROUPED_RE = /\b(?:\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}(?:[- ]\d{1,3})?|\d{4}[- ]\d{6}[- ]\d{5})\b/g;
  // Contiguous card: 13-19 digits. Luhn-checked in the replacer.
  var CARD_CONTIGUOUS_RE = /\b\d{13,19}\b/g;
  // Pakistani mobile: +92 3xx xxxxxxx, 03xx-xxxxxxx / 03xxxxxxxxx.
  var PHONE_PK_RE = /(?:\+92[\s-]?\d{3}[\s-]?\d{7}|\b03\d{2}[- ]?\d{7}\b)/g;
  // Other international numbers: a leading +, at least 10 digits in
  // total, separators only. Checked for digit count in the replacer.
  var PHONE_INTL_RE = /\+\d[\d\s().-]{7,}\d/g;

  function luhnOk(digits) {
    var sum = 0;
    var doubleNext = false;
    for (var i = digits.length - 1; i >= 0; i--) {
      var d = digits.charCodeAt(i) - 48;
      if (doubleNext) {
        d *= 2;
        if (d > 9) d -= 9;
      }
      sum += d;
      doubleNext = !doubleNext;
    }
    return digits.length > 0 && sum % 10 === 0;
  }

  function digitsOf(s) {
    return s.replace(/\D/g, '');
  }

  function redactText(text) {
    if (typeof text !== 'string' || text === '') return text === '' ? '' : '';
    var out = text;

    out = out.replace(IBAN_RE, function (m) {
      var compact = m.replace(/ /g, '');
      // Real IBANs are 15-34 characters; shorter runs are not IBANs.
      if (compact.length >= 15 && compact.length <= 34) return '[IBAN]';
      return m;
    });

    out = out.replace(CNIC_RE, '[CNIC]');

    out = out.replace(EMAIL_RE, '[EMAIL]');

    out = out.replace(CARD_GROUPED_RE, function (m) {
      var digits = digitsOf(m);
      if (digits.length >= 13 && digits.length <= 19 && luhnOk(digits)) {
        return '[CARD]';
      }
      return m;
    });

    out = out.replace(CARD_CONTIGUOUS_RE, function (m) {
      if (luhnOk(m)) return '[CARD]';
      return m;
    });

    out = out.replace(PHONE_PK_RE, '[PHONE]');

    out = out.replace(PHONE_INTL_RE, function (m) {
      var digits = digitsOf(m);
      if (digits.length >= 10 && digits.length <= 15) return '[PHONE]';
      return m;
    });

    return out;
  }

  var api = { redactText: redactText };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    global.SaylientRedact = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
