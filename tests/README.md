# Le contrat entre ce compose et le cœur qu'il déploie

Compose ne transmet à un conteneur que ce que le service **déclare**. Une
valeur saisie dans le panneau de la plateforme, une variable exportée sur
l'hôte : tout le reste s'arrête au mur du conteneur, sans bruit, et
l'application démarre en ayant l'air configurée.

Les trois pannes du 08/09/2026 sont cette phrase, trois fois :

| | ce qui manquait | ce qu'on voyait |
|---|---|---|
| hosting#23 | `ORCHESTRATOR` non déclarée | écran Orchestrateur vide, 503, devant un th2etl sain |
| hosting#24 | 19 variables d'intégration non déclarées | identifiants Azure posés dans le panneau, Outlook refuse quand même |
| hosting#25 | `OUTLOOK_MAIL_REDIRECT_URI: ${OUTLOOK_MAIL_REDIRECT_URI:-}` | `AADSTS90102` en production |

La troisième est la plus chère et la moins visible : **une variable déclarée
vide n'est pas une variable absente**. `pydantic-settings` la compte comme
*fournie* (`model_fields_set`), donc elle **écrase** la valeur que le cœur
aurait déduite de `APP_PUBLIC_URL` au lieu de s'y effacer.

Chacune est une comparaison entre deux listes que personne ne faisait.

## Ce qui est comparé

Les deux côtés sont lus tels que le déploiement les lit.

- **Le compose** passe par `docker compose config`, avec un environnement
  vide et `--env-file /dev/null` : une valeur est donc ce que le conteneur
  recevrait vraiment, replis imbriqués résolus et `${X:-}` rendu comme la
  chaîne vide qu'il est.
- **Le cœur** est lu en exécutant `probe_core.py` **dans l'image épinglée**
  (`docker run --entrypoint python`). Pas un `git clone` du même tag à côté :
  atteindre `setup_status` depuis les sources demande `google-adk`, `boto3`,
  `asyncpg` et quarante autres paquets, et resterait une bonne approximation
  de l'artefact. L'image *est* l'artefact.

## Les sept contrôles

1. **Tout nom que la checklist du produit donne à un administrateur est
   déclaré.** `GET /api/config/setup` rend les *noms* des variables encore
   manquantes et l'interface les affiche. Sans liste d'exclusion : nommer une
   variable à l'écran puis la laisser tomber au mur du conteneur n'a pas de
   justification.
2. **Tout réglage du cœur est déclaré, ou écarté par écrit** dans
   `compose_contract.yml`. Un réglage neuf ne correspond ni à l'un ni à
   l'autre : le test rougit à la prochaine modification de ce fichier.
3. **Aucune entrée périmée** dans ce fichier d'exclusions.
4. **Aucune URL déduite déclarée vide** — hosting#25.
5. **Une URL déduite qui EST déclarée reproduit la déduction du cœur** : rendue
   contre une origine réelle, elle vaut cette origine plus le chemin exact que
   le cœur ajoute.
6. **`APP_PUBLIC_URL` et `PUBLIC_BASE_URL` ne sont jamais vides** : la première
   éteint les cinq déductions d'un coup, la seconde a envoyé Graph sur
   `http://localhost:8000`.
7. **Rien n'est déclaré que personne ne lit** : une variable ni réglage du cœur
   ni citée dans ses sources est une valeur que la plateforme collecte et que
   personne ne recueille à l'autre bout. Une faute de frappe atterrit ici.

## Le lancer

```bash
pip install -r tests/requirements.txt
cd tests && python -m pytest
```

Il faut Docker (`docker compose config` et l'image épinglée) ; l'image est
tirée toute seule au premier passage.

## Ce qu'il ne couvre pas

Il compare des **noms**, jamais des valeurs. Un `MICROSOFT_INTEGRATION_CLIENT_ID`
bien déclaré et rempli avec l'identifiant d'une autre application passe ici et
échoue chez Microsoft. Il ne dit rien non plus des services `apowerb-ui`,
`th2etl` et `th2pulse`, dont la configuration ne passe pas par `Settings`.
