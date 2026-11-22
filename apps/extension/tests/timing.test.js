'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { debounce, createThrottle } = require('../lib/util.js');

test('debounce fires once after quiet, with the latest arguments', async () => {
  const calls = [];
  const debounced = debounce((value) => calls.push(value), 20);
  debounced('a');
  debounced('b');
  debounced('c');
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.deepEqual(calls, ['c']);
});

test('debounce cancel prevents the call', async () => {
  let calls = 0;
  const debounced = debounce(() => { calls += 1; }, 15);
  debounced();
  debounced.cancel();
  await new Promise((resolve) => setTimeout(resolve, 40));
  assert.equal(calls, 0);
});

test('throttle allows the first call, blocks inside the gap, allows after', () => {
  const gate = createThrottle(3000);
  assert.equal(gate.allows(1000), true);
  gate.mark(1000);
  assert.equal(gate.allows(2000), false);
  assert.equal(gate.allows(3999), false);
  assert.equal(gate.allows(4000), true);
  gate.mark(4000);
  assert.equal(gate.allows(5000), false);
});

test('throttle reset allows immediately', () => {
  const gate = createThrottle(3000);
  gate.mark(0);
  assert.equal(gate.allows(100), false);
  gate.reset();
  assert.equal(gate.allows(100), true);
});
