import json
import os
from datetime import datetime

# =========================
# Configurações
# =========================
PACKAGE_DB = "/var/lib/pm/packages.db"
MANIFESTO_REMOTE = "/var/lib/pm/recipes.json"
VERSIONS_JSON = "/var/lib/pm/versions.json"
LOG_FILE = "/var/log/pm.log"

# =========================
# Logs
# =========================
def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"{timestamp} - {msg}\n")
    print(msg)

# =========================
# Classes principais
# =========================
class Package:
    def __init__(self, name, version, url, use_flags=None, update_policy="notify", group=None):
        self.name = name
        self.version = version
        self.url = url
        self.use_flags = use_flags or []
        self.update_policy = update_policy  # notify | auto
        self.group = group  # e.g., @core, @desktop

class VersionTracker:
    def __init__(self):
        self.installed_packages = self.load_installed_packages()
        self.manifest = self.load_manifest()
        self.versions = {}

    # -------------------------
    # Carrega pacotes instalados
    # -------------------------
    def load_installed_packages(self):
        packages = {}
        if os.path.exists(PACKAGE_DB):
            with open(PACKAGE_DB) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        name, version = parts[0], parts[1]
                        packages[name] = Package(name=name, version=version, url="", update_policy="notify")
        return packages

    # -------------------------
    # Carrega manifesto remoto
    # -------------------------
    def load_manifest(self):
        if os.path.exists(MANIFESTO_REMOTE):
            with open(MANIFESTO_REMOTE) as f:
                data = json.load(f)
            manifest = {}
            for pkg_name, info in data.items():
                manifest[pkg_name] = Package(
                    name=pkg_name,
                    version=info.get("latest"),
                    url=info.get("url"),
                    update_policy=info.get("update_policy", "notify"),
                    group=info.get("group")
                )
            return manifest
        return {}

    # -------------------------
    # Verifica versões upstream
    # -------------------------
    def check_updates(self):
        updates = {}
        for name, pkg in self.installed_packages.items():
            if name in self.manifest:
                upstream = self.manifest[name]
                if pkg.version != upstream.version:
                    updates[name] = (pkg.version, upstream.version, upstream.update_policy, upstream.group)
        self.versions = updates
        return updates

    # -------------------------
    # Atualiza pacotes automaticamente
    # -------------------------
    def update_auto(self):
        for name, (old_ver, new_ver, policy, group) in self.versions.items():
            if policy == "auto":
                log(f"Updating {name}: {old_ver} → {new_ver} (group {group})")
                # Aqui chamaria o build do gerenciador para atualizar
                # build_package(stage, name, recipe, dep_mgr)
                self.installed_packages[name].version = new_ver
                # Registrar no PACKAGE_DB e logs
                log(f"{name} updated successfully")

    # -------------------------
    # Notifica pacotes críticos
    # -------------------------
    def notify(self):
        for name, (old_ver, new_ver, policy, group) in self.versions.items():
            if policy == "notify":
                log(f"CRITICAL PACKAGE: {name} has new version {new_ver} (installed {old_ver})")

    # -------------------------
    # Atualiza todos pacotes de um grupo
    # -------------------------
    def update_group(self, group_name):
        for name, (old_ver, new_ver, policy, group) in self.versions.items():
            if group == group_name and policy == "auto":
                log(f"Updating {name} in group {group_name}: {old_ver} → {new_ver}")
                # Aqui chamaria build_package
                self.installed_packages[name].version = new_ver
                log(f"{name} updated successfully")

# =========================
# Exemplo de uso
# =========================
if __name__ == "__main__":
    vt = VersionTracker()
    updates = vt.check_updates()
    vt.notify()        # Avisar pacotes críticos
    vt.update_auto()   # Atualizar pacotes automáticos
    vt.update_group("@desktop")  # Atualizar todos pacotes do grupo desktop
