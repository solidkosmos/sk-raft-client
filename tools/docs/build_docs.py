# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 SOLIDKOSMOS S.A.

"""
Build the documentation of the SK-RAFT Python client as one HTML file.

The script makes the documentation from the Markdown files of the
repository. The folders of the repository become the sections of the
navigation. The README.md of a folder is the first page of its section.
The API reference is made from the docstrings of the client.

The result is one HTML file that contains all the pages, the styles, the
images and a search. It needs no other file and no internet, so a
browser can open it from the disk, also from a sandbox (Flatpak, Snap).

The steps are:

1. Copy the Markdown files, and the files that they link to, into a
   temporary folder.
2. Make the navigation from the folders.
3. Run "mkdocs build --strict". A broken link stops the build.
4. Join the pages of the site, with the files of template/, into one
   HTML file.

Usage: python build_docs.py
"""

from __future__ import annotations

import base64
import json
import mimetypes
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from html import escape
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

import yaml
from bs4 import BeautifulSoup, Tag

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# The directory of this script.
HERE = Path(__file__).resolve().parent

# The root of the repository.
REPO = HERE.parent.parent

# The directory of the skraft project. It contains pyproject.toml.
CLIENT_DIR = REPO / "api" / "python"

# The directory for the HTML file. Git ignores it.
OUTPUT_DIR = CLIENT_DIR / "dist"

# The folder of the template of the HTML file: page.html, page.css and
# page.js.
TEMPLATE_DIR = HERE / "template"

# The stylesheets of the site that the HTML file contains, relative to
# the site folder.
THEME_CSS = (
    "assets/stylesheets/main.*.min.css",
    "assets/stylesheets/palette.*.min.css",
    "assets/_mkdocstrings.css",
)

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

# A link to another web site: with a scheme (https:, mailto:, data:) or
# with a host (//host/path).
EXTERNAL = re.compile(r"^([a-z][a-z0-9+.-]*:|//)", re.IGNORECASE)

# The link from a stylesheet to its source map. The HTML file has no
# source maps.
SOURCE_MAP = re.compile(r"/\*# sourceMappingURL=[^*]*\*/")

# A {{name}} in the template.
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


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
# Step 3: build the site
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


# --------------------------------------------------------------------------- #
# Step 4: join the pages into one HTML file
# --------------------------------------------------------------------------- #

def md_to_html(page: str) -> str:
    """
    Get the name of the HTML page that mkdocs makes from a Markdown page.

    Parameters:
        page (str): The Markdown page, relative to the docs folder.

    Returns:
        str: The HTML page, relative to the site folder.
    """
    path = PurePosixPath(page)
    stem = "index" if path.name in ("README.md", "index.md") else path.stem
    return str(path.with_name(stem + ".html"))


def data_uri(path: Path) -> str:
    """
    Get a data: address that contains a file.

    Parameters:
        path (Path): The file.

    Returns:
        str: The address.
    """
    media_type = mimetypes.guess_type(path.name)[0]
    if path.suffix == ".svg":
        media_type = "image/svg+xml"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type or 'application/octet-stream'};base64,{data}"


def plain_text(html: str) -> str:
    """
    Get the text of an HTML fragment, without the tags.

    Parameters:
        html (str): The HTML fragment.

    Returns:
        str: The text, with single spaces between the words.
    """
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return " ".join(text.split())


