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

## Conteneurisation (Docker)

### Construction de l'image

```bash
docker build -t nettoyage_disque .
```

### Image publique (Docker Hub)

L'image est publiée automatiquement sur **Docker Hub** via GitHub Actions à chaque push sur `main` (et tag `v*`), avec les tags `latest` et un tag basé sur le SHA du commit :

```bash
docker pull eunicefelixtine/nettoyage_disque:latest
```

> Remplace `eunicefelixtine` par ton nom d'utilisateur Docker Hub.

### Analyse / nettoyage des dossiers de projets

Montez le dossier hôte à analyser et indiquez son chemin **dans le conteneur** :

```bash
docker run --rm -it -v "$HOME":/home/appuser nettoyage_disque --path /home/appuser/Documents --dry-run
```

### Limites du mode conteneur

- **Nettoyage Docker sur l'hôte** : l'image ne contient pas de client Docker et le binaire de l'hôte n'est pas compatible (binaire glibc vs conteneur musl). Le nettoyage du cache Docker (`--docker`) doit être exécuté directement sur l'hôte. Le conteneur est destiné à l'analyse et au nettoyage des dossiers de projets.
- La corbeille (`send2trash`) ne fonctionne pas dans un conteneur (aucun service de corbeille) : les suppressions sont définitives, après confirmation.
- Le conteneur tourne en utilisateur non-root (`appuser`).

## Déploiement Kubernetes (ArgoCD / GitOps)

Le projet est déployé sur Kubernetes via **ArgoCD** à partir des manifests du dossier `k8s/`.

### Manifests (`k8s/`)

| Fichier | Rôle |
|---|---|
| `namespace.yaml` | Namespace `nettoyage` |
| `configmap.yaml` | Configuration : schedule, chemin à analyser, arguments (`--dry-run` par défaut) |
| `cronjob.yaml` | CronJob `nettoyage-disque` exécuté chaque jour à 02:00 |

Le CronJob monte le dossier du nœud `/tmp/nettoyage-data` dans `/data` puis lance :

```bash
python dev_sweep.py --path /data --dry-run
```

> Par défaut en **mode simulation** (`--dry-run`) : aucun fichier n'est supprimé. Pour activer le vrai nettoyage, modifiez `extra-args` dans `configmap.yaml` (`--folders --yes`) et commitez le changement.

### Boucle GitOps (déploiement continu)

1. `git push` sur `main` → GitHub Actions (CI + CD)
2. Le CD construit l'image et la publie sur Docker Hub avec un tag basé sur le SHA
3. Le workflow met à jour `k8s/cronjob.yaml` (nouveau tag image) et committe le changement
4. ArgoCD détecte le commit et **resynchronise automatiquement** le cluster

### Application ArgoCD

```bash
kubectl apply -f - <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: nettoyage
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/eunicefelixtine/nettoyage_disque.git
    targetRevision: HEAD
    path: k8s
  destination:
    server: https://kubernetes.default.svc
    namespace: nettoyage
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF
```

### Exécution manuelle du CronJob

```bash
# Lancer un scan maintenant (sans attendre le schedule)
kubectl create job nettoyage-test --from=cronjob/nettoyage-disque -n nettoyage
kubectl logs -n nettoyage -l job-name=nettoyage-test
```

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
├── Dockerfile            # Image Docker (python:3.12-alpine, utilisateur non-root)
├── .dockerignore
├── .github/workflows/    # Pipelines CI/CD (GitHub Actions)
│   ├── ci.yml           # Tests unitaires (Python 3.9 → 3.12)
│   └── docker-cd.yml    # Build + push image Docker Hub + mise à jour GitOps des manifests
├── k8s/                 # Manifests Kubernetes (déployés par ArgoCD)
│   ├── namespace.yaml
│   ├── configmap.yaml
│   └── cronjob.yaml
├── .gitignore
└── README.md
```

## Tests Unitaires

Exécuter la suite de tests localement :

```bash
pip install pytest
python3 -m pytest -q
```
