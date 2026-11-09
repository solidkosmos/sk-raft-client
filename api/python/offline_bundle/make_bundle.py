# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""
Make an offline installation bundle of the SK-RAFT Python client.

Run this script on a computer that has internet access. The script builds
the skraft wheel, downloads the wheels of its dependencies for each target
platform and Python version, and writes one archive. Copy the archive to
the computer that has no internet access, extract it, and run the installer
in it: install.sh on Linux, install.bat on Windows.

The wheels of grpcio contain compiled code. Thus each target platform and
each Python version of the computer without internet access must be in the
bundle.

Usage:
    python make_bundle.py --target linux-x86_64 --target windows-amd64 \\
        --python-version 3.11 --python-version 3.12
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from email.parser import HeaderParser
from pathlib import Path
from typing import Optional, Sequence

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# The directory of this script.
_HERE = Path(__file__).resolve().parent

# The directory of the skraft project. It contains pyproject.toml.
_PROJECT_DIR = _HERE.parent

# The directory that contains the installer files of the bundle.
_INSTALLER_DIR = _HERE / "installer"

# The default directory for the archive. Git ignores it.
_DEFAULT_OUTPUT_DIR = _PROJECT_DIR / "dist"

# The packages that the examples of this repository use in addition to the
# client. pyserial gives the "serial" module.
_EXAMPLE_PACKAGES = ("pyserial",)

# The name of the directory in the bundle that holds the wheels.
_WHEELHOUSE = "wheelhouse"

# The name of the file in the bundle that tells what the bundle contains.
_MANIFEST = "bundle.json"

_log = logging.getLogger("make_bundle")


# --------------------------------------------------------------------------- #
# Targets
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Target:
    """
    A platform that the bundle can install on.

    Attributes:
        name (str): The name of the target on the command line.
        pip_platform (str): The platform tag that pip downloads wheels for.
        os_name (str): The value of sys.platform on the target.
        machines (tuple[str, ...]): The values of platform.machine() on the
            target, in lower case.
        archive_format (str): The archive format that the target opens
            without other tools: "zip" or "tar.gz".
    """

    name: str
    pip_platform: str
    os_name: str
    machines: tuple[str, ...]
    archive_format: str


# The targets that the bundle supports. manylinux2014 needs glibc 2.17 or
# later, so the Linux bundles also install on old distributions. pip also
# accepts the older manylinux tags when it gets manylinux2014.
TARGETS: dict[str, Target] = {
    t.name: t
    for t in (
        Target(
            "linux-x86_64", "manylinux2014_x86_64", "linux",
            ("x86_64", "amd64"), "tar.gz",
        ),
        Target(
            "linux-aarch64", "manylinux2014_aarch64", "linux",
            ("aarch64", "arm64"), "tar.gz",
        ),
        Target(
            "windows-amd64", "win_amd64", "win32",
            ("amd64", "x86_64"), "zip",
        ),
    )
}


class BundleError(Exception):
    """The bundle could not be made."""


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #

def _run_pip(args: Sequence[str]) -> None:
    """
    Run pip of this Python interpreter.

    Parameters:
        args (Sequence[str]): The arguments of pip.

    Raises:
        BundleError: If pip fails.
    """
    command = [sys.executable, "-m", "pip", *args]
    _log.debug("run: %s", " ".join(command))
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise BundleError(f"failed to run pip {args[0]} (see the output)")


def build_client_wheel(wheelhouse: Path) -> Path:
    """
    Build the wheel of the skraft client.

    Parameters:
        wheelhouse (Path): The directory to write the wheel to.

    Returns:
        Path: The wheel file.

    Raises:
        BundleError: If the wheel could not be built.
    """
    _log.info("Build the skraft wheel from %s", _PROJECT_DIR)
    with tempfile.TemporaryDirectory() as tmp:
        _run_pip([
            "wheel", "--no-deps", "--quiet", "--wheel-dir", tmp,
            str(_PROJECT_DIR),
        ])
        wheels = list(Path(tmp).glob("skraft-*.whl"))
        if len(wheels) != 1:
            raise BundleError("failed to find the built skraft wheel")
        wheel = wheelhouse / wheels[0].name
        shutil.move(str(wheels[0]), str(wheel))
    return wheel


