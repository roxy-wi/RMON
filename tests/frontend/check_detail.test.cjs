const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const repo = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(repo, 'app/static/js/rmon/check_detail.js'), 'utf8');
const raw = fs.readFileSync(path.join(repo, 'app/templates/languages/check_detail_en.html'), 'utf8');
const strings = JSON.parse(raw.slice(raw.indexOf('=') + 1, raw.lastIndexOf('%}')));
const settle = () => new Promise(resolve => setTimeout(resolve, 5));
const stamp = minutes => new Date(Date.UTC(2026,8,29,11,minutes)).toISOString();
function snapshot(location = null, kind = 'http') {
    const metricNames = kind === 'ping' ? ['response_time','avg_resp_time','max_resp_time','min_resp_time','packet_loss_percent'] : ['response_time','name_lookup','connect','app_connect','pre_transfer','redirect','start_transfer','download'];
    const locations = [1,2].map(id => ({id,region:id === 1 ? 'Paris' : 'Frankfurt',country:id === 1 ? 'FR':'DE',agent:'agent-' + id,
        state:'up',status:1,response_ms:174,uptime:99.9,mean_ms:150,last_result:stamp(59),config:{url:'https://example.org',method:'get',interval:60,accepted_status_codes:[200]},timeout:2,retries:1}));
    return {id:8,name:'Store <img src=x onerror=alert(1)>',description:'Production',type:kind,type_id:kind==='ping'?4:2,
        summary:{state:'up',locations:{up:2},total_locations:2,response_ms:1234.5,uptime:99.9},locations,
        series:(location ? metricNames : [1,2]).map((metric,index) => ({location_id:location || metric,id:location ? metric : 'response_time',unit:metric === 'packet_loss_percent'?'%':'ms',
            points:[{x:stamp(0),y:10+index},{x:stamp(30),y:20+index},{x:stamp(60),y:30+index}]})),
        events:[{location_id:location || 1,status:1,date:stamp(59),message:'<script>alert(1)</script>'}],
        selected_location:location,start:stamp(0),end:stamp(60),updated_at:stamp(60),point_limit:2000,truncated:false};
}
async function page(t, {canEdit=true, search='', kind='http'}={}) {
    const dom = new JSDOM(`<html lang="en"><head></head><body><header class="page-header"><h2></h2></header>
        <section id="rmon-check-detail" data-can-edit="${canEdit}" data-endpoint="/rmon/dashboard/8/2/data">
        <h3 id="cd-name"></h3><span id="cd-status"></span><p id="cd-description"></p>${canEdit?'<button id="cd-edit"></button>':''}
        <select id="cd-period"><option value="1">1</option><option value="6">6</option><option value="24">24</option></select><input id="cd-auto" type="checkbox" checked><button id="cd-refresh"></button>
        <nav role="tablist"><button id="cd-tab-overview" data-tab="overview"></button><button id="cd-tab-diagnostic" data-tab="diagnostic"></button></nav>
        <span id="cd-updated"></span><p id="cd-error" hidden></p><div id="cd-content">
        <section id="cd-overview"><div id="cd-notice"></div><strong id="cd-response"></strong><strong id="cd-uptime"></strong><strong id="cd-count"></strong><div id="cd-overview-chart"></div><div id="cd-locations"></div><dl id="cd-parameters"></dl></section>
        <section id="cd-diagnostic" hidden><aside id="cd-picker"></aside><div id="cd-result"></div><div id="cd-diagnostic-chart"></div><div id="cd-events"></div></section>
        <section id="cd-chart-panel"><h4 id="cd-chart-title"></h4><span id="cd-chart-time"></span><div><canvas id="cd-chart"></canvas></div><p id="cd-no-data"></p><div id="cd-legend"></div><p id="cd-limited"></p></section>
        </div><p id="cd-timezone"></p></section><script id="cd-strings" type="application/json">${JSON.stringify(strings)}</script></body></html>`,
        {url:'https://rmon.test/rmon/dashboard/8/2'+search,runScripts:'outside-only',pretendToBeVisual:true});
    const w=dom.window,d=w.document,calls=[],timers=[],charts=[];
    let intercept=null;
    w.setInterval=fn=>{timers.push(fn);return timers.length;};
    w.clearInterval=id=>{timers[id-1]=null;};
    w.Chart=class {
        constructor(canvas, config) {this.canvas=canvas;this.data=config.data;this.options=config.options;this.plugins=config.plugins;charts.push(this);}
        update() {} resize() {}
    };
    w.fetch=async (url, options)=>{calls.push({url:String(url),options}); return intercept ? intercept(url,options) : {ok:true,json:async()=>snapshot(Number(url.searchParams.get('location')) || null, kind)};};
    w.eval(source);t.after(()=>w.close());await settle();
    return {w,d,calls,timers,charts,intercept:fn=>{intercept=fn;},click:selector=>d.querySelector(selector).click()};
}
test('overview is safe, localized, uses European numbers and one chart', async t=>{
    const p=await page(t);
    assert.equal(p.d.querySelector('#cd-response').textContent,'1 234,5 ms');
    assert.equal(p.d.querySelectorAll('#cd-name img').length,0);
    assert.match(p.d.querySelector('#cd-locations').textContent,/France/);
    assert.equal(p.charts.length,1);assert.equal(p.charts[0].data.datasets.length,2);
    assert.equal(p.d.querySelector('#cd-error').hidden,true);
    assert.equal(p.d.querySelector('#cd-content').getAttribute('aria-busy'),'false');
});
test('selecting a location shows all HTTP metrics together and shares the same canvas', async t=>{
    const p=await page(t);p.click('#cd-row-2');await settle();
    assert.equal(p.charts.length,1);assert.equal(p.charts[0].data.datasets.length,8);
    assert.equal(p.d.querySelector('#cd-diagnostic').hidden,false);
    assert.equal(p.d.querySelector('#cd-chart-panel').parentElement.id,'cd-diagnostic-chart');
    assert.equal(p.d.querySelectorAll('#cd-legend output').length,8);
    assert.equal(p.d.querySelectorAll('#cd-events script').length,0);
    assert.ok(p.calls.at(-1).url.includes('location=2'));
    p.d.querySelector('#cd-period').value='6';p.d.querySelector('#cd-period').dispatchEvent(new p.w.Event('change'));await settle();
    assert.ok(p.calls.at(-1).url.includes('hours=6'));assert.ok(p.calls.at(-1).url.includes('location=2'));
    p.click('#cd-tab-overview');await settle();
    assert.equal(p.charts[0].data.datasets.length,2);assert.equal(p.charts.length,1);
});
test('Ping keeps all time metrics and packet loss on the correct axes', async t=>{
    const p=await page(t,{kind:'ping',search:'?tab=diagnostic&location=1'});
    assert.equal(p.charts[0].data.datasets.length,5);
    assert.equal(p.charts[0].data.datasets[4].yAxisID,'percent');
    assert.equal(p.charts[0].options.scales.percent.max,100);
    assert.ok(p.charts[0].data.datasets.slice(0,4).every(set=>set.yAxisID==='ms'));
});
test('rapid location changes discard stale responses', async t=>{
    const p=await page(t);let finishOld;
    p.intercept(url=>Number(url.searchParams.get('location'))===1 ? new Promise(resolve=>{finishOld=resolve;}) : {ok:true,json:async()=>snapshot(2)});
    p.click('#cd-row-1');p.click('#cd-row-2');await settle();
    assert.equal(p.calls[1].options.signal.aborted,true);
    finishOld({ok:true,json:async()=>snapshot(1)});await settle();
    assert.match(p.d.querySelector('#cd-result').textContent,/Frankfurt/);
    assert.equal(p.d.querySelector('#cd-pick-2').getAttribute('aria-pressed'),'true');
});
test('auto-refresh does not overlap or run in hidden tabs and resumes after navigation', async t=>{
    const p=await page(t);let finish;
    p.intercept(()=>new Promise(resolve=>{finish=resolve;}));
    p.d.querySelector('#cd-period').focus();p.timers[0]();p.timers[0]();assert.equal(p.calls.length,2);
    finish({ok:true,json:async()=>snapshot()});await settle();p.intercept(null);
    Object.defineProperty(p.d,'hidden',{configurable:true,value:true});p.timers[0]();assert.equal(p.calls.length,2);
    Object.defineProperty(p.d,'hidden',{configurable:true,value:false});
    p.w.dispatchEvent(new p.w.PageTransitionEvent('pagehide',{persisted:true}));
    p.w.dispatchEvent(new p.w.PageTransitionEvent('pageshow',{persisted:true}));await settle();
    assert.equal(p.timers.filter(Boolean).length,1);assert.equal(p.calls.length,3);
    p.d.querySelector('#cd-auto').checked=false;p.timers.filter(Boolean)[0]();assert.equal(p.calls.length,3);
});
test('failed refresh retains loaded data and its location labels; retry recovers', async t=>{
    const p=await page(t,{search:'?tab=diagnostic&location=1'});
    p.intercept(async()=>({ok:false,status:503}));p.click('#cd-pick-2');await settle();
    assert.equal(p.d.querySelector('#cd-error').hidden,false);
    assert.match(p.d.querySelector('#cd-result').textContent,/Paris/);
    assert.equal(p.d.querySelector('#cd-pick-1').getAttribute('aria-pressed'),'true');
    p.d.querySelector('#cd-period').value='24';p.d.querySelector('#cd-period').dispatchEvent(new p.w.Event('change'));await settle();
    assert.equal(p.d.querySelector('#cd-period').value,'1');
    p.intercept(null);await p.w.RmonCheckDetail.refresh();
    assert.equal(p.d.querySelector('#cd-error').hidden,true);
});
test('empty results and read-only settings remain explicit', async t=>{
    const p=await page(t,{canEdit:false});const empty=snapshot();empty.series.forEach(series=>{series.points=[];});
    p.intercept(async()=>({ok:true,json:async()=>empty}));await p.w.RmonCheckDetail.refresh();
    assert.equal(p.d.querySelector('#cd-no-data').hidden,false);
    assert.equal(p.d.querySelector('#cd-chart').parentElement.hidden,true);
    assert.equal(p.d.querySelector('#cd-edit'),null);
    assert.ok([...p.d.querySelectorAll('#cd-legend output')].every(output=>output.textContent.trim()==='—'));
});
test('a single measurement stays visible as a point', async t=>{
    const p=await page(t), single=snapshot();single.series.forEach(series=>{series.points=series.points.slice(0,1);});
    p.intercept(async()=>({ok:true,json:async()=>single}));await p.w.RmonCheckDetail.refresh();
    assert.equal(p.d.querySelector('#cd-no-data').hidden,true);
    assert.ok(p.charts[0].data.datasets.every(set=>set.pointRadius>0));
});
test('crosshair interpolates every series at the same time and preserves gaps', async t=>{
    const p=await page(t,{search:'?tab=diagnostic&location=1'}), chart=p.charts[0];
    chart.data.datasets[1].data[1].y=null;
    chart.chartArea={left:0,right:600,top:0,bottom:200};
    chart.scales={x:{getValueForPixel:()=>Date.parse(stamp(15))},ms:{getPixelForValue:value=>value}};
    chart.ctx={save(){},restore(){},setLineDash(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},arc(){},fill(){}};
    const plugin=chart.plugins[0];
    plugin.afterEvent(chart,{event:{type:'mousemove',x:150,y:70}});plugin.afterDraw(chart);
    assert.equal(p.d.querySelectorAll('.cd-tip-row').length,8);
    assert.match(p.d.querySelector('#cd-value-0').textContent,/15/);
    assert.equal(p.d.querySelector('#cd-value-1').textContent.trim(),'—');
    plugin.afterEvent(chart,{event:{type:'click',x:150,y:70}});
    plugin.afterEvent(chart,{event:{type:'mouseout'}});assert.ok(chart.$cursor);
    plugin.afterEvent(chart,{event:{type:'click',x:150,y:70}});
    plugin.afterEvent(chart,{event:{type:'mouseout'}});assert.equal(chart.$cursor,null);
});
