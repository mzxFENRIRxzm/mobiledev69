const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../frontend/web/the_x_startup.js'), 'utf8');
async function setup(cryptoApi = { randomUUID: () => 'unit-tab-id' }, options = {}) {
  const events = new Map(), timers = new Map(), scripts = [];
  const session = new Map(options.session || []);
  const state = { removed: false, reloads: 0, tabIds: [], removedSessionKeys: [] };
  const nodes = {
    'the-x-startup': { remove() { state.removed = true; } },
    'the-x-startup-message': { textContent: 'loading' },
    'the-x-startup-retry': { hidden: true },
  };
  const window = { addEventListener(name, callback) { events.set(name, callback); } };
  if (options.broadcastOccupied) window.BroadcastChannel = true;
  class BroadcastChannel {
    constructor() { this.onmessage = null; }
    postMessage(message) {
      if (options.broadcastOccupied && message.type === 'probe') {
        queueMicrotask(() => this.onmessage?.({ data: { type: 'occupied', id: message.id } }));
      }
    }
    close() {}
  }
  await vm.runInNewContext(source, {
    navigator: {},
    crypto: cryptoApi,
    performance: { getEntriesByType() { return [{ type: options.navigationType || 'navigate' }]; } },
    BroadcastChannel,
    localStorage: { removeItem() {} },
    sessionStorage: {
      getItem(key) { return session.get(key) ?? null; },
      setItem(key, value) { session.set(key, value); if (key === 'the_x_tab_id') state.tabIds.push(value); },
      removeItem(key) { session.delete(key); state.removedSessionKeys.push(key); },
    },
    window,
    document: { getElementById(id) { return nodes[id]; }, createElement() { return {}; },
      body: { appendChild(script) { scripts.push(script); } } },
    location: { reload() { state.reloads++; } },
    setTimeout(callback) { timers.set(1, callback); return 1; },
    clearTimeout(id) { timers.delete(id); },
  });
  return { nodes, events, timers, scripts, state };
}
(async () => {
  const normal = await setup();
  assert.equal(normal.scripts[0].src, 'flutter_bootstrap.js');
  normal.events.get('flutter-first-frame')();
  assert.equal(normal.state.removed, true);
  assert.equal(normal.timers.size, 0);
  console.log('PASS: first Flutter frame removes loading UI and cancels timeout');
  const slow = await setup();
  slow.timers.get(1)();
  assert.equal(slow.nodes['the-x-startup-retry'].hidden, false);
  assert.match(slow.nodes['the-x-startup-message'].textContent, /โหลดแอปไม่สำเร็จ/);
  slow.nodes['the-x-startup-retry'].onclick();
  assert.equal(slow.state.reloads, 1);
  slow.events.get('flutter-first-frame')();
  assert.equal(slow.state.removed, true);
  console.log('PASS: stalled startup shows retry and late first frame still recovers');
  const failed = await setup();
  failed.scripts[0].onerror();
  assert.equal(failed.nodes['the-x-startup-retry'].hidden, false);
  assert.equal(failed.timers.size, 0);
  console.log('PASS: bootstrap download failure shows retry immediately');
  const lan = await setup({
    getRandomValues(bytes) { bytes.fill(7); return bytes; },
  });
  assert.equal(lan.state.tabIds[0], '07'.repeat(16));
  assert.equal(lan.scripts[0].src, 'flutter_bootstrap.js');
  console.log('PASS: LAN HTTP starts without crypto.randomUUID secure context');
  const reload = await setup(undefined, {
    navigationType: 'reload', broadcastOccupied: true,
    session: [['the_x_tab_id', 'same-tab'], ['FlutterSecureStorage.the_x_session', 'credential']],
  });
  assert.ok(!reload.state.removedSessionKeys.includes('FlutterSecureStorage.the_x_session'));
  console.log('PASS: reload never mistakes the outgoing document for a duplicate tab');
  const duplicate = await setup(undefined, {
    broadcastOccupied: true,
    session: [['the_x_tab_id', 'copied-tab'], ['FlutterSecureStorage.the_x_session', 'credential']],
  });
  assert.ok(duplicate.state.removedSessionKeys.includes('FlutterSecureStorage.the_x_session'));
  console.log('PASS: a copied session is cleared when another live tab owns its identity');
})().catch(error => { console.error(error); process.exitCode = 1; });
