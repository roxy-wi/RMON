const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '../..');
const fixture = fs.readFileSync(path.join(__dirname, 'fixtures/client-checks.html'), 'utf8');
const code = name => fs.readFileSync(path.join(root, 'app/static/js/rmon', name + '.js'), 'utf8');
const token = 'rmon_pub_' + 'A'.repeat(43);
const clone = value => JSON.parse(JSON.stringify(value));
const definition = () => ({has_outcome: true, duration: {label: 'Duration', type: 'number', unit: 'ms', minimum: 0, maximum: null, required: false},
    metrics: {items: {label: 'Items', type: 'integer', unit: 'count', required: true, minimum: 0, maximum: 100}},
    context: {cached: {label: 'Cached', type: 'boolean', required: false, filterable: true, values: []}}, primary_metric: 'duration_ms'});
const json = (data, status = 200) => new Response(JSON.stringify(data), {status, headers: {'Content-Type': 'application/json'}});
function report(check = 10, observations = 3) {
    const summary = {observations, errors: 1, outcomes: observations, successful: observations - 1, error_rate: 1 / observations,
        sampling: {min_probability: 1, max_probability: 1}, metric: {count: observations, mean: 25, min: 10, max: 40, p50: 25, p95: 39, p99: 40}};
    return {check_id: check, metric: 'duration_ms', unit: 'ms', state: 'ready', summary,
        aggregation: {last_received_us: 1790496000000000, last_processed_us: 1790496060000000, lag_seconds: 0},
        series: [{at: '2026-09-27T10:00:00Z', ...clone(summary)}], group_by: 'platform', groups: [{value: 'android', ...clone(summary)}], groups_truncated: false};
}
async function settle() { await new Promise(resolve => setTimeout(resolve, 15)); }
async function until(condition) {
    for (let i = 0; i < 60; i++) { if (condition()) return; await settle(); }
    assert.ok(condition(), 'Expected UI state did not arrive');
}
function page(t, options = {}) {
    const dom = new JSDOM('<!doctype html><html lang="en"><body>' + fixture + '</body></html>', {
        url: 'http://rmon.test/client-checks' + (options.search || ''), runScripts: 'outside-only', pretendToBeVisual: true});
    t.after(() => dom.window.close());
    const w = dom.window, d = w.document, calls = [], logs = [], charts = [], timers = [];
    if (options.language) {
        const source = fs.readFileSync(path.join(root, 'app/templates/languages/client_' + options.language + '.html'), 'utf8');
        const catalog = JSON.parse(source.slice(source.indexOf('=') + 1, source.lastIndexOf('%}')));
        d.getElementById('cc-strings').textContent = JSON.stringify(catalog);
        d.documentElement.lang = options.language;
    }
    if (options.noDisplayNames) w.Intl.DisplayNames = undefined;
    w.Chart = class { constructor(canvas, config) { this.config = config; charts.push(this); } destroy() { this.destroyed = true; } };
    w.setInterval = (callback, delay) => { timers.push({callback, delay}); return timers.length; };
    w.clearInterval = id => { timers[id - 1].cleared = true; };
    w.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
    w.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open'); };
    w.confirm = () => true; w.console.warn = (...args) => logs.push(args);
    w.console.info = (...args) => logs.push(args);
    const projects = [{id: 1, name: 'Shop <img src=x onerror=alert(1)>', description: '', enabled: true}, {id: 2, name: 'Launcher', description: '', enabled: true}];
    const checks = {1: [{id: 10, code: 'catalog.load', name: 'Catalog', current_version: 1}], 2: [{id: 20, code: 'game.start', name: 'Start', current_version: 1}]};
    const definitions = {10: [{version: 1, definition: definition()}], 20: [{version: 1, definition: definition()}]};
    const keys = [];
    let intercept = options.intercept;
    w.fetch = async (url, settings) => {
        const parsed = new URL(url, w.location.href), route = parsed.pathname.replace('/api/v1.0/client/projects', '');
        const call = {url: parsed, route, ...settings, payload: settings.body && JSON.parse(settings.body)}; calls.push(call);
        if (intercept) { const result = await intercept(call); if (result !== undefined) return result; }
        if (!route && settings.method === 'POST') { const value = {id: 3, ...call.payload, enabled: true}; projects.push(value); checks[3] = []; return json(value, 201); }
        if (!route) return json({items: projects, next_after_id: null});
        const parts = route.split('/').filter(Boolean), project = Number(parts[0]);
        if (parts.length === 1) return json(projects.find(value => value.id === project));
        if (parts[1] === 'checks' && parts.length === 2 && settings.method === 'POST') {
            const check = {id: 11, code: call.payload.code, name: call.payload.name, description: call.payload.description, current_version: 1};
            checks[project].push(check); definitions[11] = [{version: 1, definition: call.payload.definition}]; return json(check, 201);
        }
        if (parts[1] === 'checks' && parts.length === 2) return json({items: checks[project], next_after_id: null});
        if (parts[3] === 'definitions' && settings.method === 'POST') return json({version: 2}, 201);
        if (parts[3] === 'definitions') return json({items: definitions[parts[2]]});
        if (parts[3] === 'report') return json(report(Number(parts[2]), project === 2 ? 222 : 3));
        if (parts[1] === 'overview') return json({items: checks[project].map(check => ({...check, report: report(check.id)})), next_after_id: null});
        if (parts[1] === 'keys' && settings.method === 'POST') {
            const key = {id: 5, ...call.payload, prefix: token.slice(0, 16), revoked: false, last_used_us: null}; keys.push(key); return json({...key, project_key: token}, 201);
        }
        if (parts[1] === 'keys' && settings.method === 'DELETE') { keys[0].revoked = true; return new Response(null, {status: 204}); }
        if (parts[1] === 'keys') return json({items: keys, next_after_id: null});
        if (parts[1] === 'events') return json({items: [{id: 1, received_us: 1790496000000000,
            event: {check: '<script>window.xss=1</script>', status: 'ok', duration_ms: 32, context: {platform: '<img src=x onerror=alert(1)>'}}}], next_before_id: null});
        throw new Error('Unexpected request: ' + route);
    };
    d.cookie = 'csrf_access_token=fixture-csrf; path=/';
    if (options.legacyWidgets) {
        for (const name of ['jquery-3.6.0.min.js', 'jquery-ui.min.js']) w.eval(fs.readFileSync(path.join(root, 'app/static/js', name), 'utf8'));
        w.jQuery('select').selectmenu(); w.jQuery('input[type=checkbox]').checkboxradio(); w.jQuery('button').button();
    }
    w.eval(code('client_contract')); w.eval(code('client_checks')); w.RmonClientChecks.init();
    const get = id => d.getElementById('cc-' + id);
    const change = (id, value) => { get(id).value = value; get(id).dispatchEvent(new w.Event('change', {bubbles: true})); };
    const input = (node, value) => { node.value = value; node.dispatchEvent(new w.Event('input', {bubbles: true})); };
    const submit = id => get(id + '-form').dispatchEvent(new w.Event('submit', {bubbles: true, cancelable: true}));
    return {w, d, calls, get, change, input, submit, logs, charts, timers, intercept(fn) { intercept = fn; }};
}

