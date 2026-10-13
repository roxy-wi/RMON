const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

function page(t) {
    const dom = new JSDOM('<body><div id="agent-1"></div><button id="start-1" disabled>Start</button><button id="reload-1" disabled>Restart</button>' +
        '<button id="stop-1" disabled>Stop</button><span id="agent-status-1" data-ready="Running" data-stopped="Stopped" data-unavailable="Unavailable"></span>' +
        '<time id="agent-uptime-1"></time><span id="agent-total-checks-1"></span></body>',
        {url: 'https://rmon.test', runScripts: 'outside-only'});
    t.after(() => dom.window.close());
    const w = dom.window;
    w.setInterval = () => 0;
    const scripts = path.resolve(__dirname, '../../app/static/js');
    w.eval(fs.readFileSync(path.join(scripts, 'jquery-3.6.0.min.js'), 'utf8'));
    w.eval(fs.readFileSync(path.join(scripts, 'rmon/agent.js'), 'utf8'));
    const $ = w.jQuery, calls = [], messages = [], actions = [];
    $.ajax = options => { calls.push(options); };
    $.fn.timeago = function () { return this; };
    w.toastr = {error: (...args) => messages.push(args), info() {}, success() {}, warning() {}, clear() {}};
    w.api_v_prefix = '/api/v1.0';
    w.confirmAjaxAction = (...args) => actions.push(args);
    return {w, $, calls, messages, actions};
}

function editor(t) {
    const result = page(t), {w, $} = result;
    $('body').append(`<span id="translate" data-edit="Save" data-add="Install"></span>
        <dialog id="add-agent-page" data-edit="Edit agent" data-create="Install agent"><form id="agent-editor-form">
        <h3 id="agent-editor-title"></h3><input id="new-agent-name" required>
        <input id="new-agent-port" type="number" min="1" max="65535" value="5101" required>
        <label id="new-agent-select-tr"><select id="new-agent-server-id" required></select></label>
        <textarea id="new-agent-desc"></textarea><input id="new-agent-enabled" type="checkbox" checked>
        <input id="new-agent-shared" type="checkbox"><select id="new-agent-result-transport"><option value=""></option><option>http</option><option>mtls</option></select>
        <div id="agent-receivers" data-strings='{"choose_endpoint":"Choose an address","request_error":"Failed to load addresses"}'></div>
        <select id="new-agent-receiver-mode"><option>inherit</option><option>custom</option></select>
        <select id="new-agent-receiver-policy"><option>balance</option><option>failover</option></select>
        <div id="new-agent-receiver-list"></div><p id="new-agent-routing-pending" hidden></p>
        <footer class="host-actions"><button type="button" id="agent-editor-cancel">Cancel</button>
        <button type="button" id="agent-editor-reconfigure">Reconfigure</button><button id="agent-editor-save" type="submit">Save</button></footer>
        </form></dialog>`);
    const dialog = w.document.getElementById('add-agent-page');
    dialog.showModal = () => { dialog.open = true; };
    dialog.close = () => { dialog.open = false; };
    w.RmonUI = {notifyRequestError: xhr => result.messages.push(xhr)};
    $.ajax = options => {
        result.calls.push(options);
        if (options.url.endsWith('/endpoints')) options.success({items: [{id: 2, name: '<Host>', url: 'https://host', role: 'classic'}]});
        else if (options.async === false) options.success({name: "John's agent", description: "Don't strip quotes", port: 5101,
            server_id: 8, enabled: 1, shared: 0, result_transport: 'mtls', receivers: {endpoint_ids: [2], policy: 'failover'}});
    };
    return {...result, dialog};
}