class SiteJoiner:
    """
    Join the pages of a built site into one HTML file.

    Each page becomes a <section> of the file. The id of the section comes
    from the address of the page, for example "get_started-index" for
    get_started/index.html. The ids in a page get the id of the page as a
    prefix ("get_started-index--quick-start"), because two pages can have
    the same id. The links change to these ids. The images become data:
    addresses. A file that a page links to and that is not a page, for
    example a VHDL source, becomes a section that shows its text.

    Parameters:
        site (Path): The folder of the built site.
        nav (list[object]): The navigation, in the format of the "nav"
            setting of mkdocs.
    """

    def __init__(self, site: Path, nav: list[object]) -> None:
        self.site = site
        self.nav = nav
        self.pages = {
            path.relative_to(site).as_posix(): ""
            for path in sorted(site.rglob("*.html"))
            if path.relative_to(site).as_posix() != "404.html"
        }
        for url in self.pages:
            self.pages[url] = url.removesuffix(".html").replace("/", "-")
        self.titles: dict[str, str] = {}
        self.sources: dict[str, str] = {}

    def source_id(self, url: str) -> str:
        """Get the section id of a file that is not a page."""
        if url not in self.sources:
            self.sources[url] = "file-" + url.replace("/", "-")
        return self.sources[url]

    def resolve(self, base: str, href: str) -> str | None:
        """
        Get the new target of a link.

        Parameters:
            base (str): The page that contains the link, relative to the
                site folder.
            href (str): The target of the link.

        Returns:
            str | None: The new target, or None if the link does not
                change: it goes to another web site, or to a file that
                does not exist.
        """
        if EXTERNAL.match(href):
            return None
        path, _, anchor = href.partition("#")
        url = base
        if path:
            url = posixpath.normpath(
                posixpath.join(posixpath.dirname(base), unquote(path)))
        if url in self.pages:
            page = self.pages[url]
            return f"#{page}--{anchor}" if anchor else f"#{page}"
        if (self.site / url).is_file():
            return "#" + self.source_id(url)
        print(f"Warning: {base}: no target for the link {href}",
              file=sys.stderr)
        return None

    def page_section(self, url: str) -> str:
        """
        Get the section of a page.

        Parameters:
            url (str): The page, relative to the site folder.

        Returns:
            str: The HTML of the section.

        Raises:
            RuntimeError: If the page has no content.
        """
        page = self.pages[url]
        soup = BeautifulSoup((self.site / url).read_text(encoding="utf-8"),
                             "html.parser")
        article = soup.find("article")
        if not isinstance(article, Tag):
            raise RuntimeError(f"{url} has no <article> element")

        for tag in article.find_all(id=True):
            tag["id"] = f"{page}--{tag['id']}"
        for tag in article.find_all("a", href=True):
            target = self.resolve(url, str(tag["href"]))
            if target is not None:
                tag["href"] = target
        for tag in article.find_all("img", src=True):
            src = str(tag["src"])
            path = posixpath.normpath(
                posixpath.join(posixpath.dirname(url), unquote(src)))
            if not EXTERNAL.match(src) and (self.site / path).is_file():
                tag["src"] = data_uri(self.site / path)

        heading = article.find("h1")
        title = heading.get_text().rstrip("¶").strip() if heading else ""
        self.titles[page] = title or url
        return (f'<section class="sk-page" id="{page}" '
                f'data-title="{escape(self.titles[page])}">\n'
                f'<div class="md-typeset">\n{article.decode_contents()}\n'
                "</div>\n</section>")

    def source_section(self, url: str) -> tuple[str, str]:
        """
        Get the section of a file that is not a page.

        A text file shows its text. An image shows the image. Another file
        has a link that saves it.

        Parameters:
            url (str): The file, relative to the site folder.

        Returns:
            tuple[str, str]: The HTML of the section, and the text of the
                file for the search ("" if it is not text).
        """
        path = self.site / url
        text = ""
        name = escape(path.name)
        media_type = mimetypes.guess_type(path.name)[0] or ""
        if path.suffix == ".svg" or media_type.startswith("image/"):
            body = f'<p><img src="{data_uri(path)}" alt="{name}"></p>'
        else:
            try:
                text = path.read_text(encoding="utf-8")
                body = f"<pre><code>{escape(text)}</code></pre>"
            except UnicodeDecodeError:
                body = (f'<p><a href="{data_uri(path)}" '
                        f'download="{name}">Save the file</a></p>')
        section = (f'<section class="sk-page" id="{self.sources[url]}" '
                   f'data-title="{name}">\n'
                   f'<div class="md-typeset">\n<h1>{name}</h1>\n'
                   f'<p class="sk-source-path">{escape(url)}</p>\n{body}\n'
                   "</div>\n</section>")
        return section, text

    def nav_html(self, items: list[object]) -> str:
        """
        Get the HTML of the navigation.

        Parameters:
            items (list[object]): The items of a level of the navigation.

        Returns:
            str: The HTML list.
        """
        lines = ["<ul>"]
        for item in items:
            if isinstance(item, str):
                page = self.pages[md_to_html(item)]
                lines.append(f'<li><a href="#{page}">'
                             f"{escape(self.titles[page])}</a></li>")
            elif isinstance(item, dict):
                for title, children in item.items():
                    lines.append(f"<li><details><summary>{escape(title)}"
                                 f"</summary>{self.nav_html(children)}"
                                 "</details></li>")
        lines.append("</ul>")
        return "\n".join(lines)

    def search_index(self, source_texts: dict[str, str]) -> str:
        """
        Get the search index, as JSON for a <script> element.

        Parameters:
            source_texts (dict[str, str]): The text of each file that is
                not a page, by section id.

        Returns:
            str: A JSON list of [target id, title, page title, text].
        """
        with (self.site / "search" / "search_index.json").open(
                encoding="utf-8") as f:
            docs = json.load(f)["docs"]
        index = []
        for doc in docs:
            location = doc["location"] or "index.html"
            target = self.resolve("index.html", location)
            if target is None:
                continue
            page = target[1:].split("--")[0]
            index.append([target[1:], plain_text(doc["title"]),
                          self.titles.get(page, ""), plain_text(doc["text"])])
        for url, section in self.sources.items():
            index.append([section, PurePosixPath(url).name, url,
                          " ".join(source_texts[section].split())])
        # "</" would end the <script> element.
        return json.dumps(index, ensure_ascii=False).replace("</", "<\\/")

    def theme_css(self) -> str:
        """Get the stylesheets of the theme, without the source map links."""
        parts = []
        for pattern in THEME_CSS:
            for path in sorted(self.site.glob(pattern)):
                parts.append(path.read_text(encoding="utf-8"))
        return SOURCE_MAP.sub("", "\n".join(parts))

    def join(self) -> str:
        """
        Join the pages.

        Returns:
            str: The HTML file.
        """
        nav_order = []
        stack = list(reversed(self.nav))
        while stack:
            item = stack.pop()
            if isinstance(item, str):
                nav_order.append(md_to_html(item))
            elif isinstance(item, dict):
                for children in reversed(list(item.values())):
                    stack.extend(reversed(children))
        order = nav_order + [url for url in self.pages if url not in nav_order]
        sections = [self.page_section(url) for url in order]

        source_texts = {}
        for url in list(self.sources):
            section, text = self.source_section(url)
            sections.append(section)
            source_texts[self.sources[url]] = text

        values = {
            "site_name": escape(site_name()),
            "version": escape(client_version()),
            "home_id": self.pages["index.html"],
            "theme_css": self.theme_css(),
            "page_css": (TEMPLATE_DIR / "page.css").read_text("utf-8"),
            "page_js": (TEMPLATE_DIR / "page.js").read_text("utf-8"),
            "nav": self.nav_html(self.nav),
            "pages": "\n".join(sections),
            "search_index": self.search_index(source_texts),
        }
        template = (TEMPLATE_DIR / "page.html").read_text(encoding="utf-8")
        return PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def site_name() -> str:
    """Get the name of the documentation from mkdocs.yml."""
    with (HERE / "mkdocs.yml").open(encoding="utf-8") as f:
        return str(yaml.safe_load(f)["site_name"])


def client_version() -> str:
    """Get the version of the client from its pyproject.toml."""
    with (CLIENT_DIR / "pyproject.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def write_output(html: str) -> Path:
    """
    Write the HTML file to the output folder.

    The script writes a temporary file first, so that a failed write
    does not leave a part of the file.

    Parameters:
        html (str): The HTML file.

    Returns:
        Path: The file.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"skraft-docs-{client_version()}.html"
    temporary = output.with_suffix(".html.tmp")
    temporary.write_text(html, encoding="utf-8")
    temporary.replace(output)
    return output


def main() -> int:
    """
    Build the documentation file.

    Returns:
        int: The exit code. 0 if the file was built.
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

        nav = make_nav(pages)
        try:
            site = build_site(work, nav)
            html = SiteJoiner(site, nav).join()
        except RuntimeError as e:
            print(f"Cannot build the documentation: {e}", file=sys.stderr)
            return 1
        output = write_output(html)

    print(f"Documentation: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