test('overview reads real API summaries, escapes names and preserves authenticated requests', async t => {
    const {get, calls, d} = page(t);
    await until(() => get('overview-rows').children.length === 1);
    assert.match(get('project-name').textContent, /<img/);
    assert.equal(get('project-name').querySelector('img'), null);
    assert.match(get('overview-rows').textContent, /39 ms/);
    assert.ok(calls.every(call => call.credentials === 'same-origin' && call.headers['X-CSRF-TOKEN'] === 'fixture-csrf'));
    assert.equal(d.querySelectorAll('#client-checks').length, 1);
    assert.match(get('overview-cards').textContent, /Catalog/);
    assert.match(get('overview-cards').textContent, /39 ms/);
});

test('chart connects measurements across missing minutes without inventing zero values', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    ui.get('tab-report').click(); await until(() => ui.charts.length);
    for (const dataset of ui.charts.at(-1).config.data.datasets) {
        const data = Array(288).fill(null); data[140] = 25;
        assert.ok(dataset.pointRadius({dataset: {data}, dataIndex: 140}) > 0);
        assert.equal(dataset.pointRadius({dataset: {data}, dataIndex: 141}), 0);
        assert.equal(dataset.spanGaps, true);
        assert.ok(dataset.pointHitRadius >= 5);
    }
    const config = ui.charts.at(-1).config;
    const chart = {options: config.options};
    config.options.onResize(chart, {width: 300});
    assert.equal(chart.options.scales.x.ticks.maxTicksLimit, 3);
    config.options.onResize(chart, {width: 1000});
    assert.equal(chart.options.scales.x.ticks.maxTicksLimit, 6);
});

test('changing the report metric reloads measured values without a separate apply click', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    ui.get('tab-report').click(); await until(() => !ui.get('report-data').hidden);
    ui.change('report-metric', 'items');
    await until(() => ui.calls.some(call => call.route.endsWith('/report') && call.url.searchParams.get('metric') === 'items'));
    assert.equal(ui.calls.filter(call => call.route.endsWith('/report')).at(-1).url.searchParams.get('outcome'), 'all');
});

