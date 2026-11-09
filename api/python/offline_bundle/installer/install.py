# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""
Install the SK-RAFT Python client from this offline bundle.

The script does not use the network. It installs the wheels in the
wheelhouse directory of the bundle into a virtual environment:

- If a virtual environment is active, the script installs into it.
- Else it installs into the directory that --venv gives. It creates the
  virtual environment if it does not exist. The default is .venv in the
  current directory.

The script uses only the standard library. install.sh and install.bat start
it.

Usage:
    python install.py [--venv PATH]
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Optional, Sequence, TypedDict, cast

# The directory of the bundle.
_BUNDLE_DIR = Path(__file__).resolve().parent

# The directory of the bundle that holds the wheels.
_WHEELHOUSE = _BUNDLE_DIR / "wheelhouse"

# The file of the bundle that tells what the bundle contains.
_MANIFEST = _BUNDLE_DIR / "bundle.json"

# The modules that must import after the installation.
_CHECK_IMPORTS = "import skraft, grpc, google.protobuf"


class Target(TypedDict):
    """A platform of the bundle, as bundle.json gives it."""

    name: str
    os: str
    machines: list[str]


class Manifest(TypedDict):
    """The contents of bundle.json, which make_bundle.py writes."""

    skraft_version: str
    packages: list[str]
    python_versions: list[str]
    targets: list[Target]
    wheels: list[str]


class InstallError(Exception):
    """The client could not be installed."""


def load_manifest() -> Manifest:
    """
    Read the manifest of the bundle.

    Returns:
        Manifest: The contents of bundle.json.

    Raises:
        InstallError: If the bundle is not complete.
    """
    if not _MANIFEST.is_file() or not _WHEELHOUSE.is_dir():
        raise InstallError(
            f"the bundle in {_BUNDLE_DIR} is not complete; extract all of "
            "the archive again"
        )
    with _MANIFEST.open(encoding="utf-8") as f:
        return cast(Manifest, json.load(f))


def check_platform(manifest: Manifest) -> None:
    """
    Make sure that the bundle has wheels for this computer.

    Parameters:
        manifest (Manifest): The contents of bundle.json.

    Raises:
        InstallError: If the platform is not in the bundle.
    """
    machine = platform.machine().lower()
    targets = manifest["targets"]
    if not any(sys.platform == t["os"] and machine in t["machines"]
               for t in targets):
        raise InstallError(
            f"this bundle is for {', '.join(t['name'] for t in targets)}, "
            f"but this computer is {sys.platform} {machine}; make a "
            "bundle with --target for this computer"
        )