def read_wheel_metadata(wheel: Path) -> tuple[str, list[str]]:
    """
    Read the version and the dependencies of a wheel.

    Parameters:
        wheel (Path): The wheel file.

    Returns:
        tuple[str, list[str]]: The version and the requirements of the
            dependencies, without the ones for extras.

    Raises:
        BundleError: If the wheel has no METADATA file.
    """
    with zipfile.ZipFile(wheel) as zf:
        names = [n for n in zf.namelist()
                 if n.endswith(".dist-info/METADATA")]
        if not names:
            raise BundleError(f"failed to find the metadata of {wheel.name}")
        text = zf.read(names[0]).decode("utf-8")
    metadata = HeaderParser().parsestr(text)
    requirements = [
        r for r in metadata.get_all("Requires-Dist") or []
        if "extra ==" not in r
    ]
    return metadata["Version"], requirements


def download_wheels(
    wheelhouse: Path,
    requirements: Sequence[str],
    target: Target,
    python_version: str,
) -> None:
    """
    Download the wheels of the requirements for one target.

    Only binary wheels are accepted, so the target does not need a compiler.

    Parameters:
        wheelhouse (Path): The directory to write the wheels to.
        requirements (Sequence[str]): The requirements to download, for
            example "grpcio" or "protobuf==5.29.3".
        target (Target): The target platform.
        python_version (str): The Python version of the target, for
            example "3.11".

    Raises:
        BundleError: If a wheel could not be downloaded.
    """
    _log.info("Download the wheels for %s, Python %s",
              target.name, python_version)
    _run_pip([
        "download", "--quiet",
        "--dest", str(wheelhouse),
        "--only-binary=:all:",
        "--platform", target.pip_platform,
        "--python-version", python_version,
        "--implementation", "cp",
        *requirements,
    ])


def check_offline_install(
    wheelhouse: Path,
    packages: Sequence[str],
    target: Target,
    python_version: str,
) -> None:
    """
    Make sure that pip can install the packages from the wheelhouse only.

    pip resolves the packages without network access, as the installer
    does. It does not install them.

    Parameters:
        wheelhouse (Path): The directory with the wheels.
        packages (Sequence[str]): The packages that the installer installs.
        target (Target): The target platform.
        python_version (str): The Python version of the target.

    Raises:
        BundleError: If a wheel is missing.
    """
    _log.info("Check the bundle for %s, Python %s",
              target.name, python_version)
    with tempfile.TemporaryDirectory() as tmp:
        _run_pip([
            "install", "--quiet", "--dry-run",
            "--no-index", "--find-links", str(wheelhouse),
            "--only-binary=:all:",
            "--platform", target.pip_platform,
            "--python-version", python_version,
            "--implementation", "cp",
            "--target", tmp,
            *packages,
        ])


def write_archive(source: Path, archive: Path, archive_format: str) -> None:
    """
    Write a directory to an archive.

    The archive contains the directory itself, not only its contents. The
    archive is first written to a temporary file, so that a failure does
    not leave a part of an archive.

    Parameters:
        source (Path): The directory to put in the archive.
        archive (Path): The archive file to write.
        archive_format (str): "zip" or "tar.gz".
    """
    tmp = archive.with_name(archive.name + ".part")
    files = sorted(p for p in source.rglob("*") if p.is_file())
    if archive_format == "zip":
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                zf.write(path, path.relative_to(source.parent).as_posix())
    else:
        with tarfile.open(tmp, "w:gz") as tf:
            tf.add(source, arcname=source.name)
    tmp.replace(archive)


