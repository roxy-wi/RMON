/* Event examples and editor validation share the public version 1 contract. */
window.RmonClientContract = (() => {
    'use strict';
    const standard = ['environment', 'platform', 'app_version', 'country', 'network_type'];
    const identifier = /^[a-z][a-z0-9_.]{0,63}$/;
    const safe = Number.MAX_SAFE_INTEGER;
    function fail() { throw new Error('invalid_definition'); }
    function number(value) {
        if (value === '' || value === null || value === undefined) return null;
        const result = Number(value);
        if (!Number.isFinite(result) || Math.abs(result) > safe) fail();
        return result;
    }
    function validate(definition) {
        if (!definition.has_outcome && !definition.duration && !Object.keys(definition.metrics).length) fail();
        if (Object.keys(definition.metrics).length > 20 || Object.keys(definition.context).length > 11) fail();
        for (const fields of [definition.metrics, definition.context]) {
            for (const name of Object.keys(fields)) {
                if (!identifier.test(name) || standard.includes(name) || name === 'duration_ms') fail();
            }
        }
        const metrics = {...definition.metrics};
        if (definition.duration) {
            if (definition.duration.minimum === null || definition.duration.minimum < 0) fail();
            metrics.duration_ms = definition.duration;
        }
        for (const metric of Object.values(metrics)) {
            if (!metric.label.trim() || !metric.unit.trim()) fail();
            const min = metric.minimum ?? -safe, max = metric.maximum ?? safe;
            if (min > max || metric.type === 'integer' && Math.ceil(min) > Math.floor(max)) fail();
        }
        if (definition.primary_metric && !Object.hasOwn(metrics, definition.primary_metric)) fail();
        let filterable = 0;
        for (const field of Object.values(definition.context)) {
            if (!field.label.trim()) fail();
            if (field.filterable) filterable++;
            if (field.type === 'enum' && (!field.values.length || field.values.length > 50 ||
                field.values.some(value => !value || value.length > 128) || new Set(field.values).size !== field.values.length)) fail();
        }
        if (filterable > 2) fail();
        return definition;
    }
    function measurement(metric, fallback) {
        let min = metric.minimum ?? -safe, max = metric.maximum ?? safe;
        if (metric.type === 'integer') { min = Math.ceil(min); max = Math.floor(max); }
        return Math.max(min, Math.min(max, fallback));
    }
    function example(definition, code, version, environment = 'production', platform = 'browser') {
        const value = {event_id: window.crypto?.randomUUID?.() || '00000000-0000-4000-8000-000000000001',
            check: code, definition_version: version, observed_at: new Date().toISOString()};
        if (definition.has_outcome) value.status = 'ok';
        if (definition.duration) value.duration_ms = measurement(definition.duration, 120);
        value.metrics = Object.fromEntries(Object.entries(definition.metrics).map(([name, metric]) => [name, measurement(metric, 1)]));
        value.context = {environment, platform};
        for (const [name, field] of Object.entries(definition.context)) {
            value.context[name] = field.type === 'boolean' ? false : field.type === 'enum' ? field.values[0] : 'example';
        }
        return value;
    }
    function endpoint(value) {
        try {
            const url = new URL(value);
            return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password && !url.hash;
        } catch (_) { return false; }
    }
    function snippet(format, url, key, event) {
        const batch = {schema_version: 1, project_key: key, events: [event]};
        if (format === 'json') return JSON.stringify(batch, null, 2);
        // Single-quote shell literals, including arbitrary custom context values.
        const quote = value => "'" + value.replaceAll("'", "'\"'\"'") + "'";
        if (format === 'curl') return `curl --fail-with-body --connect-timeout 5 --max-time 10 \\\n  --retry 3 --retry-delay 2 --retry-max-time 60 \\\n  -H 'Content-Type: application/json' \\\n  --data-raw ${quote(JSON.stringify(batch))} \\\n  ${quote(url)}`;
        return `// Replace example values with the measured operation's values.
const event = ${JSON.stringify(event, null, 2)};
event.event_id = crypto.randomUUID();
event.observed_at = new Date().toISOString();
// The source page excludes query parameters and fragments.
const pageUrl = location.origin + location.pathname;
if (pageUrl.length <= 2048) event.page_url = pageUrl;
const body = JSON.stringify({schema_version: 1, project_key: ${JSON.stringify(key)}, events: [event]});

async function sendObservation() {
  for (let attempt = 0; attempt < 4; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    let retryAfter = 0;
    try {
      const response = await fetch(${JSON.stringify(url)}, {
        method: 'POST', credentials: 'omit', referrerPolicy: 'no-referrer',
        headers: {'Content-Type': 'application/json'},
        body, signal: controller.signal
      });
      if (response.status === 200 || response.status === 202) return {accepted: true};
      if (response.status !== 429 && response.status < 500) return {accepted: false, status: response.status};
      const seconds = Number(response.headers.get('Retry-After'));
      if (Number.isFinite(seconds)) retryAfter = Math.min(30000, Math.max(0, seconds * 1000));
    } catch (error) {
      if (!(error instanceof TypeError) && error.name !== 'AbortError') throw error;
      // Network failures retry the same body and event_id.
    } finally {
      clearTimeout(timeout);
    }
    if (attempt < 3) await new Promise(resolve => setTimeout(resolve,
      Math.max(retryAfter, 1000 * 2 ** attempt) + Math.random() * 500));
  }
  return {accepted: false, reason: 'retry_limit'};
}
// Delivery runs independently of the measured operation.
sendObservation().then(result => console.info('RMON delivery:', result))
  .catch(error => console.warn('RMON delivery failed:', error.name));`;
    }
    return {standard, identifier, number, validate, example, endpoint, snippet};
})();
