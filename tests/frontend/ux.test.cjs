const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');

const scripts = path.resolve(__dirname, '../../app/static/js');
const messages = {network_error: 'Offline', server_error: 'Try later', unauthorized: 'Sign in',
    forbidden: 'No access', validation_error: 'Check fields', not_found: 'Not found',
    conflict: 'Conflict', rate_limit: 'Wait', request_error: 'Request failed',
    loading: 'Loading', widget_error: 'Unavailable', retry: 'Retry', table_label: 'Data', action: 'Action'};

async function page(t, html = '', mobile = false) {
    const dom = new JSDOM(`<!doctype html><body><script id="rmon-ui-strings" type="application/json">${JSON.stringify(messages)}</script>${html}</body>`,
        {url: 'http://rmon.test', runScripts: 'outside-only', pretendToBeVisual: true});
    t.after(() => dom.window.close());
    const w = dom.window;
    const media = {matches: mobile, addEventListener: (_, fn) => {media.change = fn;}};
    w.matchMedia = () => media;
    w.toastr = {error: () => {}, clear: () => {}};
    for (const file of ['jquery-3.6.0.min.js', 'jquery-ui.min.js', 'ux.js']) {
        w.eval(fs.readFileSync(path.join(scripts, file), 'utf8'));
    }
    w.jQuery.fx.off = true;
    await new Promise(resolve => w.jQuery(resolve));
    return {w, $: w.jQuery, ui: w.RmonUI, media};
}

test('request errors are localized and do not display backend HTML or tracebacks', async t => {
    const {ui} = await page(t);
    for (const [status, key] of [[0,'network_error'],[400,'validation_error'],[401,'unauthorized'],
        [403,'forbidden'],[404,'not_found'],[409,'conflict'],[422,'validation_error'],
        [429,'rate_limit'],[500,'server_error'],[503,'server_error'],[418,'request_error']]) {
        assert.equal(ui.requestError({status, responseJSON: {error: '<script>private traceback</script>'}}), messages[key]);
    }
});

test('failed overview fragment offers retry and restores content when retry succeeds', async t => {
    const {ui, $} = await page(t, '<table><tbody id="widget"></tbody></table>');
    const requests = [];
    $.ajax = options => { requests.push(options); options.beforeSend(); };
    ui.loadFragment('#widget', '/overview/users');
    assert.equal($('#widget').attr('aria-busy'), 'true');
    assert.equal(requests[0].global, false);
    requests[0].error({status: 500});
    assert.equal($('#widget').attr('aria-busy'), 'false');
    assert.equal($('#widget button').text(), 'Retry');
    $('#widget button').trigger('click');
    assert.equal(requests.length, 2);
    requests[1].success('<tr><td>Alice</td></tr>');
    assert.equal($('#widget').text(), 'Alice');
    assert.equal($('#widget').attr('aria-busy'), 'false');
    assert.equal($('#widget button').length, 0);
});

test('legacy error text is replaced and absent role-specific widgets make no requests', async t => {
    const {ui, $} = await page(t, '<table id="widget"></table>');
    let request;
    $.ajax = options => {request = options; options.beforeSend();};
    ui.loadFragment('#missing', '/private');
    assert.equal(request, undefined);
    ui.loadFragment('#widget', '/overview/logs');
    request.success('error: secret backend traceback');
    assert.equal($('#widget').text(), 'UnavailableRetry');
});

test('chart loading and error states do not accumulate and ready restores canvas', async t => {
    const {ui, $} = await page(t, '<div id="chart"><canvas></canvas></div>');
    ui.widgetState('#chart', 'loading');
    ui.widgetState('#chart', 'loading');
    assert.equal($('#chart .widget-state').length, 1);
    assert.equal($('#chart canvas').css('display'), 'none');
    ui.widgetState('#chart', 'error', () => {});
    ui.widgetState('#chart', 'ready');
    assert.equal($('#chart .widget-state').length, 0);
    assert.notEqual($('#chart canvas').css('display'), 'none');
});

