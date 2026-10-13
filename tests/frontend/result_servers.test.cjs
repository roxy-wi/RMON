const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const fixture = fs.readFileSync(path.join(__dirname, 'fixtures/result-servers.html'), 'utf8');
const source = fs.readFileSync(path.join(__dirname, '../../app/static/js/rmon/result_servers.js'), 'utf8');
const wait = () => new Promise(resolve => setTimeout(resolve, 20));
async function page(t, overrides = {}, legacyWidgets = false) {
    const dom = new JSDOM(fixture, {url: 'https://rmon.test/rmon/servers', runScripts: 'outside-only'});
    t.after(() => dom.window.close());
    const w = dom.window, d = w.document, calls = [], intervals = [];
    d.cookie = 'csrf_access_token=test-csrf';
    w.setInterval = fn => intervals.push(fn);
    w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
    w.HTMLDialogElement.prototype.close = function () { this.open = false; };
    w.confirm = () => true;
    const config = {can_install: true, can_edit: true, defaults: [], deployment: {database_type: 'postgresql', database_host: 'database', database_port: 5432, transport: 'http'},
        hosts: [{id: 1, name: 'Private host', ip: '10.0.0.1'}],
        endpoints: [{id: 20, group_id: 1, name: '<img src=x onerror=alert(1)>', url: 'https://metrics.test', role: 'classic', kind: 'lb', transport: 'https', shared: false, revision: 1, server_ids: [1, 2], agent_count: 3, project_count: 0, default_group_count: 1}],
        servers: [{id: 1, name: 'Server A', hostname: 'Host A', ip: '10.0.0.1', roles: ['classic'], endpoint_ids: [20], revision: 1, applied_revision: 1, state: 'ready'},
            {id: 2, name: 'Server B', hostname: 'Host B', ip: '10.0.0.2', roles: ['classic'], endpoint_ids: [20], revision: 1, applied_revision: 0, state: 'unknown', task: {status: 'running'}}], ...overrides};
    w.fetch = async (url, settings) => {
        const body = settings.body && JSON.parse(settings.body); calls.push({url, ...settings, body});
        return {ok: true, status: settings.method === 'GET' ? 200 : 202, headers: {get: () => 'application/json'}, json: async () => settings.method === 'GET' ? config : {task_id: 1}};
    };
    if (legacyWidgets) {
        for (const name of ['jquery-3.6.0.min.js', 'jquery-ui.min.js']) {
            w.eval(fs.readFileSync(path.join(__dirname, '../../app/static/js', name), 'utf8'));
        }
        w.jQuery('select').selectmenu();
        w.jQuery('button').button();
    }
    w.eval(source); await wait();
    const $ = id => d.getElementById('rs-' + id);
    const submit = () => $('form').dispatchEvent(new w.Event('submit', {bubbles: true, cancelable: true}));
    const input = (element, value) => { element.value = value; element.dispatchEvent(new w.Event('input', {bubbles: true})); };
    return {w, d, $, config, calls, intervals, submit, input};
}

test('server controls keep their own theme after legacy widgets initialize', async t => {
    const {$, d} = await page(t, {}, true);
    assert.equal(d.querySelector('.ui-button, .ui-selectmenu-button'), null);
    assert.equal($('install').classList.contains('rs-primary'), true);
    $('install').click();
    assert.equal($('dialog').open, true);
    $('cancel').click();
    assert.equal($('dialog').open, false);
});

test('one load-balancer address links two servers and renders text safely', async t => {
    const {$, calls} = await page(t);
    assert.equal($('servers').querySelectorAll('article').length, 2);
    assert.equal($('endpoints').querySelectorAll('article').length, 1);
    assert.match($('endpoints').textContent, /Server A, Server B/);
    assert.equal($('endpoints').querySelector('img'), null);
    assert.equal(calls[0].credentials, 'same-origin');
    assert.equal(calls[0].headers['X-CSRF-TOKEN'], 'test-csrf');
    assert.ok([...$('servers').querySelectorAll('article')[1].querySelectorAll('button')].every(b => b.disabled));
});

test('wizard sends both roles and reuses the shared address without duplicating it', async t => {
    const {$, d, calls, submit, input} = await page(t);
    $('install').click();
    input($('fields').querySelector('input[type=text]'), 'New server');
    $('fields').querySelectorAll('input[type=checkbox]')[1].click();
    submit();
    $('fields').querySelector('input[type=checkbox]').click();
    submit(); submit(); await wait();
    const request = calls.find(c => c.method === 'POST');
    assert.deepEqual(request.body.roles, ['classic', 'client']);
    assert.deepEqual(request.body.endpoint_ids, [20]);
    assert.deepEqual(request.body.new_endpoints, []);
    assert.equal(request.body.host_id, 1);
    assert.equal(request.body.database_port, 5432);
    assert.equal($('dialog').open, false);
});

test('read-only users cannot install servers or change defaults', async t => {
    const {$} = await page(t, {can_install: false, can_edit: false});
    assert.equal($('install').hidden, true);
    assert.equal($('add-endpoint').hidden, true);
    assert.equal($('servers').querySelector('button'), null);
    assert.ok([...$('defaults').querySelectorAll('select,button,input')].every(el => el.disabled));
});

