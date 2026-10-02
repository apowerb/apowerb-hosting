{{- define "apowerb.name" -}}
{{/*
The PRODUCT name, fixed, and not `.Chart.Name`: the package has been called
`apowerb-chart` since it stopped sharing the Docker Hub repository with the
images, and that rename must not touch any resource. Without this constant,
every object would have become `apowerb-chart-backend`, `apowerb-chart-secrets`...
and a `helm upgrade` would have recreated everything alongside the existing
objects.
*/}}
{{- default "apowerb" .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "apowerb.namespace" -}}
{{- if .Values.namespaceOverride -}}
{{- .Values.namespaceOverride -}}
{{- else -}}
{{- .Release.Namespace -}}
{{- end -}}
{{- end -}}

{{- define "apowerb.backend.fullname" -}}
{{- printf "%s-backend" (include "apowerb.name" .) -}}
{{- end -}}

{{- define "apowerb.frontend.fullname" -}}
{{- printf "%s-frontend" (include "apowerb.name" .) -}}
{{- end -}}

{{- define "apowerb.postgres.fullname" -}}
{{- printf "%s-postgres" (include "apowerb.name" .) -}}
{{- end -}}

{{- define "apowerb.th2etl.fullname" -}}
{{- printf "%s-th2etl" (include "apowerb.name" .) -}}
{{- end -}}

{{- define "apowerb.th2pulse.fullname" -}}
{{- printf "%s-th2pulse" (include "apowerb.name" .) -}}
{{- end -}}

{{- define "apowerb.th2forecast.fullname" -}}
{{- printf "%s-th2forecast" (include "apowerb.name" .) -}}
{{- end -}}

{{- define "apowerb.otel.fullname" -}}
{{- printf "%s-otel-collector" (include "apowerb.name" .) -}}
{{- end -}}

{{- define "apowerb.data.fullname" -}}
{{- printf "%s-data" (include "apowerb.name" .) -}}
{{- end -}}

{{/*
The th2etl environment, shared word for word between the service and the seed
Job. Both talk to the same database with the same key: duplicating it risks a
seed writing somewhere other than where the orchestrator reads.
*/}}
{{- define "apowerb.th2etl.env" -}}
- name: DATABASE_HOST
  value: {{ include "apowerb.postgres.fullname" . }}
- name: DATABASE_PORT
  value: "5432"
- name: DATABASE_NAME
  valueFrom:
    secretKeyRef:
      name: {{ include "apowerb.secretName" . }}
      key: DB_NAME
- name: DATABASE_USER
  valueFrom:
    secretKeyRef:
      name: {{ include "apowerb.secretName" . }}
      key: DB_USER
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "apowerb.secretName" . }}
      key: DB_PASSWORD
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "apowerb.secretName" . }}
      key: TH2ETL_API_KEY
- name: ADK_BASE_URL
  value: "http://{{ include "apowerb.backend.fullname" . }}:{{ .Values.service.backend.port }}"
- name: ENCRYPT_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "apowerb.secretName" . }}
      key: ENCRYPT_KEY
{{- end -}}

{{/*
The th2forecast engine environment. TH2FORECAST_API_TOKEN only exists in the
Secret when a token is set (see secret.yaml) -- `optional: true` lets the pod
start, but an engine without a token accepts any caller on the cluster
network, which _validate.tpl refuses as soon as enabled=true.
*/}}
{{/*
Engine behind image.th2forecast: th2forecast.implementation, or deduced from
the repository name (apowerb/th2forecast-py is the Python engine).
*/}}
{{- define "apowerb.th2forecast.implementation" -}}
{{- if .Values.th2forecast.implementation -}}
{{- .Values.th2forecast.implementation -}}
{{- else if hasSuffix "-py" (toString .Values.image.th2forecast.repository) -}}
python
{{- else -}}
r
{{- end -}}
{{- end }}

