const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'app/static/js/rmon/dashboard.js'), 'utf8');
const raw = fs.readFileSync(path.join(root, 'app/templates/languages/dashboard_en.html'), 'utf8');
const strings = JSON.parse(raw.slice(raw.indexOf('=') + 1, raw.lastIndexOf('%}')));
const settle = () => new Promise(resolve => setTimeout(resolve, 5));
function snapshot() {
    return {counts:{up:1, down:1, stale:0, warning:0, disabled:0}, updated_at:new Date().toISOString(), history_start:'2026-09-27T12:00:00Z', history_available:true,
        items:[1,2].map(id => ({id, name:id===1?'Store <img onerror="alert(1)">':'API', description:'Production', type:'http', type_id:2, state:id===1?'up':'down',
            group_id:id, group_name:'Group '+id, locations:{up:id===1?1:0, down:id===1?0:1, warning:0, stale:0, disabled:0}, total_locations:1,
            response_ms:id===1?1234.5:null, uptime:99.5, last_result:new Date().toISOString(), history:Array.from({length:24},()=>({total:10,up:10,state:'up'}))}))};
}
async function page(t, {canEdit=true, search=''}={}) {
    const dom = new JSDOM(`<section id="rmon-dashboard" data-can-edit="${canEdit}" data-endpoint="/rmon/dashboard/data">
        <input id="rd-search"><select id="rd-sort"><option value="group">group</option><option value="status">status</option><option value="name">name</option></select><select id="rd-group"></select>
        <input type="checkbox" id="rd-auto" checked><button id="rd-refresh"></button><button id="rd-clear"></button>
        ${['up','down','stale','warning','disabled','all'].map(state=>`<button data-status="${state}"><span data-count="${state}"></span></button>`).join('')}
        <div id="dashboards"></div><p id="rd-updated"></p><p id="rd-error" hidden></p><p id="rd-empty" hidden></p><p id="rd-no-match" hidden></p><p id="rd-history-note" hidden></p>
        </section><script id="rd-strings" type="application/json">${JSON.stringify(strings)}</script>`, {url:'https://rmon.test/rmon/dashboard'+search, runScripts:'outside-only', pretendToBeVisual:true});
    const w=dom.window, d=w.document, timers=[], calls=[];
    let intercept=null, current=snapshot();
    w.setInterval=fn=>{timers.push(fn);return timers.length};
    w.clearInterval=id=>{timers[id-1]=null};
    w.fetch=async (...args)=>{calls.push(args);return intercept?intercept(...args):{ok:true,json:async()=>current}};
    w.eval(source);
    t.after(()=>w.close());
    await settle();
    return {w,d,timers,calls, intercept:fn=>{intercept=fn}, current:value=>{current=value}, click:selector=>d.querySelector(selector).click()};
}
test('cards show real values, safe names and exact detail links', async t=>{
    const p=await page(t);
    assert.equal(p.d.querySelectorAll('.rd-card').length,2);
    assert.equal(p.d.querySelectorAll('.rd-card img').length,0);
    assert.equal(p.d.querySelector('#smon-name-1').getAttribute('href'),'/rmon/dashboard/1/2');
    assert.match(p.d.querySelector('#smon-1').textContent,/1 234,5 ms/);
    assert.equal(p.d.querySelectorAll('.rd-history i').length,48);
    assert.equal(p.d.querySelector('#rd-error').hidden,true);
});
test('search, status, group and sorting survive refresh', async t=>{
    const p=await page(t);
    p.click('[data-status=down]');
    assert.equal(p.d.querySelectorAll('.rd-card').length,1);
    p.d.querySelector('#rd-search').value='API';p.d.querySelector('#rd-search').dispatchEvent(new p.w.Event('input'));
    p.d.querySelector('#rd-sort').value='status';p.d.querySelector('#rd-sort').dispatchEvent(new p.w.Event('change'));
    await p.w.RmonDashboard.refresh();
    assert.equal(p.d.querySelectorAll('.rd-card').length,1);
    assert.ok(p.w.location.search.includes('status=down'));
    assert.equal(p.d.querySelector('#rd-search').value,'API');
    p.click('#rd-clear');assert.equal(p.d.querySelectorAll('.rd-card').length,2);
});
test('autorefresh works while a selector is focused and never overlaps', async t=>{
    const p=await page(t);
    p.d.querySelector('#rd-group').focus();
    let finish;
    p.intercept(()=>new Promise(resolve=>{finish=resolve}));
    p.timers[0]();p.timers[0]();
    assert.equal(p.calls.length,2);
    finish({ok:true,json:async()=>snapshot()});await settle();
    assert.equal(p.d.activeElement.id,'rd-group');
});
test('failed refresh retains cards and reports the failure; next retry recovers', async t=>{
    const p=await page(t);
    p.intercept(async()=>({ok:false,status:503}));await p.w.RmonDashboard.refresh();
    assert.equal(p.d.querySelectorAll('.rd-card').length,2);
    assert.equal(p.d.querySelector('#rd-error').hidden,false);
    p.intercept(null);await p.w.RmonDashboard.refresh();
    assert.equal(p.d.querySelector('#rd-error').hidden,true);
});
test('hidden tabs and edit dialogs pause polling; browser history restores one timer', async t=>{
    const p=await page(t);
    Object.defineProperty(p.d,'hidden',{configurable:true,value:true});p.timers[0]();assert.equal(p.calls.length,1);
    Object.defineProperty(p.d,'hidden',{configurable:true,value:false});
    const overlay=p.d.createElement('div');overlay.className='ui-widget-overlay';p.d.body.append(overlay);p.timers[0]();assert.equal(p.calls.length,1);overlay.remove();
    p.w.dispatchEvent(new p.w.PageTransitionEvent('pagehide',{persisted:true}));
    p.w.dispatchEvent(new p.w.PageTransitionEvent('pageshow',{persisted:true}));await settle();
    assert.equal(p.timers.filter(Boolean).length,1);assert.equal(p.calls.length,2);
});
test('read-only users get no mutation controls, and collapse survives new snapshots', async t=>{
    const p=await page(t,{canEdit:false});
    assert.equal(p.d.querySelectorAll('[data-action],[data-group-action]').length,0);
    p.click('#rd-toggle-1');await p.w.RmonDashboard.refresh();
    assert.equal(p.d.querySelector('#rd-grid-1').hidden,true);
    assert.equal(p.d.querySelector('#rd-toggle-1').getAttribute('aria-expanded'),'false');
});
test('legacy issue-sort URL is honored', async t=>{
    const p=await page(t,{search:'?sort=by_status'});
    assert.equal(p.d.querySelector('.rd-card').id,'smon-2');
});
test('empty groups remain editable and can be selected', async t=>{
    const p=await page(t), data=snapshot();
    data.groups=[{id:3,name:'Empty'}];p.current(data);await p.w.RmonDashboard.refresh();
    assert.ok(p.d.querySelector('#check-group-3 [data-group-action=edit]'));
    p.d.querySelector('#rd-group').value='3';p.d.querySelector('#rd-group').dispatchEvent(new p.w.Event('change'));
    assert.equal(p.d.querySelectorAll('.rd-card').length,0);
    assert.ok(p.d.querySelector('#rd-toggle-3'));
});