test('returning to roles removes unused addresses and preserves the other connection', async t => {
    const {$, calls, submit, input} = await page(t, {
        hosts: [{id: 1, name: 'IPv6 host', ip: '2001:db8::1'}],
        deployment: {database_type: 'postgresql', database_host: 'database', database_port: 5432, transport: 'mtls'}
    });
    $('install').click();
    input($('fields').querySelector('input[type=text]'), 'New server');
    $('fields').querySelectorAll('input[type=checkbox]')[1].click();
    submit();
    $('fields').querySelector('.rs-choices input').click();
    $('fields').querySelector('fieldset button').click();
    assert.equal($('fields').querySelector('input[type=url]').value, 'https://[2001:db8::1]:5100');
    assert.equal($('fields').querySelectorAll('fieldset select')[1].value, 'mtls');
    $('fields').querySelectorAll('fieldset')[1].querySelector('button').click();
    input($('fields').querySelectorAll('input[type=url]')[1], 'http://client.test');
    $('back').click();
    assert.equal($('fields').querySelector('input[type=text]').value, 'New server');
    $('fields').querySelector('input[type=checkbox]').click();
    submit();
    assert.equal($('fields').querySelectorAll('input[type=url]').length, 1);
    submit();
    assert.match($('fields').textContent, /http:\/\/client.test/);
    assert.doesNotMatch($('fields').textContent, /Classic checks|metrics.test/);
    submit(); await wait();
    const request = calls.find(c => c.method === 'POST');
    assert.deepEqual(request.body.roles, ['client']);
    assert.deepEqual(request.body.endpoint_ids, []);
    assert.deepEqual(request.body.new_endpoints, [{name: 'New server · Client projects', url: 'http://client.test',
        role: 'client', transport: 'http', kind: 'direct', shared: false}]);
});

test('editing a SQLite server preserves its host and revision through the review step', async t => {
    const server = {id: 1, name: 'Server A', host_id: 1, hostname: 'Private host', ip: '10.0.0.1',
        roles: ['classic'], endpoint_ids: [20], classic_port: 5100, client_port: 5102,
        bind_ip: '0.0.0.0', sqlite_path: '/data/rmon.db', revision: 7, applied_revision: 7, state: 'ready'};
    const {$, calls, submit, input} = await page(t, {servers: [server], deployment: {database_type: 'sqlite'}});
    $('servers').querySelector('button').click();
    assert.equal($('dialog-title').textContent, 'Configure');
    assert.equal($('fields').querySelector('select').disabled, true);
    submit();
    const storage = $('fields').querySelectorAll('fieldset')[1];
    input(storage.querySelector('input'), '/shared/rmon.db');
    submit();
    assert.match($('fields').textContent, /\/shared\/rmon.db/);
    $('back').click();
    assert.equal($('fields').querySelectorAll('fieldset')[1].querySelector('input').value, '/shared/rmon.db');
    submit(); submit(); await wait();
    const request = calls.find(c => c.method === 'PUT');
    assert.equal(request.url, '/api/v1.0/receivers/servers/1');
    assert.equal(request.body.host_id, 1);
    assert.equal(request.body.revision, 7);
    assert.equal(request.body.sqlite_path, '/shared/rmon.db');
    assert.equal(server.sqlite_path, '/data/rmon.db');
});

test('receiver editor submits editable fields and keeps the revision for updates', async t => {
    const {$, config, calls, submit, input} = await page(t);
    $('add-endpoint').click();
    assert.equal($('steps').textContent, '');
    assert.equal($('back').hidden, true);
    assert.equal($('submit').textContent, 'Save');
    input($('fields').querySelector('input[type=text]'), 'New address');
    input($('fields').querySelector('input[type=url]'), 'http://receiver.test');
    submit(); await wait();
    assert.deepEqual(calls.find(c => c.method === 'POST').body, {
        name: 'New address', url: 'http://receiver.test', role: 'classic', transport: 'http', kind: 'direct', shared: false
    });
    $('endpoints').querySelector('button').click();
    assert.equal($('dialog-title').textContent, 'Edit');
    input($('fields').querySelector('input[type=text]'), 'Renamed address');
    submit(); await wait();
    const request = calls.find(c => c.method === 'PUT');
    assert.equal(request.url, '/api/v1.0/receivers/endpoints/20');
    assert.deepEqual(request.body, {
        name: 'Renamed address', url: 'https://metrics.test', role: 'classic', transport: 'https', kind: 'lb', shared: false, revision: 1
    });
    assert.notEqual(config.endpoints[0].name, 'Renamed address');
});

test('polling preserves unfinished default selection and pauses while editing', async t => {
    const {w, $, intervals, calls} = await page(t);
    $('default-mode').value = 'custom'; $('default-mode').dispatchEvent(new w.Event('change'));
    $('default-choices').querySelector('input').click();
    intervals[0](); await wait();
    assert.equal($('default-mode').value, 'custom');
    assert.equal($('default-choices').querySelector('input').checked, true);
    $('install').click(); const before = calls.length;
    intervals[0](); await wait(); assert.equal(calls.length, before);
});

test('expired-session HTML produces a readable message instead of a parser error', async t => {
    const {w, $} = await page(t);
    w.fetch = async () => ({status: 200, headers: {get: () => 'text/html'}});
    $('refresh').click(); await wait();
    assert.match($('message').textContent, /Unable to complete/);
    assert.doesNotMatch($('message').textContent, /Unexpected|DOCTYPE|SyntaxError/);
});
