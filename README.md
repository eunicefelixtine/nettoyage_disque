# nettoyage_disque

[![CI](https://github.com/eunicefelixtine/nettoyage_disque/actions/workflows/ci.yml/badge.svg)](https://github.com/eunicefelixtine/nettoyage_disque/actions/workflows/ci.yml)
[![Licence: MIT](https://img.shields.io/badge/Licence-MIT-blue.svg)](LICENSE)

Nettoyeur de disque pour développeurs : repère les dossiers de projets recréables (`node_modules`, `target`, `.venv`, ...) et nettoie l'espace récupérable de Docker.

## Fonctionnalités

- **Scan récursif** des dossiers de projets : `node_modules`, `target` (Rust), `.venv`/`venv` (Python), `.next`, `dist`, `build` (Node).
- **Détection fiable** via un fichier indicateur dans le projet (`package.json`, `Cargo.toml`, `pyvenv.cfg`).
- **Rapport d'espace récupérable** trié par taille décroissante.
- **Statut Docker** (`docker system df`) et **nettoyage sécurisé** : conteneurs arrêtés + images dangling uniquement (pas de `prune` global destructeur).
- **Barre de progression** pendant le calcul des tailles (tqdm, avec repli automatique sans dépendance).
- **Calcul des tailles en parallèle** pour accélérer les scans de gros projets.
- **Deux modes** : interactif (menu) et non-interactif (ligne de commande, scriptable).
- **Suppression réversible** : les dossiers sont envoyés vers la corbeille (`send2trash`) si disponible, sinon suppression définitive après confirmation.

## Prérequis

- Python 3.8+
- `docker` (optionnel, uniquement pour les fonctionnalités Docker)

## Installation

```bash
git clone https://github.com/eunicefelixtine/nettoyage_disque.git
cd nettoyage_disque
pip install -r requirements.txt
```

Les dépendances (`tqdm`, `send2trash`) sont optionnelles : le script reste fonctionnel sans elles (repli automatique), mais il est conseillé de les installer.

| Paquet | Rôle |
|---|---|
| `tqdm` | Barre de progression (repli automatique sans lui) |
| `send2trash` | Suppression vers la corbeille au lieu de la suppression définitive |

## Utilisation

### Mode interactif

```bash
python3 dev_sweep.py
```

Vous choisissez le chemin à analyser (défaut : `~/Documents`), puis un menu propose : simulation, nettoyage des dossiers de projets, nettoyage Docker, ou tout nettoyer.

### Mode non-interactif (CLI)

```bash
python3 dev_sweep.py --path ~/code --dry-run                    # rapport seul, rien ne bouge
python3 dev_sweep.py --path ~/code --folders                    # nettoyer les dossiers de projets (confirmation)
python3 dev_sweep.py --path ~/code --folders --yes              # sans confirmation
python3 dev_sweep.py --path ~/code --docker                     # nettoyage Docker
python3 dev_sweep.py --path ~/code --folders --docker --yes     # tout nettoyer
```

### Options

| Option | Description |
|---|---|
| `--path PATH` | Chemin à analyser (défaut : `~/Documents`). `~` est expansé. |
| `--dry-run` | Affiche le rapport sans supprimer quoi que ce soit. |
| `--folders` | Nettoie les dossiers de projets détectés. |
| `--docker` | Nettoie Docker (conteneurs arrêtés + images dangling). |
| `--yes` | Saute la confirmation (à utiliser avec `--folders`). |
| `-h, --help` | Affiche l'aide. |

## Dossiers détectés

| Dossier | Indicateur | Projet |
|---|---|---|
| `node_modules` | `package.json` | Node.js |
| `target` | `Cargo.toml` | Rust |
| `.venv` | `pyvenv.cfg` (dans le dossier) | Python |
| `venv` | `pyvenv.cfg` (dans le dossier) | Python |
| `.next` | `package.json` | Next.js |
| `dist` | `package.json` | Node |
| `build` | `package.json` | Node |

## Sécurité

- **Racines système protégées** : l'outil ne parcourt ni ne supprime jamais sous les racines système, détectées selon l'OS (Linux : `/bin`, `/usr`, `/var`, `/proc`, ... ; macOS : `/System`, `/Library`, `/Volumes` ; Windows : `C:\Windows`, `Program Files`, ...).
- **Sous-dépôts git ignorés** : un dossier cible contenant `.git` n'est jamais supprimé.
- **Confirmation obligatoire** : chaque suppression affiche les chemins et tailles exacts, et demande une confirmation explicite.
- **Corbeille par défaut** : avec `send2trash`, rien n'est supprimé définitivement (l'espace est libéré après vidage de la corbeille). Sans lui, l'outil le signale clairement avant la suppression définitive.

## Nettoyage Docker

Le nettoyage est volontairement conservateur :

- `docker container prune -f` : supprime uniquement les conteneurs arrêtés.
- `docker image prune -f` : supprime uniquement les images *dangling* (sans tag).

Il n'y a pas d'option `-a` : les images utilisées ou taguées sont conservées.

## Structure du projet

```
nettoyage_disque/
├── dev_sweep.py                 # script principal (scanner + cleaner + CLI)
├── test_dev_sweep.py            # tests unitaires (pytest)
├── requirements.txt             # dépendances optionnelles
├── .github/workflows/ci.yml     # intégration continue (GitHub Actions)
├── .gitignore
├── LICENSE                      # licence MIT
└── README.md
```

Le script est volontairement monofichier pour rester simple à déployer (copier le fichier suffit). Les grandes étapes du code :

1. `scan_directory` : parcours de l'arborescence (`os.walk`) et collecte des cibles valides.
2. `_size_targets` : calcul parallèle des tailles avec barre de progression.
3. `_print_report` : rapport trié par taille.
4. `clean_folders` / `clean_docker` : nettoyage avec confirmations et protections.

## Tests

```bash
pip install pytest
python -m pytest -q
```

La CI (GitHub Actions) exécute les tests sur Python 3.9 à 3.12 à chaque push et pull request.

Test manuel :

```bash
python3 dev_sweep.py --path /chemin/vers/un/projet --dry-run
```

## Licence

Distribué sous licence [MIT](LICENSE).
