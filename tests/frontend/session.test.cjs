const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const source = fs.readFileSync(path.resolve(__dirname, '../../app/static/js/session.js'), 'utf8');
const settle = () => new Promise(resolve => setTimeout(resolve, 0));
const ok = () => ({ok: true, json: async () => ({refresh_after: 300})});

async function page(t, {authenticated=true, hidden=false}={}) {
    const dom = new JSDOM('<button id="edit">Edit</button><a href="/logout" id="logout">Logout</a>' +
        (authenticated ? '<script id="rmon-session" data-refresh-url="/api/v1.0/session/refresh"></script>' : ''),
        {url:'https://rmon.test/client-checks', runScripts:'outside-only', pretendToBeVisual:true});
    t.after(() => dom.window.close());
    const w=dom.window, d=w.document, timers=new Map(), listeners=new Map(), calls=[], errors=[];
    let now=1000000, sequence=0, cookie='csrf-one', respond=ok;
    Object.defineProperty(d, 'hidden', {get: () => hidden});
    w.Date.now=() => now;
    w.setTimeout=(fn, delay) => {timers.set(++sequence,{fn,at:now+delay});return sequence;};
    w.clearTimeout=id => timers.delete(id);
    const add=d.addEventListener.bind(d);
    d.addEventListener=(name, fn, options) => {listeners.set(name,[...(listeners.get(name)||[]),fn]);add(name,fn,options);};
    w.Cookies={get: () => cookie};
    w.RmonUI={notifyRequestError: error => errors.push(error.status)};
    w.fetch=async (url, options) => {calls.push({url,...options});return respond(options);};
    w.eval(source); await settle();
    async function advance(ms) {
        const target=now+ms;
        for (;;) {
            const next=[...timers].filter(([,timer])=>timer.at<=target).sort((a,b)=>a[1].at-b[1].at)[0];
            if (!next) break;
            now=next[1].at;timers.delete(next[0]);next[1].fn();await settle();
        }
        now=target; await settle();
    }
    return {w,d,calls,errors,timers,advance, intercept:fn=>{respond=fn}, cookie:value=>{cookie=value},
        async activity(type='keydown', target=d.querySelector('#edit')) {
            for (const fn of listeners.get(type)||[]) fn({type,target,isTrusted:true,key:'a'});
            await settle();
        },
        async visible(value) {hidden=!value;d.dispatchEvent(new w.Event('visibilitychange'));await settle();}
    };
}

test('active user stays signed in beyond one hour with bounded refresh requests', async t => {
    const p=await page(t);
    for(let i=0;i<130;i++){await p.advance(30000);await p.activity(i%2?'wheel':'keydown');}
    assert.equal(p.calls.length,14);
    assert.ok(p.calls.every(call=>call.method==='POST' && call.credentials==='same-origin' &&
        call.headers['X-CSRF-TOKEN']==='csrf-one' && call.url==='/api/v1.0/session/refresh'));
    assert.deepEqual(p.errors,[]);
});

test('idle and background updates never keep a session alive', async t => {
    const p=await page(t);
    await p.advance(10000);await p.activity();
    for(let i=0;i<70;i++) {
        p.d.querySelector('#edit').textContent='Updated '+i;
        p.d.dispatchEvent(new p.w.Event('keydown'));
        await p.advance(60000);
    }
    assert.equal(p.calls.length,1);
    assert.equal(p.timers.size,0);
});

test('hidden pages wait for the user to return and login pages never renew', async t => {
    const p=await page(t,{hidden:true});
    await p.advance(600000);await p.activity();assert.equal(p.calls.length,0);
    await p.visible(true);assert.equal(p.calls.length,1);
    await p.visible(false);await p.advance(600000);await p.activity();assert.equal(p.calls.length,1);
    await p.visible(true);assert.equal(p.calls.length,2);
    const login=await page(t,{authenticated:false});
    await login.activity();assert.equal(login.calls.length,0);
});

test('requests never overlap and current cookies are read for each renewal', async t => {
    const p=await page(t);let finish;
    p.intercept(()=>new Promise(resolve=>{finish=resolve}));
    await p.advance(300001);p.cookie('csrf-two');await p.activity();
    for(let i=0;i<5;i++){await p.advance(1000);await p.activity('pointermove');}
    assert.equal(p.calls.length,2);
    assert.equal(p.calls[1].headers['X-CSRF-TOKEN'],'csrf-two');
    finish(ok());await settle();assert.equal(p.calls.length,2);
});

test('network failures retry while activity is recent and recover without repeated notifications', async t => {
    const p=await page(t);p.intercept(async()=>{throw new TypeError('offline')});
    await p.advance(300001);await p.activity();
    await p.advance(15000);assert.equal(p.calls.length,3);
    assert.deepEqual(p.errors,[0]);
    p.intercept(ok);await p.advance(15000);assert.equal(p.calls.length,4);
    await p.advance(600000);assert.equal(p.calls.length,4);
});

test('expired or disabled sessions stop renewal without navigating away from an editor', async t => {
    for(const status of [401,403,422]) {
        const p=await page(t);p.intercept(()=>({ok:false,status}));
        await p.advance(300001);await p.activity();await p.advance(600000);await p.activity();
        assert.equal(p.calls.length,2);assert.deepEqual(p.errors,[status]);
        assert.equal(p.w.location.pathname,'/client-checks');
    }
});

test('group switch in another tab retries CSRF once with the current cookie', async t => {
    const p=await page(t);
    p.intercept(()=>{p.cookie('csrf-new-group');p.intercept(ok);return {ok:false,status:401}});
    await p.advance(300001);await p.activity();await p.advance(1000);
    assert.equal(p.calls.length,3);assert.equal(p.calls[2].headers['X-CSRF-TOKEN'],'csrf-new-group');
    assert.deepEqual(p.errors,[]);
});

test('leaving cancels a pending request and BFCache restores renewal on activity', async t => {
    const p=await page(t);
    p.intercept(options=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new p.w.DOMException('Aborted','AbortError')))));
    await p.advance(300001);await p.activity();
    p.w.dispatchEvent(new p.w.PageTransitionEvent('pagehide',{persisted:true}));await settle();
    assert.equal(p.calls[1].signal.aborted,true);assert.equal(p.timers.size,0);
    p.intercept(ok);p.w.dispatchEvent(new p.w.PageTransitionEvent('pageshow',{persisted:true}));await settle();
    assert.equal(p.calls.length,3);assert.deepEqual(p.errors,[]);
});

test('logout click stops renewal but hovering its link does not', async t => {
    const p=await page(t);await p.advance(300001);
    await p.activity('pointermove',p.d.querySelector('#logout'));assert.equal(p.calls.length,2);
    await p.advance(300001);await p.activity('pointerdown',p.d.querySelector('#logout'));
    await p.activity();await p.advance(300001);assert.equal(p.calls.length,2);
});

test('reloading the same script does not create another activity listener or request', async t => {
    const p=await page(t);p.w.eval(source);await settle();assert.equal(p.calls.length,1);
    await p.advance(300001);await p.activity();assert.equal(p.calls.length,2);
});