test('automatic refresh waits for requests and respects unfinished filters and the toggle', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    const timer = ui.timers.find(timer => timer.delay === 30000);
    const count = () => ui.calls.filter(call => call.route.endsWith('/overview')).length;
    const initial = count(); timer.callback(); await until(() => count() > initial);
    await until(() => ui.get('panel-overview').getAttribute('aria-busy') === 'false');
    ui.get('auto-refresh').checked = false; const stopped = count(); timer.callback(); await settle();
    assert.equal(count(), stopped);
    ui.get('auto-refresh').checked = true; ui.get('tab-report').click(); await until(() => !ui.get('report-data').hidden);
    ui.get('add-filter').click();
    assert.match(ui.get('refresh-status').textContent, /Apply filters/);
    const before = ui.calls.length; timer.callback(); await settle(); assert.equal(ui.calls.length, before);
    ui.w.dispatchEvent(new ui.w.Event('pagehide')); assert.equal(timer.cleared, true);
});

test('background refresh preserves the visible report and never overlaps a slow response', async t => {
    let finish;
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    ui.get('tab-report').click(); await until(() => !ui.get('report-data').hidden);
    ui.intercept(call => call.route.endsWith('/report') ? new Promise(resolve => { finish = resolve; }) : undefined);
    const timer = ui.timers.find(timer => timer.delay === 30000);
    timer.callback(); await until(() => finish);
    assert.equal(ui.get('report-data').hidden, false);
    const count = ui.calls.length; timer.callback(); await settle(); assert.equal(ui.calls.length, count);
    finish(json(report())); await until(() => ui.get('panel-report').getAttribute('aria-busy') === 'false');
});

test('auto-refresh stays active after using selectors, applied filters and its checkbox', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    ui.get('tab-report').click(); await until(() => ui.charts.length);
    const timer = ui.timers.find(timer => timer.delay === 30000);
    for (const id of ['report-metric', 'report-group', 'period', 'auto-refresh']) {
        ui.get(id).focus(); const before = ui.charts.length;
        timer.callback(); await until(() => ui.charts.length > before);
    }
    ui.get('add-filter').click();
    const value = ui.get('filters').querySelector('[data-filter-value]');
    ui.input(value, 'production');
    ui.get('report-form').dispatchEvent(new ui.w.Event('submit', {bubbles: true, cancelable: true}));
    await until(() => ui.get('panel-report').getAttribute('aria-busy') === 'false');
    value.focus(); const before = ui.charts.length;
    timer.callback(); await until(() => ui.charts.length > before);
});

test('auto-refresh is restored after returning from the back-forward cache', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    ui.get('tab-report').click(); await until(() => ui.charts.length);
    const firstTimer = ui.timers.find(timer => timer.delay === 30000);
    const pageEvent = name => { const event = new ui.w.Event(name); Object.defineProperty(event, 'persisted', {value: true}); return event; };
    const before = ui.charts.length;
    ui.w.dispatchEvent(pageEvent('pagehide')); assert.equal(firstTimer.cleared, true);
    ui.w.dispatchEvent(pageEvent('pageshow'));
    await until(() => ui.charts.length > before);
    assert.equal(ui.timers.filter(timer => timer.delay === 30000 && !timer.cleared).length, 1);
    const restored = ui.charts.length; ui.timers.at(-1).callback();
    await until(() => ui.charts.length > restored);
});

test('returning to a visible tab refreshes stale data, while hidden tabs and dialogs wait', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    assert.match(ui.get('refresh-status').textContent, /Data refreshed: \d{2}\.\d{2}\.\d{4}/);
    const timer = ui.timers.find(timer => timer.delay === 30000);
    let visibility = 'hidden'; Object.defineProperty(ui.d, 'visibilityState', {get: () => visibility});
    const before = ui.calls.length; timer.callback(); await settle(); assert.equal(ui.calls.length, before);
    ui.w.Date.now = () => Date.now() + 31000;
    visibility = 'visible'; ui.d.dispatchEvent(new ui.w.Event('visibilitychange'));
    await until(() => ui.calls.length > before);
    await until(() => ui.get('panel-overview').getAttribute('aria-busy') === 'false');
    ui.get('new-project').click(); const editing = ui.calls.length;
    assert.match(ui.get('refresh-status').textContent, /paused while editing/);
    timer.callback(); await settle(); assert.equal(ui.calls.length, editing);
    ui.get('project-dialog').close(); timer.callback(); await until(() => ui.calls.length > editing);
});

test('empty project onboarding keeps project creation available', async t => {
    const ui = page(t, {intercept: call => call.route === '' ? json({items: [], next_after_id: null}) : undefined});
    await until(() => !ui.get('empty').hidden);
    assert.equal(ui.get('project-area').hidden, true);
    ui.get('new-project').click(); assert.ok(ui.get('project-dialog').open);
});

