# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""
Build the documentation site of the SK-RAFT Python client.

The script makes a static HTML site from the Markdown files of the
repository. The folders of the repository become the sections of the
navigation. The README.md of a folder is the first page of its section.
The API reference is made from the docstrings of the client.

The site works on a web server and also from the disk (file://), with
search. The script writes the site to a folder and to a zip file. The
contents of the folder and of the zip file are the same.

The steps are:

1. Copy the Markdown files, and the files that they link to, into a
   temporary folder.
2. Make the navigation from the folders.
3. Run "mkdocs build --strict". A broken link stops the build.
4. Write the site folder and the zip file.

Usage: python build_docs.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path

import yaml

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# The directory of this script.
HERE = Path(__file__).resolve().parent

# The root of the repository.
REPO = HERE.parent.parent

# The directory of the skraft project. It contains pyproject.toml.
CLIENT_DIR = REPO / "api" / "python"

# The directory for the site folder and the zip file. Git ignores it.
OUTPUT_DIR = CLIENT_DIR / "dist"

# Folders that do not contain documentation.
EXCLUDED_DIRS = {".git", ".github", ".venv", "venv", "build", "dist"}

# The page of the API reference. The script replaces the page with one
# that mkdocstrings makes from the docstrings, so the links to it stay.
API_PAGE = Path("api/python/python_api_reference.md")

# The modules that the API reference shows.
API_MODULES = ("skraft.skraft_fpga", "skraft.datatypes", "skraft.exceptions")

# The pages to show as plain text. The licence text contains brackets,
# such as "[yyyy] [name of copyright owner]", that Markdown would read
# as links.
PLAIN_TEXT_PAGES = {Path("LICENSE.md")}

# The order of the items at the top of the navigation. Other items come
# after them, in alphabetical order.
TOP_LEVEL_ORDER = (
    "README.md",
    "get_started",
    "docs",
    "application_examples",
    "auxiliary_components",
    "api",
)

# The titles of the sections that have no README.md, or that need a
# different title.
SECTION_TITLES = {"docs": "Guides", "api": "API reference"}

# A relative link in Markdown, ](target), or in HTML, src="target" or
# href="target". The anchor (#...) is not a part of the target.
LINK = re.compile(r'(\]\(|src="|href=")([^)"#\s]+)')


# --------------------------------------------------------------------------- #
# Step 1: copy the pages
# --------------------------------------------------------------------------- #

def find_pages() -> list[Path]:
    """
    Find the Markdown files of the repository.

    Returns:
        list[Path]: The files, relative to the root of the repository.
    """
    pages = []
    for path in REPO.rglob("*.md"):
        relative = path.relative_to(REPO)
        if EXCLUDED_DIRS.isdisjoint(relative.parts):
            pages.append(relative)
    return sorted(pages)


def copy_file(relative: Path, docs: Path) -> None:
    """
    Copy a file of the repository into the docs folder.

    Parameters:
        relative (Path): The file, relative to the root of the repository.
        docs (Path): The docs folder.
    """
    target = docs / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / relative, target)


def write_folder_page(relative: Path, docs: Path) -> Path:
    """
    Make a page that lists the files of a folder, and copy the files.

    A link to a folder that has no README.md goes to this page.

    Parameters:
        relative (Path): The folder, relative to the root of the
            repository.
        docs (Path): The docs folder.

    Returns:
        Path: The page, relative to the root of the repository.
    """
    lines = [f"# {relative.as_posix()}", ""]
    for path in sorted((REPO / relative).iterdir()):
        if path.is_file():
            copy_file(relative / path.name, docs)
            lines.append(f"- [{path.name}]({path.name})")
    page = relative / "index.md"
    (docs / page).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return page


def fix_links(page: Path, text: str, docs: Path) -> str:
    """
    Prepare the links of a page for the site.

    - A link to a file that is not Markdown, for example a VHDL source:
      copy the file into the docs folder, so that the link works.
    - A link to a folder: change it into a link to the README.md of the
      folder, or to a page that lists the files of the folder.

    Links to web addresses and to anchors do not change. mkdocs reports
    the links that are broken.

    Parameters:
        page (Path): The page, relative to the root of the repository.
        text (str): The Markdown text of the page.
        docs (Path): The docs folder.

    Returns:
        str: The Markdown text with the changed links.
    """

    def fix(match: re.Match[str]) -> str:
        prefix, target = match.groups()
        if ":" in target or target.startswith("/"):
            return match.group(0)
        path = (REPO / page.parent / target).resolve()
        if not path.exists() or not path.is_relative_to(REPO):
            return match.group(0)

        relative = path.relative_to(REPO)
        if path.is_dir():
            index = relative / "README.md"
            if not (REPO / index).exists():
                index = write_folder_page(relative, docs)
            new_target = target.rstrip("/") + "/" + index.name
            return prefix + new_target
        if path.suffix != ".md":
            copy_file(relative, docs)
        return match.group(0)

    return LINK.sub(fix, text)


def write_api_page(docs: Path) -> None:
    """
    Write the page of the API reference.

    mkdocstrings changes each "::: module" line into the documentation of
    the module.

    Parameters:
        docs (Path): The docs folder.
    """
    lines = ["# Python API reference", ""]
    lines += [f"::: {module}\n" for module in API_MODULES]
    (docs / API_PAGE).write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Step 2: make the navigation
