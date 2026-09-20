const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

function page(t) {
    const dom = new JSDOM('<body><div id="agent-1"></div><a id="start-1"><span></span></a><a id="reload-1"><span></span></a>' +
        '<a id="stop-1"><span></span></a><time id="agent-uptime-1"></time><span id="agent-total-checks-1"></span></body>',
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

test('agent probes request JSON and accept already-decoded values', t => {
    const {w, $, calls} = page(t);
    w.getAgentStatus('host', 1);
    assert.equal(calls[0].dataType, 'json');
    calls[0].success({running: true});
    assert.ok($('#agent-1').hasClass('div-server-head-up'));
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
    assert.ok($('#agent-1').hasClass('div-server-head-down'));
    assert.doesNotThrow(() => calls[0].success('<!doctype html>'));
    assert.equal($('#start-1 span').attr('aria-disabled'), 'false');
    w.getAgentTotalChecks('host', 1);
    calls[1].error({status: 502});
    assert.equal($('#agent-total-checks-1').text(), '—');
});

test('start, stop and restart handlers recover after state changes without duplicate callbacks', t => {
    const {w, $, actions} = page(t);
    w.setAgentStatus(1, true);
    $('#start-1 span').trigger('click');
    assert.equal(actions.length, 0);
    w.setAgentStatus(1, null);
    w.setAgentStatus(1, null);
    $('#start-1 span').trigger('click');
    assert.deepEqual(actions, [['start', 1]]);
    $('#stop-1 span').trigger('click');
    assert.equal(actions.length, 1);
    w.setAgentStatus(1, true);
    $('#stop-1 span').trigger('click');
    $('#reload-1 span').trigger('click');
    assert.deepEqual(actions, [['start', 1], ['stop', 1], ['restart', 1]]);
    assert.ok(!$('#agent-1').hasClass('div-server-head-down'));
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
