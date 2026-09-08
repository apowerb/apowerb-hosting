{{- define "apowerb.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
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

{{- define "apowerb.otel.fullname" -}}
{{- printf "%s-otel-collector" (include "apowerb.name" .) -}}
{{- end -}}

{{- define "apowerb.data.fullname" -}}
{{- printf "%s-data" (include "apowerb.name" .) -}}
{{- end -}}

{{/*
L'environnement de th2etl, partagé mot pour mot entre le service et le Job de
seed. Les deux parlent à la même base avec la même clé : les dupliquer, c'est
prendre le risque qu'un seed écrive ailleurs que là où l'orchestrateur lit.
*/}}
{{- define "apowerb.th2etl.env" -}}
- name: DATABASE_HOST
  value: {{ include "apowerb.postgres.fullname" . }}
- name: DATABASE_PORT
  value: "5432"
- name: DATABASE_NAME
  valueFrom:
    secretKeyRef:
      name: apowerb-secrets
      key: DB_NAME
- name: DATABASE_USER
  valueFrom:
    secretKeyRef:
      name: apowerb-secrets
      key: DB_USER
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: apowerb-secrets
      key: DB_PASSWORD
- name: API_KEY
  valueFrom:
    secretKeyRef:
      name: apowerb-secrets
      key: TH2ETL_API_KEY
- name: ADK_BASE_URL
  value: "http://{{ include "apowerb.backend.fullname" . }}:{{ .Values.service.backend.port }}"
- name: ENCRYPT_KEY
  valueFrom:
    secretKeyRef:
      name: apowerb-secrets
      key: ENCRYPT_KEY
{{- end -}}
