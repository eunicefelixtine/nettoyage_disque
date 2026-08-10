import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple

TARGET_PATTERNS: Dict[str, str] = {
    "node_modules": "package.json",
    "target": "Cargo.toml",
    ".venv": "pyproject.toml",
    "venv": "requirements.txt",
    ".next": "package.json",
    "dist": "package.json",
    "build": "package.json",
}

FORBIDDEN_DIRS = {"Windows", "System32", "System", "usr", "bin", "lib", "Applications"}

def check_docker_reclaimable() -> str:
    """Vérifie l'espace récupérable via Docker."""
    try:
        result = subprocess.run(
            ["docker", "system", "df"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "Docker n'est pas installé ou le daemon n'est pas démarré."

def clean_docker() -> None:
    """Exécute un nettoyage Docker sécurisé (dangling images & stopped containers)."""
    try:
        print("\n🐳 Nettoyage de Docker en cours...")
        subprocess.run(["docker", "system", "prune", "-f"], check=True)
        print("✅ Cache Docker nettoyé avec succès !")
    except Exception as e:
        print(f"❌ Erreur lors du nettoyage Docker : {e}")

def get_dir_size(path: Path) -> int:
    total_size = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file(follow_symlinks=False):
                total_size += entry.stat().st_size
            elif entry.is_dir(follow_symlinks=False):
                total_size += get_dir_size(Path(entry.path))
    except (PermissionError, FileNotFoundError):
        pass
    return total_size

def format_bytes(size: int) -> str:
    for unit in ['B', 'Ko', 'Mo', 'Go', 'To']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} To"

def scan_directory(root_path: Path) -> List[Tuple[Path, int, str]]:
    found_targets = []
    print(f"🔍 Analyse en cours de : {root_path}...\n")

    for current_root, dirs, _ in os.walk(root_path, topdown=True):
        current_path = Path(current_root)
        dirs[:] = [d for d in dirs if d not in FORBIDDEN_DIRS]

        for dir_name in list(dirs):
            if dir_name in TARGET_PATTERNS:
                target_dir = current_path / dir_name
                indicator_file = TARGET_PATTERNS[dir_name]
                
                if (current_path / indicator_file).exists() or indicator_file == "":
                    size = get_dir_size(target_dir)
                    found_targets.append((target_dir, size, dir_name))
                    dirs.remove(dir_name)

    return found_targets

def main():
    default_dir = Path.home() / "Documents"
    if not default_dir.exists():
        default_dir = Path.home()

    print("=== DEV-SWEEP / TO-CLEAN ===")
    user_input = input(f"Chemin à analyser [{default_dir}] : ").strip()
    scan_path = Path(user_input) if user_input else default_dir

    if not scan_path.exists():
        print("❌ Ce chemin n'existe pas.")
        return

    # Scan des dossiers de dev
    results = scan_directory(scan_path)

    # Affichage du rapport des dossiers
    total_reclaimable = 0
    if results:
        print("-" * 65)
        print(f"{'TYPE':<15} | {'TAILLE':<10} | CHEMIN")
        print("-" * 65)
        for path, size, dir_type in results:
            total_reclaimable += size
            print(f"{dir_type:<15} | {format_bytes(size):<10} | {path}")
        print("-" * 65)
        print(f"📊 ESPACE DOSSIERS PROJETS RÉCUPÉRABLE : {format_bytes(total_reclaimable)}\n")
    else:
        print("✨ Aucun dossier temporaire de build trouvé dans vos projets.")

    # État de Docker
    print("\n🐳 STATUS DOCKER :")
    print(check_docker_reclaimable())

    # Actions
    print("\nQue souhaitez-vous faire ?")
    print("1. [Simulation] Voir sans rien supprimer")
    print("2. Nettoyer les dossiers de projets (node_modules, target, etc.)")
    print("3. Nettoyer le cache Docker (docker system prune)")
    print("4. TOUT nettoyer (Projets + Docker)")
    print("5. Quitter")

    choice = input("\nChoix (1-5) : ").strip()

    if choice == "1":
        print("\n🧪 Mode Simulation terminé. Aucune modification effectuée.")
    elif choice == "2":
        clean_folders(results)
    elif choice == "3":
        clean_docker()
    elif choice == "4":
        clean_folders(results)
        clean_docker()
    else:
        print("\nOpération annulée.")

def clean_folders(results):
    if not results:
        print("Rien à nettoyer dans les dossiers.")
        return
    confirm = input(f"\n⚠️  Supprimer ces {len(results)} dossiers ? (oui/non) : ").strip().lower()
    if confirm == "oui":
        freed = 0
        for path, size, _ in results:
            try:
                shutil.rmtree(path)
                freed += size
                print(f"✅ Supprimé : {path}")
            except Exception as e:
                print(f"❌ Erreur sur {path} : {e}")
        print(f"\n🎉 {format_bytes(freed)} libérés !")

if __name__ == "__main__":
    main()
