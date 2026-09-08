# Dépôt Helm d'apowerb

Cette branche n'est pas de la documentation : c'est l'**index du dépôt Helm**.
`chart-releaser` (workflow `release-helm.yml`) y ajoute une entrée à chaque
nouvelle version de `helm/apowerb/Chart.yaml` poussée sur `main`, et publie la
release GitHub correspondante.

Elle n'existait pas, et c'est tout ce qui manquait : le workflow échouait sur
`fatal: invalid reference: origin/gh-pages` — huit runs de suite — donc aucun
chart n'a jamais été publié malgré ce que promettaient les README.

Ne pas la supprimer, ne pas y committer à la main.

    helm repo add apowerb https://apowerb.github.io/apowerb-hosting
    helm repo update
    helm search repo apowerb

L'installation par OCI (`oci://registry-1.docker.io/apowerb/apowerb`) ne dépend
pas de cette branche : elle vient de `publish-dockerhub-helm.yml`, déclenché par
la release que `chart-releaser` crée ici.
