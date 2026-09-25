const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const scripts = path.resolve(__dirname, '../../app/static/js');
const fixture = fs.readFileSync(path.join(__dirname, 'fixtures/check-editor.html'), 'utf8');

async function editor(t) {
    const dom = new JSDOM('<!doctype html><body><div id="translate" data-add="Add" data-service="location"></div>' + fixture + '</body>',
        {url: 'http://rmon.test', runScripts: 'outside-only', pretendToBeVisual: true});
    t.after(() => dom.window.close());
    const w = dom.window;
    w.matchMedia = () => ({matches: false, addEventListener() {}, removeEventListener() {}});
    w.ResizeObserver = class {observe() {} unobserve() {} disconnect() {}};
    w.toastr = {error() {}, warning() {}};
    w.cancel_word = 'Cancel'; w.delete_word = 'Delete'; w.api_v_prefix = '/api/v1.0';
    w.check_types = {http:2,tcp:1,dns:5,ping:4,smtp:3,rabbitmq:6};
    for (const file of ['jquery-3.6.0.min.js','jquery-ui.min.js','ux.js','tagify.js','rmon/check_editor.js','rmon/smon.js','rmon/check.js']) {
        w.eval(fs.readFileSync(path.join(scripts, file), 'utf8'));
    }
    const $ = w.jQuery;
    w.translate_div = $('#translate');
    $.fx.off = true;
    $('select').selectmenu(); $('input[type=checkbox]').checkboxradio();
    const requests = [], saved = [];
    $.ajax = options => {
        if (options.url === '/rmon/checks/count') options.success('0');
        else if (/\/rmon\/(agents|regions|countries)$/.test(options.url)) options.success([{id:7,name:'Test location',enabled:1}]);
        else if (/\/rmon\/(agent|region|country)\/7$/.test(options.url)) options.success({id:7,name:'Test location'});
        else requests.push(options);
        return options;
    };
    w.getSmonCheck = (...args) => saved.push(args);
    await new Promise(resolve => $(resolve));
    return {w, $, requests, saved, ui:w.CheckEditor};
}

const cases = {
    http: {url:'https://example.test/health',ssl_policy:'require_https'},
    tcp: {ip:'example.test',port:443},
    dns: {ip:'example.test',port:53,resolver:'1.1.1.1',record_type:'mx'},
    ping: {ip:'192.0.2.1',packet_size:56,count_packets:3,use_kernel_timestamp:true},
    smtp: {ip:'smtp.example.test',port:587,username:'monitor',password:'smtp-pass'},
    rabbitmq: {ip:'rabbit.example.test',port:5672,username:'monitor',password:'rabbit-pass',vhost:'/monitor'}
};
const control = {record_type:'dns_record_type',resolver:'resolver-server'};
function fill($, type) {
    $('#new-smon-name').val('Health check');
    for (const [key,value] of Object.entries(cases[type])) {
        const field = $('#new-smon-' + (control[key] || key));
        if (field.attr('type') === 'checkbox') field.prop('checked',value); else field.val(value);
    }
}
function response(type) {
    return {name:'Saved check',place:'all',entities:[],retries:4,description:"Owner's check",priority:'warning',
        runbook:'https://docs.example.test/runbook',check_group:'Production',threshold_timeout:200,
        checks:[{...cases[type],interval:120,method:'post',body_req:'{"name":"O\'Brien"}',header_req:'{"X-Test":"it\'s valid"}',
            accepted_status_codes:type === 'http' ? [200,'300-304'] : [],
            smon_id:{check_timeout:5,enabled:0,telegram_channel_id:9}}]};
}

