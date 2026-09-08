# Kubernetes

Le déploiement se fait par le **chart Helm** — [`helm/apowerb-chart`](../helm/apowerb-chart/README.md),
publié sur `oci://registry-1.docker.io/apowerb/apowerb-chart`. Il couvre le
backend, l'interface, PostgreSQL, th2etl et son seed, th2pulse, le collecteur
OpenTelemetry, le volume de données et l'Ingress.

Ce dossier ne contient plus que ce qui vit **à côté** d'une release : des
objets à l'échelle du cluster, que le chart d'une application n'a pas à créer.

## `cert-manager/`

L'émetteur Let's Encrypt. cert-manager installé ne délivre rien tant qu'aucun
`ClusterIssuer` n'existe.

```bash
kubectl apply -f k8s/cert-manager/cluster-issuer-letsencrypt.yaml
kubectl get clusterissuer            # READY=True attendu
```

Puis l'Ingress du chart s'y raccroche :

```bash
--set ingress.enabled=true \
--set ingress.className=traefik \
--set ingress.host=<le nom public> \
--set ingress.tlsEnabled=true \
--set ingress.annotations."cert-manager\.io/cluster-issuer"=letsencrypt-prod
```

Éprouver la chaîne avec `letsencrypt-staging` d'abord : ses certificats ne sont
pas reconnus par les navigateurs, mais ses quotas sont larges. La production
bloque pour une semaine après cinq échecs dans l'heure.

## Les anciens manifestes

`00-namespace.yaml` … `05-ingress.yaml` décrivaient un déploiement antérieur au
chart : ni th2etl, ni th2pulse, ni collecteur, ni volume pour les fichiers
importés, un Ingress en `ingressClassName: nginx` sur `apowerb.local`, et des
secrets à remplir à la main. `kubectl apply -f k8s/` installerait donc une
pile incomplète qui *ressemble* à la bonne. Ils sont conservés le temps de
vérifier que personne ne s'en sert ; utilisez le chart.
