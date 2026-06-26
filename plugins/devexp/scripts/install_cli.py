#!/usr/bin/env python3
"""Install the devexp CLI and make the command available on PATH."""

from __future__ import annotations

import argparse
import os
import shutil
import site
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_GITHUB_PACKAGE = "git+https://github.com/Ansein/devexp.git"


def run(cmd: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(cmd))
    return subprocess.run(list(cmd), check=check, text=True)


def probe(cmd: Sequence[str]) -> bool:
    result = subprocess.run(
        list(cmd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode == 0


def pipx_command() -> list[str] | None:
    pipx = shutil.which("pipx")
    if pipx:
        return [pipx]
    if probe([sys.executable, "-m", "pipx", "--version"]):
        return [sys.executable, "-m", "pipx"]
    return None


def ensure_pipx(*, bootstrap: bool) -> list[str] | None:
    command = pipx_command()
    if command:
        return command
    if not bootstrap:
        return None

    print("pipx was not found; installing pipx into the current Python user environment.")
    run([sys.executable, "-m", "pip", "install", "--user", "pipx"])
    command = pipx_command()
    if command:
        return command
    raise RuntimeError("pipx installation completed, but python -m pipx is still unavailable.")


def find_source_checkout() -> Path | None:
    script = Path(__file__).resolve()
    candidates: list[Path] = []
    candidates.extend(script.parents)
    candidates.append(Path.cwd().resolve())

    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "record-engineering-experience" / "SKILL.md"
        ).is_file():
            return candidate
    return None


def resolve_package_source(source_mode: str, github_package: str) -> str:
    checkout = find_source_checkout()

    if source_mode == "local":
        if not checkout:
            raise RuntimeError("Could not find a local devexp source checkout.")
        return str(checkout)

    if source_mode == "github":
        return github_package

    if checkout:
        return str(checkout)
    return github_package


def pipx_bin_candidates(pipx_cmd: Sequence[str]) -> Iterable[Path]:
    result = subprocess.run(
        list(pipx_cmd) + ["environment", "--value", "PIPX_BIN_DIR"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        yield Path(result.stdout.strip()).expanduser()

    env_bin = os.environ.get("PIPX_BIN_DIR")
    if env_bin:
        yield Path(env_bin).expanduser()

    yield Path.home() / ".local" / "bin"


def user_script_candidates() -> Iterable[Path]:
    yield Path(site.USER_BASE) / ("Scripts" if os.name == "nt" else "bin")
    yield Path.home() / ".local" / "bin"


def find_devexp(extra_dirs: Iterable[Path] = ()) -> Path | None:
    command = shutil.which("devexp")
    if command:
        return Path(command)

    names = ["devexp.exe", "devexp.cmd", "devexp.bat", "devexp"] if os.name == "nt" else ["devexp"]
    for directory in extra_dirs:
        for name in names:
            candidate = directory / name
            if candidate.exists():
                return candidate
    return None


def install_with_pipx(pipx_cmd: Sequence[str], package_source: str, *, force: bool) -> list[Path]:
    cmd = list(pipx_cmd) + ["install"]
    if force:
        cmd.append("--force")
    cmd.append(package_source)
    run(cmd)
    run(list(pipx_cmd) + ["ensurepath"], check=False)
    return list(pipx_bin_candidates(pipx_cmd))


def install_with_pip_user(package_source: str) -> list[Path]:
    run([sys.executable, "-m", "pip", "install", "--user", "--upgrade", package_source])
    return list(user_script_candidates())


def run_doctor(devexp_path: Path) -> None:
    print("\nRunning devexp doctor:")
    run([str(devexp_path), "doctor"], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the devexp CLI into PATH.")
    parser.add_argument(
        "--source",
        choices=["auto", "local", "github"],
        default="auto",
        help="Install from the local checkout when available, or from GitHub.",
    )
    parser.add_argument(
        "--github-package",
        default=DEFAULT_GITHUB_PACKAGE,
        help="Package spec used when installing from GitHub.",
    )
    parser.add_argument(
        "--method",
        choices=["auto", "pipx", "pip-user"],
        default="auto",
        help="Installer backend. auto prefers pipx and falls back to pip --user.",
    )
    parser.add_argument(
        "--no-bootstrap-pipx",
        action="store_true",
        help="Do not install pipx automatically when it is missing.",
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="Do not pass --force to pipx install.",
    )
    parser.add_argument(
        "--skip-doctor",
        action="store_true",
        help="Do not run devexp doctor after installation.",
    )
    args = parser.parse_args()

    package_source = resolve_package_source(args.source, args.github_package)
    print(f"Installing devexp from: {package_source}")

    extra_dirs: list[Path] = []

    if args.method in {"auto", "pipx"}:
        pipx_cmd = ensure_pipx(bootstrap=not args.no_bootstrap_pipx)
        if pipx_cmd:
            extra_dirs = install_with_pipx(pipx_cmd, package_source, force=not args.no_force)
        elif args.method == "pipx":
            print("pipx is required but was not found.", file=sys.stderr)
            return 1
        else:
            print("pipx is unavailable; falling back to python -m pip install --user.")
            extra_dirs = install_with_pip_user(package_source)
    else:
        extra_dirs = install_with_pip_user(package_source)

    devexp_path = find_devexp(extra_dirs)
    if not devexp_path:
        print("\ndevexp was installed, but the command is not visible on PATH yet.", file=sys.stderr)
        print("Candidate script directories:", file=sys.stderr)
        for directory in extra_dirs:
            print(f"  {directory}", file=sys.stderr)
        print("Restart the terminal or Codex session after PATH changes take effect.", file=sys.stderr)
        return 2

    print(f"\ndevexp command: {devexp_path}")
    if not args.skip_doctor:
        run_doctor(devexp_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
