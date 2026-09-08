{{/*
Ce qui doit être refusé à l'installation plutôt que découvert en
CrashLoopBackOff.

th2pulse exige ses deux jetons pour démarrer -- c'est sa règle, pas la nôtre :
le compose l'écrit déjà avec `${...:?}`. Sans ce garde, `helm install` réussit,
le pod redémarre en boucle, et l'écran Journaux dit « magasin injoignable »
sans que rien ne nomme la cause.
*/}}
{{- define "apowerb.validate" -}}
{{- if .Values.th2pulse.enabled }}
{{- if not .Values.th2pulse.ingestToken }}
{{- fail "th2pulse.ingestToken est vide : th2pulse refuse de démarrer sans lui. Posez-le (openssl rand -hex 32) ou mettez th2pulse.enabled=false." -}}
{{- end }}
{{- if not .Values.th2pulse.queryToken }}
{{- fail "th2pulse.queryToken est vide : th2pulse refuse de démarrer sans lui, et l'interface en a besoin pour lire les journaux. Posez-le (openssl rand -hex 32) ou mettez th2pulse.enabled=false." -}}
{{- end }}
{{- end }}
{{- if and .Values.otelCollector.enabled (not .Values.th2pulse.enabled) }}
{{- fail "otelCollector.enabled sans th2pulse.enabled : le collecteur n'aurait nulle part où pousser. Activez th2pulse, ou désactivez le collecteur." -}}
{{- end }}
{{- if and .Values.th2etl.enabled .Values.th2etl.seed.enabled (lt (int .Values.th2etl.seed.attempts) 1) }}
{{- fail "th2etl.seed.attempts doit valoir au moins 1." -}}
{{- end }}
{{- end -}}
