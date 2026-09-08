# Frontend interaction tests

Run `npm ci --ignore-scripts` and `npm test` from this directory (Node.js 22+).
The Tests workflow runs this suite in the `frontend-tests` job.

Tests execute RMON's bundled jQuery, jQuery UI and application scripts in jsdom.
They cover navigation state and keyboard access, dialog constraints, background
request errors and retries, and status-page URL suggestions and draft preservation.
Check editor tests run the real form with Tagify and cover creation, editing and
cloning for HTTP, TCP, DNS, Ping, SMTP and RabbitMQ, payloads, advanced settings,
validation, locations, keyboard navigation and duplicate-submit protection.
Agent card tests cover JSON health probes, failure/recovery states, restored service
buttons and SSH action errors.
Admin table tests run the bundled DataTables plugin and cover toolbar separation,
non-sortable/non-searchable Actions, saved sorting state, three-dot menus and keyboard
navigation, viewport boundaries, AJAX row addition/removal and delegated field updates.

`fixtures/check-editor.html` is the English rendering of
`app/templates/include/smon/add_form.html` with empty notification channels and the
real input macros. Update it alongside the template; a Python UI test compares it
to Flask's actual rendering to prevent fixture drift.

They do not replace real-browser layout checks; verify mobile and desktop layouts
when changing CSS or dialog behavior. Rendered page contracts are in `tests/ui`.
