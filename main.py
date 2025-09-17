import argparse
from core import build, search, revdep, updater, groups, database

def main():
    parser = argparse.ArgumentParser(prog="pm", description="Gerenciador de Pacotes em Python")
    subparsers = parser.add_subparsers(dest="command")

    # Install
    sp_install = subparsers.add_parser("install", aliases=["i"])
    sp_install.add_argument("package")

    # Remove
    sp_remove = subparsers.add_parser("remove", aliases=["rm"])
    sp_remove.add_argument("package")

    # Search
    sp_search = subparsers.add_parser("search", aliases=["s"])
    sp_search.add_argument("query")

    # Info
    sp_info = subparsers.add_parser("info", aliases=["if"])
    sp_info.add_argument("package")

    # Rebuild
    sp_rebuild = subparsers.add_parser("rebuild", aliases=["rb"])
    sp_rebuild.add_argument("target", help="'system' ou nome do pacote")

    # Revdep
    subparsers.add_parser("revdep", aliases=["rd"])

    # Upgrade
    subparsers.add_parser("upgrade", aliases=["up"])

    # Orphans
    subparsers.add_parser("orphans", aliases=["or"])

    # Groups
    sp_group = subparsers.add_parser("group", aliases=["g"])
    sp_group.add_argument("action", choices=["install", "remove", "list"])
    sp_group.add_argument("group_name", nargs="?")

    args = parser.parse_args()

    if args.command in ("install", "i"):
        build.install(args.package)
    elif args.command in ("remove", "rm"):
        build.remove(args.package)
    elif args.command in ("search", "s"):
        search.run(args.query)
    elif args.command in ("info", "if"):
        search.info(args.package)
    elif args.command in ("rebuild", "rb"):
        if args.target == "system":
            build.rebuild_system()
        else:
            build.rebuild_package(args.target)
    elif args.command in ("revdep", "rd"):
        revdep.run()
    elif args.command in ("upgrade", "up"):
        updater.run()
    elif args.command in ("orphans", "or"):
        build.remove_orphans()
    elif args.command in ("group", "g"):
        groups.handle(args.action, args.group_name)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
