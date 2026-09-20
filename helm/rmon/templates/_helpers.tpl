{{- define "rmon.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 52 | trimSuffix "-" -}}
{{- end -}}
{{- define "rmon.placement" -}}
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}
{{- define "rmon.colocate" -}}
{{- if has "ReadWriteOnce" .Values.persistence.accessModes }}
affinity:
  podAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            {{- include "rmon.selector" . | nindent 12 }}
          matchExpressions:
            - key: app.kubernetes.io/component
              operator: In
              values: [web, scheduler, operations, server]
        topologyKey: kubernetes.io/hostname
{{- end }}
{{- end -}}
{{- define "rmon.fullname" -}}
{{- default (printf "%s-%s" .Release.Name (include "rmon.name" .)) .Values.fullnameOverride | trunc 52 | trimSuffix "-" -}}
{{- end -}}
{{- define "rmon.selector" -}}
app.kubernetes.io/name: {{ include "rmon.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
{{- define "rmon.labels" -}}
{{ include "rmon.selector" . }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | quote }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
{{- define "rmon.image" -}}
{{- if .image.digest -}}
{{ printf "%s@%s" .image.repository .image.digest }}
{{- else -}}
{{ printf "%s:%s" .image.repository (default .version .image.tag) }}
{{- end -}}
{{- end -}}
{{- define "rmon.configSecret" -}}
{{ default (printf "%s-config" (include "rmon.fullname" .)) .Values.existingConfigSecret }}
{{- end -}}
{{- define "rmon.claim" -}}
{{ default (printf "%s-data" (include "rmon.fullname" .)) .Values.persistence.existingClaim }}
{{- end -}}
{{- define "rmon.account" -}}
{{- if .Values.serviceAccount.create -}}
{{ default (include "rmon.fullname" .) .Values.serviceAccount.name }}
{{- else -}}
{{ default "default" .Values.serviceAccount.name }}
{{- end -}}
{{- end -}}
{{- define "rmon.config" -}}
{{- range $section, $options := .Values.config }}
[{{ $section }}]
{{ range $key, $value := $options -}}
{{ $key }} = {{ if kindIs "float64" $value }}{{ printf "%.0f" $value }}{{ else }}{{ $value }}{{ end }}
{{ end }}
{{- end -}}
{{- end -}}
{{- define "rmon.validate" -}}
{{- if and .Values.migration.enabled (not .Values.maintenance) -}}{{ fail "Enable maintenance and stop all RMON pods before enabling migration" }}{{- end -}}
{{- $_ := required "Set publicURL to the RMON address reachable by users and agents" .Values.publicURL -}}
{{- if ne (int .Values.web.replicaCount) 1 -}}{{ fail "This chart requires web.replicaCount=1" }}{{- end -}}
{{- if not .Values.existingConfigSecret -}}
{{- $key := required "Set config.main.secret_phrase or existingConfigSecret; preserve existing application keys" .Values.config.main.secret_phrase -}}
{{- if not (regexMatch "^[A-Za-z0-9_-]{43}=$" $key) -}}{{ fail "config.main.secret_phrase must be a Fernet key" }}{{- end -}}
{{- if and (eq (int .Values.config.mysql.enable) 1) (eq (int .Values.config.pgsql.enable) 1) -}}{{ fail "Enable only one database backend" }}{{- end -}}
{{- if and (eq (int .Values.config.mysql.enable) 0) (eq (int .Values.config.pgsql.enable) 0) (has "ReadWriteMany" .Values.persistence.accessModes) -}}{{ fail "SQLite requires ReadWriteOnce storage; use an external database before selecting ReadWriteMany" }}{{- end -}}
{{- if or (ne .Values.config.main.lib_path "/var/lib/rmon") (ne .Values.config.main.log_path "/var/log/rmon") -}}{{ fail "Keep config.main.lib_path=/var/lib/rmon and log_path=/var/log/rmon for the chart's persistent volumes" }}{{- end -}}
{{- end -}}
{{- if .Values.bootstrap.enabled -}}{{- $_ := required "Set bootstrap.existingSecret with the initial administrator password" .Values.bootstrap.existingSecret -}}{{- end -}}
{{- if or .Values.server.enabled .Values.server.externalURL -}}
{{- $_ := required "Set server.existingTokenSecret with the result server access token" .Values.server.existingTokenSecret -}}
{{- end -}}
{{- if and .Values.server.enabled (ne .Values.server.transport "http") -}}
{{- $_ := required "Set server.tls.existingServerSecret for HTTPS/mTLS" .Values.server.tls.existingServerSecret -}}
{{- $_ = required "Set server.tls.existingClientSecret for HTTPS/mTLS" .Values.server.tls.existingClientSecret -}}
{{- end -}}
{{- if .Values.ingress.enabled -}}{{- $_ := required "Set ingress.host" .Values.ingress.host -}}{{- end -}}
{{- end -}}
{{- define "rmon.env" -}}
- name: RMON_CONFIG_FILE
  value: /etc/rmon/rmon.cfg
- name: RMON_DB_PATH
  value: /var/lib/rmon/rmon.db
- name: RMON_PUBLIC_URL
  value: {{ .Values.publicURL | quote }}
- name: RMON_AGENT_CONTROL_URL
  value: {{ default .Values.publicURL .Values.agentControlURL | quote }}
- name: RMON_COOKIE_SECURE
  value: {{ ternary "1" "0" .Values.cookieSecure | quote }}
- name: RMON_AGENT_IMAGE
  value: {{ .Values.agentImage | quote }}
{{- if or .Values.server.enabled .Values.server.externalURL }}
- name: RMON_SERVER_INTERNAL_URL
  value: {{ if .Values.server.enabled }}{{ printf "%s://%s-server:%v" (ternary "http" "https" (eq .Values.server.transport "http")) (include "rmon.fullname" .) .Values.server.service.port | quote }}{{ else }}{{ .Values.server.externalURL | quote }}{{ end }}
- name: RMON_SERVER_INTERNAL_TOKEN_FILE
  value: /run/rmon-token/token
{{- end }}
{{- if and .Values.server.enabled (ne .Values.server.transport "http") }}
- name: RMON_SERVER_CA_FILE
  value: /run/rmon-client-tls/ca.crt
{{- if eq .Values.server.transport "mtls" }}
- name: RMON_SERVER_CLIENT_CERT_FILE
  value: /run/rmon-client-tls/tls.crt
- name: RMON_SERVER_CLIENT_KEY_FILE
  value: /run/rmon-client-tls/tls.key
{{- end }}
{{- end }}
{{- with .Values.extraEnv }}
{{ toYaml . }}
{{- end }}
{{- end -}}
{{- define "rmon.mounts" -}}
- name: config
  mountPath: /etc/rmon/rmon.cfg
  subPath: rmon.cfg
  readOnly: true
- name: data
  mountPath: /var/lib/rmon
- name: data
  mountPath: /var/log/rmon
  subPath: logs
{{- if or .Values.server.enabled .Values.server.externalURL }}
- name: server-token
  mountPath: /run/rmon-token
  readOnly: true
{{- end }}
{{- if and .Values.server.enabled (ne .Values.server.transport "http") }}
- name: client-tls
  mountPath: /run/rmon-client-tls
  readOnly: true
{{- end }}
{{- with .Values.extraVolumeMounts }}
{{ toYaml . }}
{{- end }}
{{- end -}}
{{- define "rmon.volumes" -}}
- name: config
  secret:
    secretName: {{ include "rmon.configSecret" . }}
    defaultMode: 0440
- name: data
  persistentVolumeClaim:
    claimName: {{ include "rmon.claim" . }}
{{- if or .Values.server.enabled .Values.server.externalURL }}
- name: server-token
  secret:
    secretName: {{ .Values.server.existingTokenSecret }}
    defaultMode: 0440
    items:
      - key: {{ .Values.server.tokenKey }}
        path: token
{{- end }}
{{- if and .Values.server.enabled (ne .Values.server.transport "http") }}
- name: client-tls
  secret:
    secretName: {{ .Values.server.tls.existingClientSecret }}
    defaultMode: 0440
{{- end }}
{{- with .Values.extraVolumes }}
{{ toYaml . }}
{{- end }}
{{- end -}}
