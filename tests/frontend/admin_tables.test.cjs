const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const scripts = path.resolve(__dirname, '../../app/static/js');
const row = id => '<tr id="user-' + id + '"><td>' + id + '</td><td>User ' + id +
    '</td><td class="actions-column"><button type="button" data-edit="' + id +
    '">Edit</button><button type="button" disabled>Unavailable</button><a href="#history-' + id + '">History</a></td></tr>';
const table = '<main class="container"><div id="tabs"><table id="users" class="overview"><thead>' +
    '<tr><th>Id</th><th>Name</th><th class="actions-column">Actions</th></tr></thead><tbody>' +
    row(1) + row(2) + '</tbody></table></div></main>';

async function page(t, savedState) {
    const dom = new JSDOM('<!doctype html><body>' + table + '</body>',
        {url: 'http://rmon.test/admin', runScripts: 'outside-only', pretendToBeVisual: true});
    t.after(() => dom.window.close());
    const w = dom.window;
    w.matchMedia = () => ({matches: false, addEventListener() {}});
    if (savedState) w.localStorage.setItem('DataTables_users_/admin', JSON.stringify(savedState));
    for (const file of ['jquery-3.6.0.min.js', 'jquery-ui.min.js', 'dataTables.min.js', 'ux.js']) {
        w.eval(fs.readFileSync(path.join(scripts, file), 'utf8'));
    }
    await new Promise(resolve => w.jQuery(resolve));
    const api = w.RmonUI.initAdminTable('#users');
    return {w, $: w.jQuery, ui: w.RmonUI, api};
}

test('admin table separates controls, scrolling and pagination and Actions cannot sort or search', async t => {
    const {w, $, api} = await page(t);
    assert.equal($('#users_wrapper > .admin-table-toolbar .dataTables_length').length, 1);
    assert.equal($('#users_wrapper > .admin-table-toolbar .dataTables_filter').length, 1);
    assert.equal($('#users_wrapper > .table-scroll > #users').length, 1);
    assert.equal($('#users_wrapper > .admin-table-bottom .dataTables_paginate').length, 1);
    assert.equal($('.table-scroll').length, 1);
    const actions = api.settings()[0].aoColumns[2];
    assert.equal(actions.bSortable, false);
    assert.equal(actions.bSearchable, false);
    const order = JSON.stringify(api.order());
    $('#users th.actions-column').trigger('click');
    assert.equal(JSON.stringify(api.order()), order);
    assert.equal($('#users th.actions-column').attr('tabindex'), undefined);
    api.search('Unavailable').draw();
    assert.equal(api.rows({search: 'applied'}).count(), 0);
    assert.equal(w.RmonUI.initAdminTable('#missing'), undefined);
});

test('persisted sorting on the former icon column is discarded on reload', async t => {
    const {api} = await page(t, {time: Date.now(), start: 0, length: 25, order: [[2, 'desc']],
        search: {search: '', smart: true, regex: false, caseInsensitive: true},
        columns: [0, 1, 2].map(() => ({visible: true, search: {search: ''}}))});
    assert.equal(JSON.stringify(api.order()), '[[0,"asc"]]');
});

test('three-dot menus are idempotent, labelled, and only one opens at a time', async t => {
    const {w, $, ui} = await page(t);
    ui.enhance(w.document);
    ui.enhance(w.document);
    assert.equal($('.row-actions-toggle').length, 2);
    assert.equal(new Set($('.row-actions-menu').map((_, el) => el.id).get()).size, 2);
    assert.equal($('.row-actions-toggle').first().attr('aria-label'), 'Actions: 1');
    $('.row-actions-toggle')[0].click();
    assert.equal($('.row-actions-toggle').first().attr('aria-expanded'), 'true');
    assert.equal(w.document.activeElement.textContent, 'Edit');
    $('.row-actions-toggle')[1].click();
    assert.equal($('.row-actions-toggle').first().attr('aria-expanded'), 'false');
    assert.equal($('.row-actions-menu').filter((_, el) => !el.hidden).length, 1);
    w.document.body.click();
    assert.equal($('.row-actions-menu').filter((_, el) => !el.hidden).length, 0);
});

