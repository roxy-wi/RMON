/* Presentation and draft state for the existing check API. Field IDs remain stable. */
window.CheckEditor = (function () {
    'use strict';
    const catalog = document.getElementById('check-editor-strings');
    const strings = catalog ? JSON.parse(catalog.textContent) : {};
    const text = key => strings[key] || key;
    const root = () => $('#smon-add-table');
    const value = id => $('#' + id).val();
    let step = 0, type = null, ports = {}, busy = false, failed = false;
    const typeClasses = {http: 'smon_http_check', tcp: 'smon_tcp_check', dns: 'smon_dns_check',
        ping: 'smon_ping_check', smtp: 'smon_smtp_check', rabbitmq: 'smon_rabbit_check'};
    const portDefaults = {tcp: '', dns: '53', smtp: '587', rabbitmq: '5672'};
    function fit() {
        if (root().data('ui-dialog') && root().dialog('isOpen')) RmonUI.fitDialog(root()[0]);
    }
    function refresh() {
        root().find('select').each(function () {
            if ($(this).data('ui-selectmenu')) $(this).selectmenu('refresh');
            const label = $(this).closest('.check-field').find('.check-field-label').first().text().replace(/\*/g, '').trim();
            // jQuery UI labels its button with the selected option; use the field name.
            $('#' + this.id + '-button').removeAttr('aria-labelledby').attr('aria-label', label);
        });
        root().find('input[type=checkbox]').each(function () {
            if ($(this).data('ui-checkboxradio')) $(this).checkboxradio('refresh');
            $(this).attr('aria-label', $(this).closest('.check-field').find('.check-field-label').first().text().trim());
        });
        window.tagify?.DOM.input.setAttribute('aria-label', $('#new-smon-status-code').closest('.check-field').find('label').text().replace(/\*/g, '').trim());
        RmonUI.enhance(root()[0]);
    }
    function conditionalFields() {
        root().find('.smon_http_check_basic').toggle(type === 'http' && value('smon_http_check_auth_method') === 'basic');
        root().find('.smon_http_check_mtls').toggle(type === 'http' && value('smon_http_check_auth_method') === 'mtls');
        root().find('.smon_http_check_proxy').toggle(type === 'http' && value('smon_http_check_proxy_method') !== '0');
        root().find('#new-smon-headers-response').toggle(type === 'http' && value('smon_http_check_headers_response_type') !== '0');
        root().find('.smon_http_check_body_type_keyword').toggle(type === 'http' && value('smon_http_check_body_type') === 'keyword');
        root().find('.smon_http_check_body_type_json').toggle(type === 'http' && value('smon_http_check_body_type') === 'json');
    }
    function setType(nextType) {
        if (!typeClasses[nextType]) return;
        if (type && Object.hasOwn(portDefaults, type)) ports[type] = value('new-smon-port');
        if (nextType !== type && Object.hasOwn(portDefaults, nextType)) $('#new-smon-port').val(ports[nextType] ?? portDefaults[nextType]);
        type = nextType;
        $('#check_type').val(type);
        const classes = Object.values(typeClasses);
        root().find(classes.map(c => '.' + c).join(',')).each(function () { $(this).toggle(this.classList.contains(typeClasses[type])); });
        root().find('.new_smon_hostname').toggle(type !== 'http');
        $('#new-smon-username').attr('placeholder', type === 'rabbitmq' ? 'guest' : 'monitor@example.com');
        conditionalFields(); refresh(); summary(); fit();
    }
    function clearErrors() {
        const errorIds = new Set(root().find('.check-field-error').map((_, error) => error.id).get());
        root().find('.check-field-error').remove();
        root().find('[aria-invalid]').each(function () {
            $(this).removeAttr('aria-invalid').removeClass('ui-state-error');
            const description = (this.getAttribute('aria-describedby') || '').split(' ').filter(id => id && !errorIds.has(id));
            if (description.length) this.setAttribute('aria-describedby', description.join(' '));
            else this.removeAttribute('aria-describedby');
        });
        $('#check-editor-error').prop('hidden', true).empty();
    }
    function showStep(index, focus = false) {
        step = Math.max(0, Math.min(2, Number(index)));
        root().find('[role=tabpanel]').each(function () { this.hidden = Number(this.dataset.step) !== step; });
        root().find('[role=tab]').each(function () {
            const active = Number(this.dataset.step) === step;
            $(this).attr({'aria-selected': String(active), tabindex: active ? '0' : '-1'});
        });
        $('#check-editor-back').prop('hidden', step === 0);
        $('#check-editor-next').prop('hidden', step === 2);
        summary();
        root().scrollTop(0);
        fit();
        if (focus) $('#check-editor-tab-' + step).trigger('focus');
    }
    function reset(nextType) {
        busy = false; failed = false; type = null; ports = {};
        const form = document.getElementById('check-editor-form');
        form.reset(); form.inert = false;
        root().attr('aria-busy', 'false');
        $('#check_type, #new-smon-place').prop('disabled', false);
        $('#checked-entities, #all-entities').empty(); $('#agent_tr').hide();
        root().find('details').prop('open', false);
        if (window.tagify) window.tagify.removeAllTags();
        clearErrors(); setType(nextType); showStep(0);
    }
    function focusField(id) {
        const field = document.getElementById(id);
        if (!field) return;
        showStep(field.closest('[role=tabpanel]')?.dataset.step || 0);
        $(field).parents('details').prop('open', true);
        fit();
        const target = document.getElementById(id + '-button') ||
            (id === 'new-smon-status-code' ? window.tagify?.DOM.input : null) || field;
        target.focus(); target.scrollIntoView?.({block: 'nearest'});
    }
    function validate(onlyStep) {
        clearErrors();
        const errors = [];
        function add(id, message) {
            const field = document.getElementById(id);
            if (!field || (onlyStep !== undefined && Number(field.closest('[role=tabpanel]')?.dataset.step) !== onlyStep)) return;
            if (!errors.some(e => e.id === id)) errors.push({id, message});
        }
        function required(id) { if (!String(value(id) ?? '').trim()) add(id, text('required')); }
        function number(id, min, max = Infinity, integer = true) {
            const n = Number(value(id));
            if (String(value(id) ?? '').trim() === '' || !Number.isFinite(n) || n < min || n > max || (integer && !Number.isInteger(n))) add(id, text(id.endsWith('port') ? 'port' : 'number'));
        }
        required('new-smon-name');
        if (type === 'http') {
            try { const url = new URL(value('new-smon-url')); if (!['http:', 'https:'].includes(url.protocol) || !url.hostname) throw new Error(); }
            catch (_) { add('new-smon-url', text('invalid_url')); }
            const codes = window.tagify?.value || [];
            if (!codes.length || codes.some(tag => {
                const code = String(tag.value);
                if (!/^(?:[1-5][0-9]{2}|[1-5]\*\*|[1-5][0-9]{2}-[1-5][0-9]{2})$/.test(code)) return true;
                const [start, end] = code.split('-').map(Number);
                return end !== undefined && start > end;
            })) add('new-smon-status-code', text('status_codes'));
            number('new-smon-redirects', 0);
            if (value('smon_http_check_body_type') === 'keyword') required('new-smon-body-keyword');
            if (value('smon_http_check_body_type') === 'json') required('new-smon-body-json-path');
            if (value('smon_http_check_auth_method') === 'mtls') { required('new-smon-mtls_key'); required('new-smon-mtls_cert'); }
            if (value('smon_http_check_proxy_method') !== '0') { required('new-smon-http_proxy_host'); number('new-smon-http_proxy_port', 2, 65535); }
            const jsonFields = ['new-smon-header-req'];
            if (value('smon_http_check_headers_response_type') !== '0') jsonFields.push('new-smon-header-response-required');
            for (const id of jsonFields) {
                if (!String(value(id) || '').trim()) continue;
                try { const parsed = JSON.parse(value(id)); if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error(); }
                catch (_) { add(id, text('json')); }
            }
        } else required('new-smon-ip');
        if (['tcp', 'dns', 'smtp', 'rabbitmq'].includes(type)) number('new-smon-port', 2, 65535);
        if (type === 'dns') required('new-smon-resolver-server');
        if (['smtp', 'rabbitmq'].includes(type)) { required('new-smon-username'); required('new-smon-password'); }
        if (type === 'rabbitmq') required('new-smon-vhost');
        number('new-smon-interval', 1); number('new-smon-timeout', 2, 59); number('new-smon-retries', 1);
        number('new-smon-threshold_timeout', 0, Infinity, false);
        if (Number(value('new-smon-timeout')) >= Number(value('new-smon-interval'))) add('new-smon-timeout', text('timeout'));
        if (Number(value('new-smon-threshold_timeout')) >= Number(value('new-smon-timeout')) * 1000) add('new-smon-threshold_timeout', text('number'));
        if (type === 'ping') {
            number('new-smon-packet_size', 17); number('new-smon-count_packets', 1);
            if (Number(value('new-smon-count_packets')) * Number(value('new-smon-timeout')) >= Number(value('new-smon-interval'))) add('new-smon-count_packets', text('ping_timeout'));
        }
        if (value('new-smon-place') !== 'all' && !$('#checked-entities > div').length) add('new-smon-place', text('entities'));
        for (const error of errors) {
            const field = $('#' + error.id);
            $('<p>', {class: 'check-field-error', id: error.id + '-error'}).text(error.message).appendTo(field.closest('.check-field-control'));
            field.attr({'aria-invalid': 'true', 'aria-describedby': ((field.attr('aria-describedby') || '') + ' ' + error.id + '-error').trim()}).addClass('ui-state-error');
            const widget = document.getElementById(error.id + '-button') || (error.id === 'new-smon-status-code' ? window.tagify?.DOM.input : null);
            if (widget) $(widget).attr({'aria-invalid': 'true', 'aria-describedby': error.id + '-error'});
        }
        if (errors.length) focusField(errors[0].id);
        return !errors.length;
    }
    function summary() {
        const host = $('#check-editor-summary').empty();
        if (!host.length) return;
        let target = value('new-smon-ip') || text('summary_empty');
        if (type === 'http') {
            try { const url = new URL(value('new-smon-url')); target = url.origin + url.pathname; }
            catch (_) { target = text('summary_empty'); }
        }
        $('<strong>').text((value('new-smon-name') || text('summary')) + ' · ' + (type || '').toUpperCase()).appendTo(host);
        $('<span>').text(target).appendTo(host);
        $('<span>').text($('#new-smon-place option:selected').text() + ' · ' + value('new-smon-interval') + ' ' + text('seconds')).appendTo(host);
        const channels = ['telegram','slack','pd','mm','incidentrelay','email'].filter(c => value('new-smon-' + c) !== '0');
        $('<span>').text(channels.length ? channels.map(c => $('#new-smon-' + c).closest('.check-field').find('label').first().text()).join(', ') : text('no_channels')).appendTo(host);
    }
    function setBusy(active, loading = false) {
        busy = active;
        root().attr('aria-busy', String(active));
        document.getElementById('check-editor-form').inert = active;
        $('#check-editor-back, #check-editor-next, #check-editor-submit, #check-editor-cancel').prop('disabled', active);
        root().find('[role=tab]').prop('disabled', active);
        if (active) $('#check-editor-error').prop('hidden', false).text(text(loading ? 'loading' : 'saving'));
        else $('#check-editor-error').prop('hidden', true);
    }
    function showError(message, loadFailed = false) {
        setBusy(false); failed = loadFailed;
        $('#check-editor-submit, #check-editor-next').prop('disabled', loadFailed);
        $('#check-editor-error').prop('hidden', false).text(message).trigger('focus');
    }
    function populate(data) {
        if (!Array.isArray(data.checks) || !data.checks.length) throw new Error('Missing check settings');
        const check = data.checks[0], common = check.smon_id || {};
        const settings = {...common, ...check, ...data};
        const map = {name:'name', ip:'ip', port:'port', resolver:'resolver-server', record_type:'dns_record_type',
            url:'url', resole_to_ip:'resole_to_ip', description:'description', packet_size:'packet_size', count_packets:'count_packets',
            interval:'interval', check_timeout:'timeout', username:'username', password:'password', vhost:'vhost', retries:'retries',
            redirects:'redirects', runbook:'runbook', priority:'priority', expiration:'expiration', threshold_timeout:'threshold_timeout',
            check_group:'group', body_req:'body-req', header_req:'header-req', method:'method', http_version:'http_version'};
        for (const [key, id] of Object.entries(map)) {
            if (Object.hasOwn(settings, key)) $('#new-smon-' + id).val(settings[key] ?? '');
        }
        for (const channel of ['telegram','slack','pd','mm','incidentrelay','email']) $('#new-smon-' + channel).val(settings[channel + '_channel_id'] || '0');
        for (const [id, key] of [['enable','enabled'],['ignore_ssl_error','ignore_ssl_error'],['accept_cookies','accept_cookies'],['use_kernel_timestamp','use_kernel_timestamp']]) {
            if (settings[key] !== undefined) $('#new-smon-' + id).prop('checked', settings[key] === true || Number(settings[key]) === 1);
        }
        window.tagify?.removeAllTags(); window.tagify?.addTags(check.accepted_status_codes || []);
        $('#new-smon-place').val(data.place).trigger('selectmenuchange');
        if (data.place !== 'all') for (const id of data.entities || []) {
            if (!getEntityJson(id, data.place)) throw new Error('Cannot load a selected location');
        }
        if (settings.body_json) {
            $('#smon_http_check_body_type').val('json');
            $('#new-smon-body-json-path').val(settings.body_json.path); $('#new-smon-body-json-value').val(settings.body_json.value ?? '');
        } else if (settings.body) { $('#smon_http_check_body_type').val('keyword'); $('#new-smon-body-keyword').val(settings.body); }
        if (check.auth?.basic) {
            $('#smon_http_check_auth_method').val('basic');
            $('#new-smon-basic_username').val(check.auth.basic.username); $('#new-smon-basic_password').val(check.auth.basic.password);
        } else if (check.auth?.mtls) {
            $('#smon_http_check_auth_method').val('mtls');
            for (const key of ['key','cert','ca']) $('#new-smon-mtls_' + key).val(check.auth.mtls[key] || '');
        }
        if (check.proxy) {
            $('#smon_http_check_proxy_method').val(check.proxy.type);
            for (const key of ['host','port','username','password']) $('#new-smon-http_proxy_' + key).val(check.proxy[key] ?? '');
        }
        if (check.headers_response) {
            $('#smon_http_check_headers_response_type').val('check');
            $('#new-smon-header-response-forbidden').val((check.headers_response.forbidden_headers || []).join(',\n'));
            $('#new-smon-header-response-required').val(check.headers_response.required_response_headers ? JSON.stringify(check.headers_response.required_response_headers, null, 2) : '');
        }
        conditionalFields(); refresh(); summary();
    }
    $(function () {
        root()[0]?.addEventListener('toggle', fit, true);
        root().on('click', '[role=tab]', function () { if (!busy) showStep(this.dataset.step, true); });
        root().on('keydown', '[role=tab]', function (event) {
            if (busy) return;
            const keys = {ArrowRight: (step + 1) % 3, ArrowLeft: (step + 2) % 3, Home: 0, End: 2};
            if (Object.hasOwn(keys, event.key)) { event.preventDefault(); showStep(keys[event.key], true); }
        });
        root().on('input change selectmenuchange', 'input, textarea, select', summary);
        root().on('selectmenuchange', 'select', function () { refresh(); fit(); });
        $('#check-editor-form').on('submit', event => { event.preventDefault(); $('#check-editor-submit').trigger('click'); });
        const labels = {'new-smon-body-json-path':'json_path','new-smon-body-json-value':'json_value',
            'new-smon-http_proxy_host':'proxy_host','new-smon-http_proxy_port':'proxy_port',
            'new-smon-http_proxy_username':'proxy_username','new-smon-http_proxy_password':'proxy_password'};
        for (const [id, key] of Object.entries(labels)) $('#' + id).attr('aria-label', text(key));
        root().find('textarea:not([aria-label])').each(function () { if (!this.labels?.length) $(this).attr('aria-label', this.title || this.placeholder); });
    });
    return {text, reset, setType, populate, refresh, summary, validate, showStep, setBusy, showError,
        isBusy: () => busy, isBlocked: () => busy || failed, next: () => { if (validate(step)) showStep(step + 1, true); }, back: () => showStep(step - 1, true)};
})();
