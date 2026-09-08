{{- define "apowerb.name" -}}
{{/*
Le nom du PRODUIT, fige, et non `.Chart.Name` : le paquet se nomme
`apowerb-chart` depuis qu'il ne partage plus le depot Docker Hub des images,
et ce renommage ne doit toucher aucune ressource. Sans cette constante, chaque
objet serait devenu `apowerb-chart-backend`, `apowerb-chart-secrets`... et un
`helm upgrade` aurait tout recree a cote de l'existant.
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
Le nom du Secret. Il était écrit en dur (« apowerb-secrets ») dans neuf
fichiers : avec un ``nameOverride``, tous les autres objets étaient renommés
et deux releases dans le même namespace se disputaient le MÊME Secret -- la
seconde écrasant les identifiants de la première. Par défaut la valeur ne
change pas, donc une installation existante n'a rien à faire.
*/}}
{{- define "apowerb.secretName" -}}
{{- printf "%s-secrets" (include "apowerb.name" .) -}}
{{- end -}}

{{/*
L'origine publique du front. Explicite d'abord ; sinon deduite de l'ingress,
qui route deja tout vers le front. Rien du tout si ni l'un ni l'autre : le
coeur garde ses defauts localhost, et l'ecran Configuration le dit -- ce qui
vaut mieux qu'une valeur inventee qu'aucun fournisseur OAuth n'acceptera.
*/}}
{{- define "apowerb.appPublicUrl" -}}
{{- if .Values.publicUrls.appPublicUrl -}}
{{- .Values.publicUrls.appPublicUrl | trimSuffix "/" -}}
{{- else if .Values.ingress.enabled -}}
{{- printf "%s://%s" (ternary "https" "http" .Values.ingress.tlsEnabled) .Values.ingress.host -}}
{{- end -}}
{{- end -}}

{{/*
L'origine de l'API vue de l'exterieur, celle que les webhooks composent.
Elle suit celle du front par defaut : l'ingress envoie tout au front, qui
relaie `/api`. Microsoft refuse un `notificationUrl` en http, donc un ingress
sans TLS produira bien une URL, et Graph la rejettera -- explicitement, ce qui
est encore la meilleure des deux facons d'apprendre qu'il manque le TLS.
*/}}
{{- define "apowerb.publicBaseUrl" -}}
{{- if .Values.publicUrls.publicBaseUrl -}}
{{- .Values.publicUrls.publicBaseUrl | trimSuffix "/" -}}
{{- else -}}
{{- include "apowerb.appPublicUrl" . -}}
{{- end -}}
{{- end -}}