def make_bundle(
    targets: Sequence[Target],
    python_versions: Sequence[str],
    output_dir: Path,
    extra_requirements: Sequence[str],
    archive_format: Optional[str],
) -> Path:
    """
    Make the offline installation bundle.

    Parameters:
        targets (Sequence[Target]): The target platforms.
        python_versions (Sequence[str]): The Python versions of the
            targets, for example ["3.11", "3.12"].
        output_dir (Path): The directory to write the archive to.
        extra_requirements (Sequence[str]): The requirements to install in
            addition to skraft and its dependencies.
        archive_format (Optional[str]): "zip" or "tar.gz". If None, use zip
            when a target is Windows, else tar.gz.

    Returns:
        Path: The archive.

    Raises:
        BundleError: If the bundle could not be made.
    """
    pip_check = subprocess.run(
        [sys.executable, "-m", "pip", "--version"], check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if pip_check.returncode != 0:
        raise BundleError(
            f"pip is not installed for {sys.executable}; run this script "
            "with the Python of a virtual environment"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_dir) as tmp:
        staging = Path(tmp) / "bundle"
        wheelhouse = staging / _WHEELHOUSE
        wheelhouse.mkdir(parents=True)

        client_wheel = build_client_wheel(wheelhouse)
        version, client_requirements = read_wheel_metadata(client_wheel)
        requirements = [*client_requirements, *extra_requirements]
        packages = ["skraft", *extra_requirements]

        for target in targets:
            for python_version in python_versions:
                download_wheels(
                    wheelhouse, requirements, target, python_version,
                )
                check_offline_install(
                    wheelhouse, packages, target, python_version,
                )

        for name in ("install.py", "install.sh", "install.bat",
                     "README.txt"):
            shutil.copy2(_INSTALLER_DIR / name, staging / name)
        (staging / "install.sh").chmod(0o755)

        manifest = {
            "skraft_version": version,
            "packages": packages,
            "python_versions": list(python_versions),
            "targets": [
                {
                    "name": t.name,
                    "os": t.os_name,
                    "machines": list(t.machines),
                }
                for t in targets
            ],
            "wheels": sorted(p.name for p in wheelhouse.iterdir()),
        }
        (staging / _MANIFEST).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
        )

        if archive_format is None:
            archive_format = (
                "zip" if any(t.archive_format == "zip" for t in targets)
                else "tar.gz"
            )
        name = "skraft-offline-{}-{}-py{}".format(
            version,
            "+".join(t.name for t in targets),
            "+".join(python_versions),
        )
        bundle_dir = staging.rename(staging.with_name(name))
        archive = output_dir / f"{name}.{archive_format}"
        _log.info("Write %s", archive)
        write_archive(bundle_dir, archive, archive_format)
    return archive


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #

def _current_python_version() -> str:
    """Return the version of this Python interpreter, for example "3.12"."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _current_target() -> Optional[str]:
    """Return the name of the target of this computer, or None."""
    machine = platform.machine().lower()
    for target in TARGETS.values():
        if sys.platform == target.os_name and machine in target.machines:
            return target.name
    return None


def _python_version(text: str) -> str:
    """Check a Python version argument, for example "3.11"."""
    parts = text.split(".")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise argparse.ArgumentTypeError(
            f"'{text}' is not a Python version such as 3.11"
        )
    return text


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Run the bundler from the command line.

    Parameters:
        argv (Optional[Sequence[str]]): The arguments. If None, use the
            arguments of the process.

    Returns:
        int: The exit code. 0 if the bundle was made.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Make an offline installation bundle of the SK-RAFT Python "
            "client."
        ),
    )
    parser.add_argument(
        "--target", action="append", choices=sorted(TARGETS),
        help=(
            "a platform of the computer without internet access. Repeat "
            "for more platforms. Default: the platform of this computer."
        ),
    )
    parser.add_argument(
        "--python-version", action="append", type=_python_version,
        help=(
            "a Python version of the computer without internet access, for "
            "example 3.11. Repeat for more versions. Default: the version "
            "that runs this script."
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR,
        help=f"the directory for the archive. Default: {_DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--format", choices=("zip", "tar.gz"), default=None,
        help=(
            "the archive format. Default: zip if a target is Windows, else "
            "tar.gz."
        ),
    )
    parser.add_argument(
        "--requirements", type=Path, default=None,
        help=(
            "a requirements file with pinned versions, for example from "
            "pip freeze. It replaces the packages that the examples need."
        ),
    )
    parser.add_argument(
        "--no-example-packages", action="store_true",
        help=(
            "do not add the packages that the examples need "
            f"({', '.join(_EXAMPLE_PACKAGES)})."
        ),
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="show the commands that the script runs.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    target_names = args.target
    if not target_names:
        current = _current_target()
        if current is None:
            parser.error("cannot find the platform of this computer; "
                         "use --target")
        target_names = [current]
    targets = [TARGETS[n] for n in dict.fromkeys(target_names)]
    python_versions = list(
        dict.fromkeys(args.python_version or [_current_python_version()])
    )

    extra_requirements: list[str] = []
    if args.requirements is not None:
        try:
            lines = args.requirements.read_text(encoding="utf-8")
        except OSError as e:
            parser.error(f"cannot read {args.requirements}: {e}")
        extra_requirements = [
            line.strip() for line in lines.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", "-"))
            and not line.strip().lower().startswith("skraft")
        ]
    elif not args.no_example_packages:
        extra_requirements = list(_EXAMPLE_PACKAGES)

    try:
        archive = make_bundle(
            targets, python_versions, args.output_dir.resolve(),
            extra_requirements, args.format,
        )
    except BundleError as e:
        _log.error("Cannot make the bundle: %s", e)
        return 1
    except KeyboardInterrupt:
        _log.error("Interrupted.")
        return 130

    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
