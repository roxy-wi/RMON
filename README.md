# RMON

RMON monitors service availability from multiple locations, records results and alerts your team. It supports HTTP(S), TCP, Ping, DNS, SMTP and RabbitMQ checks, notification channels and public status pages.

![RMON Dashboard](https://rmon.io/static/images/docs/dashboard.jpg)

## Get started

Follow the [installation guide](https://rmon.io/installation) for native installations or Docker. For a new Docker deployment, prepare `compose.yaml` and `.env` as described in the [Docker guide](https://rmon.io/installation#docker), make the selected images available on the host, then run:

```sh
docker compose config --quiet
docker compose run --rm --no-deps web init
docker compose up -d --no-build
```

Choose the administrator password when prompted and open your RMON HTTPS address. For an existing installation, follow the [migration guide](https://rmon.io/installation#docker-existing-rmon-installation) and preserve the database and application keys; do not run `init`.

Add [hosts and SSH credentials](https://rmon.io/howto/setup), [install agents](https://rmon.io/howto/manage-agents), then [create a check](https://rmon.io/howto/assign-checks). The website covers [HTTPS and mTLS settings](https://rmon.io/settings#agent-connections), [notifications](https://rmon.io/howto/notifications), [status pages](https://rmon.io/howto/status-pages) and [updates and backups](https://rmon.io/update-guide).

For Kubernetes, prepare the Secrets, storage and `values.yaml` using the [Kubernetes guide](https://rmon.io/installation#kubernetes), then install:

```sh
helm upgrade --install rmon oci://ghcr.io/roxy-wi/rmon-charts/rmon \
  --version 1.4.0 --namespace rmon --create-namespace \
  --values values.yaml --wait --timeout 10m
```

## Plans and support

RMON is a commercial product. See [plans](https://rmon.io/pricing), [documentation](https://rmon.io/howto) and [support contacts](https://rmon.io/contacts).

## License

Starting with the 1.4.0 release line, RMON is source-available under the
[Elastic License 2.0](LICENSE) (`Elastic-2.0`). Self-hosted and internal use is
available subject to ELv2. Offering RMON, or a service exposing a substantial
set of its functionality, to third parties as a hosted or managed service
requires rights permitted by ELv2 or a separate commercial license.

See [LICENSING.md](LICENSING.md) for usage examples and historical release
terms, and [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) for commercial
licensing. Contributions are subject to [CLA.md](CLA.md); see
[CONTRIBUTING.md](CONTRIBUTING.md) for the signing process.

Historical versions and copies retain the terms that accompanied them.
Third-party dependencies and vendored components retain their own licenses.