test('shared jQuery widgets do not replace native controls or tab semantics', async t => {
    const ui = page(t, {legacyWidgets: true}); await until(() => ui.get('overview-rows').children.length);
    assert.equal(ui.get('tab-report').getAttribute('role'), 'tab');
    assert.notEqual(ui.get('project').style.display, 'none');
    assert.equal(ui.w.jQuery(ui.get('project')).selectmenu('instance'), undefined);
    ui.get('new-check').click(); assert.ok(ui.get('definition-dialog').open);
    ui.get('definition-dialog').querySelector('[data-close]').click(); assert.equal(ui.get('definition-dialog').open, false);
});

test('initial network errors offer a retry that loads the projects', async t => {
    let fail = true;
    const ui = page(t, {intercept: call => { if (!call.route && fail) { fail = false; throw new TypeError('offline'); } }});
    await until(() => ui.get('message').querySelector('button'));
    ui.get('message').querySelector('button').click();
    await until(() => ui.get('overview-rows').children.length === 1);
    assert.equal(ui.get('message').hidden, true);
});

test('editor saves user metrics, units, enum context and an outcome-free definition', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    ui.get('new-check').click(); const form = ui.get('definition-form');
    ui.input(form.elements.name, 'Temperature'); ui.input(form.elements.code, 'temperature');
    ui.get('has-outcome').checked = false; ui.get('has-duration').checked = false;
    ui.get('has-duration').dispatchEvent(new ui.w.Event('change', {bubbles: true}));
    ui.get('add-metric').click(); let metric = ui.get('metrics').firstElementChild;
    for (const [name, value] of Object.entries({name: 'temperature', label: 'Temperature', unit: 'C', minimum: '-80', maximum: '200'})) ui.input(metric.querySelector(`[data-field=${name}]`), value);
    ui.get('primary-metric').value = 'temperature';
    ui.get('add-context').click(); const context = ui.get('context').firstElementChild;
    ui.input(context.querySelector('[data-field=name]'), 'location'); ui.input(context.querySelector('[data-field=label]'), 'Location');
    context.querySelector('[data-field=type]').value = 'enum'; context.querySelector('[data-field=type]').dispatchEvent(new ui.w.Event('change', {bubbles: true}));
    ui.input(context.querySelector('[data-field=values]'), 'EU\nUS'); context.querySelector('[data-field=filterable]').checked = true;
    ui.submit('definition'); await until(() => ui.calls.some(call => call.route === '/1/checks' && call.method === 'POST'));
    const saved = ui.calls.find(call => call.route === '/1/checks' && call.method === 'POST').payload.definition;
    assert.equal(saved.duration, null); assert.equal(saved.has_outcome, false); assert.equal(saved.primary_metric, 'temperature');
    assert.equal(saved.metrics.temperature.minimum, -80); assert.deepEqual(saved.context.location.values, ['EU', 'US']);
    await until(() => !ui.get('definition-dialog').open);
    assert.equal(ui.get('tab-connect').getAttribute('aria-selected'), 'true');
});

test('invalid duplicate metric codes keep editor values and never send a request', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length);
    ui.get('new-check').click(); const form = ui.get('definition-form'); form.elements.name.value = 'A'; form.elements.code.value = 'a';
    for (let i = 0; i < 2; i++) {
        ui.get('add-metric').click(); const item = ui.get('metrics').lastElementChild;
        for (const [key, value] of Object.entries({name: 'size', label: 'Size', unit: 'bytes'})) ui.input(item.querySelector(`[data-field=${key}]`), value);
    }
    ui.submit('definition'); await settle();
    assert.equal(ui.calls.filter(call => call.method === 'POST').length, 0);
    assert.ok(ui.get('definition-dialog').open); assert.equal(ui.get('metrics').children.length, 2);
    assert.equal(form.querySelector('.cc-form-error').hidden, false);
});

test('editing a definition sends its precondition and shows concurrent-save conflicts', async t => {
    const ui = page(t, {intercept: call => call.method === 'POST' && call.route.endsWith('/definitions') ? json({error: 'definition_changed', message: 'Changed'}, 409) : undefined});
    await until(() => ui.get('overview-rows').children.length); ui.get('tab-report').click();
    await until(() => !ui.get('report-data').hidden); ui.get('edit-definition').click();
    await until(() => ui.get('definition-dialog').open); ui.submit('definition');
    await until(() => !ui.get('definition-form').querySelector('.cc-form-error').hidden);
    const saved = ui.calls.find(call => call.method === 'POST'); assert.equal(saved.headers['If-Match'], '"1"');
    assert.match(ui.get('definition-form').querySelector('.cc-form-error').textContent, /Another version/);
    assert.ok(ui.get('definition-dialog').open);
});