test('keyboard navigation skips disabled actions, wraps, and Escape restores focus', async t => {
    const {w, $} = await page(t);
    const key = name => w.document.activeElement.dispatchEvent(new w.KeyboardEvent('keydown', {key: name, bubbles: true}));
    $('.row-actions-toggle')[0].focus();
    key('ArrowDown');
    assert.equal(w.document.activeElement.textContent, 'Edit');
    key('ArrowDown');
    assert.equal(w.document.activeElement.textContent, 'History');
    key('ArrowDown');
    assert.equal(w.document.activeElement.textContent, 'Edit');
    key('End');
    assert.equal(w.document.activeElement.textContent, 'History');
    key('Home');
    assert.equal(w.document.activeElement.textContent, 'Edit');
    key('Escape');
    assert.equal(w.document.activeElement, $('.row-actions-toggle')[0]);
    assert.equal($('.row-actions-menu')[0].hidden, true);
    key('ArrowUp');
    assert.equal(w.document.activeElement.textContent, 'History');
    key('Tab');
    assert.equal($('.row-actions-menu')[0].hidden, true);
});

test('row actions keep their callbacks and disabled items cannot invoke them', async t => {
    const {w, $} = await page(t);
    let edits = 0;
    let disabledClicks = 0;
    $('#user-2 [data-edit]').on('click', () => edits++);
    $('#user-2 button:disabled').on('click', () => disabledClicks++);
    $('#user-2 .row-actions-toggle')[0].click();
    $('#user-2 button:disabled')[0].click();
    assert.equal(disabledClicks, 0);
    $('#user-2 [data-edit]')[0].click();
    assert.equal(edits, 1);
    assert.equal($('#user-2 .row-actions-menu')[0].hidden, true);
    assert.notEqual(w.document.activeElement, $('#user-1 .row-actions-toggle')[0]);
});

test('menu is clamped to viewport and closes on table redraw, scrolling and resize', async t => {
    const {w, $, api} = await page(t);
    w.innerWidth = 390; w.innerHeight = 500;
    const toggle = $('.row-actions-toggle')[0];
    const menu = $('.row-actions-menu')[0];
    toggle.getBoundingClientRect = () => ({top: 430, bottom: 474, right: 382});
    menu.getBoundingClientRect = () => ({width: 220, height: 180});
    toggle.click();
    assert.equal(menu.style.left, '158px');
    assert.equal(menu.style.top, '246px');
    menu.dispatchEvent(new w.Event('scroll'));
    assert.equal(menu.hidden, false);
    w.document.dispatchEvent(new w.Event('scroll'));
    assert.equal(menu.hidden, true);
    toggle.click(); api.draw(false);
    assert.equal(menu.hidden, true);
    toggle.click(); w.dispatchEvent(new w.Event('resize'));
    assert.equal(menu.hidden, true);
});

test('AJAX rows survive sorting, filtering and pagination; removed rows never return', async t => {
    const {w, $, ui, api} = await page(t);
    const newRow = $(row(3));
    let calls = 0;
    newRow.find('[data-edit]').on('click', () => calls++);
    ui.addTableRows('#users', newRow);
    assert.equal(api.rows().count(), 3);
    api.page.len(1).order([[0, 'desc']]).draw();
    assert.equal($('#users tbody tr').first().attr('id'), 'user-3');
    $('#user-3 .row-actions-toggle')[0].click();
    $('#user-3 [data-edit]')[0].click();
    assert.equal(calls, 1);
    api.search('User 3').draw();
    assert.equal(api.rows({search: 'applied'}).count(), 1);
    ui.removeTableRow('#user-3');
    api.search('').page.len(25).order([[0, 'asc']]).draw();
    assert.equal(api.rows().count(), 2);
    assert.equal($('#user-3').length, 0);
    assert.equal($('.row-actions-toggle').length, 2);
    assert.equal(w.document.querySelectorAll('.table-scroll .table-scroll').length, 0);
});

test('plain AJAX tables receive the same menu without enabling sorting', async t => {
    const {w, $, ui} = await page(t);
    $('<table id="plain"><tbody></tbody></table>').appendTo('main');
    ui.addTableRows('#plain', row(9));
    assert.equal($('#plain .row-actions-toggle').length, 1);
    assert.equal($.fn.dataTable.isDataTable($('#plain')[0]), false);
    ui.removeTableRow('#user-9');
    assert.equal(w.document.getElementById('user-9'), null);
});

for (const [file, tableId, handler, inputPrefix] of [
    ['users.js', 'ajax-users', 'updateUser', 'login'],
    ['admin/server.js', 'ajax-servers', 'updateServer', 'hostname'],
    ['admin/group.js', 'ajax-group', 'updateGroup', 'name'],
    ['admin/cred.js', 'ssh_enable_table', 'updateSSH', 'ssh_name']
]) {
    test(file + ': dynamically added fields save exactly once without reloading scripts', async t => {
        const {w, $, ui} = await page(t);
        $('<table>', {id: tableId}).append('<tbody></tbody>').appendTo('main');
        Object.assign(w, {add_word: 'Add', cancel_word: 'Cancel', sshKeyEnableShow() {}});
        w.eval(fs.readFileSync(path.join(scripts, file), 'utf8'));
        const calls = [];
        w[handler] = id => calls.push(id);
        await new Promise(resolve => $(resolve));
        ui.addTableRows('#' + tableId, '<tr id="dynamic"><td><input id="' + inputPrefix + '-9" value="new"></td></tr>');
        $('#' + inputPrefix + '-9').val('edited').trigger('change');
        assert.deepEqual(calls, ['9']);
    });
}