for (const type of Object.keys(cases)) {
    test(`${type}: create preserves API payload and sends only one request while saving`, async t => {
        const {w,$,ui,requests,saved} = await editor(t);
        w.openSmonDialog(type); fill($,type);
        assert.equal(ui.validate(),true);
        w.addNewSmonServer($('#smon-add-table')[0]);
        w.addNewSmonServer($('#smon-add-table')[0]);
        assert.equal(requests.length,1);
        const request = requests[0], payload = JSON.parse(request.data);
        assert.equal(request.url,`/api/v1.0/rmon/check/${type}`);
        assert.equal(request.type,'post');
        assert.equal(payload.name,'Health check');
        for (const [key,value] of Object.entries(cases[type])) assert.equal(String(payload[key]), typeof value === 'boolean' ? String(Number(value)) : String(value));
        assert.equal(payload.interval,'120');
        assert.equal(payload.enabled,'1');
        assert.equal($('#check-editor-submit').prop('disabled'),true);
        request.success({id:42});
        assert.equal(saved[0][0],42);
        assert.equal(saved[0][3],true);
        assert.equal(ui.isBusy(),false);
    });

    test(`${type}: edit restores values and uses PUT; clone uses POST without losing the draft`, async t => {
        const {w,$,requests} = await editor(t);
        $('#new-smon-telegram').append('<option value="9">Operations</option>');
        w.editSmon(17,type);
        requests.shift().success(response(type));
        assert.equal($('#check_type').prop('disabled'),true);
        assert.equal($('#new-smon-place').prop('disabled'),true);
        assert.equal($('#new-smon-description').val(),"Owner's check");
        assert.equal($('#new-smon-timeout').val(),'5');
        assert.equal($('#new-smon-enable').prop('checked'),false);
        assert.equal($('#new-smon-telegram').val(),'9');
        for (const [key,value] of Object.entries(cases[type])) {
            const field = $('#new-smon-' + (control[key] || key));
            assert.equal(String(field.attr('type') === 'checkbox' ? field.prop('checked') : field.val()),String(value));
        }
        if (type === 'http') {
            assert.equal($('#new-smon-body-req').val(),'{"name":"O\'Brien"}');
            assert.equal($('#new-smon-header-req').val(),'{"X-Test":"it\'s valid"}');
            assert.deepEqual(Array.from(w.tagify.value,tag => tag.value),['200','300-304']);
        }
        $('#check-editor-submit').trigger('click');
        const update = requests.shift();
        assert.equal(update.type,'put');
        assert.equal(update.url,`/api/v1.0/rmon/check/${type}/17`);
        update.error(); // Keep the test dialog available for a subsequent clone.
        w.cloneSmon(17,type);
        requests.shift().success(response(type));
        assert.equal($('#check_type').prop('disabled'),false);
        assert.equal($('#new-smon-place').prop('disabled'),false);
        assert.equal($('#new-smon-name').val(),'Saved check (copy)');
        assert.equal($('#new-smon-group').val(),'Production');
        $('#check-editor-submit').trigger('click');
        assert.equal(requests[0].type,'post');
        assert.equal(requests[0].url,`/api/v1.0/rmon/check/${type}`);
        if (type === 'http') assert.equal(JSON.parse(requests[0].data).ssl_policy, 'require_https');
    });
}

test('switching type and steps preserves shared fields and per-protocol ports', async t => {
    const {w,$,ui} = await editor(t);
    w.openSmonDialog('tcp'); fill($,'tcp');
    $('#new-smon-group').val('Production'); $('#new-smon-runbook').val('https://docs.example.test');
    ui.setType('dns'); assert.equal($('#new-smon-port').val(),'53');
    $('#new-smon-port').val('5353');
    ui.setType('tcp'); assert.equal($('#new-smon-port').val(),'443');
    ui.setType('dns'); assert.equal($('#new-smon-port').val(),'5353');
    ui.showStep(2); ui.showStep(0);
    assert.equal($('#new-smon-name').val(),'Health check');
    assert.equal($('#new-smon-group').val(),'Production');
    assert.equal($('#new-smon-ip').val(),'example.test');
});

test('next validates only the current step; save exposes the first invalid section', async t => {
    const {w,$,ui,requests} = await editor(t);
    w.openSmonDialog('http');
    ui.next();
    assert.equal($('#new-smon-name').attr('aria-invalid'),'true');
    fill($,'http'); $('#new-smon-timeout').val('999');
    ui.next(); assert.equal($('#check-editor-step-1').prop('hidden'),false);
    ui.showStep(2); $('#check-editor-submit').trigger('click');
    assert.equal(requests.length,0);
    assert.equal($('#check-editor-step-1').prop('hidden'),false);
    assert.equal($('#new-smon-timeout').attr('aria-invalid'),'true');
});

