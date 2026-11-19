"""Dateieinstieg für PyInstaller; regulärer Start über python -m stadtmeisterschaft."""
from stadtmeisterschaft.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
