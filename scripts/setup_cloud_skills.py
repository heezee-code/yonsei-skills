#!/usr/bin/env python3
"""Expose bundled skills through Codex's repository-local discovery directory."""
from pathlib import Path
import os


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    destination = root / ".agents" / "skills"
    destination.mkdir(parents=True, exist_ok=True)
    sources = sorted(root.glob("plugins/*/skills/*/SKILL.md"))
    for definition in sources:
        source = definition.parent
        link = destination / source.name
        if link.is_symlink() and link.resolve() == source.resolve():
            continue
        if link.exists() or link.is_symlink():
            raise SystemExit(f"Refusing to replace existing skill: {link}")
        link.symlink_to(os.path.relpath(source, destination), target_is_directory=True)
    print(f"Prepared {len(sources)} repository-local skills in {destination}")


if __name__ == "__main__":
    main()
