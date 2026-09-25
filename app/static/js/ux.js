/* Shared interaction helpers. Existing editor IDs and event handlers stay stable. */
window.RmonUI = (function () {
    'use strict';
    const catalog = document.getElementById('rmon-ui-strings');
    const strings = catalog ? JSON.parse(catalog.textContent) : {};
    const text = key => strings[key] || key;
    function requestError(xhr) {
        const keys = {0: 'network_error', 400: 'validation_error', 401: 'unauthorized',
            403: 'forbidden', 404: 'not_found', 409: 'conflict', 422: 'validation_error', 429: 'rate_limit'};
        return text(xhr.status >= 500 ? 'server_error' : (keys[xhr.status] || 'request_error'));
    }
    function notifyRequestError(xhr) {
        toastr.error(requestError(xhr));
    }
    function widgetState(target, state, retry) {
        const host = $(target);
        if (!host.length) return;
        host.children('.widget-state, .widget-state-row').remove();
        host.attr('aria-busy', String(state === 'loading'));
        host.children('canvas').toggle(state === 'ready');
        if (state === 'ready') return;
        const message = $('<div>', {class: 'widget-state', role: 'status'});
        $('<span>').text(text(state === 'loading' ? 'loading' : 'widget_error')).appendTo(message);
        if (state === 'error' && retry) {
            $('<button>', {type: 'button', class: 'retry-button'}).text(text('retry')).on('click', retry).appendTo(message);
        }
        if (host.is('tbody, tr, table')) {
            const cell = $('<td>', {colspan: 20}).append(message);
            if (host.is('tr')) host.empty().append(cell);
            else host.empty().append($('<tr>', {class: 'widget-state-row'}).append(cell));
        } else host.append(message);
    }
    function loadFragment(target, url) {
        if (!$(target).length) return;
        const retry = () => loadFragment(target, url);
        return $.ajax({url, global: false, beforeSend: () => widgetState(target, 'loading'),
            success: function (data) {
                if (typeof data !== 'string' || /^\s*error:/i.test(data)) {
                    widgetState(target, 'error', retry);
                } else {
                    $(target).attr('aria-busy', 'false').html(data);
                    enhance(document);
                }
            }, error: () => widgetState(target, 'error', retry)});
    }
    function initNavigation() {
        const nav = document.getElementById('main-navigation');
        const toggle = document.getElementById('menu-toggle');
        const backdrop = document.getElementById('menu-backdrop');
        if (!nav || !toggle) return;
        const mobile = window.matchMedia('(max-width: 800px)');
        let desktopHidden = false;
        try { desktopHidden = sessionStorage.getItem('hide_menu') === 'hide'; } catch (_) {}
        function setOpen(open, focusMenu = false) {
            document.body.classList.toggle('nav-collapsed', !mobile.matches && !open);
            document.body.classList.toggle('nav-open', mobile.matches && open);
            nav.inert = !open;
            nav.setAttribute('aria-hidden', String(!open));
            toggle.setAttribute('aria-expanded', String(open));
            backdrop.hidden = !(mobile.matches && open);
            $('#hide_menu').toggle(open);
            $('.show_menu').toggle(!open);
            if (focusMenu && open && mobile.matches) nav.querySelector('a').focus();
        }
        function close() { setOpen(false); toggle.focus(); }
        toggle.addEventListener('click', () => {
            const open = toggle.getAttribute('aria-expanded') !== 'true';
            if (!mobile.matches) {
                desktopHidden = !open;
                try { sessionStorage.setItem('hide_menu', open ? 'show' : 'hide'); } catch (_) {}
            }
            setOpen(open, true);
        });
        backdrop.addEventListener('click', close);
        nav.addEventListener('click', event => {
            if (mobile.matches && event.target.closest('a')) close();
        });
        document.addEventListener('keydown', event => {
            if (!mobile.matches || toggle.getAttribute('aria-expanded') !== 'true') return;
            if (event.key === 'Escape') { event.preventDefault(); close(); }
            if (event.key === 'Tab') {
                const links = Array.from(nav.querySelectorAll('a')).filter(a => a.getClientRects().length);
                if (event.shiftKey && document.activeElement === links[0]) { event.preventDefault(); toggle.focus(); }
                else if (!event.shiftKey && document.activeElement === links[links.length - 1]) { event.preventDefault(); toggle.focus(); }
                else if (document.activeElement === toggle) { event.preventDefault(); links[event.shiftKey ? links.length - 1 : 0].focus(); }
            }
        });
        $('#hide_menu, #show_menu').on('click', function (event) {
            event.preventDefault(); desktopHidden = this.id === 'hide_menu';
            try { sessionStorage.setItem('hide_menu', desktopHidden ? 'hide' : 'show'); } catch (_) {}
            setOpen(!desktopHidden);
        });
        mobile.addEventListener('change', () => setOpen(!mobile.matches && !desktopHidden));
        setOpen(!mobile.matches && !desktopHidden);
    }
    function fitDialog(element) {
        const content = $(element);
        const dialog = content.dialog('widget');
        const intended = content.dialog('option', 'width');
        dialog.css({width: Math.min(Number(intended) || 600, window.innerWidth - 24),
            maxHeight: 'calc(100dvh - 24px)', display: 'flex', flexDirection: 'column', position: 'fixed'});
        content.css({minHeight: 0, maxHeight: 'none', overflow: 'auto', flex: '1 1 auto'});
        content.dialog('option', 'position', {my: 'center', at: 'center', of: window});
    }
    let menuSequence = 0;
    let openMenu = null;
    function closeActions(restoreFocus = false) {
        if (!openMenu) return;
        const {toggle, menu} = openMenu;
        menu.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
        openMenu = null;
        if (restoreFocus && toggle.isConnected) toggle.focus();
    }
    function showActions(toggle, last = false) {
        closeActions();
        const menu = toggle.nextElementSibling;
        menu.hidden = false;
        toggle.setAttribute('aria-expanded', 'true');
        openMenu = {toggle, menu};
        const anchor = toggle.getBoundingClientRect();
        const box = menu.getBoundingClientRect();
        const top = anchor.bottom + 4 + box.height <= window.innerHeight - 12 ? anchor.bottom + 4 : anchor.top - box.height - 4;
        menu.style.left = Math.max(12, Math.min(anchor.right - box.width, window.innerWidth - box.width - 12)) + 'px';
        menu.style.top = Math.max(12, top) + 'px';
        const items = menu.querySelectorAll('[role=menuitem]:not(:disabled)');
        items[last ? items.length - 1 : 0]?.focus();
    }
    function enhanceActions(root) {
        $(root).find('td.actions-column').each(function () {
            if (this.querySelector('.row-actions') || !this.querySelector('button, a')) return;
            const id = 'row-actions-' + (++menuSequence);
            const label = (this.closest('tr').querySelector('input')?.value || this.closest('tr').cells[0]?.textContent || '').trim();
            const menu = $('<div>', {id, class: 'row-actions-menu', role: 'menu', hidden: true})
                .append($(this).contents().detach());
            menu.children('button, a').attr({role: 'menuitem', tabindex: -1});
            const toggle = $('<button>', {type: 'button', class: 'icon-button row-actions-toggle',
                'aria-label': 'Actions: ' + label, 'aria-haspopup': 'menu', 'aria-expanded': 'false', 'aria-controls': id}).text('⋮');
            $(this).append($('<div>', {class: 'row-actions'}).append(toggle, menu));
        });
    }
    function initAdminTable(selector) {
        const table = $(selector);
        if (!table.length || $.fn.dataTable.isDataTable(table[0])) return;
        // An early enhancement must not leave the toolbar inside another scroll box.
        if (table.parent().hasClass('table-scroll')) table.unwrap();
        return table.DataTable({
            dom: '<"admin-table-toolbar"lf><"table-scroll"t><"admin-table-bottom"ip>',
            autoWidth: false, pageLength: 25, stateSave: true,
            lengthMenu: [[10, 25, 50, -1], [10, 25, 50, 'All']],
            columnDefs: [{targets: 'actions-column', orderable: false, searchable: false}],
            stateLoadParams: function (settings, data) {
                data.order = (data.order || []).filter(order => settings.aoColumns[order[0]]?.bSortable);
                if (!data.order.length) data.order = [[0, 'asc']];
            },
            drawCallback: function () { closeActions(); enhance(document); }
        });
    }
    function addTableRows(selector, data) {
        const table = $(selector);
        const nodes = $(data);
        (table.children('tbody').first().length ? table.children('tbody').first() : table).append(nodes);
        if ($.fn.checkboxradio) nodes.find('input[type=checkbox]').checkboxradio();
        if ($.fn.selectmenu) nodes.find('select').selectmenu();
        if ($.fn.dataTable?.isDataTable(table[0])) {
            // Register DOM rows with the plugin so later draws cannot drop them.
            table.DataTable().rows.add(nodes.filter('tr').detach()).draw(false);
        }
        enhance(document);
    }
    function removeTableRow(selector) {
        const row = $(selector);
        const table = row.closest('table');
        closeActions();
        if (table.length && $.fn.dataTable?.isDataTable(table[0])) table.DataTable().row(row).remove().draw(false);
        else row.remove();
    }
    function adjustTables() {
        if ($.fn.dataTable) $.fn.dataTable.tables({visible: true, api: true}).columns.adjust();
        enhance(document);
    }
    function enhance(root) {
        enhanceActions(root);
        $(root).find('.container table.overview, .container table.overview-wi').each(function () {
            if (this.closest('.table-scroll, .ui-dialog-content') ||
                !this.getClientRects().length || this.closest('[style*="display: none"], [style*="display:none"]')) return;
            $(this).wrap($('<div>', {class: 'table-scroll', tabindex: 0, role: 'region', 'aria-label': text('table_label')}));
        });
        $(root).find('.dataTables_wrapper > .table-scroll').attr({
            tabindex: 0, role: 'region', 'aria-label': text('table_label')
        });
        $(root).find('[onclick], .add-button, .add-button-wi, .check-button, .span-link').each(function () {
            if (this.matches('button, input, select, textarea, a[href]')) return;
            if (!this.getAttribute('role')) this.setAttribute('role', 'button');
            if (!this.hasAttribute('tabindex')) this.setAttribute('tabindex', '0');
            if (!this.textContent.trim() && !this.hasAttribute('aria-label')) {
                this.setAttribute('aria-label', this.title || text(this.classList.contains('delete') ? 'delete' : this.classList.contains('edit') ? 'edit' : 'action'));
            }
        });
        // Preserve existing forms while exposing their row labels to assistive technology.
        $(root).find('input[id]:not([type=hidden]), select[id], textarea[id]').each(function () {
            let name = this.getAttribute('aria-label') || Array.from(this.labels || []).map(l => l.textContent.trim()).filter(Boolean).join(' ');
            if (!name && !this.hasAttribute('aria-labelledby')) {
                const cell = this.closest('td');
                const label = cell?.previousElementSibling || this.closest('tr')?.querySelector('td');
                const heading = this.closest('table')?.querySelector('thead th:nth-child(' + ((cell?.cellIndex || 0) + 1) + ')');
                name = (heading || label)?.textContent.trim().replace(/\s+/g, ' ').replace(/\*/g, '').trim();
                if (name && !label?.contains(this)) this.setAttribute('aria-label', name);
            }
            // jQuery UI/Select2 expose a separate combobox, not the hidden native select.
            if (name && this.tagName === 'SELECT') {
                document.getElementById(this.id + '-button')?.setAttribute('aria-label', name);
                $(this).next('.select2').find('[role=combobox]').attr('aria-label', name);
            }
        });
    }
    $(function () {
        enhance(document);
        $(document).on('click', '.row-actions-toggle', function () {
            if (openMenu?.toggle === this) closeActions(true);
            else showActions(this);
        });
        $(document).on('click', function (event) {
            if (!openMenu || event.target.closest('.row-actions-toggle')) return;
            if (!openMenu.menu.contains(event.target) || event.target.closest('[role=menuitem]:not(:disabled)')) closeActions();
        });
        $(document).on('keydown', '.row-actions', function (event) {
            const toggle = this.querySelector('.row-actions-toggle');
            if (!openMenu || openMenu.toggle !== toggle) {
                if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                    event.preventDefault(); showActions(toggle, event.key === 'ArrowUp');
                }
                return;
            }
            const items = Array.from(openMenu.menu.querySelectorAll('[role=menuitem]:not(:disabled)'));
            const index = items.indexOf(document.activeElement);
            if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeActions(true); }
            else if (event.key === 'Tab') closeActions(true);
            else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
                event.preventDefault();
                const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 :
                    (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
                items[next]?.focus();
            }
        });
        document.addEventListener('scroll', event => {
            if (openMenu && !openMenu.menu.contains(event.target)) closeActions();
        }, true);
        $(document).on('keydown', '[role=button]:not(button)', function (event) {
            if (event.target === this && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault(); this.click();
            }
        });
        // jQuery UI's fade effect restores inline styles before emitting dialogfocus.
        $(document).on('dialogopen dialogfocus', '.ui-dialog-content', function () { fitDialog(this); enhance(this); });
        $(window).on('resize', function () {
            closeActions();
            adjustTables();
            $('.ui-dialog-content').each(function () { if ($(this).dialog('isOpen')) fitDialog(this); });
        });
        $('#tabs').on('tabsactivate', adjustTables);
        let pending = false;
        new MutationObserver(records => {
            if (pending || !records.some(r => r.addedNodes.length)) return;
            pending = true;
            requestAnimationFrame(() => { pending = false; enhance(document); });
        }).observe(document.body, {childList: true, subtree: true});
    });
    return {text, requestError, notifyRequestError, widgetState, loadFragment, initNavigation, enhance, fitDialog,
        initAdminTable, addTableRows, removeTableRow};
})();