test('report serializes boolean and missing filters and shows approximate percentiles', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length); ui.get('tab-report').click();
    await until(() => !ui.get('report-data').hidden); ui.get('add-filter').click();
    const filter = ui.get('filters').firstElementChild;
    const field = filter.querySelector('[data-filter-field]'); field.value = 'cached'; field.dispatchEvent(new ui.w.Event('change'));
    filter.querySelector('[data-filter-value]').value = 'false'; ui.submit('report'); await settle();
    let call = ui.calls.filter(call => call.route.endsWith('/report')).at(-1); assert.deepEqual(JSON.parse(call.url.searchParams.get('filters')), {cached: false});
    filter.querySelector('[data-filter-missing]').checked = true; ui.submit('report'); await settle();
    call = ui.calls.filter(call => call.route.endsWith('/report')).at(-1); assert.deepEqual(JSON.parse(call.url.searchParams.get('filters')), {cached: null});
    assert.match(ui.get('stats').textContent, /≈ p95/);
});

test('switching projects discards a report response that arrives late', async t => {
    let finish;
    const ui = page(t, {intercept: call => call.route === '/1/checks/10/report' ? new Promise(resolve => { finish = resolve; }) : undefined});
    await until(() => ui.get('overview-rows').children.length); ui.get('tab-report').click(); await until(() => finish);
    ui.change('project', 2); await until(() => !ui.get('report-data').hidden && ui.get('stats').textContent.includes('222'));
    finish(json(report(10, 9999))); await settle();
    assert.ok(ui.get('stats').textContent.includes('222')); assert.ok(!ui.get('stats').textContent.includes('9,999'));
});

test('issuing a key is single-flight, scopes it to selected checks and clears it on project changes', async t => {
    let resolveKey;
    const ui = page(t, {intercept: call => call.route === '/1/keys' && call.method === 'POST' ? new Promise(resolve => { resolveKey = () => resolve(json({id: 5, ...call.payload, project_key: token}, 201)); }) : undefined});
    await until(() => ui.get('overview-rows').children.length); ui.get('tab-connect').click();
    await until(() => ui.get('connect-version').textContent); ui.get('new-key').click(); ui.get('key-form').elements.name.value = 'Web';
    ui.submit('key'); ui.submit('key'); await until(() => resolveKey);
    assert.equal(ui.calls.filter(call => call.method === 'POST').length, 1);
    assert.deepEqual(ui.calls.find(call => call.method === 'POST').payload.checks, ['catalog.load']);
    resolveKey(); await until(() => !ui.get('key-once').hidden);
    ui.input(ui.get('endpoint'), 'https://collector.example/api/v1/client/events');
    await until(() => ui.get('example').textContent.includes(token));
    assert.equal(ui.w.localStorage.length, 0); assert.equal(ui.w.sessionStorage.length, 0); assert.ok(!ui.w.location.href.includes(token));
    ui.change('project', 2); await settle(); assert.equal(ui.get('sending-key').value, ''); assert.ok(!ui.get('example').textContent.includes(token));
});

test('connection example uses the selected application platform and definition version', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length); ui.get('tab-connect').click();
    await until(() => ui.get('connect-version').textContent);
    ui.input(ui.get('endpoint'), 'https://collector.example/events'); ui.input(ui.get('sending-key'), token); ui.input(ui.get('example-platform'), 'windows');
    const batch = JSON.parse(ui.get('example').textContent);
    assert.equal(batch.schema_version, 1); assert.equal(batch.events[0].definition_version, 1);
    assert.equal(batch.events[0].context.platform, 'windows'); assert.equal(batch.events[0].context.cached, false);
    assert.equal(ui.get('copy-example').disabled, false);
    ui.input(ui.get('endpoint'), 'javascript:alert(1)'); assert.equal(ui.get('copy-example').disabled, true);
});

test('connect shows a useful preview before a key is entered and fills the local endpoint', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length); ui.get('tab-connect').click();
    await until(() => ui.get('example').textContent);
    assert.equal(ui.get('endpoint').value, 'http://rmon.test/api/v1/client/events');
    assert.match(ui.get('example').textContent, /YOUR_SENDING_KEY/);
    assert.match(ui.get('example-state').textContent, /Paste the sending key/);
    assert.equal(ui.get('copy-example').disabled, true);
    ui.input(ui.get('sending-key'), token);
    assert.ok(ui.get('example').textContent.includes(token));
    assert.equal(ui.get('copy-example').disabled, false);
});

