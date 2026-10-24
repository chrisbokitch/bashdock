"""Absolute-import entry point used by the executable builder."""
import sys

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--shell-smoke-test":
        from gitbasher.packaged_smoke import run
        sys.exit(run(sys.argv[2]))
    else:
        from gitbasher.app import main
        main()