const navigation = '<aside id="main-navigation"><a href="/overview">Overview</a><a href="/admin">Admin</a></aside>' +
    '<button id="menu-toggle"></button><button id="menu-backdrop" hidden></button>';

test('mobile menu opens, closes on Escape and restores focus to toggle', async t => {
    const {ui, w, $} = await page(t, navigation, true);
    ui.initNavigation();
    assert.equal($('#menu-toggle').attr('aria-expanded'), 'false');
    assert.equal(w.document.getElementById('main-navigation').inert, true);
    $('#menu-toggle')[0].click();
    assert.equal($('#menu-toggle').attr('aria-expanded'), 'true');
    assert.equal($('#menu-backdrop')[0].hidden, false);
    assert.equal(w.document.activeElement.textContent, 'Overview');
    w.document.dispatchEvent(new w.KeyboardEvent('keydown', {key: 'Escape'}));
    assert.equal($('#menu-toggle').attr('aria-expanded'), 'false');
    assert.equal(w.document.activeElement.id, 'menu-toggle');
});

test('desktop menu preference survives resize while mobile starts collapsed', async t => {
    const {ui, w, $, media} = await page(t, navigation);
    ui.initNavigation();
    $('#menu-toggle')[0].click();
    assert.equal(w.sessionStorage.getItem('hide_menu'), 'hide');
    assert.ok(w.document.body.classList.contains('nav-collapsed'));
    media.matches = true; media.change();
    assert.equal($('#menu-toggle').attr('aria-expanded'), 'false');
    media.matches = false; media.change();
    assert.ok(w.document.body.classList.contains('nav-collapsed'));
});

