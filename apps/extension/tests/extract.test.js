'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const extract = require('../lib/extract.js');

// --- Minimal fake DOM -------------------------------------------------
function fakeNode(text, opts) {
  const o = opts || {};
  return {
    tagName: o.tagName || 'DIV',
    type: o.type || '',
    hidden: !!o.hidden,
    style: o.style || {},
    textContent: text,
    innerText: o.innerText !== undefined ? o.innerText : text,
    offsetParent: o.visible === false ? null : {},
    getAttribute: (name) => (o.attrs && o.attrs[name] !== undefined ? o.attrs[name] : null),
    querySelector: () => o.child || null,
    getBoundingClientRect: () => ({
      width: o.visible === false ? 0 : 100,
      height: o.visible === false ? 0 : 20,
    }),
  };
}

function fakeDoc(selectorMap, mainNode, bodyNode) {
  return {
    querySelectorAll: (sel) => (selectorMap && selectorMap[sel]) || [],
    querySelector: (sel) => {
      if (sel === 'main') return mainNode || null;
      if (sel === 'body') return bodyNode || null;
      return null;
    },
    body: bodyNode || null,
  };
}

function fakeWin(selectionText, opts) {
  const o = opts || {};
  return {
    getSelection: () => ({ toString: () => selectionText || '' }),
    getComputedStyle:
      o.noComputedStyle === true
        ? undefined
        : (node) => ({
            display: (node.style && node.style.display) || 'block',
            visibility: (node.style && node.style.visibility) || 'visible',
          }),
  };
}

// --- Priority ----------------------------------------------------------
test('selection wins over messages and visible text', () => {
  const doc = fakeDoc(
    { '.a3s.aiL': [fakeNode('older message')] },
    fakeNode('whole page text'),
    fakeNode('whole page text'),
  );
  const result = extract.extractConversation(doc, fakeWin('selected words'), 'mail.google.com');
  assert.equal(result.source, 'selection');
  assert.equal(result.text, 'selected words');
});

test('last 8 messages are used on a per-site platform (Gmail)', () => {
  const nodes = [];
  for (let i = 1; i <= 10; i++) nodes.push(fakeNode('message ' + i));
  const doc = fakeDoc({ '.a3s.aiL': nodes }, null, fakeNode('fallback'));
  const result = extract.extractConversation(doc, fakeWin(''), 'mail.google.com');
  assert.equal(result.source, 'messages');
  assert.equal(result.text, 'message 3\nmessage 4\nmessage 5\nmessage 6\nmessage 7\nmessage 8\nmessage 9\nmessage 10');
});

test('generic platform falls back to visible main text', () => {
  const doc = fakeDoc({}, fakeNode('instagram caption text'), fakeNode('body text'));
  const result = extract.extractConversation(doc, fakeWin(''), 'www.instagram.com');
  assert.equal(result.source, 'visible');
  assert.equal(result.text, 'instagram caption text');
  assert.equal(result.platform.kind, 'generic');
});

test('empty page yields the empty source', () => {
  const doc = fakeDoc({}, fakeNode(''), fakeNode(''));
  const result = extract.extractConversation(doc, fakeWin(''), 'example.com');
  assert.equal(result.source, 'empty');
  assert.equal(result.text, '');
});

// --- Truncation / normalization ---------------------------------------
test('truncation keeps the tail and marks it honestly', () => {
  const long = 'x'.repeat(1500) + 'TAIL' + 'y'.repeat(600);
  const result = extract.truncateTail(long);
  assert.equal(result.truncated, true);
  assert.ok(result.text.length <= 2000, 'capped at 2000 chars');
  assert.ok(result.text.startsWith(extract.TRUNCATION_MARKER));
  assert.ok(result.text.endsWith('y'.repeat(600)));
  assert.ok(result.text.includes('TAIL'));
});

test('short text is not truncated', () => {
  const result = extract.truncateTail('hello');
  assert.deepEqual(result, { text: 'hello', truncated: false });
});

test('normalizeText collapses whitespace but keeps message breaks', () => {
  assert.equal(extract.normalizeText('  hello   world \n\n  next  '), 'hello world\nnext');
});

test('normalizedChanged ignores whitespace-only differences', () => {
  assert.equal(extract.normalizedChanged('hello  world', 'hello world'), false);
  assert.equal(extract.normalizedChanged('hello world', 'hello there'), true);
});

// --- Visibility and sensitive fields -----------------------------------
test('hidden message nodes are skipped', () => {
  const nodes = [
    fakeNode('visible one'),
    fakeNode('hidden one', { visible: false }),
    fakeNode('visible two', { style: { display: 'none' } }),
  ];
  const texts = extract.collectMessageTexts(nodes, null, fakeWin(''));
  assert.deepEqual(texts, ['visible one']);
});

test('password and payment inputs are skipped', () => {
  const password = fakeNode('secret', { tagName: 'INPUT', type: 'password', attrs: {} });
  const card = fakeNode('4242', {
    tagName: 'INPUT',
    type: 'text',
    attrs: { autocomplete: 'cc-number' },
  });
  assert.equal(extract.shouldSkipNode(password), true);
  assert.equal(extract.shouldSkipNode(card), true);
  assert.equal(extract.shouldSkipNode(fakeNode('normal text')), false);
  assert.equal(extract.nodeText(password, fakeWin('')), '');
});

// --- Platform registry --------------------------------------------------
test('platform registry: 5 per-site, 9 generic, nothing else claimed', () => {
  assert.equal(extract.PLATFORMS.length, 5);
  assert.equal(extract.GENERIC_PLATFORMS.length, 9);
  assert.equal(extract.matchPlatform('mail.google.com').name, 'Gmail');
  assert.equal(extract.matchPlatform('www.linkedin.com').kind, 'per-site');
  assert.equal(extract.matchPlatform('www.upwork.com').name, 'Upwork');
  assert.equal(extract.matchPlatform('www.fiverr.com').name, 'Fiverr');
  assert.equal(extract.matchPlatform('web.whatsapp.com').name, 'WhatsApp Web');
  assert.equal(extract.matchPlatform('web.telegram.org').kind, 'generic');
  assert.equal(extract.matchPlatform('example.com').kind, 'unknown');
});

test('compose selectors exist for per-site platforms', () => {
  const gmail = extract.composeSelectorsFor('mail.google.com');
  assert.ok(gmail.some((s) => s.includes('contenteditable') || s.includes('Message Body')));
  const generic = extract.composeSelectorsFor('example.com');
  assert.ok(generic.length > 0);
});
