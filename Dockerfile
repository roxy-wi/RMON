FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv python3-ldap python3-pkg-resources \
      ca-certificates openssl openssh-client sshpass git util-linux \
      iputils-ping iputils-tracepath dnsutils netcat-openbsd nmap \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv --system-site-packages /opt/rmon-venv

ENV PATH="/opt/rmon-venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    RMON_CONTAINER=1 RMON_PROXY_MODE=1 RMON_PROMETHEUS_MULTIPROC_DIR=/tmp/rmon-prometheus \
    ANSIBLE_HOME=/tmp/ansible-local ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote

WORKDIR /var/www/rmon
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/scripts/ansible/requirements.yml /tmp/ansible-requirements.yml
RUN ANSIBLE_HOME=/tmp/ansible-build ANSIBLE_LOCAL_TEMP=/tmp/ansible-build ansible-galaxy collection install \
      -r /tmp/ansible-requirements.yml -p /usr/share/ansible/collections
COPY app ./app
COPY config_other ./config_other
COPY container ./container
COPY app.wsgi gunicorn.conf.py scheduler_runner.py operations_runner.py runtime_health.py rotate_credential_secret.py favicon.ico LICENSE NOTICE LICENSING.md ./
RUN install -d /etc/rmon /var/lib/rmon /var/log/rmon \
    && install -d -o www-data -g www-data \
       app/scripts/ansible/inventory app/scripts/ansible/artifacts app/scripts/ansible/env /tmp/ansible-local \
    && chmod -R go-w /var/www/rmon

EXPOSE 8080
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["/opt/rmon-venv/bin/python", "-m", "container.runtime", "healthcheck"]
ENTRYPOINT ["/opt/rmon-venv/bin/python", "-m", "container.runtime"]
CMD ["serve"]