for (const [language, name, metric, device] of [
    ['en', 'Page load', 'Full page load', 'Device type'],
    ['ru', 'Загрузка страницы', 'Полная загрузка', 'Тип устройства'],
    ['fr', 'Chargement de la page', 'Chargement complet', 'Type d’appareil'],
    ['pt-br', 'Carregamento da página', 'Carregamento completo', 'Tipo de dispositivo'],
]) {
    test('preset labels use the application language in every view: ' + language, async t => {
        const preset = {id: 10, code: 'page.load', name: 'Загрузка страницы',
            description: 'Время загрузки документа и этапов соединения в браузере посетителя.', current_version: 1};
        const def = definition(); def.duration.label = 'Полная загрузка'; def.metrics.items.label = 'My custom metric';
        def.context.device = {label: 'Тип устройства', type: 'enum', values: ['desktop', 'mobile'], filterable: true};
        const summary = {...report(), metric_label: 'Полная загрузка'};
        const ui = page(t, {language, intercept: call => {
            if (call.route === '') return json({items: [{id: 1, name: 'shop.example', description: 'Измерения из браузеров посетителей shop.example'}], next_after_id: null});
            if (call.route === '/1/checks') return json({items: [preset], next_after_id: null});
            if (call.route.endsWith('/overview')) return json({items: [{...preset, report: summary}], next_after_id: null});
            if (call.route.endsWith('/definitions') && call.method === 'GET') return json({items: [{version: 1, definition: def}]});
            if (call.route.endsWith('/report')) return json(summary);
        }});
        await until(() => ui.get('overview-rows').children.length);
        assert.equal(ui.get('overview-cards').querySelector('button').textContent, name);
        assert.ok(ui.get('overview-cards').textContent.includes(metric));
        if (language !== 'ru') assert.doesNotMatch(ui.get('project-description').textContent, /[А-Яа-я]/);
        ui.get('tab-report').click(); await until(() => !ui.get('report-data').hidden);
        assert.equal(ui.get('chart-title').textContent, metric);
        assert.equal(ui.get('report-check').selectedOptions[0].textContent, name + ' · page.load');
        assert.equal([...ui.get('report-group').options].find(option => option.value === 'device').textContent, device);
        assert.match(ui.get('report-metric').textContent, /My custom metric/);
        ui.get('edit-definition').click(); await until(() => ui.get('definition-dialog').open);
        assert.equal(ui.get('definition-form').elements.name.value, name);
        assert.equal(ui.get('duration-label').value, metric);
        // Localized presentation must not turn a no-op edit into a rename.
        ui.submit('definition'); await until(() => ui.calls.some(call => call.method === 'POST'));
        const saved = ui.calls.find(call => call.method === 'POST').payload;
        assert.equal(saved.duration.label, 'Полная загрузка');
        assert.equal(saved.context.device.label, 'Тип устройства');
        assert.equal(saved.metrics.items.label, 'My custom metric');
        assert.equal(def.duration.label, 'Полная загрузка');
    });
}

test('a custom name on a standard check code is preserved', async t => {
    const custom = {id: 10, code: 'page.load', name: 'Мой особый сценарий', current_version: 1};
    const ui = page(t, {intercept: call => {
        if (call.route === '/1/checks') return json({items: [custom], next_after_id: null});
        if (call.route.endsWith('/overview')) return json({items: [{...custom, report: {...report(), metric_label: 'Моя метрика'}}], next_after_id: null});
    }});
    await until(() => ui.get('overview-rows').children.length);
    assert.equal(ui.get('overview-cards').querySelector('button').textContent, custom.name);
    assert.match(ui.get('overview-cards').textContent, /Моя метрика/);
});

test('source page supports grouping and full length filters without HTML injection', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length); ui.get('tab-report').click();
    await until(() => !ui.get('report-data').hidden);
    ui.change('report-group', '_page_url');
    await until(() => ui.calls.some(call => call.url.searchParams.get('group_by') === '_page_url'));
    ui.get('add-filter').click();
    const field = ui.get('filters').querySelector('[data-filter-field]');
    field.value = '_page_url'; field.dispatchEvent(new ui.w.Event('change'));
    assert.equal(ui.get('filters').querySelector('[data-filter-value]').maxLength, 2048);
    ui.intercept(call => call.route.endsWith('/events') ? json({items: [{received_us: 1,
        event: {check: 'page.load', page_url: 'https://example.com/<img src=x onerror=alert(1)>', context: {country: 'DE'}}}], next_before_id: null}) : undefined);
    ui.get('tab-events').click(); await until(() => ui.get('event-rows').textContent.includes('https://example.com/'));
    assert.equal(ui.get('event-rows').querySelector('img'), null);
    assert.ok(ui.get('event-rows').textContent.includes('DE'));
});

