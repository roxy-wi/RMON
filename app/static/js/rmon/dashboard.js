(() => {
    'use strict';
    const root = document.getElementById('rmon-dashboard');
    if (!root) return;
    const strings = JSON.parse(document.getElementById('rd-strings').textContent);
    const $ = id => document.getElementById(id);
    const t = (key, values = {}) => (strings[key] || key).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? '—');
    const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
    const fmt = value => value === null || !Number.isFinite(Number(value)) ? '—' : new Intl.NumberFormat('fr-FR', {maximumFractionDigits:2}).format(value).replace(/[\u00a0\u202f]/g, ' ');
    const date = value => new Intl.DateTimeFormat('de-DE', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}).format(new Date(value));
    const canEdit = root.dataset.canEdit === 'true';
    const states = ['down', 'warning', 'stale', 'up', 'disabled'];
    let data = null, busy = null, timer = null, status = 'all', sort = 'group', queued = false;
    const collapsed = new Set();
    // The shared page setup enhances all controls. Keep this workspace's
    // responsive, labelled native controls after that setup has completed.
    if (window.jQuery) window.jQuery(() => {
        const jq = window.jQuery;
        jq(root).find('select').each(function () {if (jq(this).selectmenu('instance')) jq(this).selectmenu('destroy');});
        jq(root).find('button').each(function () {if (jq(this).button('instance')) jq(this).button('destroy');});
        jq(root).find('input[type=checkbox]').each(function () {if (jq(this).checkboxradio('instance')) jq(this).checkboxradio('destroy');});
    });
    const params = new URL(location.href).searchParams;
    if (states.includes(params.get('status'))) status = params.get('status');
    if (params.get('sort') === 'by_status') sort = 'status';
    else if (['status', 'name'].includes(params.get('sort'))) sort = params.get('sort');
    $('rd-sort').value = sort;
    $('rd-search').value = params.get('q') || '';
    let selectedGroup = params.get('group') || 'all';

    function age(value) {
        if (!value) return t('never');
        const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
        if (seconds < 10) return t('just_now');
        const [unit, factor] = seconds < 60 ? ['seconds_ago', 1] : seconds < 3600 ? ['minutes_ago', 60] : seconds < 86400 ? ['hours_ago', 3600] : ['days_ago', 86400];
        return t(unit, {value:fmt(Math.floor(seconds / factor))});
    }
    function saveFilters() {
        const url = new URL(location.href);
        for (const [key, value] of Object.entries({status:status === 'all' ? '' : status, sort:sort === 'group' ? '' : sort, q:$('rd-search').value, group:selectedGroup === 'all' ? '' : selectedGroup})) {
            if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
        }
        history.replaceState(null, '', url);
    }
    function action(name, card) {
        return `<button type="button" id="rd-${name}-${card.id}" data-action="${name}" data-id="${card.id}" aria-label="${escape(t(name) + ': ' + card.name)}">${escape(t(name))}</button>`;
    }
    function cardView(card) {
        let history = `<p class="rd-muted">${escape(t('history_locked'))}</p>`;
        if (card.history) {
            const start = new Date(data.history_start).getTime();
            history = `<div><div class="rd-history" role="img" aria-label="${escape(t('history'))}">${card.history.map((bin, i) => {
                const label = `${date(start + i * 3600000)} – ${date(start + (i + 1) * 3600000)} · ${t(bin.state)} · ${t('observations', {up:fmt(bin.up), total:fmt(bin.total)})}`;
                return `<i data-state="${bin.state}" title="${escape(label)}"></i>`;
            }).join('')}</div><div class="rd-history-labels"><span>${escape(t('ago'))}</span><span>${escape(t('now'))}</span></div></div>`;
        }
        return `<article class="rd-card" id="smon-${card.id}" data-state="${card.state}">
            <div class="rd-card-heading"><h4><a id="smon-name-${card.id}" href="/rmon/dashboard/${card.id}/${card.type_id}">${escape(card.name)}</a></h4><span class="rd-badge rd-${card.state}">${escape(t('state_' + card.state))}</span></div>
            <p class="rd-muted" title="${escape(t('point_summary', card.locations))}">${escape(card.type.toUpperCase())} · ${escape(t('locations', {up:fmt(card.locations.up), total:fmt(card.total_locations)}))}</p>
            ${card.description ? `<p class="rd-card-description">${escape(card.description)}</p>` : ''}
            <div class="rd-stats"><div class="rd-stat" title="${escape(t('response_hint'))}"><span>${escape(t('response'))}</span><strong>${fmt(card.response_ms)}${card.response_ms === null ? '' : ' ms'}</strong></div><div class="rd-stat"><span>${escape(t('uptime'))}</span><strong>${fmt(card.uptime)}${card.uptime === null ? '' : ' %'}</strong></div></div>
            ${history}
            <div class="rd-card-footer"><span>${escape(t('last_result', {time:age(card.last_result)}))}</span>${card.last_result ? `<time datetime="${escape(card.last_result)}" title="${escape(date(card.last_result))}">${escape(date(card.last_result))}</time>` : ''}</div>
            <div class="rd-card-actions">${canEdit ? ['edit', 'clone', 'delete'].map(name => action(name, card)).join('') : ''}<a href="/rmon/history/check/${card.id}">${escape(t('alerts'))}</a></div>
        </article>`;
    }
    function render() {
        if (!data) return;
        const active = document.activeElement;
        const focus = $('dashboards').contains(active) ? active.id : null;
        root.querySelectorAll('[data-count]').forEach(node => {node.textContent = fmt(node.dataset.count === 'all' ? data.items.length : data.counts[node.dataset.count]);});
        root.querySelectorAll('[data-status]').forEach(node => node.setAttribute('aria-pressed', String(node.dataset.status === status)));
        const query = $('rd-search').value.trim().toLocaleLowerCase();
        const groupNames = new Map(data.items.map(card => [String(card.group_id ?? 'none'), card.group_name || t('ungrouped')]));
        for (const group of data.groups || []) groupNames.set(String(group.id), group.name);
        $('rd-group').innerHTML = `<option value="all">${escape(t('all_groups'))}</option>` + [...groupNames].sort((a, b) => a[1].localeCompare(b[1])).map(([id, name]) => `<option value="${escape(id)}">${escape(name)}</option>`).join('');
        if (!groupNames.has(selectedGroup)) selectedGroup = 'all';
        $('rd-group').value = selectedGroup;
        const items = data.items.filter(card => (status === 'all' || card.state === status) &&
            (selectedGroup === 'all' || String(card.group_id ?? 'none') === selectedGroup) &&
            (!query || `${card.name} ${card.description}`.toLocaleLowerCase().includes(query)));
        items.sort((a, b) => (sort === 'status' ? states.indexOf(a.state) - states.indexOf(b.state) : 0) || a.name.localeCompare(b.name) || a.id - b.id);
        const groups = new Map();
        // Empty named groups remain editable, as on the original dashboard.
        if (sort === 'group' && status === 'all' && !query) {
            for (const key of groupNames.keys()) if (selectedGroup === 'all' || selectedGroup === key) groups.set(key, []);
        }
        for (const card of items) {
            const key = sort === 'group' ? String(card.group_id ?? 'none') : 'all';
            if (!groups.has(key)) groups.set(key, []);
            groups.get(key).push(card);
        }
        const sections = [...groups];
        if (sort === 'group') sections.sort((a, b) => (groupNames.get(a[0]) || '').localeCompare(groupNames.get(b[0]) || ''));
        $('dashboards').innerHTML = sections.map(([key, cards]) => {
            const isGroup = key !== 'all', groupId = cards[0]?.group_id ?? (key === 'none' || key === 'all' ? null : Number(key));
            const open = !collapsed.has(key) || Boolean(query) || status !== 'all';
            const heading = isGroup ? `<div class="rd-group-heading"><div class="rd-group-title"><button type="button" class="rd-group-toggle" id="rd-toggle-${key}" data-toggle="${key}" aria-expanded="${open}" aria-controls="rd-grid-${key}"><span id="smon_group_name-${key}">${escape(groupNames.get(key))}</span><span class="rd-muted">${fmt(cards.length)}</span></button></div>${canEdit && groupId ? `<div class="rd-group-actions"><button type="button" data-group-action="edit" data-id="${groupId}">${escape(t('edit_group'))}</button><button type="button" data-group-action="delete" data-id="${groupId}">${escape(t('delete_group'))}</button></div>` : ''}</div>` : '';
            return `<section id="check-group-${key}">${heading}<div id="rd-grid-${key}" class="rd-grid" ${open ? '' : 'hidden'}>${cards.map(cardView).join('')}</div></section>`;
        }).join('');
        $('rd-empty').hidden = data.items.length !== 0;
        $('rd-no-match').hidden = !data.items.length || items.length !== 0;
        $('rd-clear').hidden = status === 'all' && !query && selectedGroup === 'all';
        $('rd-history-note').hidden = !data.items.length || !data.history_available;
        $('rd-updated').textContent = t('updated', {time:date(data.updated_at)}) + ($('rd-auto').checked ? '' : ` · ${t('paused')}`);
        if (focus) $(focus)?.focus({preventScroll:true});
    }
    function editing() {
        return Boolean(document.querySelector('.ui-dialog[style*="display: block"], .ui-widget-overlay'));
    }
    async function refresh() {
        if (busy) {queued = true; return;}
        const controller = new AbortController();
        busy = controller;
        const timeout = setTimeout(() => controller.abort(), 20000);
        $('dashboards').setAttribute('aria-busy', 'true');
        $('rd-refresh').disabled = true;
        try {
            const response = await fetch(root.dataset.endpoint, {signal:controller.signal, credentials:'same-origin', headers:{Accept:'application/json'}, cache:'no-store'});
            if (response.status === 401 || response.redirected) throw new Error('session');
            if (!response.ok) throw new Error('load');
            const result = await response.json();
            if (!Array.isArray(result.items) || !result.counts || !result.updated_at) throw new Error('load');
            data = result;
            $('rd-error').hidden = true;
            render();
        } catch (error) {
            // Keep the last complete snapshot visible on network failures.
            $('rd-error').textContent = t(error.message === 'session' ? 'login_error' : 'load_error');
            $('rd-error').hidden = false;
        } finally {
            clearTimeout(timeout);
            if (busy === controller) busy = null;
            $('dashboards').setAttribute('aria-busy', 'false');
            $('rd-refresh').disabled = false;
            if (queued) {queued = false; refresh();}
        }
    }
    function automatic() {
        if ($('rd-auto').checked && !document.hidden && !busy && !editing()) refresh();
    }
    function startTimer() {clearInterval(timer); timer = setInterval(automatic, 30000);}
    root.addEventListener('click', event => {
        const button = event.target.closest('button');
        if (!button) return;
        if (button.dataset.status) {status = button.dataset.status; render(); saveFilters();}
        if (button.id === 'rd-refresh') refresh();
        if (button.id === 'rd-clear') {status = 'all'; selectedGroup = 'all'; $('rd-search').value = ''; render(); saveFilters();}
        if (button.dataset.toggle) {
            const key = button.dataset.toggle, open = button.getAttribute('aria-expanded') === 'true';
            if (open) collapsed.add(key); else collapsed.delete(key);
            $('rd-grid-' + key).hidden = open;
            button.setAttribute('aria-expanded', String(!open));
        }
        if (button.dataset.action && canEdit) {
            const card = data.items.find(card => String(card.id) === button.dataset.id);
            if (!card) return;
            if (button.dataset.action === 'edit') window.editSmon(card.id, card.type);
            if (button.dataset.action === 'clone') window.cloneSmon(card.id, card.type);
            if (button.dataset.action === 'delete') window.confirmDeleteSmon(card.id, card.type);
        }
        if (button.dataset.groupAction && canEdit) {
            if (button.dataset.groupAction === 'edit') window.editCheckGroupDialog(button.dataset.id);
            if (button.dataset.groupAction === 'delete') window.confirmDeleteCheckGroup(button.dataset.id);
        }
    });
    $('rd-search').addEventListener('input', () => {render(); saveFilters();});
    $('rd-group').addEventListener('change', () => {selectedGroup = $('rd-group').value; render(); saveFilters();});
    $('rd-sort').addEventListener('change', () => {sort = $('rd-sort').value; render(); saveFilters();});
    $('rd-auto').addEventListener('change', () => {render(); if ($('rd-auto').checked) automatic();});
    document.addEventListener('visibilitychange', () => {if (!document.hidden) automatic();});
    window.addEventListener('pagehide', () => {clearInterval(timer); queued = false; busy?.abort();});
    window.addEventListener('pageshow', event => {if (event.persisted) {startTimer(); automatic();}});
    window.RmonDashboard = {refresh};
    startTimer();
    refresh();
})();