# --------------------------------------------------------------------------- #

def order_key(name: str) -> tuple[bool, int, list[str | int]]:
    """
    Get the sort key of an item of the navigation.

    README.md comes first. Then the items of TOP_LEVEL_ORDER, then the
    other items. Numbers sort by value, so example2 comes before
    example10.

    Parameters:
        name (str): The name of the file or folder.

    Returns:
        tuple[bool, int, list[str | int]]: The sort key.
    """
    rank = (TOP_LEVEL_ORDER.index(name) if name in TOP_LEVEL_ORDER
            else len(TOP_LEVEL_ORDER))
    natural = [int(part) if part.isdigit() else part.lower()
               for part in re.split(r"(\d+)", name)]
    return name != "README.md", rank, natural


def first_heading(page: Path) -> str | None:
    """
    Get the first level-1 heading of a page.

    Parameters:
        page (Path): The page, relative to the root of the repository.

    Returns:
        str | None: The heading, or None if the page has none.
    """
    text = (REPO / page).read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def make_nav(pages: list[Path], folder: Path = Path(".")) -> list[object]:
    """
    Make the navigation of a folder from its pages and subfolders.

    Parameters:
        pages (list[Path]): All the pages, relative to the root of the
            repository.
        folder (Path): The folder.

    Returns:
        list[object]: The navigation, in the format of the "nav" setting
            of mkdocs.
    """
    names = set()
    for page in pages:
        if page.parent == folder or folder in page.parents:
            names.add(page.relative_to(folder).parts[0])

    nav: list[object] = []
    for name in sorted(names, key=order_key):
        path = folder / name
        if name.endswith(".md"):
            nav.append(path.as_posix())
            continue
        children = make_nav(pages, path)
        # A folder with only one page shows the page, not a section.
        if len(children) == 1:
            nav.append(children[0])
            continue
        title = SECTION_TITLES.get(name)
        if title is None and (REPO / path / "README.md").exists():
            title = first_heading(path / "README.md")
        nav.append({title or name: children})
    return nav


# --------------------------------------------------------------------------- #
# Steps 3 and 4: build the site, and write the folder and the zip file
# --------------------------------------------------------------------------- #

def build_site(work: Path, nav: list[object]) -> Path:
    """
    Run mkdocs on the docs folder.

    Parameters:
        work (Path): The temporary folder. It contains the docs folder.
        nav (list[object]): The navigation.

    Returns:
        Path: The folder of the built site.

    Raises:
        RuntimeError: If mkdocs fails.
    """
    with (HERE / "mkdocs.yml").open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    config["docs_dir"] = str(work / "docs")
    config["site_dir"] = str(work / "site")
    config["nav"] = nav
    for plugin in config["plugins"]:
        if isinstance(plugin, dict) and "mkdocstrings" in plugin:
            python = plugin["mkdocstrings"]["handlers"]["python"]
            python["paths"] = [str(CLIENT_DIR)]

    config_file = work / "mkdocs.yml"
    config_file.write_text(yaml.safe_dump(config), encoding="utf-8")
    command = [sys.executable, "-m", "mkdocs", "build", "--strict",
               "--config-file", str(config_file)]
    if subprocess.run(command, check=False).returncode != 0:
        raise RuntimeError("mkdocs failed (see the output)")
    return work / "site"


def client_version() -> str:
    """Get the version of the client from its pyproject.toml."""
    with (CLIENT_DIR / "pyproject.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def write_output(site: Path) -> tuple[Path, Path]:
    """
    Write the site to the output folder and to a zip file.

    The script adds an empty .nojekyll file. It tells GitHub Pages to
    publish the files as they are. It also adds the files of the launcher
    folder: a README.txt and a script that serves the site on this
    computer, for browsers that cannot open the site from the disk.

    Parameters:
        site (Path): The folder of the built site.

    Returns:
        tuple[Path, Path]: The site folder and the zip file.
    """
    (site / ".nojekyll").touch()
    shutil.copytree(HERE / "launcher", site, dirs_exist_ok=True)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    folder = OUTPUT_DIR / "docs"
    shutil.rmtree(folder, ignore_errors=True)
    shutil.copytree(site, folder)

    archive = OUTPUT_DIR / f"skraft-docs-{client_version()}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(site.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(site).as_posix())
    return folder, archive


def main() -> int:
    """
    Build the documentation site.

    Returns:
        int: The exit code. 0 if the site was built.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        docs = work / "docs"

        pages = find_pages()
        for page in pages:
            text = (REPO / page).read_text(encoding="utf-8")
            if page in PLAIN_TEXT_PAGES:
                text = f"# {page.stem}\n\n```text\n{text}\n```\n"
            target = docs / page
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(fix_links(page, text, docs), encoding="utf-8")
        write_api_page(docs)
        shutil.copytree(HERE / "vendor", docs / "vendor")

        try:
            site = build_site(work, make_nav(pages))
        except RuntimeError as e:
            print(f"Cannot build the documentation: {e}", file=sys.stderr)
            return 1
        folder, archive = write_output(site)

    print(f"Site:     {folder / 'index.html'}")
    print(f"Zip file: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