for (const [language, germany] of [['en', 'Germany'], ['ru', 'Германия'], ['fr', 'Allemagne'], ['pt-br', 'Alemanha']]) {
    test('European numbers and translated country names in ' + language, async t => {
        const data = report(10, 12345);
        data.summary.error_rate = .1234;
        Object.assign(data.summary.metric, {p95: 1906.812, mean: 507.647, min: 0, max: 1935.6, p99: .0001234});
        data.series = [{at: new Date(2026, 8, 27, 23, 5, 2).toISOString(), ...clone(data.summary)}];
        data.group_by = 'country';
        data.groups = [{value: 'DE', ...clone(data.summary)}, {value: null, ...clone(data.summary)}];
        const ui = page(t, {language, intercept: call => {
            if (call.route.endsWith('/overview')) return json({items: [{id: 10, code: 'catalog.load', name: 'Catalog', report: data}], next_after_id: null});
            if (call.route.endsWith('/report')) return json(data);
            if (call.route.endsWith('/events')) return json({items: [{received_us: 1790496000000000,
                event: {check: 'catalog.load', duration_ms: 1906.812, context: {country: 'DE'}}}], next_before_id: null});
        }});
        const text = node => node.textContent.replace(/[\u00a0\u202f]/g, ' ');
        await until(() => ui.get('overview-rows').children.length);
        assert.match(text(ui.get('overview-cards')), /1 906,812 ms/);
        assert.match(text(ui.get('overview-rows')), /12 345/);
        ui.get('tab-report').click(); await until(() => ui.charts.length);
        const stats = [...ui.get('stats').querySelectorAll('strong')].map(text);
        assert.deepEqual(stats, ['12 345', '12,34 %', '12 345', '1 906,812 ms', '507,647 ms', '0 ms', '1 935,6 ms', '1']);
        assert.match(text(ui.get('series-rows')), /27\.09\.2026, 23:05:02/);
        assert.doesNotMatch(text(ui.get('report-quality')), /[AP]M/);
        assert.match(text(ui.get('series-rows')), /1,234E-4 ms/);
        assert.equal(ui.get('group-rows').querySelector('td').textContent, germany + ' (DE)');
        assert.notEqual(ui.get('group-rows').children[1].firstChild.textContent, '—');
        const chart = ui.charts.at(-1).config;
        assert.equal(chart.options.scales.y.ticks.callback(1906.812).replace(/[\u00a0\u202f]/g, ' '), '1 906,812');
        assert.equal(chart.options.plugins.tooltip.callbacks.label({dataset: chart.data.datasets[1], parsed: {y: 1906.812}}).replace(/[\u00a0\u202f]/g, ' '), '≈ p95 (ms): 1 906,812');
        assert.match(chart.options.scales.x.ticks.callback(null, 0), /^\d{2}:\d{2}$/);
        data.group_by = 'platform';
        ui.get('refresh').click(); await until(() => ui.charts.length === 2);
        assert.equal(ui.get('group-rows').querySelector('td').textContent, 'DE');
        ui.get('tab-events').click(); await until(() => ui.get('event-rows').children.length);
        const cells = ui.get('event-rows').querySelectorAll('td');
        assert.equal(text(cells[3]), '1 906,812 ms');
        assert.equal(text(cells[4]), germany + ' (DE)');
        const raw = JSON.parse(ui.get('event-rows').querySelector('pre').textContent);
        assert.equal(raw.duration_ms, 1906.812); assert.equal(raw.context.country, 'DE');
    });
}

test('country labels preserve unknown values safely and do not translate other dimensions', async t => {
    const data = report(); data.groups = [{value: 'DE', ...clone(data.summary)}];
    const ui = page(t, {noDisplayNames: true, intercept: call => {
        if (call.route.endsWith('/report')) return json(data);
        if (call.route.endsWith('/events')) return json({items: ['DE', undefined, '<img src=x onerror=alert(1)>'].map(country => ({
            received_us: 1790496000000000, event: {check: 'catalog.load', context: {country}}
        })), next_before_id: null});
    }});
    await until(() => ui.get('overview-rows').children.length);
    ui.get('tab-report').click(); await until(() => ui.charts.length);
    assert.equal(ui.get('group-rows').querySelector('td').textContent, 'DE');
    ui.get('tab-events').click(); await until(() => ui.get('event-rows').children.length);
    const rows = [...ui.get('event-rows').children];
    assert.deepEqual(rows.map(row => row.children[4].textContent), ['DE', '—', '<img src=x onerror=alert(1)>']);
    assert.equal(ui.get('event-rows').querySelector('img'), null);
});

test('event details render untrusted payloads as text', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length); ui.get('tab-events').click();
    await until(() => ui.get('event-rows').children.length);
    assert.equal(ui.get('event-rows').querySelector('script, img'), null);
    assert.match(ui.get('event-rows').textContent, /window.xss/); assert.equal(ui.w.xss, undefined);
});

