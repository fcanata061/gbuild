import os
import shutil
import subprocess
import filecmp
import difflib
import fnmatch
from datetime import datetime
import tarfile
import hashlib

# =========================
# Configurações principais
# =========================
BASE_DIR = "/mnt"
SANDBOX_DIR = "/tmp/pm-sandbox"
ETC_NEW_DIR = "/var/lib/pm/etc-new"
ETC_BACKUP_DIR = "/var/lib/pm/etc-backup"
LOG_FILE = "/var/log/pm.log"

# =========================
# Logs e cores
# =========================
class Colors:
    HEADER = "\033[95m"
    OK = "\033[92m"
    WARN = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"

def log(msg, level="OK"):
    color = getattr(Colors, level, Colors.OK)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} - {msg}\n")
    print(f"{color}{msg}{Colors.END}")

# =========================
# Sandbox
# =========================
def prepare_sandbox():
    os.makedirs(SANDBOX_DIR, exist_ok=True)
    log("Sandbox prepared")

def clean_sandbox():
    if os.path.exists(SANDBOX_DIR):
        shutil.rmtree(SANDBOX_DIR)
    log("Sandbox cleaned")

# =========================
# Utilitários
# =========================
def download(url, dest):
    log(f"Downloading {url} -> {dest}")
    subprocess.run(["curl", "-L", "-o", dest, url], check=True)

def verify_sha256(path, sha256sum):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    valid = h.hexdigest() == sha256sum
    log(f"SHA256 {'valid' if valid else 'invalid'} for {path}")
    return valid

def extract_tarball(tar_path, dest):
    log(f"Extracting {tar_path} -> {dest}")
    with tarfile.open(tar_path) as tar:
        tar.extractall(dest)

def apply_patch(patch_path, work_dir):
    log(f"Applying patch {patch_path}")
    subprocess.run(["patch", "-p1", "-i", patch_path], cwd=work_dir, check=True)

# =========================
# Gerenciamento /etc
# =========================
class EtcManager:
    def __init__(self, stage_dir):
        self.ETC_DIR = os.path.join(BASE_DIR, stage_dir, "etc")
        self.ETC_NEW_DIR = ETC_NEW_DIR
        self.ETC_BACKUP_ROOT = ETC_BACKUP_DIR
        self.MERGE_RULES = {"*.conf":"merge","*.cfg":"merge","*":"keep-local"}

    def backup_file(self, path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rel_path = os.path.relpath(path, self.ETC_DIR)
        backup_dir = os.path.join(self.ETC_BACKUP_ROOT, timestamp, os.path.dirname(rel_path))
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(path, os.path.join(backup_dir, os.path.basename(path)))
        log(f"Backup created: {path}")

    def merge_files(self, local, new):
        with open(local) as f1, open(new) as f2:
            local_lines = f1.readlines()
            new_lines = f2.readlines()
        return list(difflib.unified_diff(local_lines, new_lines, fromfile='local', tofile='new'))

    def process_file(self, filename, auto=True):
        local_path = os.path.join(self.ETC_DIR, filename)
        new_path = os.path.join(self.ETC_NEW_DIR, filename)

        if not os.path.exists(local_path):
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            shutil.copy2(new_path, local_path)
            log(f"Installed new config: {filename}")
            return

        if filecmp.cmp(local_path, new_path, shallow=False):
            return

        self.backup_file(local_path)
        rule = "merge" if filename.endswith((".conf",".cfg")) else "keep-local"
        if rule == "keep-local":
            log(f"Kept local: {filename}")
        elif rule == "replace":
            shutil.copy2(new_path, local_path)
            log(f"Replaced: {filename}")
        elif rule == "merge":
            merged_diff = self.merge_files(local_path, new_path)
            if merged_diff and auto:
                merged_lines = list(difflib.restore(merged_diff, 1))
                with open(local_path, "w") as f:
                    f.writelines(merged_lines)
                log(f"Merged automatically: {filename}")

    def process_all(self, auto=True):
        for root, dirs, files in os.walk(self.ETC_NEW_DIR):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), self.ETC_NEW_DIR)
                self.process_file(rel_path, auto=auto)

def update_etc(stage_dir):
    etc_mgr = EtcManager(stage_dir)
    etc_mgr.process_all(auto=True)

# =========================
# Hooks
# =========================
def run_hooks(stage, hook_type, package=None):
    log(f"Running hook {hook_type} for {package} in {stage}")

# =========================
# Build packages (real)
# =========================
def build_package(stage, package, recipe):
    prepare_sandbox()
    work_dir = os.path.join(SANDBOX_DIR, package)
    os.makedirs(work_dir, exist_ok=True)

    # Download
    tarball_path = os.path.join(work_dir, package + ".tar.xz")
    download(recipe['urls']['tarball'], tarball_path)
    if not verify_sha256(tarball_path, recipe['sha256']):
        log(f"SHA256 mismatch for {package}", "FAIL")
        return

    # Extract
    extract_tarball(tarball_path, work_dir)

    # Patch
    for patch in recipe.get('patches', []):
        apply_patch(patch, work_dir)

    # Build
    build_type = recipe.get('tipo_build', 'autotools')
    if build_type == 'autotools':
        subprocess.run(["./configure"] + recipe.get('configure_opts', []), cwd=work_dir, check=True)
        subprocess.run(["make", "-j4"], cwd=work_dir, check=True)
        subprocess.run(["make", "install", f"DESTDIR={BASE_DIR}/{stage}"], cwd=work_dir, check=True)
    elif build_type == 'python':
        subprocess.run(["python3", "setup.py", "install", f"--root={BASE_DIR}/{stage}"], cwd=work_dir, check=True)
    elif build_type == 'meson':
        build_dir = os.path.join(work_dir, "build")
        os.makedirs(build_dir, exist_ok=True)
        subprocess.run(["meson", ".."], cwd=build_dir, check=True)
        subprocess.run(["ninja", "-C", build_dir], cwd=build_dir, check=True)
        subprocess.run(["ninja", "-C", build_dir, "install"], cwd=build_dir, check=True)
    elif build_type == 'rust':
        subprocess.run(["cargo", "install", "--root", f"{BASE_DIR}/{stage}"], cwd=work_dir, check=True)

    run_hooks(stage, "post_install", package)
    update_etc(stage)
    clean_sandbox()

# =========================
# Pipeline Stage
# =========================
def build_stage(stage, recipes):
    for package, recipe in recipes.items():
        deps = recipe.get('dependencias_build', [])
        for dep in deps:
            if dep in recipes:
                build_package(stage, dep, recipes[dep])
        build_package(stage, package, recipe)

# =========================
# Exemplo de receitas
# =========================
GCC_RECIPE = {
    "urls": {"tarball": "https://ftp.gnu.org/gnu/gcc/gcc-12.2.0/gcc-12.2.0.tar.xz"},
    "sha256": "d08a6c1a8c23ee8b3e1c1b8d7d5ebf5f9f7715c7b6f4b5646f6b3f6f6b5f6c5f",
    "dependencias_build": ["mpfr","gmp","mpc"],
    "tipo_build": "autotools",
    "configure_opts": ["--disable-multilib"]
}

# =========================
# Execução exemplo
# =========================
if __name__ == "__main__":
    stage_recipes = {"gcc": GCC_RECIPE}
    build_stage("stage3", stage_recipes)
