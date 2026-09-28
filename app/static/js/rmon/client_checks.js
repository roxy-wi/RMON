/* Client checks use the authenticated API; sending keys stay in this page only. */
window.RmonClientChecks = (() => {
    'use strict';
    function init() {
        const root = document.getElementById('client-checks');
        if (!root || root.dataset.initialized) return;
        root.dataset.initialized = 'true';
        const $ = id => root.querySelector('#cc-' + id);
        const all = selector => [...root.querySelectorAll(selector)];
        const strings = JSON.parse($('strings').textContent);
        const t = key => strings[key] || key;
        const presetLabels = JSON.parse($('preset-labels').textContent);
        function presetLabel(key, value, replacements = {}) {
            const format = text => Object.entries(replacements).reduce((text, [name, value]) => text.replaceAll('{' + name + '}', () => value), text);
            const aliases = presetLabels[key] || [];
            if (!aliases.some(alias => format(alias) === value || key === 'preset_site_description' && format(alias) + '.' === value)) return value;
            return format(t(key));
        }
        function checkLabel(check, field, value) {
            if (!check || !['page.load', 'http.reachability'].includes(check.code)) return value;
            return presetLabel('preset_' + check.code.replaceAll('.', '_') + '_' + field, value);
        }
        const checkName = check => checkLabel(check, 'name', check.name);
        const metricLabel = (check, name, value) => checkLabel(check, 'metric_' + name, value);
        const contextLabel = (check, name, value) => checkLabel(check, 'context_' + name, value);
        function displayLabel(input, original, translated) {
            input.value = translated;
            input.dataset.originalLabel = original;
            input.dataset.displayLabel = translated;
        }
        // Changing language must not rewrite a stored definition on save.
        const storedLabel = input => input.value === input.dataset.displayLabel ? input.dataset.originalLabel : input.value.trim();
        const contract = window.RmonClientContract;
        $('endpoint').value = new URL('/api/v1/client/events', location.origin).href;
        const canEdit = root.dataset.canEdit === 'true';
        const api = root.dataset.api;
        const params = new URLSearchParams(location.search);
        const validId = value => /^\d{1,10}$/.test(value || '') && Number(value) > 0 && Number(value) <= 2147483647;
        const state = {projects: new Map(), projectsNext: null, project: null, checks: new Map(), checksLoaded: false,
            checksNext: null, check: validId(params.get('check')) ? Number(params.get('check')) : null,
            definitions: [], definitionCheck: null, fields: {}, metrics: {}, tab: 'overview', controller: null,
            pages: {}, chart: null, editing: null, issued: null};
        function resetPages() {
            for (const name of ['overview', 'keys', 'events']) state.pages[name] = {cursor: null, previous: [], next: null};
        }
        resetPages();
        // This screen uses native, labelled controls, including dynamically added fields.
        if (window.jQuery) {
            for (const [selector, plugin] of [['select', 'selectmenu'], ['input[type=checkbox]', 'checkboxradio'], ['button', 'button']]) {
                window.jQuery(root).find(selector).each(function () {
                    if (window.jQuery(this)[plugin]?.('instance')) window.jQuery(this)[plugin]('destroy');
                });
            }
        }
        function el(tag, text, className) {
            const node = document.createElement(tag);
            if (text !== undefined && text !== null) node.textContent = String(text);
            if (className) node.className = className;
            return node;
        }
        function button(text, action, className) {
            const node = el('button', text, className); node.type = 'button'; node.addEventListener('click', action); return node;
        }
        function option(value, label) { const node = el('option', label); node.value = value; return node; }
        function options(select, values, value) {
            select.replaceChildren(...values.map(([key, label]) => option(key, label)));
            if (value !== undefined && [...select.options].some(item => item.value === String(value))) select.value = value;
        }
        // Keep the same decimal comma and space grouping in every UI language.
        const decimalFormat = new Intl.NumberFormat('fr-FR', {maximumFractionDigits: 3});
        const scientificFormat = new Intl.NumberFormat('fr-FR', {notation: 'scientific', maximumSignificantDigits: 4});
        const percentFormat = new Intl.NumberFormat('fr-FR', {style: 'percent', maximumFractionDigits: 2});
        const dateFormat = new Intl.DateTimeFormat('de-DE', {day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'});
        const number = value => value === null || value === undefined ? '—' :
            (value !== 0 && Math.abs(value) < .001 ? scientificFormat : decimalFormat).format(value);
        const percent = value => value === null || value === undefined ? '—' : percentFormat.format(value);
        const date = value => value === null || value === undefined ? '—' : dateFormat.format(new Date(typeof value === 'number' ? value / 1000 : value));
        const measurement = (value, unit) => value === null || value === undefined ? '—' : number(value) + (unit ? ' ' + unit : '');
        const countries = typeof Intl.DisplayNames === 'function' ? new Intl.DisplayNames(document.documentElement.lang || 'en', {type: 'region', fallback: 'code'}) : null;
        function country(value) {
            if (!value) return '—';
            if (typeof value !== 'string' || !/^[A-Za-z]{2}$/.test(value)) return value;
            const code = value.toUpperCase(), name = countries?.of(code);
            return name && name !== code ? name + ' (' + code + ')' : code;
        }
        function message(error, target = $('message')) {
            const code = error.code || error.message;
            const lines = [strings[code] || error.message || t('request_error')];
            for (const detail of error.details || []) lines.push(detail.field + ': ' + detail.message);
            target.textContent = lines.join('\n'); target.hidden = false;
        }
        function appError(code, text, details) { const error = new Error(text || t(code)); error.code = code; error.details = details; return error; }
        async function request(path, {method = 'GET', body, signal, headers = {}} = {}) {
            const controller = new AbortController();
            let timedOut = false;
            const onAbort = () => controller.abort();
            if (signal?.aborted) controller.abort();
            signal?.addEventListener('abort', onAbort, {once: true});
            const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, 30000);
            const csrf = document.cookie.split('; ').find(cookie => cookie.startsWith('csrf_access_token='));
            const requestHeaders = {Accept: 'application/json', ...headers};
            if (body !== undefined) requestHeaders['Content-Type'] = 'application/json';
            if (csrf) requestHeaders['X-CSRF-TOKEN'] = decodeURIComponent(csrf.slice('csrf_access_token='.length));
            try {
                const response = await fetch(api + path, {method, credentials: 'same-origin', cache: 'no-store',
                    headers: requestHeaders, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal});
                if (response.status === 204) return null;
                if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw appError(response.redirected ? 'unauthorized' : 'request_error');
                const data = await response.json();
                if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
                if (!response.ok) {
                    const code = response.status === 401 ? 'unauthorized' : response.status === 403 ? 'forbidden' :
                        response.status >= 500 ? 'request_error' : data.error;
                    throw appError(code, data.message, data.details);
                }
                return data;
            } catch (error) {
                if (timedOut) throw appError('timeout');
                if (error.name === 'TypeError') throw appError('request_error');
                throw error;
            } finally {
                clearTimeout(timeout); signal?.removeEventListener('abort', onAbort);
            }
        }
        function urlState() {
            const url = new URL(location.href);
            for (const [name, value] of Object.entries({project: state.project?.id, check: state.check, view: state.tab})) {
                if (value) url.searchParams.set(name, value); else url.searchParams.delete(name);
            }
            history.replaceState(null, '', url);
        }
        function statusTarget(tab) { return $(tab === 'connect' ? 'keys-state' : tab + '-state'); }
        async function run(tab, task, {background = false} = {}) {
            state.controller?.abort();
            const controller = new AbortController(); state.controller = controller;
            $('message').hidden = true;
            const target = statusTarget(tab);
            if (!background) target.replaceChildren(el('span', t('loading')));
            const panel = $('panel-' + tab); panel.setAttribute('aria-busy', 'true');
            refreshStatus();
            const paginated = tab === 'connect' ? 'keys' : tab;
            if (state.pages[paginated]) {
                $(paginated + '-prev').disabled = true; $(paginated + '-next').disabled = true;
            }
            if (tab === 'report' && !background) $('report-data').hidden = true;
            try {
                await task(controller.signal);
                if (state.controller === controller && !controller.signal.aborted) state.refreshedAt = Date.now();
            } catch (error) {
                if (controller.signal.aborted || error.name === 'AbortError') return;
                target.replaceChildren(); message(error, target);
                target.append(' ', button(t('retry'), refreshView));
                if (state.pages[paginated]) $(paginated + '-prev').disabled = !state.pages[paginated].previous.length;
            } finally {
                if (state.controller === controller || state.tab !== tab) panel.setAttribute('aria-busy', 'false');
                if (state.controller === controller) refreshStatus();
            }
        }
        async function action(task, target = $('message')) {
            try { await task(); } catch (error) { if (error.name !== 'AbortError') message(error, target); }
        }
        function projectPath(suffix = '') { return '/' + state.project.id + suffix; }
        function populateProjects() {
            options($('project'), [[ '', t('choose_project') ], ...[...state.projects.values()].map(row => [row.id, row.name])], state.project?.id || '');
            $('project').disabled = !state.projects.size;
            $('more-projects').hidden = !state.projectsNext;
        }
        function heading() {
            $('project-name').textContent = state.project.name;
            $('project-description').textContent = presetLabel('preset_site_description', state.project.description, {site: state.project.name});
            $('project-state').textContent = t(state.project.enabled ? 'active' : 'paused');
            $('project-state').classList.toggle('cc-paused', !state.project.enabled);
            if (canEdit) $('toggle-collection').textContent = t(state.project.enabled ? 'pause' : 'resume');
        }
        function clearKey() { $('sending-key').value = ''; $('key-once').hidden = true; state.issued = null; $('example').textContent = ''; }
        function activateProject(id, preserveCheck = false) {
            state.bootstrapController?.abort(); state.controller?.abort(); clearKey();
            state.project = state.projects.get(Number(id)) || null;
            state.checks.clear(); state.checksLoaded = false; state.checksNext = null;
            state.definitions = []; state.definitionCheck = null;
            if (!preserveCheck) state.check = null;
            resetPages(); $('filters').replaceChildren(); state.filtersDirty = false;
            state.refreshedAt = null; refreshStatus();
            for (const host of ['overview-cards', 'overview-rows', 'event-rows', 'key-list', 'stats', 'series-rows', 'group-rows']) $(host).replaceChildren();
            $('report-data').hidden = true;
            $('empty').hidden = Boolean(state.project); $('project-area').hidden = !state.project;
            populateProjects();
            if (!state.project) return;
            heading(); urlState(); refreshView();
        }
        function populateChecks() {
            const values = [['', t('choose_check')], ...[...state.checks.values()].map(row => [row.id, checkName(row) + ' · ' + row.code])];
            all('.cc-check-select').forEach(select => options(select, values, state.check || ''));
            all('.cc-more-checks').forEach(node => { node.hidden = !state.checksNext; });
            if (canEdit) $('edit-definition').disabled = !state.check;
        }
        async function ensureChecks(signal) {
            if (state.checksLoaded) return;
            const page = await request(projectPath('/checks?limit=100'), {signal});
            const checks = new Map(page.items.map(check => [check.id, check]));
            let selected = state.check;
            if (selected && !checks.has(selected)) {
                const found = await request(projectPath('/checks?limit=1&after_id=' + (state.check - 1)), {signal});
                if (found.items[0]?.id === selected) checks.set(selected, found.items[0]);
                else selected = null;
            }
            state.checks = checks; state.check = selected; state.checksNext = page.next_after_id; state.checksLoaded = true;
            if (!state.check) state.check = state.checks.keys().next().value || null;
            populateChecks(); urlState();
        }
        async function loadMoreChecks() {
            const project = state.project.id, cursor = state.checksNext;
            if (!cursor) return;
            const data = await request('/' + project + '/checks?limit=100&after_id=' + cursor);
            if (state.project?.id !== project || state.checksNext !== cursor) return;
            data.items.forEach(row => state.checks.set(row.id, row)); state.checksNext = data.next_after_id;
            populateChecks();
            if ($('key-dialog')?.open) keyChoices(true);
        }
        function period() {
            const to = Math.floor(Date.now() / 60000) * 60000;
            const from = to - Number($('period').value) * 3600000;
            return {from: new Date(from).toISOString(), to: new Date(to).toISOString()};
        }
        function pageQuery(name, extra = {}) {
            const cursor = state.pages[name].cursor;
            const values = {...extra};
            if (cursor) values[name === 'events' ? 'before_id' : 'after_id'] = cursor;
            return new URLSearchParams(values).toString();
        }
        function pageButtons(name, next) {
            state.pages[name].next = next;
            $(name + '-prev').disabled = !state.pages[name].previous.length;
            $(name + '-next').disabled = !next;
        }
        function row(cells) {
            const tr = el('tr'); for (const cell of cells) { const td = el('td'); td.append(cell instanceof Node ? cell : String(cell)); tr.append(td); } return tr;
        }
        async function overview(signal) {
            const data = await request(projectPath('/overview?' + pageQuery('overview', {...period(), checks_limit: 20})), {signal});
            $('overview-cards').replaceChildren(...data.items.map(check => {
                const report = check.report, card = el('article', null, 'cc-check-card');
                const title = el('h3'); title.append(button(checkName(check), () => { chooseCheck(check.id); selectTab('report'); }, 'cc-link'));
                const values = el('div', null, 'cc-check-values');
                values.append(el('span', t('observations') + ': ' + number(report.summary.observations)));
                if (report.summary.outcomes) values.append(el('span', t('error_rate') + ': ' + percent(report.summary.error_rate)));
                const metric = metricLabel(check, report.metric, report.metric_label) || (report.metric === 'duration_ms' ? t('duration') : report.metric) || '—';
                const measured = el('div', null, 'cc-check-measurement');
                measured.append(el('span', metric + ' · ≈ p95'), el('strong', measurement(report.summary.metric.p95, report.unit)));
                card.append(title, el('p', check.code, 'cc-muted'), values, measured, el('span', t(report.state), 'cc-check-state'));
                return card;
            }));
            $('overview-rows').replaceChildren(...data.items.map(check => {
                state.checks.set(check.id, check);
                const report = check.report;
                const open = button(checkName(check), () => { chooseCheck(check.id); selectTab('report'); }, 'cc-link');
                const name = el('div'); name.append(open, el('div', check.code, 'cc-muted'));
                return row([name, number(report.summary.observations), percent(report.summary.error_rate), metricLabel(check, report.metric, report.metric_label) || (report.metric === 'duration_ms' ? t('duration') : report.metric) || '—',
                    measurement(report.summary.metric.p95, report.unit), t(report.state)]);
            }));
            $('overview-state').textContent = data.items.length ? '' : t('no_checks');
            populateChecks(); pageButtons('overview', data.next_after_id);
        }
        function chooseCheck(id) {
            const next = Number(id) || null;
            if (next === state.check) return;
            state.check = next; state.definitionCheck = null; state.definitions = [];
            $('filters').replaceChildren(); state.filtersDirty = false; populateChecks(); urlState();
        }
        async function ensureDefinitions(signal) {
            if (!state.check) return false;
            if (state.definitionCheck === state.check) return true;
            const previous = state.definitions.length ? {metric: $('report-metric').value, group: $('report-group').value,
                outcome: $('report-outcome').value} : null;
            const result = await request(projectPath('/checks/' + state.check + '/definitions'), {signal});
            state.definitions = result.items; state.definitionCheck = state.check;
            state.fields = Object.fromEntries(contract.standard.map(name => [name, {type: 'string', label: t(name)}]));
            state.fields._page_url = {type: 'string', label: t('page_url')};
            state.metrics = Object.create(null);
            for (const {definition} of result.items) {
                Object.assign(state.metrics, definition.metrics);
                if (definition.duration) state.metrics.duration_ms = definition.duration;
                for (const [name, field] of Object.entries(definition.context)) {
                    if (field.filterable) state.fields[name] = {...field, label: contextLabel(state.checks.get(state.check), name, field.label)};
                }
            }
            const latest = result.items[result.items.length - 1]?.definition;
            if (!latest) throw appError('request_error');
            options($('report-metric'), Object.entries(state.metrics).map(([key, field]) => [key, metricLabel(state.checks.get(state.check), key, field.label) + ' (' + field.unit + ')']),
                previous?.metric || latest.primary_metric || (latest.duration ? 'duration_ms' : Object.keys(latest.metrics)[0]));
            if (!$('report-metric').options.length) $('report-metric').append(option('', t('none')));
            options($('report-group'), [['', t('none')], ...Object.entries(state.fields).map(([key, field]) => [key, field.label])], previous ? previous.group : 'platform');
            $('report-outcome').disabled = !latest.has_outcome;
            defaultOutcome();
            if (previous && previous.metric === $('report-metric').value && latest.has_outcome) $('report-outcome').value = previous.outcome;
            $('connect-version').textContent = t('version') + ': ' + result.items[result.items.length - 1].version;
            return true;
        }
        function defaultOutcome() {
            const latest = state.definitions.at(-1)?.definition;
            $('report-outcome').value = latest?.has_outcome && $('report-metric').value === 'duration_ms' ? 'ok' : 'all';
        }
        function addFilter() {
            if (!state.check || $('filters').children.length >= 8) return;
            state.filtersDirty = true;
            const container = el('div', null, 'cc-filter-row');
            const field = labelledSelect(t('context'), Object.entries(state.fields).map(([key, value]) => [key, value.label]));
            const valueHost = el('div');
            const missing = labelledCheck(t('missing'), false);
            function control() {
                const definition = state.fields[field.input.value];
                const value = definition.type === 'boolean' ? labelledSelect(t('value'), [['true', t('true')], ['false', t('false')]]) : labelledInput(t('value'), '', {maxLength: field.input.value === '_page_url' ? 2048 : 128});
                value.input.dataset.filterValue = 'true'; value.input.disabled = missing.input.checked;
                valueHost.replaceChildren(value.label);
            }
            field.input.dataset.filterField = 'true'; missing.input.dataset.filterMissing = 'true';
            field.input.addEventListener('change', control); missing.input.addEventListener('change', () => { valueHost.querySelector('input, select').disabled = missing.input.checked; });
            container.append(field.label, valueHost, missing.label, button(t('remove'), () => { container.remove(); state.filtersDirty = true; refreshStatus(); })); control(); $('filters').append(container);
            refreshStatus();
        }
        function filters() {
            const result = Object.create(null);
            for (const container of $('filters').children) {
                const name = container.querySelector('[data-filter-field]').value;
                const value = container.querySelector('[data-filter-value]').value;
                const missing = container.querySelector('[data-filter-missing]').checked;
                if (Object.hasOwn(result, name) || !missing && !value) throw appError('invalid_filters');
                result[name] = missing ? null : state.fields[name].type === 'boolean' ? value === 'true' : value;
            }
            return result;
        }
        function stat(label, value) { const item = el('div', null, 'cc-stat'); item.append(el('span', label), el('strong', value)); return item; }
        async function report(signal) {
            if (!await ensureDefinitions(signal)) { $('report-state').textContent = t('no_checks'); return; }
            const query = {...period(), filters: JSON.stringify(filters()), outcome: $('report-outcome').value};
            state.filtersDirty = false;
            if ($('report-metric').value) query.metric = $('report-metric').value;
            if ($('report-group').value) query.group_by = $('report-group').value;
            const data = await request(projectPath('/checks/' + state.check + '/report?' + new URLSearchParams(query)), {signal});
            $('report-state').textContent = t(data.state === 'no_data' ? 'no_data_hint' : data.state === 'processing' ? 'processing_hint' : 'minute_hint');
            const summary = data.summary, metric = summary.metric;
            $('stats').replaceChildren(stat(t('observations'), number(summary.observations)), stat(t('error_rate'), percent(summary.error_rate)),
                stat(t('metric_count'), number(metric.count)), stat('≈ p95', measurement(metric.p95, data.unit)),
                stat(t('mean'), measurement(metric.mean, data.unit)), stat(t('minimum'), measurement(metric.min, data.unit)),
                stat(t('maximum'), measurement(metric.max, data.unit)), stat(t('errors'), summary.outcomes ? number(summary.errors) : '—'));
            $('report-quality').textContent = t('last_received') + ': ' + date(data.aggregation.last_received_us) + ' · ' +
                t('last_processed') + ': ' + date(data.aggregation.last_processed_us) + ' · ' + t('lag') + ': ' + number(data.aggregation.lag_seconds);
            $('sampling').textContent = t('sampling') + ': ' + percent(summary.sampling.min_probability) + ' – ' + percent(summary.sampling.max_probability) + '. ' + t('sampling_hint');
            $('series-rows').replaceChildren(...data.series.map(point => row([date(point.at), number(point.observations), number(point.metric.count),
                measurement(point.metric.p50, data.unit), measurement(point.metric.p95, data.unit), measurement(point.metric.p99, data.unit)])));
            $('groups').hidden = !data.group_by;
            $('group-rows').replaceChildren(...data.groups.map(group => row([
                group.value === null ? t('missing') : data.group_by === 'country' ? country(group.value) : typeof group.value === 'boolean' ? t(String(group.value)) : group.value,
                number(group.observations), percent(group.error_rate), number(group.metric.count), measurement(group.metric.p95, data.unit)])));
            $('omitted').textContent = data.groups_truncated ? t('omitted') + ': ' + number(data.omitted_group_observations) : '';
            $('chart-title').textContent = metricLabel(state.checks.get(state.check), data.metric, data.metric_label || state.metrics[data.metric]?.label) || t('timeline');
            $('chart-empty').hidden = Boolean(metric.count);
            $('report-data').hidden = false;
            state.chart?.destroy(); state.chart = null;
            if (window.Chart) {
                const colors = ['#31afe1', '#00243e', '#d08720'];
                state.chart = new Chart($('chart'), {type: 'line', data: {labels: data.series.map(point => date(point.at)),
                    datasets: ['p50', 'p95', 'p99'].map((key, index) => ({label: '≈ ' + key + (data.unit ? ' (' + data.unit + ')' : ''),
                        data: data.series.map(point => point.metric[key]), borderColor: colors[index], pointBackgroundColor: colors[index],
                        // With gaps, a lone value has no line segment. Keep its marker visible even in long reports.
                        pointRadius: context => {
                            const values = context.dataset.data, i = context.dataIndex;
                            return values[i] == null ? 0 : values.length <= 120 || values[i - 1] == null || values[i + 1] == null ? 3 : 0;
                        }, pointHoverRadius: 5, pointHitRadius: 10, borderWidth: 2, spanGaps: true}))}, options: {responsive: true, maintainAspectRatio: false,
                    locale: 'fr-FR', animation: false, interaction: {mode: 'index', intersect: false},
                    plugins: {legend: {position: 'bottom'}, tooltip: {callbacks: {
                        label: context => context.dataset.label + ': ' + number(context.parsed.y)
                    }}},
                    onResize: (chart, size) => { chart.options.scales.x.ticks.maxTicksLimit = size.width < 480 ? 3 : 6; },
                    scales: {x: {grid: {display: false}, ticks: {maxTicksLimit: $('chart').parentElement.clientWidth < 480 ? 3 : 6, maxRotation: 0,
                        callback: (_, index) => {
                            const at = data.series[index]?.at;
                            return at ? new Date(at).toLocaleString('de-DE', {
                                ...(Number($('period').value) > 24 ? {month: '2-digit', day: '2-digit'} : {}),
                                hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}) : '';
                        }}}, y: {beginAtZero: false, ticks: {callback: value => number(value)}, title: {display: Boolean(data.unit), text: data.unit}}}}});
            }
        }
        function updateExample() {
            const last = state.definitions.at(-1);
            const check = state.checks.get(state.check);
            const endpoint = $('endpoint').value.trim(), key = $('sending-key').value.trim(), environment = $('example-env').value.trim();
            const platform = $('example-platform').value.trim();
            const ready = last && check && contract.endpoint(endpoint) && environment && platform;
            const validKey = /^rmon_pub_[A-Za-z0-9_-]{43}$/.test(key);
            $('copy-example').disabled = !ready || !validKey;
            $('example-state').textContent = !ready ? t('sample_setup') : !validKey ? t('sample_key_required') : '';
            $('example').textContent = ready ? contract.snippet($('example-format').value, endpoint, validKey ? key : 'YOUR_SENDING_KEY',
                contract.example(last.definition, check.code, last.version, environment, platform)) : '';
        }
        async function keys(signal) {
            const data = await request(projectPath('/keys?' + pageQuery('keys', {limit: 20})), {signal});
            $('key-list').replaceChildren(...data.items.map(key => {
                const card = el('div', null, 'cc-field-row'); const head = el('div', null, 'cc-section-head');
                head.append(el('strong', presetLabel('preset_site_key', key.name)), el('span', key.revoked ? t('revoked') : key.prefix + '…', 'cc-badge'));
                if (canEdit && !key.revoked) head.append(button(t('revoke'), () => revokeKey(key)));
                card.append(head, el('p', t('check') + ': ' + key.checks.join(', ')), el('p', t('environment') + ': ' + key.environments.join(', ')),
                    el('p', t('origins') + ': ' + (key.origins.join(', ') || '—')), el('p', t('allow_no_origin') + ': ' + t(String(key.allow_no_origin))),
                    el('p', t('last_received') + ': ' + date(key.last_used_us), 'cc-muted'));
                return card;
            }));
            $('keys-state').textContent = data.items.length ? '' : t('no_keys'); pageButtons('keys', data.next_after_id);
        }
        async function connect(signal) {
            await ensureDefinitions(signal); updateExample(); await keys(signal);
        }
        async function events(signal) {
            const data = await request(projectPath('/events?' + pageQuery('events', {limit: 20})), {signal});
            $('event-rows').replaceChildren(...data.items.map(record => {
                const details = el('details'); details.append(el('summary', t('details')), el('pre', JSON.stringify(record.event, null, 2)));
                return row([date(record.received_us), record.event.check, record.event.status ? t(record.event.status) : '—', measurement(record.event.duration_ms, 'ms'),
                    country(record.event.context?.country), record.event.page_url || '—', details]);
            }));
            $('events-state').textContent = data.items.length ? '' : t('no_events'); pageButtons('events', data.next_before_id);
        }
        function refreshView({background = false} = {}) {
            if (!state.project) return loadProjects();
            const tab = state.tab;
            return run(tab, async signal => {
                await ensureChecks(signal);
                await ({overview, report, connect, events})[tab](signal);
            }, {background});
        }
        function selectTab(tab) {
            if (!['overview', 'report', 'connect', 'events'].includes(tab)) tab = 'overview';
            state.tab = tab;
            state.refreshedAt = null;
            all('[data-tab]').forEach(node => { const active = node.dataset.tab === tab; node.setAttribute('aria-selected', String(active)); node.tabIndex = active ? 0 : -1; $('panel-' + node.dataset.tab).hidden = !active; });
            urlState(); refreshView();
        }
        function labelledInput(text, value, attrs = {}) {
            const label = el('label', text), input = el('input'); input.type = 'text'; input.value = value;
            Object.assign(input, attrs); label.append(input); return {label, input};
        }
        function labelledSelect(text, values, selected) {
            const label = el('label', text), input = el('select'); options(input, values, selected); label.append(input); return {label, input};
        }
        function labelledCheck(text, checked) {
            const label = el('label', null, 'cc-check'), input = el('input'); input.type = 'checkbox'; input.checked = checked;
            label.append(input, document.createTextNode(text)); return {label, input};
        }
        function control(container, name, item) { item.input.dataset.field = name; container.append(item.label); return item.input; }
        const field = (row, name) => row.querySelector('[data-field="' + name + '"]');
        function addMetric(name = '', metric = {}) {
            if ($('metrics').children.length >= 20) return;
            const container = el('div', null, 'cc-field-row'), grid = el('div', null, 'cc-field-grid');
            control(grid, 'name', labelledInput(t('code'), name, {required: true, maxLength: 64, pattern: '[a-z][a-z0-9_.]{0,63}'}));
            const labelInput = control(grid, 'label', labelledInput(t('label'), '', {required: true, maxLength: 160}));
            displayLabel(labelInput, metric.label || '', metricLabel(state.editing?.check, name, metric.label || ''));
            control(grid, 'type', labelledSelect(t('type'), [['number', t('number')], ['integer', t('integer')]], metric.type || 'number'));
            control(grid, 'unit', labelledInput(t('unit'), metric.unit || '', {required: true, maxLength: 32}));
            control(grid, 'minimum', labelledInput(t('minimum'), metric.minimum ?? '', {type: 'number', step: 'any'}));
            control(grid, 'maximum', labelledInput(t('maximum'), metric.maximum ?? '', {type: 'number', step: 'any'}));
            control(grid, 'required', labelledCheck(t('required'), Boolean(metric.required)));
            container.append(grid, button(t('remove'), () => { container.remove(); editorChanged(); })); $('metrics').append(container);
            editorChanged();
        }
        function addContext(name = '', value = {}) {
            if ($('context').children.length >= 11) return;
            const container = el('div', null, 'cc-field-row'), grid = el('div', null, 'cc-field-grid');
            control(grid, 'name', labelledInput(t('code'), name, {required: true, maxLength: 64, pattern: '[a-z][a-z0-9_.]{0,63}'}));
            const labelInput = control(grid, 'label', labelledInput(t('label'), '', {required: true, maxLength: 160}));
            displayLabel(labelInput, value.label || '', contextLabel(state.editing?.check, name, value.label || ''));
            const type = control(grid, 'type', labelledSelect(t('type'), [['string', t('string')], ['enum', t('enum')], ['boolean', t('boolean')]], value.type || 'string'));
            control(grid, 'required', labelledCheck(t('required'), Boolean(value.required)));
            control(grid, 'filterable', labelledCheck(t('filterable'), Boolean(value.filterable)));
            const label = el('label', t('enum_hint')), textarea = el('textarea'); textarea.value = (value.values || []).join('\n'); textarea.rows = 3; textarea.maxLength = 6449;
            label.append(textarea); control(grid, 'values', {label, input: textarea});
            const sync = () => { label.hidden = type.value !== 'enum'; textarea.disabled = type.value !== 'enum'; };
            type.addEventListener('change', sync); sync();
            container.append(grid, button(t('remove'), () => { container.remove(); editorChanged(); })); $('context').append(container); editorChanged();
        }
        function definitionBody() {
            const result = {has_outcome: $('has-outcome').checked, duration: null, metrics: Object.create(null), context: Object.create(null), primary_metric: $('primary-metric').value || null};
            if ($('has-duration').checked) result.duration = {label: storedLabel($('duration-label')), type: 'number', unit: 'ms',
                required: $('duration-required').checked, minimum: contract.number($('duration-min').value), maximum: contract.number($('duration-max').value)};
            for (const container of $('metrics').children) {
                const name = field(container, 'name').value.trim();
                if (Object.hasOwn(result.metrics, name)) throw appError('invalid_definition');
                result.metrics[name] = {label: storedLabel(field(container, 'label')), type: field(container, 'type').value,
                    unit: field(container, 'unit').value.trim(), required: field(container, 'required').checked,
                    minimum: contract.number(field(container, 'minimum').value), maximum: contract.number(field(container, 'maximum').value)};
            }
            for (const container of $('context').children) {
                const name = field(container, 'name').value.trim();
                if (Object.hasOwn(result.context, name)) throw appError('invalid_definition');
                const type = field(container, 'type').value;
                result.context[name] = {label: storedLabel(field(container, 'label')), type, required: field(container, 'required').checked,
                    filterable: field(container, 'filterable').checked,
                    values: type === 'enum' ? field(container, 'values').value.split('\n').map(value => value.trim()).filter(Boolean) : []};
            }
            return contract.validate(result);
        }
        function editorChanged() {
            if (!canEdit) return;
            const selected = $('primary-metric').value;
            const values = [['', t('none')]];
            if ($('has-duration').checked) values.push(['duration_ms', $('duration-label').value || t('duration')]);
            for (const container of $('metrics').children) {
                const name = field(container, 'name').value.trim();
                if (name) values.push([name, field(container, 'label').value || name]);
            }
            options($('primary-metric'), values, selected);
            $('duration-fields').hidden = !$('has-duration').checked;
            $('duration-fields').querySelectorAll('input').forEach(node => { node.disabled = !$('has-duration').checked; });
            $('add-metric').disabled = $('metrics').children.length >= 20; $('add-context').disabled = $('context').children.length >= 11;
            try {
                const form = $('definition-form');
                $('definition-preview').textContent = JSON.stringify(contract.example(definitionBody(), form.elements.code.value || 'operation',
                    state.editing ? state.editing.version + 1 : 1), null, 2);
            } catch (_) { $('definition-preview').textContent = t('invalid_definition'); }
        }
        function openDialog(id) {
            const dialog = $(id + '-dialog'); dialog.querySelector('.cc-form-error').hidden = true; dialog.showModal();
            refreshStatus();
        }
        function fillEditor(check, version, definition) {
            const form = $('definition-form'); form.reset();
            state.editing = check ? {id: check.id, version, check} : null;
            for (const name of ['name', 'code', 'description']) { form.elements[name].value = checkLabel(check, name, check?.[name] || ''); form.elements[name].disabled = Boolean(check); }
            $('definition-title').textContent = t(check ? 'edit_definition' : 'new_check'); $('version-hint').hidden = !check;
            $('has-outcome').checked = definition.has_outcome; $('has-outcome').disabled = Boolean(check);
            $('has-duration').checked = Boolean(definition.duration);
            const durationLabel = definition.duration?.label || t('duration');
            displayLabel($('duration-label'), durationLabel, metricLabel(check, 'duration_ms', durationLabel));
            $('duration-min').value = definition.duration?.minimum ?? 0; $('duration-max').value = definition.duration?.maximum ?? '';
            $('duration-required').checked = Boolean(definition.duration?.required);
            $('metrics').replaceChildren(); $('context').replaceChildren();
            for (const [name, metric] of Object.entries(definition.metrics)) addMetric(name, metric);
            for (const [name, context] of Object.entries(definition.context)) addContext(name, context);
            editorChanged(); $('primary-metric').value = definition.primary_metric || ''; editorChanged(); openDialog('definition');
        }
        function keyChoices(preserve) {
            const selected = preserve ? new Set([...$('key-checks').querySelectorAll('input:checked')].map(input => input.value)) : new Set([state.checks.get(state.check)?.code]);
            $('key-checks').replaceChildren(...[...state.checks.values()].map(check => {
                const value = labelledCheck(checkName(check) + ' · ' + check.code, selected.has(check.code)); value.input.value = check.code; return value.label;
            }));
        }
        function formAction(id, task) {
            const form = $(id + '-form'), dialog = $(id + '-dialog');
            form.addEventListener('submit', async event => {
                event.preventDefault(); if (dialog.dataset.busy === 'true' || !form.reportValidity()) return;
                const errorTarget = form.querySelector('.cc-form-error'); errorTarget.hidden = true;
                dialog.dataset.busy = 'true';
                const controls = [...form.querySelectorAll('input, select, textarea, button')].map(node => [node, node.disabled]);
                controls.forEach(([node]) => { node.disabled = true; });
                try { await task(form); dialog.close(); }
                catch (error) { message(error, errorTarget); errorTarget.scrollIntoView?.({block: 'nearest'}); }
                finally { dialog.dataset.busy = 'false'; controls.forEach(([node, disabled]) => { node.disabled = disabled; }); }
            });
            dialog.addEventListener('cancel', event => { if (dialog.dataset.busy === 'true') event.preventDefault(); });
        }
        async function revokeKey(key) {
            if (!confirm(t('revoke_confirm'))) return;
            const project = state.project.id;
            await action(async () => {
                await request('/' + project + '/keys/' + key.id, {method: 'DELETE'});
                if (state.project?.id !== project) return;
                if (state.issued?.id === key.id) clearKey();
                updateExample(); refreshView();
            });
        }
        if (canEdit) {
            $('new-project').addEventListener('click', () => { $('project-form').reset(); openDialog('project'); });
            formAction('project', async form => {
                const value = await request('', {method: 'POST', body: {name: form.elements.name.value.trim(), description: form.elements.description.value.trim()}});
                state.projects.set(value.id, value); activateProject(value.id);
            });
            $('new-check').addEventListener('click', () => fillEditor(null, 0, {has_outcome: true, duration: {label: t('duration'), unit: 'ms', type: 'number', minimum: 0}, metrics: {}, context: {}, primary_metric: 'duration_ms'}));
            $('edit-definition').addEventListener('click', () => action(async () => {
                // Fetch again when opening an editor; the save also checks this version.
                const project = state.project.id, check = state.check;
                const result = await request('/' + project + '/checks/' + check + '/definitions');
                if (state.project?.id !== project || state.check !== check) return;
                const latest = result.items.at(-1); fillEditor(state.checks.get(check), latest.version, latest.definition);
            }));
            $('add-metric').addEventListener('click', () => addMetric()); $('add-context').addEventListener('click', () => addContext());
            $('definition-form').addEventListener('input', editorChanged); $('definition-form').addEventListener('change', editorChanged);
            formAction('definition', async form => {
                const body = definitionBody(); let check;
                if (state.editing) {
                    const result = await request(projectPath('/checks/' + state.editing.id + '/definitions'), {method: 'POST', body, headers: {'If-Match': '"' + state.editing.version + '"'}});
                    check = state.checks.get(state.editing.id); check.current_version = result.version;
                } else {
                    check = await request(projectPath('/checks'), {method: 'POST', body: {name: form.elements.name.value.trim(), code: form.elements.code.value.trim(), description: form.elements.description.value.trim(), definition: body}});
                    state.checks.set(check.id, check);
                }
                state.definitionCheck = null; chooseCheck(check.id); populateChecks(); selectTab('connect');
            });
            $('new-key').addEventListener('click', () => {
                if (!state.checks.size) { message(appError('no_checks')); return; }
                $('key-form').reset(); keyChoices(false); openDialog('key');
            });
            formAction('key', async form => {
                const checks = [...$('key-checks').querySelectorAll('input:checked')].map(input => input.value);
                if (!checks.length || checks.length > 100) throw appError('validation_error');
                const result = await request(projectPath('/keys'), {method: 'POST', body: {name: form.elements.name.value.trim(), checks,
                    environments: form.elements.environments.value.split(',').map(value => value.trim()).filter(Boolean),
                    origins: form.elements.origins.value.split('\n').map(value => value.trim()).filter(Boolean), allow_no_origin: form.elements.allow_no_origin.checked}});
                state.issued = {id: result.id}; $('sending-key').value = result.project_key;
                $('example-env').value = result.environments[0]; $('key-once').hidden = false;
                const match = [...state.checks.values()].find(check => result.checks.includes(check.code));
                chooseCheck(match.id); state.pages.keys = {cursor: null, previous: [], next: null}; refreshView();
            });
            $('toggle-collection').addEventListener('click', () => {
                if (state.project.enabled && !confirm(t('pause_confirm'))) return;
                const project = state.project.id, enabled = !state.project.enabled;
                const button = $('toggle-collection'); button.disabled = true;
                action(async () => {
                    const result = await request('/' + project, {method: 'PATCH', body: {enabled}}); state.projects.set(result.id, result);
                    if (state.project?.id === project) { state.project = result; heading(); }
                }).finally(() => { button.disabled = false; });
            });
            all('[data-close]').forEach(node => node.addEventListener('click', () => { const dialog = node.closest('dialog'); if (dialog.dataset.busy !== 'true') dialog.close(); }));
        }
        all('[data-tab]').forEach(node => {
            node.setAttribute('role', 'tab');
            node.addEventListener('click', () => selectTab(node.dataset.tab));
            node.addEventListener('keydown', event => {
                const tabs = all('[data-tab]'); let next;
                if (event.key === 'ArrowRight') next = (tabs.indexOf(node) + 1) % tabs.length;
                if (event.key === 'ArrowLeft') next = (tabs.indexOf(node) + tabs.length - 1) % tabs.length;
                if (event.key === 'Home') next = 0; if (event.key === 'End') next = tabs.length - 1;
                if (next !== undefined) { event.preventDefault(); tabs[next].focus(); selectTab(tabs[next].dataset.tab); }
            });
        });
        $('project').addEventListener('change', () => activateProject($('project').value));
        $('more-projects').addEventListener('click', () => action(async () => {
            if (!state.projectsNext) return;
            const cursor = state.projectsNext; const data = await request('?limit=100&after_id=' + cursor);
            if (state.projectsNext !== cursor) return;
            data.items.forEach(project => state.projects.set(project.id, project)); state.projectsNext = data.next_after_id; populateProjects();
        }));
        all('.cc-more-checks').forEach(node => node.addEventListener('click', () => action(loadMoreChecks,
            $('key-dialog')?.open ? $('key-form').querySelector('.cc-form-error') : $('message'))));
        all('.cc-check-select').forEach(node => node.addEventListener('change', () => { chooseCheck(node.value); refreshView(); }));
        $('period').addEventListener('change', () => { resetPages(); refreshView(); });
        $('refresh').addEventListener('click', () => { resetPages(); state.definitionCheck = null; refreshView(); });
        $('report-form').addEventListener('submit', event => { event.preventDefault(); refreshView(); });
        $('report-metric').addEventListener('change', () => { defaultOutcome(); refreshView(); });
        for (const name of ['report-group', 'report-outcome']) $(name).addEventListener('change', refreshView);
        $('add-filter').addEventListener('click', addFilter);
        for (const event of ['input', 'change']) $('filters').addEventListener(event, () => { state.filtersDirty = true; refreshStatus(); });
        for (const name of ['overview', 'keys', 'events']) {
            $(name + '-next').addEventListener('click', () => { const page = state.pages[name]; if (!page.next) return; page.previous.push(page.cursor); page.cursor = page.next; refreshView(); });
            $(name + '-prev').addEventListener('click', () => { const page = state.pages[name]; if (!page.previous.length) return; page.cursor = page.previous.pop(); refreshView(); });
        }
        for (const id of ['endpoint', 'sending-key', 'example-env', 'example-platform', 'example-format']) $(id).addEventListener('input', updateExample);
        $('copy-example').addEventListener('click', () => action(async () => {
            try { await navigator.clipboard.writeText($('example').textContent); $('example-state').textContent = t('copied'); }
            catch (_) { $('example-state').textContent = t('copy_failed'); const selection = getSelection(); const range = document.createRange(); range.selectNodeContents($('example')); selection.removeAllRanges(); selection.addRange(range); $('example').focus(); }
        }));
        function refreshStatus() {
            const target = $('refresh-status');
            target.hidden = !state.project || state.tab === 'connect';
            if (target.hidden) return;
            const parts = state.refreshedAt ? [t('last_refreshed') + ': ' + date(state.refreshedAt * 1000)] : [];
            if ($('auto-refresh').checked) {
                if (root.querySelector('dialog[open]')) parts.push(t('refresh_paused_dialog'));
                else if (state.tab === 'report' && state.filtersDirty) parts.push(t('refresh_paused_filters'));
                else if (state.pages[state.tab]?.cursor) parts.push(t('refresh_paused_history'));
                else if (root.querySelector('[aria-busy="true"]')) parts.push(t('loading'));
            }
            target.textContent = parts.join(' · ');
        }
        function autoRefresh() {
            refreshStatus();
            if (!$('auto-refresh').checked || document.visibilityState !== 'visible' || !state.project ||
                !['overview', 'report', 'events'].includes(state.tab) || root.querySelector('[aria-busy="true"], dialog[open]') ||
                state.pages[state.tab]?.cursor || state.tab === 'report' && state.filtersDirty) return;
            // Focus can stay on a selector after a choice. Only unfinished edits pause refresh.
            refreshView({background: true});
        }
        let refreshTimer;
        function startRefreshTimer() {
            if (refreshTimer !== undefined) clearInterval(refreshTimer);
            refreshTimer = setInterval(autoRefresh, 30000);
        }
        $('auto-refresh').addEventListener('change', () => { refreshStatus(); if ($('auto-refresh').checked) autoRefresh(); });
        all('dialog').forEach(dialog => dialog.addEventListener('close', refreshStatus));
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && (!state.refreshedAt || Date.now() - state.refreshedAt >= 30000)) autoRefresh();
        });
        window.addEventListener('pagehide', event => {
            clearInterval(refreshTimer); refreshTimer = undefined;
            state.bootstrapController?.abort(); state.controller?.abort(); clearKey();
            if (!event.persisted) { state.chart?.destroy(); state.chart = null; }
        });
        window.addEventListener('pageshow', event => {
            if (event.persisted) {
                startRefreshTimer();
                if (!state.project) loadProjects(); else autoRefresh();
            }
        });
        startRefreshTimer();
        async function loadProjects() {
            state.bootstrapController?.abort();
            const controller = new AbortController(); state.bootstrapController = controller;
            $('message').hidden = true;
            try {
            const data = await request('?limit=100', {signal: controller.signal}); data.items.forEach(project => state.projects.set(project.id, project)); state.projectsNext = data.next_after_id;
            let id = validId(params.get('project')) ? Number(params.get('project')) : data.items[0]?.id;
            if (id && !state.projects.has(id)) { const project = await request('/' + id, {signal: controller.signal}); state.projects.set(project.id, project); }
            state.tab = ['report', 'connect', 'events'].includes(params.get('view')) ? params.get('view') : 'overview';
            activateProject(id, true);
            all('[data-tab]').forEach(node => { const active = node.dataset.tab === state.tab; node.setAttribute('aria-selected', String(active)); node.tabIndex = active ? 0 : -1; $('panel-' + node.dataset.tab).hidden = !active; });
            } catch (error) {
                if (controller.signal.aborted || error.name === 'AbortError') return;
                message(error); $('message').append(' ', button(t('retry'), loadProjects));
            }
        }
        loadProjects();
    }
    if (window.jQuery) window.jQuery(init);
    else if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
    return {init};
})();