test('report errors hide old results and retain the selected period for retry', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length); ui.get('tab-report').click();
    await until(() => !ui.get('report-data').hidden);
    ui.intercept(call => call.route.endsWith('/report') ? json({error: 'report_too_large'}, 422) : undefined);
    ui.change('period', 720); await until(() => ui.get('report-state').querySelector('button'));
    assert.equal(ui.get('report-data').hidden, true); assert.match(ui.get('report-state').textContent, /Narrow the period/);
    assert.equal(ui.get('period').value, '720'); ui.intercept(null); ui.get('report-state').querySelector('button').click();
    await until(() => !ui.get('report-data').hidden);
});

test('refresh preserves the chosen metric, outcome and comparison field', async t => {
    const ui = page(t); await until(() => ui.get('overview-rows').children.length); ui.get('tab-report').click();
    await until(() => !ui.get('report-data').hidden);
    ui.change('report-metric', 'items'); ui.change('report-group', 'country'); ui.change('report-outcome', 'error');
    ui.get('refresh').click(); await until(() => !ui.get('report-data').hidden);
    const request = ui.calls.filter(call => call.route.endsWith('/report')).at(-1);
    assert.equal(request.url.searchParams.get('metric'), 'items');
    assert.equal(request.url.searchParams.get('group_by'), 'country');
    assert.equal(request.url.searchParams.get('outcome'), 'error');
});

test('pagination disables repeat clicks and passes the server cursor', async t => {
    let finish;
    const ui = page(t, {intercept: call => {
        if (call.route === '/1/events' && !call.url.searchParams.has('before_id')) return json({items: [], next_before_id: 42});
        if (call.route === '/1/events') return new Promise(resolve => { finish = resolve; });
    }});
    await until(() => ui.get('overview-rows').children.length); ui.get('tab-events').click();
    await until(() => !ui.get('events-next').disabled); ui.get('events-next').click(); ui.get('events-next').click();
    await until(() => finish);
    assert.equal(ui.calls.filter(call => call.route === '/1/events').length, 2);
    assert.equal(ui.calls.filter(call => call.route === '/1/events').at(-1).url.searchParams.get('before_id'), '42');
    finish(json({items: [], next_before_id: null})); await until(() => !ui.get('events-prev').disabled);
    ui.get('events-prev').click(); await until(() => !ui.get('events-next').disabled);
    assert.equal(ui.calls.filter(call => call.route === '/1/events').at(-1).url.searchParams.has('before_id'), false);
});

test('browser example retries identical event bodies and stops on permanent errors', async t => {
    const dom = new JSDOM('', {url: 'http://rmon.test', runScripts: 'outside-only'}); t.after(() => dom.window.close());
    const w = dom.window; w.eval(code('client_contract')); const calls = [], results = [];
    const nativeTimeout = w.setTimeout.bind(w);
    w.setTimeout = (fn, delay) => nativeTimeout(fn, delay === 5000 ? delay : 0);
    w.console.info = (_message, result) => results.push(result); w.console.warn = () => assert.fail('Unexpected script failure');
    w.fetch = async (_url, options) => { calls.push(options); return json({}, calls.length === 1 ? 503 : 202); };
    const event = w.RmonClientContract.example(definition(), 'catalog.load', 1);
    const snippet = w.RmonClientContract.snippet('browser', 'http://collector.test/events', token, event);
    w.eval(snippet); await until(() => results.length);
    assert.equal(calls.length, 2); assert.equal(calls[0].body, calls[1].body); assert.equal(calls[0].credentials, 'omit');
    assert.equal(results[0].accepted, true); assert.ok(!JSON.stringify(results).includes(token));
    assert.equal(JSON.parse(calls[0].body).events[0].page_url, 'http://rmon.test/');
    assert.equal(calls[0].referrerPolicy, 'no-referrer');
    calls.length = 0; results.length = 0;
    w.fetch = async (_url, options) => { calls.push(options); return json({}, 422); };
    // A new realm avoids redeclaring the example's top-level const bindings.
    w.Function(snippet)(); await until(() => results.length);
    assert.equal(calls.length, 1); assert.equal(results[0].status, 422);
});

test('curl quotes apostrophes safely and has no spurious continuation characters', t => {
    const dom = new JSDOM('', {runScripts: 'outside-only'}); t.after(() => dom.window.close());
    dom.window.eval(code('client_contract')); const contract = dom.window.RmonClientContract;
    const event = contract.example(definition(), 'catalog.load', 1); event.context.note = "a' $(not-a-command)";
    const snippet = contract.snippet('curl', 'https://collector.test/events', token, event);
    assert.ok(snippet.includes("a'\"'\"' $(not-a-command)")); assert.ok(!snippet.includes('\n+'));
    assert.ok(snippet.includes('--retry-max-time 60'));
});
