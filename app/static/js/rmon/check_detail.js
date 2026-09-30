(() => {
    'use strict';
    const root = document.getElementById('rmon-check-detail');
    if (!root) return;
    const strings = JSON.parse(document.getElementById('cd-strings').textContent);
    const $ = id => document.getElementById(id);
    const t = (key, values = {}) => (strings[key] || key).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? '—');
    const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
    const fmt = value => value === null || value === undefined || !Number.isFinite(Number(value)) ? '—' : new Intl.NumberFormat('fr-FR', {maximumFractionDigits:2}).format(value).replace(/[\u00a0\u202f]/g, ' ');
    const date = (value, full = true) => value && Number.isFinite(new Date(value).getTime()) ? new Intl.DateTimeFormat('de-DE', {
        ...(full ? {day:'2-digit', month:'2-digit', year:'numeric'} : {}), hour:'2-digit', minute:'2-digit', second:full ? '2-digit' : undefined, hour12:false
    }).format(new Date(value)) : '—';
    const unitValue = (value, unit = 'ms') => fmt(value) + (value === null || value === undefined ? '' : ' ' + unit);
    const countryNames = new Intl.DisplayNames([document.documentElement.lang || 'en'], {type:'region'});
    const country = value => /^[A-Z]{2}$/.test(value || '') ? countryNames.of(value) : value;
    const placeName = item => item.region || item.agent || country(item.country) || t('location_fallback', {id:item.id});
    const placeSub = item => [...new Set([country(item.country), item.agent].filter(value => value && value !== placeName(item)))].join(' · ');
    const badge = (state, label = t('state_' + state)) => `<span class="rd-badge rd-${esc(state)}">${esc(label)}</span>`;
    const stateForStatus = status => status === 1 ? 'up' : [0,2,7,8].includes(status) ? 'down' : [5,6,9].includes(status) ? 'warning' : status === 4 ? 'disabled' : 'stale';
    const resultLabel = status => t(({0:data?.type === 'http' ? 'http_failure' : 'failure',1:'success',2:'failure',3:'unknown',4:'state_disabled',5:'state_warning',6:'threshold',7:'body_failure',8:'headers_failure',9:'state_warning'})[status] || 'unknown');
    const params = new URL(location.href).searchParams;
    let tab = params.get('tab') === 'diagnostic' ? 'diagnostic' : 'overview';
    let locationId = /^\d+$/.test(params.get('location') || '') ? Number(params.get('location')) : null;
    let data = null, chart = null, request = null, timer = null, suspended = false, revision = 0, loadedHours = '1';
    $('cd-period').value = ['1','6','24'].includes(params.get('hours')) ? params.get('hours') : '1';
    const tip = document.createElement('div');
    tip.className = 'cd-tooltip'; tip.hidden = true; tip.setAttribute('role', 'tooltip');
    $('cd-chart-panel').append(tip);
    $('cd-timezone').textContent = t('timezone', {zone:Intl.DateTimeFormat().resolvedOptions().timeZone});

    if (window.jQuery) window.jQuery(() => {
        const jq = window.jQuery;
        for (const [selector, plugin] of [['select','selectmenu'], ['button','button'], ['input[type=checkbox]','checkboxradio']]) {
            if (jq.fn[plugin]) jq(root).find(selector).each(function () {if (jq(this)[plugin]('instance')) jq(this)[plugin]('destroy');});
        }
    });
    function saveView() {
        const url = new URL(location.href);
        url.searchParams.set('tab', tab); url.searchParams.set('hours', $('cd-period').value);
        if (locationId) url.searchParams.set('location', locationId); else url.searchParams.delete('location');
        history.replaceState(null, '', url);
    }
    function showTab() {
        for (const name of ['overview','diagnostic']) {
            $('cd-' + name).hidden = tab !== name;
            $('cd-tab-' + name).setAttribute('aria-selected', String(tab === name));
            $('cd-tab-' + name).tabIndex = tab === name ? 0 : -1;
        }
        $('cd-' + tab + '-chart').append($('cd-chart-panel'));
        tip.hidden = true;
        if (chart) {chart.$cursor = null; chart.$pinned = false; chart.resize();}
    }
    function parameters(item, compact = false) {
        if (!item) return '';
        const config = item.config;
        const values = [
            ['target', config.url || (config.ip ? config.ip + (config.port ? ':' + config.port : '') : null)],
            ['method', config.method?.toUpperCase()], ['interval', config.interval === undefined ? null : t('seconds',{value:fmt(config.interval)})],
            ['timeout', t('seconds',{value:fmt(item.timeout)})], ['retries', fmt(item.retries)],
            ['codes', config.accepted_status_codes?.join(', ')], ['resolver', config.resolver], ['record_type', config.record_type?.toUpperCase()],
            ['packet_size', config.packet_size], ['count_packets', config.count_packets], ['certificate', item.certificate_expires],
            ['mean', unitValue(item.mean_ms)]
        ];
        return values.filter(([key,value]) => value !== null && value !== undefined && value !== '' && (!compact || ['target','interval','timeout'].includes(key))).map(([key,value]) => `<dt>${esc(t(key))}</dt><dd>${esc(value)}</dd>`).join('');
    }
    function render() {
        const focus = root.contains(document.activeElement) ? document.activeElement.id : null;
        const summary = data.summary;
        if (!data.locations.some(item => item.id === locationId)) locationId = data.locations[0]?.id ?? null;
        $('cd-name').textContent = data.name;
        document.querySelector('.page-header h2')?.replaceChildren(document.createTextNode(data.name));
        document.title = data.name;
        $('cd-status').className = 'rd-badge rd-' + summary.state;
        $('cd-status').textContent = summary.state === 'down' && summary.locations.up ? t('partial') : t('state_' + summary.state);
        $('cd-description').textContent = [data.type.toUpperCase(), data.description].filter(Boolean).join(' · ');
        if ($('cd-edit')) $('cd-edit').disabled = false;
        $('cd-response').textContent = unitValue(summary.response_ms);
        $('cd-uptime').textContent = unitValue(summary.uptime, '%');
        $('cd-count').textContent = fmt(summary.locations.up || 0) + ' / ' + fmt(summary.total_locations);
        const issues = (summary.locations.down || 0) + (summary.locations.warning || 0) + (summary.locations.stale || 0);
        $('cd-notice').hidden = !issues;
        $('cd-notice').textContent = t('issues', {count:fmt(issues), total:fmt(summary.total_locations)});
        $('cd-locations').innerHTML = data.locations.map(item => `<button type="button" class="cd-location-row" id="cd-row-${item.id}" data-location="${item.id}"><span><span class="cd-location-name">${esc(placeName(item))}</span><span class="cd-location-sub">${esc(placeSub(item))}</span></span><span class="cd-location-values">${badge(item.state)}<span>${esc(unitValue(item.response_ms))}</span></span></button>`).join('');
        $('cd-picker').innerHTML = data.locations.map(item => `<button type="button" id="cd-pick-${item.id}" data-location="${item.id}" aria-pressed="${item.id === locationId}"><span class="cd-location-name">${esc(placeName(item))}</span><span class="cd-location-sub">${esc(placeSub(item))}</span>${badge(item.state)}</button>`).join('');
        const selected = data.locations.find(item => item.id === locationId);
        $('cd-parameters').innerHTML = parameters(data.locations[0]);
        $('cd-result').innerHTML = selected ? `<div class="cd-result-heading"><div><h4>${esc(placeName(selected))}</h4><span class="cd-location-sub">${esc(placeSub(selected))}</span></div>${badge(selected.state)}</div><p class="rd-muted">${esc(selected.last_result ? t('last_result',{time:date(selected.last_result)}) : t('never'))}</p><dl class="cd-parameters">${parameters(selected, true)}</dl>${selected.error ? `<p class="cd-message">${esc(selected.error)}</p>` : ''}<button type="button" class="cd-route" data-route="${selected.id}">${esc(t('route'))}</button>` : '';
        const events = data.events.filter(item => tab === 'overview' || item.location_id === locationId);
        const expanded = $('cd-more-results')?.open;
        const eventRows = events.map(item => `<div class="cd-event"><time datetime="${esc(item.date)}">${esc(date(item.date))}</time><div>${badge(stateForStatus(item.status), resultLabel(item.status))}${item.message ? `<p>${esc(item.message)}</p>` : ''}</div></div>`);
        $('cd-events').innerHTML = events.length ? eventRows.slice(0,5).join('') + (events.length > 5 ? `<details id="cd-more-results" ${expanded ? 'open' : ''}><summary>${esc(t('more_results',{count:fmt(events.length-5)}))}</summary>${eventRows.slice(5).join('')}</details>` : '') : `<p class="cd-empty">${esc(t('no_results'))}</p>`;
        $('cd-updated').textContent = t('refreshed', {time:date(data.updated_at)});
        showTab(); drawChart();
        if (focus) $(focus)?.focus({preventScroll:true});
    }
    function interpolate(points, x) {
        if (!points.length || x < points[0].x || x > points[points.length - 1].x) return null;
        let low = 0, high = points.length - 1;
        while (low < high) {const middle = Math.floor((low + high) / 2); if (points[middle].x < x) low = middle + 1; else high = middle;}
        const right = points[low];
        if (right.x === x || low === 0) return right.y;
        const left = points[low - 1];
        return left.y === null || right.y === null ? null : left.y + (right.y - left.y) * (x - left.x) / (right.x - left.x);
    }
    function readings(values) {
        chart.data.datasets.forEach((set, i) => {
            const output = $('cd-value-' + i);
            if (output) output.innerHTML = `${esc(fmt(values[i]))} <small>${values[i] === null ? '' : esc(set.unit)}</small>`;
        });
    }
    function latestReadings() {
        if (!chart) return;
        readings(chart.data.datasets.map(set => set.data.at(-1)?.y ?? null));
        $('cd-chart-time').textContent = t('latest');
    }
    const crosshair = {
        id:'rmonCheckCrosshair',
        afterEvent(instance, args) {
            const event = args.event, area = instance.chartArea;
            if (event.type === 'mouseout') {
                if (!instance.$pinned) {instance.$cursor = null; tip.hidden = true; latestReadings(); args.changed = true;}
                return;
            }
            if (!area || event.x < area.left || event.x > area.right || event.y < area.top || event.y > area.bottom) return;
            if (event.type === 'click') instance.$pinned = !instance.$pinned;
            else if (instance.$pinned) return;
            instance.$cursor = {x:event.x, y:event.y}; args.changed = true;
        },
        afterDraw(instance) {
            const cursor = instance.$cursor;
            if (!cursor) return;
            const x = instance.scales.x.getValueForPixel(cursor.x);
            const values = instance.data.datasets.map(set => interpolate(set.data, x));
            const context = instance.ctx, area = instance.chartArea;
            context.save(); context.lineWidth = 1; context.strokeStyle = getComputedStyle(root).getPropertyValue('--rd-muted').trim();
            context.setLineDash([3,3]); context.beginPath(); context.moveTo(cursor.x, area.top); context.lineTo(cursor.x, area.bottom); context.stroke(); context.setLineDash([]);
            values.forEach((value, index) => {if (value === null) return; const set = instance.data.datasets[index], y = instance.scales[set.yAxisID].getPixelForValue(value); context.beginPath(); context.arc(cursor.x, y, 3, 0, Math.PI * 2); context.fillStyle = set.borderColor; context.fill();});
            context.restore(); readings(values);
            const stamp = t('at', {time:date(x)}); $('cd-chart-time').textContent = stamp;
            tip.innerHTML = `<div class="cd-tip-time">${esc(stamp)}</div>` + instance.data.datasets.map((set, i) => `<div class="cd-tip-row"><span>${esc(set.label)}</span><span>${esc(unitValue(values[i], set.unit))}</span></div>`).join('');
            tip.hidden = false;
            const canvasBox = instance.canvas.getBoundingClientRect(), panelBox = $('cd-chart-panel').getBoundingClientRect();
            const left = canvasBox.left - panelBox.left + cursor.x + 12;
            tip.style.left = Math.max(8, Math.min(left, panelBox.width - tip.offsetWidth - 8)) + 'px';
            tip.style.top = Math.max(8, Math.min(canvasBox.top - panelBox.top + cursor.y + 12, panelBox.height - tip.offsetHeight - 8)) + 'px';
        }
    };
    function drawChart() {
        const styles = getComputedStyle(root), color = key => styles.getPropertyValue(key).trim();
        const colors = ['--cd-blue','--rd-good','--cd-gold','--cd-purple','--cd-gray','--cd-pink','--cd-orange','--cd-teal'].map(color);
        const datasets = data.series.map((series, index) => {
            const location = data.locations.find(item => item.id === series.location_id);
            const isolated = series.points.filter(point => point.y !== null).length === 1;
            return {label:tab === 'overview' ? placeName(location) : t('metric_' + series.id), unit:series.unit,
                data:series.points.map(point => ({x:Date.parse(point.x), y:point.y})),
                yAxisID:series.unit === '%' ? 'percent' : 'ms', borderColor:colors[index % colors.length],
                backgroundColor:colors[index % colors.length], borderDash:index >= colors.length ? [5,3] : [],
                borderWidth:2, pointRadius:isolated ? 3 : 0, pointHitRadius:8, tension:0, fill:false, spanGaps:false};
        });
        const title = t(tab === 'overview' ? 'response_chart' : 'metrics_chart');
        $('cd-chart-title').textContent = title;
        $('cd-chart').setAttribute('aria-label', title + ': ' + datasets.map(set => set.label + ' (' + set.unit + ')').join(', '));
        const hasData = datasets.some(set => set.data.some(point => point.y !== null));
        $('cd-no-data').hidden = hasData;
        $('cd-chart').parentElement.hidden = !hasData;
        $('cd-limited').hidden = !data.truncated;
        $('cd-limited').textContent = t('limited', {limit:fmt(data.point_limit)});
        $('cd-legend').innerHTML = datasets.map((set,i) => `<div><span class="cd-legend-label"><i class="cd-swatch" aria-hidden="true" style="border-color:${set.borderColor};${set.borderDash.length ? 'border-top-style:dashed' : ''}"></i>${esc(set.label)}</span><output id="cd-value-${i}" aria-label="${esc(set.label)}">—</output></div>`).join('');
        const options = {
            responsive:true, maintainAspectRatio:false, animation:false, parsing:false,
            interaction:{intersect:false, mode:'index'},
            plugins:{legend:{display:false}, tooltip:{enabled:false}},
            scales:{
                x:{type:'linear', min:Date.parse(data.start), max:Date.parse(data.end), grid:{display:false},
                    title:{display:true,text:t('axis_time'),color:color('--rd-muted')}, ticks:{color:color('--rd-muted'),maxTicksLimit:5,maxRotation:0,callback:value=>date(value,false)}},
                ms:{type:'linear',beginAtZero:true,position:'left',title:{display:true,text:t('axis_ms'),color:color('--rd-muted')},
                    grid:{color:color('--rd-line')},ticks:{color:color('--rd-muted'),maxTicksLimit:5,callback:value=>fmt(value)}},
                percent:{type:'linear',display:datasets.some(set=>set.unit === '%'),position:'right',min:0,max:100,
                    title:{display:true,text:t('axis_percent'),color:color('--rd-muted')},grid:{drawOnChartArea:false},ticks:{color:color('--rd-muted'),maxTicksLimit:3,callback:value=>fmt(value)}}
            }
        };
        if (chart) {chart.$cursor = null; chart.$pinned = false; chart.data.datasets = datasets; chart.options = options; chart.update('none');}
        else chart = new Chart($('cd-chart'), {type:'line',data:{datasets},options,plugins:[crosshair]});
        latestReadings();
    }
    async function refresh(replace = false) {
        if (suspended || request && !replace) return;
        if (replace) request?.abort();
        const current = new AbortController(), version = ++revision;
        request = current;
        const requestedTab = tab, requestedLocation = locationId;
        const url = new URL(root.dataset.endpoint, location.origin);
        url.searchParams.set('hours', $('cd-period').value);
        if (requestedTab === 'diagnostic' && requestedLocation) url.searchParams.set('location', requestedLocation);
        const timeout = setTimeout(() => current.abort(), 20000);
        $('cd-content').setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(url, {credentials:'same-origin', cache:'no-store',headers:{Accept:'application/json'},signal:current.signal});
            if (!response.ok || response.redirected) throw {status:response.redirected ? 401 : response.status};
            const result = await response.json();
            if (version !== revision || suspended) return;
            data = result;
            loadedHours = url.searchParams.get('hours');
            if (requestedTab === 'diagnostic' && !requestedLocation) {
                locationId = data.locations[0]?.id ?? null;
                if (locationId) {request = null; return refresh(true);}
            }
            $('cd-error').hidden = true;
            render(); saveView();
        } catch (error) {
            if (version !== revision || suspended) return;
            $('cd-error').textContent = t(error.status === 404 ? 'not_found' : [401,403].includes(error.status) ? 'session_error' : 'load_error');
            $('cd-error').hidden = false;
            // Keep the view and labels attached to the data that was actually loaded.
            if (data) {tab = data.selected_location ? 'diagnostic' : 'overview'; locationId = data.selected_location || locationId; $('cd-period').value = loadedHours; render();}
        } finally {
            clearTimeout(timeout);
            if (version === revision) {request = null; $('cd-content').setAttribute('aria-busy','false');}
        }
    }
    root.addEventListener('click', event => {
        const button = event.target.closest('button'); if (!button) return;
        if (button.dataset.tab) {tab = button.dataset.tab; refresh(true);}
        else if (button.dataset.location) {locationId = Number(button.dataset.location); tab = 'diagnostic'; refresh(true);}
        else if (button.dataset.route) window.showRoute?.(Number(button.dataset.route));
        else if (button.id === 'cd-edit' && data && root.dataset.canEdit === 'true') window.editSmon?.(data.id, data.type);
        else if (button.id === 'cd-refresh') refresh(true);
    });
    root.querySelector('[role=tablist]').addEventListener('keydown', event => {
        if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
        event.preventDefault(); const next = event.key === 'Home' ? 'overview' : event.key === 'End' ? 'diagnostic' : event.target.dataset.tab === 'overview' ? 'diagnostic' : 'overview';
        $('cd-tab-' + next).focus(); $('cd-tab-' + next).click();
    });
    $('cd-period').addEventListener('change', () => refresh(true));
    function startTimer() {clearInterval(timer); timer = setInterval(() => {if ($('cd-auto').checked && !document.hidden && !document.querySelector('.ui-widget-overlay')) refresh();}, 30000);}
    $('cd-auto').addEventListener('change', () => {if ($('cd-auto').checked) refresh();});
    document.addEventListener('visibilitychange', () => {if (!document.hidden && $('cd-auto').checked) refresh();});
    window.addEventListener('pagehide', () => {suspended = true; revision++; request?.abort(); request = null; clearInterval(timer);});
    window.addEventListener('pageshow', event => {if (event.persisted) {suspended = false; startTimer(); refresh();}});
    const themeObserver = new MutationObserver(() => {if (data && chart) drawChart();});
    themeObserver.observe(document.head, {childList:true,subtree:true,attributes:true,attributeFilter:['href']});
    window.RmonCheckDetail = {refresh:() => refresh(true)};
    showTab(); startTimer(); refresh();
})();