test('new row checkbox and select widgets initialize before a table draw', async t => {
    const {w, $, ui, api} = await page(t);
    ui.addTableRows('#users', '<tr id="user-4"><td>4</td><td><label for="active-4">Active</label>' +
        '<input type="checkbox" id="active-4"><select id="role-4"><option>Editor</option></select></td><td class="actions-column"></td></tr>');
    assert.ok($('#active-4').checkboxradio('instance'));
    assert.ok($('#role-4').selectmenu('instance'));
    api.order([[0, 'desc']]).draw();
    assert.equal(w.document.querySelectorAll('#role-4-button').length, 1);
});

test('server poll before widget initialization does not throw or trigger a save', async t => {
    const {w, $} = await page(t);
    $('<div>').append('<label for="server_enabled-9">Enabled</label><input type="checkbox" id="server_enabled-9">' +
        '<select id="servergroup-9"><option value="1">Default</option></select>' +
        '<select id="credentials-9"><option value="1">SSH</option></select>').appendTo('main');
    Object.assign(w, {add_word: 'Add', cancel_word: 'Cancel'});
    w.eval(fs.readFileSync(path.join(scripts, 'admin/server.js'), 'utf8'));
    const requests = [];
    $.ajax = options => requests.push(options);
    w.serverIsUp(9);
    assert.doesNotThrow(() => requests[0].success({status: 'up', enabled: 1, group_id: 1, cred_id: 1}));
    assert.equal($('#server_enabled-9').prop('checked'), true);
    assert.equal(requests.length, 1);
});

test('OIDC provider and mapping callbacks remain usable inside a single Actions cell', async t => {
    const {w, $, ui} = await page(t);
    const messages = {mappings_action: 'Mappings', edit_action: 'Edit', delete_action: 'Delete',
        enabled: 'Enabled', disabled: 'Disabled', active: 'Active', no_providers: 'No providers', no_mappings: 'No mappings'};
    $('<script>', {id:'oidc-translations', type:'application/json'}).text(JSON.stringify(messages)).appendTo('body');
    $('body').append('<table><tbody id="oidc-provider-list"></tbody></table>' +
        '<div id="oidc-provider-dialog"><form id="oidc-provider-form"><input id="oidc-provider-id"><input id="oidc-client-id"></form></div>' +
        '<div id="oidc-mappings-dialog"><table><tbody id="oidc-mapping-list"></tbody></table></div>' +
        '<div id="oidc-mapping-dialog"><form id="oidc-mapping-form"><input id="oidc-mapping-id"><input id="oidc-external-group"></form></div>');
    const requests = [];
    $.ajax = options => requests.push(options);
    w.eval(fs.readFileSync(path.join(scripts, 'admin/oidc.js'), 'utf8'));
    await new Promise(resolve => $(resolve));
    assert.equal(requests[0].url, '/admin/oidc/providers');
    requests[0].success([]);
    assert.equal($('#oidc-provider-list td').attr('colspan'), '4');
    requests[0].success([{id: 7, label: 'Company', slug: 'company', client_id: 'public-client', enabled: true}]);
    ui.enhance(w.document);
    assert.equal($('#oidc-provider-list tr > td').length, 4);
    assert.equal($('#oidc-provider-list .row-actions-toggle').length, 1);
    $('#oidc-provider-list [data-action=map]')[0].click();
    assert.equal(requests[1].url, '/admin/oidc/providers/7/mappings');
    requests[1].success([]);
    assert.equal($('#oidc-mapping-list td').attr('colspan'), '6');
    requests[1].success([{id: 8, external_group: 'ops', group_id: 1, role_id: 2, priority: 100, active: true}]);
    ui.enhance(w.document);
    assert.equal($('#oidc-mapping-list tr > td').length, 6);
    assert.equal($('#oidc-mapping-list .row-actions-toggle').length, 1);
    $('#oidc-mapping-list [data-action=edit]')[0].click();
    assert.equal($('#oidc-mapping-id').val(), '8');
    assert.equal($('#oidc-external-group').val(), 'ops');
    $('#oidc-provider-list [data-action=edit]')[0].click();
    assert.equal($('#oidc-provider-id').val(), '7');
    assert.equal($('#oidc-client-id').val(), 'public-client');
});
