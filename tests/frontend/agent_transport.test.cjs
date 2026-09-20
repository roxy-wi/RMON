const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.resolve(__dirname, '../../app/static/js/rmon/agent.js'), 'utf8');

for (const status of ['running', 'completed', 'failed']) {
    test(`agent card follows ${status} installation status`, () => {
        const storage = new Map();
        const refreshed = [];
        const context = vm.createContext({
            Map, console, api_v_prefix: '/api/v1.0',
            setInterval: () => 1, clearInterval: () => {}, setTimeout: () => {}, clearTimeout: () => {},
            document: {hidden: false},
            NProgress: {configure: () => {}},
            toastr: {info: () => {}, success: () => {}, error: () => {}},
            sessionStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value)},
            $: {ajax: options => options.success({status, service_name: 'Agent', server: 'test'})},
        });
        vm.runInContext(source, context);
        context.getAgent = id => refreshed.push(id);
        vm.runInContext('runInstallationTaskCheck([10], 7); checkInstallationStatus(10);', context);
        assert.deepEqual(refreshed, status === 'running' ? [] : [7]);
    });
}
