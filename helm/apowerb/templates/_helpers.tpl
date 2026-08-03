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