test('legacy action controls support keyboard activation without duplicate activation', async t => {
    const {w, $} = await page(t, '<span id="action" onclick="" title="Edit"></span>');
    let clicks = 0;
    $('#action').on('click', () => clicks++);
    assert.equal($('#action').attr('role'), 'button');
    assert.equal($('#action').attr('aria-label'), 'Edit');
    $('#action')[0].dispatchEvent(new w.KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
    assert.equal(clicks, 1);
});

test('enhancement keeps a single scroll region when a table plugin inserts a wrapper', async t => {
    const {w, ui} = await page(t, '<main class="container"><div class="table-scroll"><div class="dataTables_wrapper"><table class="overview"></table></div></div></main>');
    w.document.querySelector('table').getClientRects = () => [{width: 600, height: 400}];
    ui.enhance(w.document);
    ui.enhance(w.document);
    assert.equal(w.document.querySelectorAll('.table-scroll').length, 1);
});

test('empty checkbox labels and custom comboboxes get meaningful field names', async t => {
    const {w, ui, $} = await page(t, '<table><tr><td>Enabled</td><td><label for="enabled"></label><input type="checkbox" id="enabled"></td>' +
        '<td>Accept cookies</td><td><label for="cookies"></label><input type="checkbox" id="cookies"></td></tr>' +
        '<tr><td>Protocol</td><td><select id="protocol"><option>HTTP</option></select></td></tr></table>');
    $('#protocol').selectmenu();
    ui.enhance(w.document);
    assert.equal($('#enabled').attr('aria-label'), 'Enabled');
    assert.equal($('#cookies').attr('aria-label'), 'Accept cookies');
    assert.equal($('#protocol-button').attr('aria-label'), 'Protocol');
});

test('mobile menu traps Tab and closes when a destination is chosen', async t => {
    const {w, ui, $} = await page(t, navigation, true);
    for (const link of w.document.querySelectorAll('aside a')) link.getClientRects = () => [{width: 100, height: 44}];
    ui.initNavigation();
    $('#menu-toggle')[0].click();
    w.document.dispatchEvent(new w.KeyboardEvent('keydown', {key: 'Tab', shiftKey: true}));
    assert.equal(w.document.activeElement.id, 'menu-toggle');
    w.document.dispatchEvent(new w.KeyboardEvent('keydown', {key: 'Tab', shiftKey: true}));
    assert.equal(w.document.activeElement.textContent, 'Admin');
    // Suppress navigation: this test verifies only the menu's click handler.
    $('aside a').on('click', event => event.preventDefault()).last()[0].click();
    assert.equal($('#menu-toggle').attr('aria-expanded'), 'false');
    assert.equal($('#menu-backdrop')[0].hidden, true);
});

test('dialog keeps viewport constraints after animation restores inline styles', async t => {
    const {w, $} = await page(t, '<div id="editor">Fields</div>');
    w.innerWidth = 390;
    $('#editor').dialog({width: 1225, autoOpen: false});
    const dialog = $('#editor').dialog('widget');
    // jsdom has no layout engine; expose the visible box used by jQuery's positioning code.
    dialog[0].getClientRects = () => [{width: 366, height: 400}];
    $('#editor').dialog('open');
    assert.equal(dialog[0].style.width, '366px');
    dialog.attr('style', 'position: absolute; display: block; width: 1225px');
    $('#editor').trigger('dialogfocus');
    assert.equal(dialog[0].style.width, '366px');
    assert.equal(dialog[0].style.position, 'fixed');
    assert.equal(dialog[0].style.display, 'flex');
    assert.equal($('#editor')[0].style.overflow, 'auto');
});

async function statusEditor(t) {
    const context = await page(t, '<div id="translate" data-next="Next"></div>' +
        '<div id="create-status-page-step-1"><table id="create-status-page-step-1-overview" title="New"></table>' +
        '<input id="new-status-page-name"><input id="new-status-page-slug">' +
        '<p id="status-page-url-preview" data-prefix="/rmon/status/"></p></div>' +
        '<div id="create-status-page-step-2"><table id="create-status-page-step-2-overview" title="New"></table>' +
        '<input id="new-status-page-desc"><textarea id="new-status-page-style"></textarea></div>' +
        '<div id="enabled-check"></div><div id="all-checks"></div>');
    Object.assign(context.w, {clearTips: () => {}, cancel_word: 'Cancel', back_word: 'Back', add_word: 'Add'});
    context.w.eval(fs.readFileSync(path.join(scripts, 'rmon/status_page.js'), 'utf8'));
    await new Promise(resolve => context.$(resolve));
    return context;
}

test('status page slug is suggested, preview is correct and manual URL is preserved', async t => {
    const {w, $} = await statusEditor(t);
    w.createStatusPageStep1();
    $('#new-status-page-name').val('API Health').trigger('input');
    assert.equal($('#new-status-page-slug').val(), 'api-health');
    assert.equal($('#status-page-url-preview').text(), 'http://rmon.test/rmon/status/api-health');
    $('#new-status-page-slug').val('public-api').trigger('input');
    $('#new-status-page-name').val('Renamed').trigger('input');
    assert.equal($('#new-status-page-slug').val(), 'public-api');
});

test('status page Back preserves draft and Cancel resets it for a new page', async t => {
    const {w, $} = await statusEditor(t);
    w.createStatusPageStep1();
    $('#new-status-page-name').val('API Health').trigger('input');
    $('#create-status-page-step-1').dialog('option', 'buttons')[0].click.call($('#create-status-page-step-1')[0]);
    $('#new-status-page-desc').val('Public description');
    $('#create-status-page-step-2').dialog('option', 'buttons')[1].click.call($('#create-status-page-step-2')[0]);
    assert.equal($('#new-status-page-name').val(), 'API Health');
    assert.equal($('#new-status-page-slug').val(), 'api-health');
    assert.equal($('#new-status-page-desc').val(), 'Public description');
    $('#create-status-page-step-1').dialog('option', 'buttons')[1].click.call($('#create-status-page-step-1')[0]);
    w.createStatusPageStep1();
    assert.equal($('#new-status-page-name').val(), '');
    assert.equal($('#new-status-page-desc').val(), '');
    assert.equal($('#new-status-page-slug').data('manually-edited'), false);
});