test('native agent editor preserves settings, saves on submit and guards duplicate requests', t => {
    const {w, $, calls, dialog, messages} = editor(t);
    w.addAgentDialog(1, true);
    assert.equal(dialog.open, true);
    assert.equal($('#new-agent-name').val(), "John's agent");
    assert.equal($('#new-agent-receiver-list img').length, 0);
    $('#agent-editor-form').trigger('submit');
    $('#agent-editor-form').trigger('submit');
    const saves = calls.filter(call => call.type === 'PUT');
    assert.equal(saves.length, 1);
    const data = JSON.parse(saves[0].data);
    assert.equal(data.reconfigure, undefined);
    assert.equal(data.description, "Don't strip quotes");
    assert.deepEqual(data.receivers, {endpoint_ids: [2], policy: 'failover'});
    saves[0].error({status: 422});
    saves[0].complete();
    assert.equal(dialog.open, true);
    assert.equal(messages.length, 1);
    $('#agent-editor-reconfigure').trigger('click');
    assert.equal(JSON.parse(calls.at(-1).data).reconfigure, '1');
    let refreshed, task;
    w.getAgent = (...args) => { refreshed = args; };
    w.runInstallationTaskCheck = (...args) => { task = args; };
    calls.at(-1).success({tasks_ids: [9]});
    calls.at(-1).complete();
    assert.equal(dialog.open, false);
    assert.deepEqual(refreshed, [1, false]);
    assert.deepEqual(task, [[9], 1]);
});

test('native agent editor validates port and custom receivers before saving', t => {
    const {w, $, calls, dialog, messages} = editor(t);
    w.addAgentDialog(1, true);
    $('#new-agent-port').val('70000');
    w.addAgent(dialog, 1, true);
    assert.equal(calls.filter(call => call.type === 'PUT').length, 0);
    $('#new-agent-port').val('5101');
    w.setAgentReceivers({endpoint_ids: [], policy: 'balance'});
    w.addAgent(dialog, 1, true);
    assert.equal(calls.filter(call => call.type === 'PUT').length, 0);
    assert.match(messages[0][0], /Choose an address/);
});

test('failed agent settings request does not open an empty editor', t => {
    const {w, $, dialog, messages} = editor(t);
    const ajax = $.ajax;
    $.ajax = options => options.url.endsWith('/agent/1') ? options.error({status: 500}) : ajax(options);
    w.addAgentDialog(1, true);
    assert.equal(dialog.open, false);
    assert.equal(messages.length, 1);
});

test('agent probes request JSON and accept already-decoded values', t => {
    const {w, $, calls} = page(t);
    w.getAgentStatus('host', 1);
    assert.equal(calls[0].dataType, 'json');
    calls[0].success({running: true});
    assert.equal($('#agent-1').attr('data-state'), 'ready');
    assert.equal($('#agent-status-1').text(), 'Running');
    w.getAgentUptime('host', 1);
    assert.equal(calls[1].dataType, 'json');
    calls[1].success({uptime: '2026-09-07 06:00:00'});
    assert.equal($('#agent-uptime-1').text(), '2026-09-07 06:00:00');
    w.getAgentTotalChecks('host', 1);
    assert.equal(calls[2].dataType, 'json');
    calls[2].success(0);
    assert.equal($('#agent-total-checks-1').text(), '0');
});

test('HTML and failed probes mark agent unavailable without JSON.parse exceptions', t => {
    const {w, $, calls} = page(t);
    w.getAgentStatus('host', 1);
    assert.doesNotThrow(() => calls[0].error({status: 502, responseText: '<!doctype html>'}));
    assert.equal($('#agent-1').attr('data-state'), 'unavailable');
    assert.equal($('#agent-status-1').text(), 'Unavailable');
    assert.doesNotThrow(() => calls[0].success('<!doctype html>'));
    assert.equal($('#start-1').prop('disabled'), false);
    w.getAgentTotalChecks('host', 1);
    calls[1].error({status: 502});
    assert.equal($('#agent-total-checks-1').text(), '—');
});

test('stopped agent version failure is handled on the card without a global error toast', t => {
    const {w, $, calls, messages} = page(t);
    $('body').append('<span id="agent-version-1">1.0</span><span id="agent-update-1">!</span>');
    w.getAgentVersion('host', 1);
    assert.equal(typeof calls[0].error, 'function');
    calls[0].error({status: 502});
    assert.equal($('#agent-version-1').text(), '—');
    assert.equal(messages.length, 0);
    w.setAgentStatus(1, false);
    assert.equal($('#agent-1').attr('data-state'), 'stopped');
    assert.equal($('#stop-1').prop('disabled'), true);
    assert.equal($('#start-1').prop('disabled'), false);
});