test('validation rejects empty RabbitMQ credentials, invalid ports and unsafe URL schemes', async t => {
    const {w,$,ui} = await editor(t);
    w.openSmonDialog('rabbitmq'); fill($,'rabbitmq');
    $('#new-smon-password').val(''); $('#new-smon-port').val('65536');
    assert.equal(ui.validate(),false);
    assert.equal($('#new-smon-password').attr('aria-invalid'),'true');
    assert.equal($('#new-smon-port').attr('aria-invalid'),'true');
    ui.setType('http'); $('#new-smon-url').val('javascript:alert(1)');
    assert.equal(ui.validate(),false);
    assert.equal($('#new-smon-url').attr('aria-invalid'),'true');
});

test('HTTP advanced settings survive editing and expand when validation fails', async t => {
    const {w,$,ui,requests} = await editor(t);
    const data = response('http');
    Object.assign(data.checks[0], {body_json:{path:'$.health',value:'ok'},auth:{basic:{username:'user',password:"a'b"}},
        proxy:{type:'http',host:'proxy.test',port:3128,username:'proxy-user',password:'proxy-pass'},
        headers_response:{required_response_headers:{'X-Health':'yes'},forbidden_headers:null}});
    w.editSmon(17,'http'); requests.shift().success(data);
    assert.equal($('#new-smon-basic_password').val(),"a'b");
    assert.equal($('#new-smon-header-response-required').val(),'{\n  "X-Health": "yes"\n}');
    assert.equal($('#new-smon-body-json-path').val(),'$.health');
    assert.equal($('#smon_http_check_proxy_method').val(),'http');
    assert.equal(ui.validate(),true);
    $('#new-smon-header-req').val('{invalid'); ui.showStep(2);
    assert.equal(ui.validate(),false);
    assert.equal($('#new-smon-header-req').closest('details').prop('open'),true);
    assert.equal($('#check-editor-step-1').prop('hidden'),false);
});

test('selected location is required and entities survive edit and clone', async t => {
    const {w,$,ui,requests} = await editor(t);
    w.openSmonDialog('tcp'); fill($,'tcp');
    $('#new-smon-place').val('agent').trigger('selectmenuchange');
    assert.equal(ui.validate(),false);
    w.addEntityToStatus(7,'Test location');
    assert.equal(ui.validate(),true);
    const data = response('tcp'); data.place='agent'; data.entities=[7];
    w.cloneSmon(17,'tcp'); requests.shift().success(data);
    assert.equal($('#checked-entities > div').length,1);
    assert.equal($('#new-smon-place').val(),'agent');
});

test('save errors keep the draft and allow retry; loading errors prevent empty overwrite', async t => {
    const {w,$,ui,requests} = await editor(t);
    w.openSmonDialog('tcp'); fill($,'tcp');
    $('#check-editor-submit').trigger('click'); requests.shift().error({status:500});
    assert.equal($('#new-smon-name').val(),'Health check');
    assert.equal($('#check-editor-error').prop('hidden'),false);
    assert.equal($('#check-editor-submit').prop('disabled'),false);
    $('#check-editor-submit').trigger('click'); assert.equal(requests.length,1);
    requests.shift().error();
    w.editSmon(99,'tcp'); requests.shift().error({status:404});
    assert.equal(ui.isBlocked(),true);
    assert.equal($('#check-editor-submit').prop('disabled'),true);
    w.addNewSmonServer($('#smon-add-table')[0],99,true);
    assert.equal(requests.length,0);
});