{{- define "apowerb.th2forecast.env" -}}
- name: TH2FORECAST_API_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ include "apowerb.secretName" . }}
      key: TH2FORECAST_API_TOKEN
      optional: true
{{- if .Values.th2forecast.engine.workers }}
- name: TH2FORECAST_WORKERS
  value: {{ .Values.th2forecast.engine.workers | quote }}
{{- end }}
{{- if .Values.th2forecast.engine.preload }}
- name: TH2FORECAST_PRELOAD
  value: {{ .Values.th2forecast.engine.preload | quote }}
{{- end }}
{{- if .Values.th2forecast.engine.maxRows }}
- name: TH2FORECAST_MAX_ROWS
  value: {{ .Values.th2forecast.engine.maxRows | quote }}
{{- end }}
{{- if .Values.th2forecast.engine.maxSeries }}
- name: TH2FORECAST_MAX_SERIES
  value: {{ .Values.th2forecast.engine.maxSeries | quote }}
{{- end }}
{{- if .Values.th2forecast.engine.maxHorizon }}
- name: TH2FORECAST_MAX_HORIZON
  value: {{ .Values.th2forecast.engine.maxHorizon | quote }}
{{- end }}
{{- if .Values.th2forecast.engine.sfJobs }}
- name: TH2FORECAST_SF_JOBS
  value: {{ .Values.th2forecast.engine.sfJobs | quote }}
{{- end }}
{{- if .Values.th2forecast.engine.torchThreads }}
- name: TH2FORECAST_TORCH_THREADS
  value: {{ .Values.th2forecast.engine.torchThreads | quote }}
{{- end }}
{{- end -}}

{{/*
The Secret name. It used to be hard-coded ("apowerb-secrets") in nine files:
with a ``nameOverride``, all the other objects were renamed and two releases in
the same namespace fought over the SAME Secret -- the second overwriting the
first one's credentials. By default the value does not change, so an existing
installation has nothing to do.
*/}}
{{- define "apowerb.secretName" -}}
{{- printf "%s-secrets" (include "apowerb.name" .) -}}
{{- end -}}

{{/*
The public origin of the front end. Explicit value first; otherwise deduced
from the ingress, which already routes everything to the front end. Nothing at
all if neither is set: the core keeps its localhost defaults, and the
Configuration screen says so -- which beats an invented value that no OAuth
provider will accept.
*/}}
{{- define "apowerb.appPublicUrl" -}}
{{- if .Values.publicUrls.appPublicUrl -}}
{{- .Values.publicUrls.appPublicUrl | trimSuffix "/" -}}
{{- else if .Values.ingress.enabled -}}
{{- printf "%s://%s" (ternary "https" "http" .Values.ingress.tlsEnabled) .Values.ingress.host -}}
{{- end -}}
{{- end -}}

{{/*
The API origin as seen from outside, the one the webhooks build on. It
follows the front end's origin by default: the ingress sends everything to the
front end, which relays `/api`. Microsoft rejects an http `notificationUrl`, so
an ingress without TLS will still produce a URL, and Graph will reject it --
explicitly, which is still the better of the two ways to find out TLS is
missing.
*/}}
{{- define "apowerb.publicBaseUrl" -}}
{{- if .Values.publicUrls.publicBaseUrl -}}
{{- .Values.publicUrls.publicBaseUrl | trimSuffix "/" -}}
{{- else -}}
{{- include "apowerb.appPublicUrl" . -}}
{{- end -}}
{{- end -}}

{{/*
Shared initContainer: waits until Postgres accepts connections before starting
a service that connects to it at boot. Without it, th2etl and th2pulse exit
with "connection refused" and restart 2-3 times while Postgres comes up -- a
transient but noisy CrashLoop. It reuses the chart's Postgres image (already
pulled) for `pg_isready`, so no extra image is needed.
*/}}
{{- define "apowerb.waitForPostgres" -}}
- name: wait-for-postgres
  image: "{{ .Values.image.postgres.repository }}:{{ .Values.image.postgres.tag }}"
  imagePullPolicy: {{ .Values.image.postgres.pullPolicy }}
  command:
    - sh
    - -c
    - |
      until pg_isready -h {{ include "apowerb.postgres.fullname" . }} -p {{ .Values.service.postgres.port }}; do
        echo "en attente de Postgres..."; sleep 2;
      done
  resources:
    requests:
      cpu: 10m
      memory: 32Mi
    limits:
      cpu: 50m
      memory: 64Mi
{{- end -}}
