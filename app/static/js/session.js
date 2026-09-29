/* Keep browser sessions alive for user interaction, never for background polling. */
(() => {
    'use strict';
    const script = document.getElementById('rmon-session');
    if (!script || script.dataset.initialized) return;
    script.dataset.initialized = 'true';
    const recentActivity = 60000;
    let lastActivity = 0, nextAttempt = 0, timer = null, pending = false;
    let controller = null, suspended = false, stopped = false, notified = false;
    const csrf = () => window.Cookies.get('csrf_access_token');

    function stop() {
        stopped = true;
        clearTimeout(timer); timer = null;
        controller?.abort();
    }
    function schedule() {
        if (timer || controller || stopped || suspended || document.hidden || !pending) return;
        timer = setTimeout(() => {timer = null; renew();}, Math.max(0, nextAttempt - Date.now()));
    }
    async function renew() {
        if (controller || stopped || suspended || document.hidden || !pending) return;
        if (Date.now() - lastActivity > recentActivity) {pending = false; return;}
        if (Date.now() < nextAttempt) {schedule(); return;}
        const token = csrf();
        if (!token) {stop(); return;}
        const request = new AbortController();
        controller = request;
        const timeout = setTimeout(() => request.abort(), 10000);
        pending = false;
        try {
            const response = await fetch(script.dataset.refreshUrl, {
                method: 'POST', credentials: 'same-origin', cache: 'no-store',
                headers: {'X-CSRF-TOKEN': token, Accept: 'application/json'}, signal: request.signal
            });
            if (!response.ok) {
                // Another tab can rotate CSRF during a group switch. Retry once
                // with the new cookie, without replaying any user's mutation.
                if (response.status === 401 && csrf() && csrf() !== token) {
                    pending = true; nextAttempt = Date.now() + 1000; return;
                }
                if ([401, 403, 422].includes(response.status)) stop();
                throw response;
            }
            const result = await response.json();
            if (!Number.isFinite(result.refresh_after) || result.refresh_after <= 0) throw new Error('Invalid refresh interval');
            nextAttempt = Date.now() + Math.min(300, result.refresh_after) * 1000;
            notified = false;
        } catch (error) {
            if (suspended || stopped && error.name === 'AbortError') return;
            nextAttempt = Date.now() + 15000;
            pending = !stopped;
            if (!notified) {
                window.RmonUI.notifyRequestError({status: error.status || 0});
                notified = true;
            }
        } finally {
            clearTimeout(timeout);
            controller = null;
            schedule();
        }
    }
    function activate() {
        if (stopped || suspended || document.hidden) return;
        lastActivity = Date.now(); pending = true;
        renew();
    }
    function interaction(event) {
        const link = event.target.closest?.('a[href]');
        const leaving = event.type === 'pointerdown' || event.type === 'touchstart' || event.type === 'keydown' && event.key === 'Enter';
        if (leaving && link && new URL(link.href, location.href).pathname === '/logout') {stop(); return;}
        if (event.isTrusted && Date.now() - lastActivity >= 1000) activate();
    }
    for (const name of ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart']) {
        document.addEventListener(name, interaction, {capture: true, passive: true});
    }
    document.addEventListener('click', event => {
        const link = event.target.closest?.('a[href]');
        if (link && new URL(link.href, location.href).pathname === '/logout') stop();
    }, true);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {clearTimeout(timer); timer = null;}
        else activate();
    });
    window.addEventListener('pagehide', () => {
        suspended = true; pending = false;
        clearTimeout(timer); timer = null; controller?.abort();
    });
    window.addEventListener('pageshow', event => {
        if (event.persisted) {suspended = false; activate();}
    });
    activate();
})();
