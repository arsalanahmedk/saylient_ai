'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { redactText } = require('../lib/redact.js');

test('redacts an email address', () => {
  assert.equal(redactText('Contact me at arsalan@example.com please'), 'Contact me at [EMAIL] please');
  assert.equal(redactText('a@b.co and c.d-e+f@gmail.com'), '[EMAIL] and [EMAIL]');
});

test('redacts a Pakistani CNIC', () => {
  assert.equal(redactText('My CNIC is 35202-1234567-1.'), 'My CNIC is [CNIC].');
  assert.equal(redactText('35202-1234567-1'), '[CNIC]');
});

test('redacts IBANs, spaced and compact', () => {
  assert.equal(redactText('IBAN PK36 SCBL 0000 0011 2345 6702'), 'IBAN [IBAN]');
  assert.equal(redactText('DE89370400440532013000'), '[IBAN]');
});

test('redacts Luhn-valid card numbers, grouped and contiguous', () => {
  assert.equal(redactText('Card 4242 4242 4242 4242'), 'Card [CARD]');
  assert.equal(redactText('Card 4111-1111-1111-1111'), 'Card [CARD]');
  assert.equal(redactText('Card 4242424242424242'), 'Card [CARD]');
  assert.equal(redactText('Amex 378282246310005'), 'Amex [CARD]');
});

test('does not mask a card-shaped number that fails Luhn', () => {
  assert.equal(redactText('Card 4242 4242 4242 4243'), 'Card 4242 4242 4242 4243');
});

test('redacts Pakistani and international phone numbers', () => {
  assert.equal(redactText('Call +92 300 1234567'), 'Call [PHONE]');
  assert.equal(redactText('Call 0300-1234567'), 'Call [PHONE]');
  assert.equal(redactText('Call 03001234567'), 'Call [PHONE]');
  assert.equal(redactText('Call +1 415 555 0132'), 'Call [PHONE]');
});

test('does not mask ordinary numbers, years or short ids', () => {
  const text = 'Order 12345 shipped in 2026, meet at 5pm, invoice 987654, room 42.';
  assert.equal(redactText(text), text);
  assert.equal(redactText('Call me at 5'), 'Call me at 5');
});

test('redacts every type in one message and is idempotent', () => {
  const input = 'Hi, mail me at a@b.com, CNIC 35202-1234567-1, card 4242 4242 4242 4242, phone 0300-1234567, IBAN DE89370400440532013000.';
  const once = redactText(input);
  assert.equal(once, 'Hi, mail me at [EMAIL], CNIC [CNIC], card [CARD], phone [PHONE], IBAN [IBAN].');
  assert.equal(redactText(once), once);
});

test('handles empty and plain text', () => {
  assert.equal(redactText(''), '');
  assert.equal(redactText('Hello, please send the revised draft.'), 'Hello, please send the revised draft.');
});
