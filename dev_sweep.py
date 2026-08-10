import argparse
import os
import shutil
import stat as statmod
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable

TARGET_PATTERNS: Dict[str, str] = {
    "node_modules": "package.json",
    "target": "Cargo.toml",
    ".venv": "pyvenv.cfg",
    "venv": "pyvenv.cfg",
    ".next": "package.json",
    "dist": "package.json",
    "build": "package.json",
}

def get_forbidden_dirs() -> List[Path]:
    """Racines système à ne jamais parcourir ni supprimer, selon l'OS."""
    if os.name == "nt":
        drive = Path(os.environ.get("SystemDrive", "C:"))
        return [
            drive / "Windows",
            drive / "Program Files",
            drive / "Program Files (x86)",
            drive / "ProgramData",
        ]
    if sys.platform == "darwin":
        return [Path("/System"), Path("/Library"), Path("/Volumes"), Path("/private")]
    return [
        Path("/bin"), Path("/boot"), Path("/dev"), Path("/etc"),
        Path("/lib"), Path("/lib64"), Path("/proc"), Path("/root"),
        Path("/run"), Path("/sbin"), Path("/sys"), Path("/usr"), Path("/var"),
    ]

FORBIDDEN_ROOTS: List[Path] = get_forbidden_dirs()

def is_forbidden(path: Path) -> bool:
    """Vrai si le chemin se situe sous une racine système protégée."""
    return any(path == root or root in path.parents for root in FORBIDDEN_ROOTS)

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
    except (OSError, subprocess.CalledProcessError):
        return "Docker n'est pas installé ou le daemon n'est pas démarré."

def clean_docker() -> None:
    """Nettoie uniquement les conteneurs arrêtés et les images dangling."""
    try:
        print("\n🐳 Nettoyage de Docker en cours...")
        subprocess.run(["docker", "container", "prune", "-f"], check=True)
        subprocess.run(["docker", "image", "prune", "-f"], check=True)
        print("✅ Conteneurs arrêtés et images dangling nettoyés !")
    except FileNotFoundError:
        print("❌ Docker n'est pas installé sur cette machine.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Échec du nettoyage Docker (code {e.returncode}) : {e.stderr or e}")

def get_dir_size(
    path: Path,
    progress: Optional[Callable[[int, int], None]] = None,
    report_every: int = 250,
) -> int:
    total_size = 0
    scanned = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    scanned += 1
                    try:
                        st = entry.stat(follow_symlinks=False)
                        if statmod.S_ISREG(st.st_mode):
                            total_size += st.st_size
                        elif statmod.S_ISDIR(st.st_mode):
                            stack.append(Path(entry.path))
                    except (PermissionError, FileNotFoundError):
                        continue
                    if progress and scanned % report_every == 0:
                        progress(scanned, total_size)
        except (PermissionError, FileNotFoundError):
            continue
    if progress:
        progress(scanned, total_size)
    return total_size

def format_bytes(size: int) -> str:
    units = ["o", "Ko", "Mo", "Go", "To"]
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024.0

def _is_valid_target(parent_dir: Path, target_dir: Path, indicator_file: str) -> bool:
    if (parent_dir / indicator_file).exists():
        return True
    return (target_dir / indicator_file).exists()

def _format_bar(done: int, total: int, width: int = 30) -> str:
    if total <= 0:
        return ""
    filled = width * done // total
    return "[" + "#" * filled + "." * (width - filled) + f"] {done}/{total}"

def _print_progress_line(text: str) -> None:
    print(f"\r{text}" + " " * max(0, 50 - len(text)), end="", flush=True)

def _collect_targets(root_path: Path) -> List[Tuple[Path, str]]:
    targets = []
    dirs_visited = 0
    for current_root, dirs, _ in os.walk(root_path, topdown=True):
        current_path = Path(current_root)
        dirs_visited += 1
        if dirs_visited % 200 == 0:
            _print_progress_line(f"Analyse de l'arborescence... {dirs_visited} dossiers visités")
        if is_forbidden(current_path):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not is_forbidden(current_path / d)]

        for dir_name in list(dirs):
            if dir_name not in TARGET_PATTERNS:
                continue
            target_dir = current_path / dir_name
            indicator_file = TARGET_PATTERNS[dir_name]

            if not _is_valid_target(current_path, target_dir, indicator_file):
                continue
            if (target_dir / ".git").exists():
                continue
            if is_forbidden(target_dir):
                continue

            targets.append((target_dir, dir_name))
            dirs.remove(dir_name)
    if dirs_visited >= 200:
        print()
    return targets