test('new check clears credentials, advanced settings, channels and errors from previous draft', async t => {
    const {w,$,ui} = await editor(t);
    w.openSmonDialog('http');
    $('#new-smon-basic_password').val('secret'); $('#smon_http_check_auth_method').val('basic');
    $('#new-smon-mtls_key').val('secret-key'); $('#new-smon-http_proxy_password').val('proxy-secret');
    $('#new-smon-description').val('Previous'); $('#new-smon-enable').prop('checked',false);
    $('#new-smon-ssl_policy').val('require_http');
    ui.validate();
    w.openSmonDialog('http');
    for (const id of ['basic_password','mtls_key','http_proxy_password','description']) assert.equal($('#new-smon-' + id).val(),'');
    assert.equal($('#smon_http_check_auth_method').val(),'0');
    assert.equal($('#new-smon-enable').prop('checked'),true);
    assert.equal($('#new-smon-ssl_policy').val(),'default');
    assert.equal($('[aria-invalid=true]').length,0);
    assert.deepEqual(Array.from(w.tagify.value,tag => tag.value),['200']);
});

test('summary excludes URL credentials and query values and tabs support keyboard navigation', async t => {
    const {w,$,ui} = await editor(t);
    w.openSmonDialog('http');
    $('#new-smon-url').val('https://user:secret@example.test/health?token=private');
    ui.showStep(2);
    assert.equal($('#check-editor-summary').text().includes('secret'),false);
    assert.equal($('#check-editor-summary').text().includes('private'),false);
    $('#check-editor-tab-2')[0].dispatchEvent(new w.KeyboardEvent('keydown',{key:'Home',bubbles:true}));
    assert.equal($('#check-editor-tab-0').attr('aria-selected'),'true');
});

test('HTTP status codes accept wildcards and ranges and reject reversed ranges', async t => {
    const {w,$,ui,requests} = await editor(t);
    w.openSmonDialog('http'); fill($,'http');
    w.tagify.removeAllTags(); w.tagify.addTags(['204','300-304','4**']);
    assert.deepEqual(Array.from(w.tagify.value, tag => tag.value),['204','300-304','4**']);
    assert.equal(ui.validate(),true);
    $('#check-editor-submit').trigger('click');
    assert.deepEqual(JSON.parse(requests[0].data).accepted_status_codes,['204','300-304','4**']);
    requests.shift().error();
    w.tagify.removeAllTags(); w.tagify.addTags(['400-300']);
    assert.equal(ui.validate(),false);
    assert.equal(w.tagify.DOM.input.getAttribute('aria-invalid'),'true');
    w.tagify.removeAllTags(); w.tagify.addTags(['200']);
    assert.equal(ui.validate(),true);
    assert.equal(w.tagify.DOM.input.hasAttribute('aria-describedby'),false);
});

test('mTLS, headers, proxy, channels and HTTP options retain their exact payload', async t => {
    const {w,$,requests} = await editor(t);
    for (const channel of ['telegram','slack','pd','mm','incidentrelay','email']) {
        $('#new-smon-' + channel).append('<option value="9">Operations</option>');
    }
    const data = response('http');
    Object.assign(data.checks[0], {
        auth:{mtls:{key:'PRIVATE KEY\nbody',cert:'CERTIFICATE\nbody',ca:'CA\nbody'}},
        proxy:{type:'socks5',host:'proxy.test',port:1080,username:'monitor',password:'proxy-pass'},
        headers_response:{required_response_headers:{'X-Ready':'yes'},forbidden_headers:['X-Error']},
        ignore_ssl_error:1,accept_cookies:false,http_version:2,resole_to_ip:'192.0.2.1',redirects:2,
    });
    for (const channel of ['telegram','slack','pd','mm','incidentrelay','email']) data[channel + '_channel_id']=9;
    w.editSmon(17,'http'); requests.shift().success(data);
    $('#check-editor-submit').trigger('click');
    const payload = JSON.parse(requests.shift().data);
    assert.deepEqual(payload.auth,data.checks[0].auth);
    assert.deepEqual(payload.proxy,{...data.checks[0].proxy,port:'1080'});
    assert.deepEqual(JSON.parse(payload.headers_response.required_response_headers),{'X-Ready':'yes'});
    assert.equal(payload.headers_response.forbidden_headers,'X-Error');
    assert.equal(payload.header_req,data.checks[0].header_req);
    assert.equal(payload.body_req,data.checks[0].body_req);
    assert.equal(payload.ignore_ssl_error,'1');
    assert.equal(payload.accept_cookies,0);
    assert.equal(payload.http_version,2);
    assert.equal(payload.resole_to_ip,'192.0.2.1');
    for (const channel of ['telegram','slack','pd','mm','incidentrelay','email']) assert.equal(payload[channel + '_channel_id'],'9');
});

