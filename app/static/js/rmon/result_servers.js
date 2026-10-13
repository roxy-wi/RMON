/* Managed result servers and shared receiver addresses. */
(function () {
    'use strict';
    function init() {
        const root = document.getElementById('result-servers');
        if (!root) return;
        const $ = id => document.getElementById('rs-' + id);
        const words = JSON.parse($('strings').textContent), t = key => words[key] || words.request_error;
        const api = '/api/v1.0/receivers', group = Number(root.dataset.group);
        let config, editor, step = 0, busy = false, loading = false;
        // The application decorates legacy controls; this page uses native controls.
        if (window.jQuery) {
            const controls = window.jQuery(root);
            controls.find('select').each(function () {
                if (window.jQuery(this).data('ui-selectmenu')) window.jQuery(this).selectmenu('destroy');
            });
            controls.find('button').each(function () {
                if (window.jQuery(this).data('ui-button')) window.jQuery(this).button('destroy');
            });
        }
        function node(tag, text, cls) {
            const value = document.createElement(tag);
            if (text !== undefined) value.textContent = text;
            if (cls) value.className = cls;
            return value;
        }
        function button(text, handler, disabled = false) {
            const value = node('button', text); value.type = 'button'; value.disabled = disabled;
            value.addEventListener('click', handler); return value;
        }
        function message(text = '', error = false, target = $('message')) {
            target.textContent = text; target.classList.toggle('rs-error', error);
        }
        async function request(path, method = 'GET', data) {
            const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 30000);
            const csrf = document.cookie.split('; ').find(c => c.startsWith('csrf_access_token='))?.split('=').slice(1).join('=');
            try {
                const response = await fetch(api + path, {method, credentials: 'same-origin', cache: 'no-store',
                    headers: {'Content-Type': 'application/json', ...(csrf ? {'X-CSRF-TOKEN': decodeURIComponent(csrf)} : {})},
                    body: data === undefined ? undefined : JSON.stringify(data), signal: controller.signal});
                if (response.status !== 204 && !(response.headers.get('Content-Type') || '').includes('application/json')) {
                    throw new Error(t(method === 'GET' ? 'request_error' : 'operation_unknown'));
                }
                const result = response.status === 204 ? {} : await response.json();
                if (!response.ok) throw new Error(t(result.error?.code || result.error || result.code));
                return result;
            } catch (error) {
                if (error.name === 'AbortError' || error instanceof TypeError || error instanceof SyntaxError) throw new Error(t(method === 'GET' ? 'request_error' : 'operation_unknown'));
                throw error;
            } finally { clearTimeout(timer); }
        }
        function roleNames(roles) { return roles.map(t).join(' · '); }
        function addresses(ids) { return ids.map(id => config.endpoints.find(e => e.id === id)).filter(Boolean); }
        function tags(values) {
            const box = node('div', undefined, 'rs-tags');
            values.forEach(value => box.append(node('span', value, 'rs-tag'))); return box;
        }
        function choices(host, values, selected, changed) {
            host.replaceChildren();
            if (!values.length) host.append(node('p', t('empty_endpoints'), 'rs-muted'));
            const items = [...values].sort((a, b) => {
                const x = selected.indexOf(a.id), y = selected.indexOf(b.id);
                return (x < 0 ? Infinity : x) - (y < 0 ? Infinity : y);
            });
            items.forEach(value => {
                const label = node('label'), input = node('input'); input.type = 'checkbox'; input.checked = selected.includes(value.id);
                input.addEventListener('change', () => {
                    if (input.checked) selected.push(value.id); else selected.splice(selected.indexOf(value.id), 1);
                    changed?.();
                });
                label.append(input, node('span', value.name + ' — ' + value.url)); host.append(label);
            });
        }
        function render() {
            $('install').hidden = !config.can_install; $('add-endpoint').hidden = !config.can_edit;
            $('servers').replaceChildren(); $('endpoints').replaceChildren();
            if (!config.servers.length) $('servers').append(node('p', t('empty_servers')));
            config.servers.forEach(server => {
                const card = node('article', undefined, 'host-card'), head = node('header', undefined, 'host-head');
                const identity = node('div', undefined, 'host-identity'), emblem = node('span', undefined, 'host-emblem');
                emblem.setAttribute('aria-hidden', 'true'); emblem.append(node('i', undefined, 'fas fa-server'));
                const title = node('div'); title.append(node('h3', server.name), node('p', server.hostname + ' · ' + server.ip, 'host-subtitle'));
                identity.append(emblem, title);
                const pending = ['created', 'queued', 'running'].includes(server.task?.status);
                const status = pending ? server.task.status : server.task?.status === 'failed' ? 'failed' : server.state;
                card.dataset.state = status;
                head.append(identity, node('span', t(status), 'host-status')); card.append(head);
                if (status === 'failed' && server.task.error) card.append(node('p', server.task.error.slice(0, 2000), 'host-note host-error'));
                if (server.applied_revision !== server.revision) card.append(node('p', t('pending'), 'host-note'));
                const connections = node('div', undefined, 'host-grid');
                for (const role of server.roles) {
                    const endpoints = addresses(server.endpoint_ids).filter(endpoint => endpoint.role === role);
                    if (!endpoints.length) endpoints.push({name: t('none'), url: '', transport: ''});
                    for (const endpoint of endpoints) {
                        const block = node('div', undefined, 'host-block'), label = node('div', undefined, 'host-label');
                        const icon = node('i', undefined, role === 'classic' ? 'fas fa-heartbeat' : 'fas fa-laptop-code');
                        icon.setAttribute('aria-hidden', 'true');
                        label.append(icon, node('span', t(role)), node('span', endpoint.transport.toUpperCase(), 'host-protocol'));
                        block.append(label, node('strong', endpoint.name));
                        if (endpoint.url) block.append(node('span', endpoint.url, 'host-url'));
                        connections.append(block);
                    }
                }
                card.append(connections);
                const footer = node('footer', undefined, 'host-footer');
                if (server.checked_at) footer.append(node('p', t('checked') + ': ' + new Date(server.checked_at).toLocaleString(document.documentElement.lang), 'host-verified'));
                if (config.can_install) {
                    const actions = node('div', undefined, 'host-actions');
                    const configure = button(t('configure'), () => openServer(server), pending); configure.className = 'host-primary';
                    actions.append(configure, button(t('check'), () => serverAction(server, 'check'), pending));
                    const lifecycle = node('div', undefined, 'host-lifecycle');
                    for (const action of ['start', 'stop', 'restart']) lifecycle.append(button(t(action), () => serverAction(server, action), pending));
                    const uninstall = button(t('uninstall'), () => serverAction(server, 'uninstall'), pending); uninstall.className = 'host-danger';
                    actions.append(lifecycle, uninstall); footer.append(actions);
                }
                if (footer.childElementCount) card.append(footer);
                $('servers').append(card);
            });
            window.FontAwesome?.dom.i2svg({node: $('servers')});
            if (!config.endpoints.length) $('endpoints').append(node('p', t('empty_endpoints')));
            config.endpoints.forEach(endpoint => {
                const card = node('article', undefined, 'rs-card');
                card.append(node('h3', endpoint.name), node('p', endpoint.url, 'rs-url'), tags([t(endpoint.role), t(endpoint.kind), endpoint.transport.toUpperCase()]));
                const names = config.servers.filter(s => endpoint.server_ids.includes(s.id)).map(s => s.name);
                card.append(node('p', t('servers') + ': ' + (names.join(', ') || t('none'))));
                card.append(node('p', `${t('agents')}: ${endpoint.agent_count} · ${t('projects')}: ${endpoint.project_count} · ${t('groups')}: ${endpoint.default_group_count}`, 'rs-muted'));
                if (config.can_edit && (endpoint.group_id === group || config.can_install)) {
                    const actions = node('div', undefined, 'rs-actions');
                    actions.append(button(t('edit'), () => openEndpoint(endpoint)), button(t('delete'), () => deleteEndpoint(endpoint))); card.append(actions);
                }
                $('endpoints').append(card);
            });
        }
        let defaultIds = [], defaultsDirty = false;
        function renderDefaults() {
            defaultIds = [...config.defaults]; $('default-mode').value = defaultIds.length ? 'custom' : 'legacy';
            $('default-choices').hidden = !defaultIds.length;
            choices($('default-choices'), config.endpoints.filter(e => e.role === 'classic'), defaultIds, () => { defaultsDirty = true; });
            $('defaults').querySelectorAll('input,select,button').forEach(el => { el.disabled = !config.can_edit; });
        }
        async function refresh(manual = false) {
            if (loading || busy) return; loading = true;
            try {
                config = await request('/configuration'); render();
                if (!defaultsDirty) renderDefaults();
                if (manual) message();
            } catch (error) { message(error.message, true); }
            finally { loading = false; }
        }
        function field(host, label, data, key, type = 'text', options = {}) {
            const wrapper = node('label', t(label)), input = node('input'); input.type = type; input.value = data[key] ?? '';
            for (const [name, value] of Object.entries(options)) input[name] = value;
            input.addEventListener('input', () => { data[key] = type === 'number' ? (input.value === '' ? null : Number(input.value)) : input.value; });
            wrapper.append(input); host.append(wrapper); return input;
        }
        function select(host, label, data, key, values) {
            const wrapper = node('label', t(label)), input = node('select');
            values.forEach(([value, text]) => { const option = node('option', text); option.value = value; input.append(option); });
            input.value = data[key]; input.addEventListener('change', () => { data[key] = input.value; });
            wrapper.append(input); host.append(wrapper); return input;
        }
        function checkbox(host, label, data, key) {
            const wrapper = node('label'), input = node('input'); input.type = 'checkbox'; input.checked = data[key];
            input.addEventListener('change', () => { data[key] = input.checked; }); wrapper.append(input, node('span', t(label))); host.append(wrapper);
        }
        function endpointFields(host, draft, roleFixed = false) {
            field(host, 'name', draft, 'name', 'text', {required: true, maxLength: 160});
            field(host, 'url', draft, 'url', 'url', {required: true, maxLength: 500, placeholder: 'https://metrics.example.com'});
            const grid = node('div', undefined, 'rs-grid'); host.append(grid);
            if (!roleFixed) select(grid, 'roles', draft, 'role', ['classic', 'client'].map(r => [r, t(r)]));
            select(grid, 'kind', draft, 'kind', ['direct', 'lb', 'external'].map(r => [r, t(r)]));
            select(grid, 'transport', draft, 'transport', [['http', 'HTTP'], ['https', 'HTTPS'], ...(draft.role === 'classic' ? [['mtls', 'HTTPS + mTLS']] : [])]);
            if (config.can_install) checkbox(host, 'shared', draft, 'shared');
        }
        function openEndpoint(endpoint) {
            editor = {type: 'endpoint', id: endpoint?.id, draft: endpoint ? {...endpoint} : {name: '', url: '', role: 'classic', transport: 'http', kind: 'direct', shared: false}};
            step = 0; renderEditor(); $('dialog').showModal();
        }
        function openServer(server) {
            if (!config.hosts.length) { message(t('no_hosts'), true); return; }
            const draft = server ? JSON.parse(JSON.stringify(server)) : {name: '', host_id: config.hosts[0].id, roles: ['classic'], endpoint_ids: [],
                classic_port: 5100, client_port: 5102, bind_ip: '0.0.0.0', database_host: config.deployment.database_host,
                database_port: config.deployment.database_port, sqlite_path: ''};
            editor = {type: 'server', id: server?.id, draft, create: {}}; step = 0; renderEditor(); $('dialog').showModal();
        }
        function renderEditor() {
            const host = $('fields');
            host.replaceChildren();
            message('', false, $('form-message'));
            if (editor.type === 'endpoint') {
                $('dialog-title').textContent = t(editor.id ? 'edit' : 'new_endpoint');
                $('steps').textContent = '';
                $('back').hidden = true;
                $('submit').textContent = t('save');
                endpointFields(host, editor.draft);
                return;
            }
            $('dialog-title').textContent = t(editor.id ? 'configure' : 'install');
            $('steps').textContent = ['host_roles', 'connections', 'review']
                .map((name, index) => (index === step ? '● ' : '') + t(name)).join('  /  ');
            $('back').hidden = step === 0;
            $('submit').textContent = t(step < 2 ? 'next' : 'apply');
            if (step === 0) {
                renderHostStep(host, editor.draft);
            } else if (step === 1) {
                renderConnectionsStep(host, editor.draft);
            } else {
                renderReviewStep(host, editor.draft);
            }
        }
        function renderHostStep(host, draft) {
            field(host, 'name', draft, 'name', 'text', {required: true, maxLength: 160});
            const hostSelect = select(host, 'host', draft, 'host_id', config.hosts.map(h => [h.id, h.name + ' · ' + h.ip]));
            hostSelect.disabled = Boolean(editor.id);
            const roles = node('fieldset');
            roles.append(node('legend', t('roles')));
            for (const role of ['classic', 'client']) {
                const label = node('label'), check = node('input');
                check.type = 'checkbox'; check.checked = draft.roles.includes(role);
                check.addEventListener('change', () => {
                    if (check.checked) draft.roles.push(role);
                    else draft.roles = draft.roles.filter(value => value !== role);
                });
                label.append(check, node('span', t(role))); roles.append(label);
            }
            roles.append(node('small', t('role_hint'))); host.append(roles);
        }
        function renderConnectionsStep(host, draft) {
            for (const role of draft.roles) {
                const box = node('fieldset'); box.append(node('legend', t(role))); host.append(box);
                field(box, 'port', draft, role + '_port', 'number', {required: true, min: 1025, max: 65535});
                const list = node('div', undefined, 'rs-choices'); box.append(list);
                choices(list, config.endpoints.filter(e => e.role === role), draft.endpoint_ids);
                box.append(button(t('new_endpoint'), () => {
                    const ip = config.hosts.find(h => h.id === Number(draft.host_id)).ip;
                    const transport = role === 'client' ? 'http' : config.deployment.transport || 'http';
                    const scheme = transport === 'http' ? 'http' : 'https';
                    const address = ip.includes(':') ? '[' + ip + ']' : ip;
                    editor.create[role] = {
                        name: draft.name + ' · ' + t(role),
                        url: `${scheme}://${address}:${draft[role + '_port']}`,
                        role, transport, kind: 'direct', shared: false
                    };
                    renderEditor();
                }, Boolean(editor.create[role])));
                if (editor.create[role]) {
                    endpointFields(box, editor.create[role], true);
                    box.append(button(t('cancel'), () => { delete editor.create[role]; renderEditor(); }));
                }
            }
            host.append(node('p', t('lb_hint'), 'rs-muted'), node('p', t('https_hint'), 'rs-muted'));
            field(host, 'bind', draft, 'bind_ip', 'text', {required: true});
            const storage = node('fieldset');
            storage.append(node('legend', t('storage') + ' · ' + config.deployment.database_type)); host.append(storage);
            storage.append(node('p', t('storage_hint'), 'rs-muted'));
            if (config.deployment.database_type === 'sqlite') {
                field(storage, 'sqlite_path', draft, 'sqlite_path', 'text', {required: true});
                storage.append(node('p', t('sqlite_hint'), 'rs-muted'));
            } else {
                field(storage, 'database_host', draft, 'database_host', 'text', {required: true});
                field(storage, 'database_port', draft, 'database_port', 'number', {required: true, min: 1, max: 65535});
            }
        }
        function renderReviewStep(host, draft) {
            const review = node('dl'), selectedHost = config.hosts.find(h => h.id === Number(draft.host_id));
            const rows = [['name', draft.name], ['host', selectedHost.name + ' · ' + selectedHost.ip], ['roles', roleNames(draft.roles)],
                ['storage', draft.sqlite_path || draft.database_host + ':' + draft.database_port]];
            draft.roles.forEach(role => rows.push([role, draft.bind_ip + ':' + draft[role + '_port']]));
            const endpoints = [...addresses(draft.endpoint_ids), ...Object.values(editor.create)];
            endpoints.forEach(e => rows.push(['url', e.name + ' — ' + e.url]));
            rows.forEach(([key, value]) => review.append(node('dt', t(key)), node('dd', value))); host.append(review);
            host.append(node('p', t('lb_hint'), 'rs-muted'));
        }
        function serverBody() {
            const d = editor.draft, body = {};
            for (const key of ['name', 'roles', 'endpoint_ids', 'classic_port', 'client_port', 'bind_ip', 'database_host', 'database_port', 'sqlite_path']) body[key] = d[key];
            body.host_id = Number(d.host_id); if (editor.id) body.revision = d.revision;
            body.new_endpoints = Object.values(editor.create); return body;
        }
        function endpointBody() {
            const body = {};
            for (const key of ['name', 'url', 'role', 'transport', 'kind', 'shared', 'revision']) {
                if (editor.draft[key] !== undefined) body[key] = editor.draft[key];
            }
            return body;
        }
        async function mutate(task, target = $('message')) {
            if (busy) return; busy = true;
            $('form').querySelectorAll('button').forEach(el => { el.disabled = true; });
            try { await task(); return true; } catch (error) { message(error.message, true, target); return false; }
            finally { busy = false; $('form').querySelectorAll('button').forEach(el => { el.disabled = false; }); }
        }
        $('form').addEventListener('submit', async event => {
            event.preventDefault(); if (busy) return;
            if (editor.type === 'server' && step < 2) {
                if (!editor.draft.roles.length) { message(t('choose_role'), true, $('form-message')); return; }
                const roles = editor.draft.roles;
                editor.draft.endpoint_ids = addresses(editor.draft.endpoint_ids).filter(e => roles.includes(e.role)).map(e => e.id);
                Object.keys(editor.create).filter(r => !roles.includes(r)).forEach(r => delete editor.create[r]);
                step++; renderEditor(); return;
            }
            const resource = editor.type === 'server' ? '/servers' : '/endpoints';
            const body = editor.type === 'server' ? serverBody() : endpointBody();
            const ok = await mutate(async () => {
                await request(resource + (editor.id ? '/' + editor.id : ''), editor.id ? 'PUT' : 'POST', body);
                $('dialog').close(); message(t(editor.type === 'server' ? 'operation_queued' : 'saved'));
            }, $('form-message'));
            if (ok) refresh();
        });
        async function serverAction(server, operation) {
            if (['stop', 'uninstall'].includes(operation) && !window.confirm(t('confirm_' + operation) + '\n' + server.name)) return;
            const ok = await mutate(async () => { await request(`/servers/${server.id}/actions/${operation}`, 'POST', {}); message(t('operation_queued')); });
            if (ok) refresh();
        }
        async function deleteEndpoint(endpoint) {
            if (!window.confirm(t('confirm_delete') + '\n' + endpoint.name)) return;
            if (await mutate(async () => { await request('/endpoints/' + endpoint.id, 'DELETE'); message(t('saved')); })) refresh();
        }
        $('default-mode').addEventListener('change', () => { defaultsDirty = true; $('default-choices').hidden = $('default-mode').value === 'legacy'; });
        $('defaults').addEventListener('submit', async event => {
            event.preventDefault(); const ids = $('default-mode').value === 'legacy' ? null : defaultIds;
            if (ids && !ids.length) { message(t('choose_endpoint'), true); return; }
            if (await mutate(async () => { await request('/defaults', 'PUT', {endpoint_ids: ids}); defaultsDirty = false; message(t('saved')); })) refresh();
        });
        $('dialog').addEventListener('cancel', event => { if (busy) event.preventDefault(); });
        for (const id of ['close', 'cancel']) $(id).addEventListener('click', () => { if (!busy) $('dialog').close(); });
        $('back').addEventListener('click', () => { step--; renderEditor(); });
        $('install').addEventListener('click', () => openServer()); $('add-endpoint').addEventListener('click', () => openEndpoint());
        $('refresh').addEventListener('click', () => refresh(true));
        root.querySelectorAll('[data-tab]').forEach(tab => tab.addEventListener('click', () => {
            root.querySelectorAll('[data-tab]').forEach(other => { const selected = other === tab; other.setAttribute('aria-selected', String(selected)); $('panel-' + other.dataset.tab).hidden = !selected; });
        }));
        setInterval(() => { if (!document.hidden && !$('dialog').open) refresh(); }, 15000);
        refresh();
    }
    if (window.jQuery) window.jQuery(init); else if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
}());