def _size_targets(targets: List[Tuple[Path, str]]) -> List[Tuple[Path, int, str]]:
    results = []
    total = len(targets)
    if total == 0:
        return results

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    lock = threading.Lock()
    state = {"entries": 0, "bytes": 0, "done": 0, "current": ""}

    def render() -> None:
        bar = _format_bar(state["done"], total)
        label = f"{state['current']} · {format_bytes(state['bytes'])}"
        _print_progress_line(f"Calcul des tailles {bar} {label}")

    def on_entry(delta_entries: int, delta_bytes: int, current_target: str) -> None:
        with lock:
            state["entries"] += delta_entries
            state["bytes"] += delta_bytes
            state["current"] = current_target
            if tqdm is not None:
                pbar.update(delta_entries)
                pbar.set_postfix_str(f"{format_bytes(state['bytes'])} · {current_target}")
            else:
                render()

    def on_done(current_target: str) -> None:
        with lock:
            state["done"] += 1
            state["current"] = current_target
            if tqdm is not None:
                pbar.set_postfix_str(f"{state['done']}/{total} dossiers · {current_target}")
            else:
                render()

    def make_reporter(target: Path) -> Callable[[int, int], None]:
        last = [0, 0]

        def report(scanned: int, size_so_far: int) -> None:
            delta_entries = scanned - last[0]
            delta_bytes = size_so_far - last[1]
            last[0], last[1] = scanned, size_so_far
            on_entry(delta_entries, delta_bytes, str(target))

        return report

    if tqdm is not None:
        pbar = tqdm(desc="Calcul des tailles", unit="entrées")

    if total == 1:
        target_dir, _ = targets[0]
        return [(target_dir, get_dir_size(target_dir, make_reporter(target_dir)), target_dir.name)]

    max_workers = max(1, min(os.cpu_count() or 1, 8))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(get_dir_size, target_dir, make_reporter(target_dir)): target_dir
            for target_dir, _ in targets
        }
        for future in as_completed(futures):
            target_dir = futures[future]
            results.append((target_dir, future.result(), target_dir.name))
            on_done(str(target_dir))

    if tqdm is not None:
        pbar.close()
    else:
        print()
    return results

def scan_directory(root_path: Path) -> List[Tuple[Path, int, str]]:
    print(f"🔍 Analyse en cours de : {root_path}...\n")
    targets = _collect_targets(root_path)
    return _size_targets(targets)

def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dev_sweep",
        description="Nettoyeur de dossiers de projets de développement et du cache Docker.",
    )
    parser.add_argument("--path", type=Path, default=None,
                        help="Chemin à analyser (défaut : ~/Documents)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Afficher le rapport sans rien supprimer")
    parser.add_argument("--folders", action="store_true",
                        help="Nettoyer les dossiers de projets (node_modules, target, etc.)")
    parser.add_argument("--docker", action="store_true",
                        help="Nettoyer Docker (conteneurs arrêtés + images dangling)")
    parser.add_argument("--yes", action="store_true",
                        help="Ne pas demander de confirmation (avec --folders)")
    return parser.parse_args(argv)

def _resolve_scan_path(args: argparse.Namespace) -> Path:
    if args.path:
        return args.path.expanduser()
    default_dir = Path.home() / "Documents"
    if not default_dir.exists():
        default_dir = Path.home()
    user_input = input(f"Chemin à analyser [{default_dir}] : ").strip()
    return Path(user_input).expanduser() if user_input else default_dir

def _print_report(results: List[Tuple[Path, int, str]]) -> int:
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
    return total_reclaimable

def _interactive_menu(results: List[Tuple[Path, int, str]]) -> None:
    print("\n🐳 STATUS DOCKER :")
    print(check_docker_reclaimable())

    print("\nQue souhaitez-vous faire ?")
    print("1. [Simulation] Voir sans rien supprimer")
    print("2. Nettoyer les dossiers de projets (node_modules, target, etc.)")
    print("3. Nettoyer Docker (conteneurs arrêtés + images dangling)")
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

def main(argv=None):
    args = _parse_args(argv)
    try:
        print("=== DEV-SWEEP / TO-CLEAN ===")
        scan_path = _resolve_scan_path(args)

        if not scan_path.exists():
            print(f"❌ Le chemin n'existe pas : {scan_path}")
            return
        if not scan_path.is_dir():
            print(f"❌ Ce n'est pas un dossier : {scan_path}")
            return

        results = scan_directory(scan_path)
        results.sort(key=lambda item: item[1], reverse=True)
        _print_report(results)

        if args.dry_run:
            print("🧪 Mode simulation (--dry-run) : aucune modification effectuée.")
            return

        if args.folders or args.docker:
            if args.folders:
                clean_folders(results, skip_confirm=args.yes)
            if args.docker:
                clean_docker()
            return

        _interactive_menu(results)
    except KeyboardInterrupt:
        print("\n⚠️  Opération interrompue par l'utilisateur.")

def _send2trash_available() -> bool:
    try:
        import send2trash
    except ImportError:
        return False
    return True

def move_to_trash(path: Path) -> None:
    from send2trash import send2trash
    send2trash(str(path))

def clean_folders(results: List[Tuple[Path, int, str]], skip_confirm: bool = False) -> None:
    if not results:
        print("Rien à nettoyer dans les dossiers.")
        return

    results = [r for r in results if not is_forbidden(r[0])]
    if not results:
        print("Tous les dossiers détectés sont protégés, aucun ne sera supprimé.")
        return

    use_trash = _send2trash_available()
    method = "déplacés vers la corbeille" if use_trash else "supprimés définitivement"

    preview = "\n".join(f"  - {p} ({format_bytes(s)})" for p, s, _ in results)
    print(f"\n⚠️  Les {len(results)} dossiers suivants seront {method} :")
    print(preview)

    if not skip_confirm:
        confirm = input("\nConfirmer ? (oui/non) : ").strip().lower()
        if confirm != "oui":
            print("Opération annulée.")
            return

    freed = 0
    for path, size, _ in results:
        try:
            if use_trash:
                move_to_trash(path)
            else:
                shutil.rmtree(path)
            freed += size
            print(f"✅ {method} : {path}")
        except Exception as e:
            print(f"❌ Erreur sur {path} : {e}")
    print(f"\n🎉 {format_bytes(freed)} {method} !")

if __name__ == "__main__":
    main()
