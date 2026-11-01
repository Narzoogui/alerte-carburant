# Alerte carburant

Reçois une **notification sur ton téléphone** dès que du **SP95 ou du gazole redevient disponible** dans les stations-service de ton choix autour de Strasbourg.

Le projet tourne **entièrement dans le cloud et gratuitement** : aucun serveur à louer, aucun ordinateur à laisser allumé.

## Le problème

En période de tensions sur l'approvisionnement, trouver une station qui a du carburant demande de consulter des cartes à la main, encore et encore. Ce projet inverse la logique : au lieu de chercher, on **est prévenu** quand une station repasse de « en rupture » à « disponible ».

## Comment ça marche

```
┌────────────────┐   toutes les ~10 min   ┌──────────────────────┐
│ GitHub Actions │ ─────────────────────► │ alerte_carburant.py  │
│   (planifié)   │                        │      (Python 3)      │
└────────────────┘                        └──────────┬───────────┘
                                                     │
        ┌────────────────────────────────────────────┼──────────────────────┐
        ▼                                            ▼                      ▼
 Données officielles                         État précédent           Notification
 prix-carburants (data.gouv)                 (cache GitHub)           push via ntfy
 disponibilité par station                   « dispo ? oui / non »    sur l'iPhone
```

1. Toutes les 10 minutes environ, **GitHub Actions** lance le script.
2. Le script récupère la **disponibilité officielle** de chaque carburant dans chaque station (jeu de données « Prix des carburants, flux instantané v2 », mis à jour toutes les 10 minutes).
3. Il compare avec **l'état du passage précédent**, conservé entre deux exécutions grâce au cache de GitHub Actions.
4. Pour chaque carburant qui passe de **indisponible à disponible**, il envoie une notification push avec l'adresse de la station, via [ntfy](https://ntfy.sh).

Une alerte n'est envoyée que lors d'un **changement réel** : pas de répétition tant qu'une station reste dans le même état.

## Fonctionnalités

- Surveillance du **SP95 et du gazole** (carburants modifiables).
- Choix précis des **stations surveillées**, par identifiant.
- Aide au choix : le mode `--list` affiche les stations dans un **rayon de 30 km** autour de Strasbourg, et repère celles de l'enseigne TotalEnergies grâce aux données d'OpenStreetMap.
- Mode `--test` : envoie une notification de test pour vérifier la chaîne complète.
- Mode `--simulation` : simule une alerte **sans toucher à l'état enregistré**, donc sans risque de fausse alerte ensuite.
- **Tolérant aux pannes** : si l'API officielle ou un serveur OpenStreetMap ne répond pas, le script réessaie au passage suivant (avec plusieurs serveurs de secours pour les enseignes).
- **Aucune dépendance externe** : uniquement la bibliothèque standard de Python 3.

## Technologies

| Rôle | Outil |
| --- | --- |
| Langage | Python 3 (bibliothèque standard) |
| Planification et exécution | GitHub Actions (cron, cache) |
| Données de disponibilité | Données ouvertes « Prix des carburants », data.economie.gouv.fr |
| Enseignes des stations | OpenStreetMap (Overpass, avec Nominatim en secours) |
| Notifications | ntfy (push iOS et Android) |

## Mise en place

1. **Créer un dépôt public** sur GitHub et y déposer `alerte_carburant.py` ainsi que `.github/workflows/alerte.yml`.
   Un dépôt public bénéficie d'exécutions gratuites sans limite, ce qui convient à une exécution toutes les 10 minutes.
2. **Installer l'appli ntfy** sur le téléphone et s'abonner à un nom de sujet long et aléatoire. Ce nom sert de mot de passe : toute personne qui le connaît peut lire les alertes.
3. Dans **Settings → Secrets and variables → Actions** :
   - créer le **secret** `NTFY_TOPIC` avec ce nom de sujet (il reste invisible, même sur un dépôt public) ;
   - créer la **variable** `STATION_IDS` avec les identifiants des stations, séparés par des virgules, sans espace.
4. Dans l'onglet **Actions → Alerte carburant → Run workflow**, lancer dans l'ordre :
   - `--test` pour vérifier la notification ;
   - `--list` pour trouver les identifiants des stations ;
   - `check` une première fois : il enregistre l'état de départ sans envoyer d'alerte.

Ensuite, tout est automatique.

## Configuration

| Paramètre | Où | Rôle |
| --- | --- | --- |
| `NTFY_TOPIC` | Secret GitHub | Sujet ntfy qui reçoit les notifications |
| `STATION_IDS` | Variable GitHub | Stations surveillées (identifiants séparés par des virgules) |
| `CARBURANTS` | Script | Carburants surveillés (`sp95`, `gazole`, `e10`, …) |
| `CENTRE`, `RAYON_KM` | Script | Point central et rayon utilisés par `--list` |

## Choix techniques

- **État conservé dans le cache de GitHub Actions** plutôt que dans des commits : le dépôt reste propre, sans historique de commits automatiques.
- **Secret pour le nom du sujet** : le code est public, mais personne ne peut s'abonner aux alertes.
- **Simulation sans écriture d'état** : on peut tester le rendu des alertes sans jamais fausser la détection des vrais changements.
- **Pas de dépendances** : le script s'exécute sur n'importe quelle machine disposant de Python 3, sans installation.

## Limites connues

- Les disponibilités viennent des **déclarations des exploitants** : elles peuvent arriver avec un peu de retard par rapport aux signalements d'automobilistes sur les applications communautaires.
- Les exécutions planifiées de GitHub peuvent être **retardées ou sautées de quelques minutes** aux heures chargées.
- GitHub **désactive les tâches planifiées** d'un dépôt public sans activité pendant 60 jours : il suffit de réactiver le workflow dans l'onglet Actions.
- Une station qui ne vend pas un carburant (par exemple pas de SP95, seulement du SP95-E10) n'enverra jamais d'alerte pour celui-ci.
- Les enseignes proviennent d'OpenStreetMap : les données peuvent être incomplètes ou ne pas refléter un changement très récent. Le rayon est calculé à vol d'oiseau, pas en temps de trajet.

## Sources de données

- Prix des carburants en France, flux instantané : [data.economie.gouv.fr](https://data.economie.gouv.fr/explore/dataset/prix-des-carburants-en-france-flux-instantane-v2/)
- Enseignes des stations : © contributeurs [OpenStreetMap](https://www.openstreetmap.org/copyright)
- Notifications : [ntfy](https://ntfy.sh)
