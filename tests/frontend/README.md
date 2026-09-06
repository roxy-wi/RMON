# Frontend interaction tests

Run `npm ci --ignore-scripts` and `npm test` from this directory (Node.js 22+).
The Tests workflow runs this suite in the `frontend-tests` job.

Tests execute RMON's bundled jQuery, jQuery UI and application scripts in jsdom.
They cover navigation state and keyboard access, dialog constraints, background
request errors and retries, and status-page URL suggestions and draft preservation.
They do not replace real-browser layout checks; verify mobile and desktop layouts
when changing CSS or dialog behavior. Rendered page contracts are in `tests/ui`.
