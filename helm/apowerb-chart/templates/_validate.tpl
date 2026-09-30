{{/*
What must be refused at install time rather than discovered as a
CrashLoopBackOff.

th2pulse needs its two tokens to start -- that is its rule, not ours: the
compose file already states it with `${...:?}`. Without this guard,
`helm install` succeeds, the pod restarts in a loop, and the Logging screen
says "store unreachable" with nothing naming the cause.
*/}}
{{- define "apowerb.validate" -}}
{{- if not .Values.postgres.password }}
{{- fail "postgres.password is empty: PostgreSQL will not initialise without it, and the backend could not connect. Set it (--set postgres.password=\"$(openssl rand -hex 16)\"). It has no default on purpose: a password shipped in a public repository is not a password." -}}
{{- end }}
{{- if .Values.th2pulse.enabled }}
{{- if not .Values.th2pulse.ingestToken }}
{{- fail "th2pulse.ingestToken is empty: th2pulse refuses to start without it. Set it (openssl rand -hex 32) or set th2pulse.enabled=false." -}}
{{- end }}
{{- if not .Values.th2pulse.queryToken }}
{{- fail "th2pulse.queryToken is empty: th2pulse refuses to start without it, and the interface needs it to read the logs. Set it (openssl rand -hex 32) or set th2pulse.enabled=false." -}}
{{- end }}
{{- end }}
{{- if and .Values.otelCollector.enabled (not .Values.th2pulse.enabled) }}
{{- fail "otelCollector.enabled without th2pulse.enabled: the collector would have nowhere to push. Enable th2pulse, or disable the collector." -}}
{{- end }}
{{- if and .Values.th2etl.enabled .Values.th2etl.seed.enabled (lt (int .Values.th2etl.seed.attempts) 1) }}
{{- fail "th2etl.seed.attempts must be at least 1." -}}
{{- end }}
{{- if not .Values.backend.env.encryptKey }}
{{- fail "backend.env.encryptKey is empty: the backend REFUSES to start (integration OAuth tokens are encrypted at rest with this Fernet key; without it, the boot ends in CrashLoopBackOff, not a degraded mode). Set it (--set backend.env.encryptKey=\"$(openssl rand -base64 32)\"). It has no default on purpose: a key shipped in a public repository is not a key." -}}
{{- end }}
{{- if and (gt (int .Values.replicaCount) 1) .Values.persistence.enabled (has "ReadWriteOnce" .Values.persistence.accessModes) }}
{{- fail "replicaCount > 1 with a ReadWriteOnce volume: the PVC mounts on a single node, so the second replica stays stuck on Multi-Attach. Keep replicaCount=1, switch persistence.accessModes to ReadWriteMany (with a compatible storage class), or set persistence.enabled=false." -}}
{{- end }}
{{- if .Values.th2forecast.enabled }}
{{- if not .Values.image.th2forecast.tag }}
{{- fail "th2forecast.enabled=true with an empty image.th2forecast.tag: set the tag of a published apowerb/th2forecast-py release (or of an image you built yourself), or set th2forecast.enabled=false." -}}
{{- end }}
{{- if not .Values.th2forecast.apiToken }}
{{- fail "th2forecast.enabled=true without th2forecast.apiToken: set it (openssl rand -hex 32) or set th2forecast.enabled=false. Without it the engine would accept any caller reaching the cluster network." -}}
{{- end }}
{{- end }}
{{- end -}}