test('start, stop and restart handlers recover after state changes without duplicate callbacks', t => {
    const {w, $, actions} = page(t);
    w.setAgentStatus(1, true);
    $('#start-1')[0].click();
    assert.equal(actions.length, 0);
    w.setAgentStatus(1, null);
    w.setAgentStatus(1, null);
    $('#start-1')[0].click();
    assert.deepEqual(actions, [['start', 1]]);
    $('#stop-1')[0].click();
    assert.equal(actions.length, 1);
    w.setAgentStatus(1, true);
    $('#stop-1')[0].click();
    $('#reload-1')[0].click();
    assert.deepEqual(actions, [['start', 1], ['stop', 1], ['restart', 1]]);
    assert.equal($('#agent-1').attr('data-state'), 'ready');
    w.setAgentStatus(1, false);
    assert.equal($('#agent-status-1').text(), 'Stopped');
    assert.equal($('#start-1').prop('disabled'), false);
});

test('SSH action errors are shown safely and never treated as success', t => {
    const {w, calls, messages} = page(t);
    let refreshes = 0;
    w.getAgent = () => refreshes++;
    w.agentAction('start', 1, {});
    assert.equal(calls[0].dataType, 'json');
    calls[0].error({status: 502, responseJSON: {error: 'SSH credentials are not configured for this server'}});
    assert.match(messages[0][0], /SSH credentials/);
    assert.equal(messages[0][2].escapeHtml, true);
    calls[0].success('<!doctype html>');
    assert.equal(refreshes, 0);
});

test('queued agent controls wait for task completion before refreshing', t => {
    const {w, calls} = page(t);
    let task;
    w.runInstallationTaskCheck = (ids, agentId) => task = [Array.from(ids), agentId];
    w.agentAction('restart', 1, {});
    w.jQuery.fn.dialog = function () { return this; };
    calls[0].success({status: 'queued', task_id: 9});
    assert.deepEqual(task, [[9], 1]);
});

test('task polling uses one timer, backs off, and stops after completion', t => {
    const {w, calls} = page(t);
    Object.defineProperty(w.document, 'hidden', {value: false});
    let now = 0, sequence = 0;
    const timers = new Map();
    w.Date.now = () => now;
    w.setTimeout = (callback, delay) => {
        timers.set(++sequence, {callback, delay});
        return sequence;
    };
    w.clearTimeout = id => timers.delete(id);
    const tick = () => {
        assert.equal(timers.size, 1);
        const [id, timer] = [...timers][0];
        timers.delete(id);
        now += timer.delay;
        timer.callback();
    };
    w.runInstallationTaskCheck([7, 7]);
    assert.equal(timers.size, 1);
    tick();
    assert.equal(calls.length, 1);
    w.checkInstallationTask();
    assert.equal(calls.length, 1); // No overlapping request for the same task.
    calls[0].success({status: 'created'});
    calls[0].complete();
    assert.equal([...timers.values()][0].delay, 10000);
    tick();
    calls[1].success({status: 'created'});
    calls[1].complete();
    assert.equal([...timers.values()][0].delay, 20000);
    tick();
    calls[2].success({status: 'completed', server: 'example.test'});
    calls[2].complete();
    assert.equal(timers.size, 0);
    assert.deepEqual(Array.from(w.getInstallationTasksFromSessionStorage()), []);
});

test('removed task stops polling after history cleanup', t => {
    const {w, calls} = page(t);
    let timer;
    w.setTimeout = callback => { timer = callback; return 1; };
    w.clearTimeout = () => { timer = null; };
    w.runInstallationTaskCheck([8]);
    const realNow = w.Date.now;
    w.Date.now = () => realNow() + 60000;
    timer();
    calls[0].error({status: 404});
    calls[0].complete();
    assert.equal(timer, null);
    assert.deepEqual(Array.from(w.getInstallationTasksFromSessionStorage()), []);
});
