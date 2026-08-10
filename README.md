# Nettoyage Disque (`nettoyage_disque`)

[![CI](https://github.com/eunicefelixtine/nettoyage_disque/actions/workflows/ci.yml/badge.svg)](https://github.com/eunicefelixtine/nettoyage_disque/actions/workflows/ci.yml)
![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![OS Linux / macOS / Windows](https://img.shields.io/badge/OS-Linux%20%7C%20macOS%20%7C%20Windows-orange.svg)

Outil CLI en Python pour détecter et nettoyer automatiquement les dépendances de développement réinstallables (`node_modules`, `target`, `.venv`, etc.) et le cache Docker afin de libérer de l'espace disque.

---

## Indicateurs Rapides

| Indicateur | Valeur / Détail |
|---|---|
| **Langage** | Python 3.8+ |
| **Type d'outil** | CLI / Script interactif |
| **Dépendances externes** | Aucune (100% optionnelles) |
| **Temps d'exécution** | Rapide (calcul des tailles en parallèle) |
| **Mode Sécurité** | Support de la corbeille système (`send2trash`) & vérification par fichiers témoins |

---

## Prise en main rapide

### 1. Clonage du projet

```bash
git clone https://github.com/eunicefelixtine/nettoyage_disque.git
cd nettoyage_disque
```

### 2. Dépendances (Optionnelles)

Le script fonctionne sans aucune dépendance. Toutefois, vous pouvez installer les paquets recommandés pour bénéficier de la barre de progression et de la suppression vers la corbeille :

```bash
pip install -r requirements.txt
```

### 3. Utilisation

#### Mode interactif (Menu guidé)

```bash
python3 dev_sweep.py
```

#### Mode non-interactif (Commandes CLI)

```bash
# Rapport d'analyse sans suppression (Dry-run)
python3 dev_sweep.py --path ~/Documents --dry-run

# Nettoyer les dossiers de projets (avec demande de confirmation)
python3 dev_sweep.py --path ~/Documents --folders

# Nettoyer les dossiers automatiquement (sans confirmation)
python3 dev_sweep.py --path ~/Documents --folders --yes

# Nettoyer uniquement le cache Docker
python3 dev_sweep.py --docker

# Nettoyage complet (Dossiers de projets + Docker)
python3 dev_sweep.py --path ~/Documents --folders --docker --yes
```

### Options de ligne de commande

| Option | Description |
|---|---|
| `--path PATH` | Dossier racine à analyser (défaut : `~/Documents`). |
| `--dry-run` | Affiche l'espace récupérable sans effectuer de suppression. |
| `--folders` | Cible les dossiers de projets détectés pour suppression. |
| `--docker` | Lance la purge sécurisée du cache Docker. |
| `--yes` | Saute la demande de confirmation explicite. |
| `-h, --help` | Affiche l'aide et les options. |

## Dossiers & Indicateurs de Détection

L'outil vérifie la présence d'un fichier témoin au niveau du projet avant de classer un dossier comme supprimable :

| Dossier Cible | Fichier Indicateur | Écosystème |
|---|---|---|
| `node_modules` | `package.json` | Node.js |
| `target` | `Cargo.toml` | Rust |
| `.venv` / `venv` | `pyvenv.cfg` (dans le dossier) | Python |
| `.next` | `package.json` | Next.js |
| `dist` / `build` | `package.json` | Node / Frontend |

## Garanties de Sécurité

- **Protection Système** : Blocage automatique du parcours sur les racines système (`/bin`, `/usr`, `/var`, `C:\Windows`, etc.).
- **Protection Git** : Exclusion stricte de tout dossier contenant un répertoire `.git`.
- **Nettoyage Docker conservateur** : Utilise `docker container prune -f` et `docker image prune -f` (les images utilisées ou taguées sont préservées).
- **Suppression réversible** : Si `send2trash` est présent, les éléments sont envoyés dans la corbeille au lieu d'être effacés directement.

## Structure du Projet

```
nettoyage_disque/
├── dev_sweep.py          # Script principal (Scanner, CLI, Nettoyeur)
├── test_dev_sweep.py     # Tests unitaires
├── requirements.txt      # Dépendances optionnelles (tqdm, send2trash)
├── .github/workflows/    # Pipeline CI (GitHub Actions)
│   └── ci.yml
├── .gitignore
└── README.md
```

## Tests Unitaires

Exécuter la suite de tests localement :

```bash
pip install pytest
python3 -m pytest -q
```