def find_supported_python(versions: Sequence[str]) -> Optional[list[str]]:
    """
    Find an installed Python interpreter that the bundle supports.

    On Windows, the script asks the py launcher. On Linux, it looks for
    python3.X on the PATH.

    Parameters:
        versions (Sequence[str]): The Python versions of the bundle, for
            example ["3.11", "3.12"].

    Returns:
        Optional[list[str]]: The command that starts the interpreter, or
            None if there is no supported interpreter.
    """
    for version in reversed(sorted(
        versions, key=lambda v: tuple(int(p) for p in v.split("."))
    )):
        if sys.platform == "win32":
            command = ["py", f"-{version}"]
        else:
            path = shutil.which(f"python{version}")
            if path is None:
                continue
            command = [path]
        try:
            result = subprocess.run(
                [*command, "-c", ""], check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            continue
        if result.returncode == 0:
            return command
    return None


def check_python(
    manifest: Manifest, argv: Sequence[str],
) -> Optional[int]:
    """
    Make sure that this Python version is in the bundle.

    If it is not, and no virtual environment is active, the script starts
    the installer again with a supported interpreter.

    Parameters:
        manifest (Manifest): The contents of bundle.json.
        argv (Sequence[str]): The arguments of the installer.

    Returns:
        Optional[int]: None if this interpreter is supported. Else the exit
            code of the installer that the supported interpreter ran.

    Raises:
        InstallError: If no supported interpreter is installed.
    """
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    versions = manifest["python_versions"]
    if version in versions:
        return None

    message = (
        f"this bundle is for Python {', '.join(versions)}, but this is "
        f"Python {version} ({sys.executable})"
    )
    if sys.prefix != sys.base_prefix:
        raise InstallError(
            f"{message}; the active virtual environment uses Python "
            f"{version}. Deactivate it, or make a bundle with "
            f"--python-version {version}"
        )
    command = find_supported_python(versions)
    if command is None:
        raise InstallError(
            f"{message}; install a supported Python, or make a bundle "
            f"with --python-version {version}"
        )
    print(f"Python {version} is not in the bundle. "
          f"Start the installer with {' '.join(command)}")
    return subprocess.run(
        [*command, str(Path(__file__).resolve()), *argv], check=False,
    ).returncode


def venv_python(venv_dir: Path) -> Path:
    """
    Get the Python interpreter of a virtual environment.

    Parameters:
        venv_dir (Path): The directory of the virtual environment.

    Returns:
        Path: The interpreter.
    """
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def prepare_venv(venv_dir: Optional[Path]) -> Path:
    """
    Get the interpreter to install into, and create the venv if necessary.

    Parameters:
        venv_dir (Optional[Path]): The virtual environment that --venv
            gives, or None.

    Returns:
        Path: The Python interpreter of the virtual environment.

    Raises:
        InstallError: If the virtual environment could not be created.
    """
    if venv_dir is None and sys.prefix != sys.base_prefix:
        print(f"Install into the active virtual environment {sys.prefix}")
        return Path(sys.executable)

    if venv_dir is None:
        venv_dir = Path.cwd() / ".venv"
    python = venv_python(venv_dir)
    if python.is_file():
        print(f"Install into the virtual environment {venv_dir}")
        return python

    print(f"Create the virtual environment {venv_dir}")
    try:
        venv.create(venv_dir, with_pip=True)
    except (OSError, subprocess.CalledProcessError) as e:
        raise InstallError(
            f"failed to create the virtual environment {venv_dir}: {e}. "
            "On Debian and Ubuntu, install the python3-venv package"
        ) from e
    return python


def install(python: Path, packages: Sequence[str]) -> None:
    """
    Install the packages from the wheelhouse, without the network.

    Parameters:
        python (Path): The interpreter of the virtual environment.
        packages (Sequence[str]): The packages to install.

    Raises:
        InstallError: If pip fails, or if the client does not import.
    """
    command = [
        str(python), "-m", "pip", "install",
        "--no-index", "--find-links", str(_WHEELHOUSE),
        "--disable-pip-version-check",
        *packages,
    ]
    print(f"Install {', '.join(packages)}")
    if subprocess.run(command, check=False).returncode != 0:
        raise InstallError("failed to install the packages (see the output)")

    check = subprocess.run(
        [str(python), "-c", _CHECK_IMPORTS], check=False,
    )
    if check.returncode != 0:
        raise InstallError("the client was installed, but it does not import")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Run the installer from the command line.

    Parameters:
        argv (Optional[Sequence[str]]): The arguments. If None, use the
            arguments of the process.

    Returns:
        int: The exit code. 0 if the client was installed.
    """
    parser = argparse.ArgumentParser(
        description="Install the SK-RAFT Python client without the network.",
    )
    parser.add_argument(
        "--venv", type=Path, default=None,
        help=(
            "the virtual environment to install into. The script creates it "
            "if it does not exist. Default: the active virtual environment, "
            "else .venv in the current directory."
        ),
    )
    # Show the messages in order with the output of pip, also in a pipe.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)

    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest()
        print(f"SK-RAFT client {manifest['skraft_version']}, offline bundle")
        check_platform(manifest)
        exit_code = check_python(manifest, argv)
        if exit_code is not None:
            return exit_code
        python = prepare_venv(
            args.venv.resolve() if args.venv is not None else None
        )
        install(python, manifest["packages"])
    except InstallError as e:
        print(f"Cannot install: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130

    venv_dir = python.parent.parent
    if sys.platform == "win32":
        activate = f"{venv_dir}\\Scripts\\activate"
    else:
        activate = f"source {venv_dir}/bin/activate"
    print("\nThe SK-RAFT client is installed. To use it, run:")
    print(f"    {activate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