test('interval, timeout, ping packet budget and mTLS required fields are validated before saving', async t => {
    const {w,$,ui} = await editor(t);
    w.openSmonDialog('ping'); fill($,'ping');
    $('#new-smon-interval').val('30');
    assert.equal(ui.validate(),false);
    assert.equal($('#new-smon-count_packets').attr('aria-invalid'),'true');
    $('#new-smon-count_packets').val('2'); $('#new-smon-packet_size').val('16');
    assert.equal(ui.validate(),false);
    assert.equal($('#new-smon-packet_size').attr('aria-invalid'),'true');
    $('#new-smon-packet_size').val('56'); $('#new-smon-threshold_timeout').val('10000');
    assert.equal(ui.validate(),false);
    assert.equal($('#new-smon-threshold_timeout').attr('aria-invalid'),'true');
    $('#new-smon-threshold_timeout').val('0');
    assert.equal(ui.validate(),true);
    ui.setType('http'); fill($,'http');
    $('#smon_http_check_auth_method').val('mtls').trigger('selectmenuchange');
    assert.equal(ui.validate(),false);
    assert.equal($('#new-smon-mtls_key').attr('aria-invalid'),'true');
    assert.equal($('#new-smon-mtls_cert').attr('aria-invalid'),'true');
});

test('location buttons support names with quotes; missing locations block edit and clone', async t => {
    const {w,$,ui,requests} = await editor(t);
    w.openSmonDialog('tcp'); fill($,'tcp');
    const name = 'Paris "DC" / O\'Brien <backup>';
    w.removeEntityFromStatus(12,name);
    $('#add_check-12 button').trigger('click');
    assert.equal($('#remove_check-12 .check-name').text(),name);
    assert.equal($('#remove_check-12 button').attr('aria-label'),'Delete ' + name);
    assert.equal($('#remove_check-12 backup').length,0);
    $('#remove_check-12 button').trigger('click');
    assert.equal($('#add_check-12 .check-name').text(),name);
    const data = response('tcp'); data.place='agent'; data.entities=[999];
    for (const action of ['editSmon','cloneSmon']) {
        w[action](17,'tcp'); requests.shift().success(data);
        requests.shift().error?.();
        assert.equal(ui.isBlocked(),true);
        assert.equal($('#checked-entities > div').length,0);
        assert.equal($('#check-editor-submit').prop('disabled'),true);
    }
});

test('custom controls have accessible names and errors on the real focus target', async t => {
    const {w,$,ui} = await editor(t);
    w.openSmonDialog('http'); fill($,'http');
    assert.equal($('#check_type-button').attr('aria-label'),'Checking');
    assert.equal($('#check_type-button').attr('aria-labelledby'),undefined);
    assert.equal($('#new-smon-place-button').attr('aria-label'),'Run checks from');
    assert.equal(w.tagify.DOM.input.getAttribute('aria-label'),'Accepted Status Codes');
    assert.equal($('#new-smon-enable').attr('aria-label'),'Enable');
    $('#new-smon-place').val('agent').trigger('selectmenuchange');
    assert.equal($('#new-smon-place-button').attr('aria-labelledby'),undefined);
    ui.validate();
    assert.equal($('#new-smon-place-button').attr('aria-invalid'),'true');
    assert.equal(w.document.activeElement.id,'new-smon-place-button');
    w.addEntityToStatus(7,'Test location'); ui.validate();
    assert.equal($('#new-smon-place-button').attr('aria-describedby'),undefined);
});
