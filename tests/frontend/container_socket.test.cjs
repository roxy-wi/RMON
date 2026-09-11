const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../app/static/js/script.js'), 'utf8');
const initializer = source.split('\n').find(line => line.includes('new ReconnectingWebSocket('));

for (const [protocol, host, expected] of [
    ['http:', 'rmon.test:8080', 'ws://rmon.test:8080'],
    ['https:', 'rmon.test', 'wss://rmon.test'],
    ['https:', '[::1]:8443', 'wss://[::1]:8443'],
]) {
    test(`websocket follows the public ${protocol} origin ${host}`, () => {
        let actual;
        vm.runInNewContext(initializer, {
            window: {location: {protocol, host}},
            ReconnectingWebSocket: function (url) { actual = url; },
        });
        assert.equal(actual, expected);
    });
}
