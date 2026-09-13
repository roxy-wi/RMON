const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM, VirtualConsole} = require('jsdom');

const scripts = path.resolve(__dirname, '../../app/static/js');

for (const protocol of ['http', 'https']) {
    test(`shared UI and user preferences work without browser notification services over ${protocol}`, async t => {
        const errors = [];
        const output = new VirtualConsole();
        output.on('jsdomError', error => errors.push(error));
        const dom = new JSDOM('<!doctype html><body><div id="translate"></div>' +
            '<select id="theme_select"><option value="dark" selected>Dark</option></select>' +
            '<select id="lang_select"><option value="ru" selected>Russian</option></select></body>',
            {url: `${protocol}://rmon.test/overview`, runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: output});
        t.after(() => dom.window.close());
        const w = dom.window;
        w.csrf_token = 'test-only-csrf';
        w.matchMedia = () => ({matches: false, addEventListener() {}});
        w.WebSocket = function () { throw new Error('Unexpected WebSocket connection'); };
        for (const file of ['jquery-3.6.0.min.js', 'jquery-ui.min.js', 'js.cookie.min.js',
            'select2.js', 'element.js', 'variables.js', 'nprogress.js', 'toastr.js', 'ux.js']) {
            w.eval(fs.readFileSync(path.join(scripts, file), 'utf8'));
        }
        w.jQuery.ajax = () => w.jQuery.Deferred().resolve().promise();
        w.jQuery.getScript = () => w.jQuery.Deferred().resolve().promise();
        w.eval(fs.readFileSync(path.join(scripts, 'script.js'), 'utf8'));
        await new Promise(resolve => w.jQuery(resolve));
        assert.deepEqual(errors, []);
        const groups = [];
        w.changeCurrentGroupF = user => groups.push(user);
        w.saveUserSettings(7);
        assert.deepEqual(groups, [7]);
        assert.equal(w.localStorage.getItem('theme'), 'dark');
        if (protocol === 'https') assert.equal(w.Cookies.get('lang'), 'ru');
        assert.equal(w.document.querySelectorAll('link[href="/static/css/dark.css"]').length, 1);
    });
}
