'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const EXT_DIR = path.resolve(__dirname, '..');

function read(rel) {
  return fs.readFileSync(path.join(EXT_DIR, rel), 'utf8');
}

test('manifest is valid JSON with the locked permissions and CSP', () => {
  const raw = read('manifest.json');
  const manifest = JSON.parse(raw);

  assert.equal(manifest.manifest_version, 3);
  assert.equal(manifest.name, 'SaylientAI');
  assert.deepEqual(manifest.permissions, ['sidePanel', 'storage']);
  assert.deepEqual(manifest.host_permissions, [
    'http://localhost:8000/*',
    'http://127.0.0.1:8000/*',
    'https://api.saylient.example/*',
  ]);
  assert.ok(!raw.includes('<all_urls>'), 'no <all_urls>');
  assert.ok(!raw.includes('identity'), 'no identity permission');
  assert.ok(!raw.includes('scripting'), 'no scripting permission');
  assert.ok(!raw.includes('activeTab'), 'no activeTab permission');
  assert.equal(
    manifest.content_security_policy.extension_pages,
    "script-src 'self'; object-src 'self'",
  );
  assert.deepEqual(manifest.background, { service_worker: 'background.js', type: 'module' });
  assert.equal(manifest.side_panel.default_path, 'sidepanel.html');
  assert.equal(manifest.commands['open-saylient'].suggested_key.default, 'Ctrl+Shift+S');
  assert.equal(manifest.commands['open-saylient'].suggested_key.mac, 'Command+Shift+S');
  assert.deepEqual(manifest.icons, {
    16: 'icons/icon16.png',
    48: 'icons/icon48.png',
    128: 'icons/icon128.png',
  });
});

test('manifest content scripts cover all 14 platforms, listener-only order', () => {
  const manifest = JSON.parse(read('manifest.json'));
  assert.equal(manifest.content_scripts.length, 1);
  const cs = manifest.content_scripts[0];
  const joined = cs.matches.join(' ');
  for (const domain of [
    'mail.google.com',
    'linkedin.com',
    'upwork.com',
    'fiverr.com',
    'web.whatsapp.com',
    'instagram.com',
    'messenger.com',
    'telegram.org',
    'snapchat.com',
    'tiktok.com',
    'discord.com',
    'x.com',
    'twitter.com',
    'slack.com',
    'teams.microsoft.com',
  ]) {
    assert.ok(joined.includes(domain), 'missing match for ' + domain);
  }
  // Pure libraries load before the content script that uses them.
  assert.deepEqual(cs.js, [
    'lib/redact.js',
    'lib/extract.js',
    'lib/util.js',
    'content/extractor.js',
  ]);
  assert.equal(cs.all_frames, false);
});

test('every file referenced by the manifest exists on disk', () => {
  const manifest = JSON.parse(read('manifest.json'));
  const referenced = [
    manifest.background.service_worker,
    manifest.side_panel.default_path,
    ...manifest.content_scripts[0].js,
    ...Object.values(manifest.icons),
  ];
  for (const rel of referenced) {
    assert.ok(fs.existsSync(path.join(EXT_DIR, rel)), 'missing: ' + rel);
  }
  assert.ok(fs.existsSync(path.join(EXT_DIR, 'sidepanel.css')));
  assert.ok(fs.existsSync(path.join(EXT_DIR, 'sidepanel.js')));
});

test('no shipped JS uses eval, remote code, innerHTML, identity or auth headers', () => {
  const jsFiles = [
    'sidepanel.js',
    'background.js',
    'content/extractor.js',
    'lib/redact.js',
    'lib/extract.js',
    'lib/util.js',
  ];
  const forbidden = [
    'eval(',
    'new Function',
    'innerHTML',
    'document.write',
    'chrome.identity',
    'launchWebAuthFlow',
  ];
  // An Authorization header literal (an actual header being sent), not
  // a comment explaining that no such header is sent.
  const forbiddenHeader = /['"]Authorization['"]\s*:/;
  for (const rel of jsFiles) {
    const src = read(rel);
    for (const pattern of forbidden) {
      assert.ok(!src.includes(pattern), rel + ' must not contain ' + pattern);
    }
    assert.ok(!forbiddenHeader.test(src), rel + ' must not send an Authorization header');
  }
});

test('side panel HTML loads only local scripts and has no inline handlers', () => {
  const html = read('sidepanel.html');
  assert.ok(!html.includes('src="http'), 'no remote script source');
  assert.ok(!/on(click|input|change|load)=/i.test(html), 'no inline event handlers');
  for (const local of ['lib/redact.js', 'lib/extract.js', 'lib/util.js', 'sidepanel.js', 'sidepanel.css']) {
    assert.ok(html.includes(local), 'missing local include: ' + local);
  }
});

test('icons are real PNGs at the declared sizes', () => {
  for (const size of [16, 48, 128]) {
    const buf = fs.readFileSync(path.join(EXT_DIR, 'icons', 'icon' + size + '.png'));
    // PNG signature + IHDR width/height (big-endian, bytes 16-23).
    assert.deepEqual([...buf.subarray(0, 8)], [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
    assert.equal(buf.readUInt32BE(16), size);
    assert.equal(buf.readUInt32BE(20), size);
  }
});
