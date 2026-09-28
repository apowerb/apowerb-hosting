{{/*
Ce qui doit être refusé à l'installation plutôt que découvert en
CrashLoopBackOff.

th2pulse exige ses deux jetons pour démarrer -- c'est sa règle, pas la nôtre :
le compose l'écrit déjà avec `${...:?}`. Sans ce garde, `helm install` réussit,
le pod redémarre en boucle, et l'écran Journaux dit « magasin injoignable »
sans que rien ne nomme la cause.
*/}}
{{- define "apowerb.validate" -}}
{{- if not .Values.postgres.password }}
{{- fail "postgres.password est vide : Postgres refuse de s'initialiser sans lui, et le backend ne pourrait pas s'y connecter. Posez-le (--set postgres.password=\"$(openssl rand -hex 16)\"). Il n'a pas de valeur par défaut à dessein : un mot de passe livré dans un dépôt public n'en est plus un." -}}
{{- end }}
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
{{- if .Values.th2forecast.enabled }}
{{- if not .Values.image.th2forecast.tag }}
{{- fail "th2forecast.enabled=true sans image.th2forecast.tag : aucune image apowerb/th2forecast-py n'est publiee a ce jour, un defaut inventerait un numero de version qui n'existe pas. Posez le tag d'une image que vous avez publiee ou construite vous-meme, ou remettez th2forecast.enabled=false." -}}
{{- end }}
{{- if not .Values.th2forecast.apiToken }}
{{- fail "th2forecast.enabled=true sans th2forecast.apiToken : posez-le (openssl rand -hex 32) ou mettez th2forecast.enabled=false. Sans lui le moteur accepterait tout appelant joignant le reseau du cluster." -}}
{{- end }}
{{- end }}
{{- end -}}
