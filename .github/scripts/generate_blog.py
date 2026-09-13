"""Generate blog.md and feed.xml from curated wiki pages.

A wiki file counts as a blog post if it starts with:
  # Title
  **YYYY-MM-DD**
(allowing leading blank lines)

Outputs (both transient build artifacts, never committed):
  blog.md  — year-grouped link list at /blog/, same format the
             8hantanu/blog repo used to publish.
  feed.xml — full-content Atom feed at /feed.xml with entries
             linking straight to their canonical wiki URLs.

Run weekly via .github/workflows/pages.yml, after checking out
8hantanu/wiki at WIKI_DIR. Markdown-to-HTML conversion uses
kramdown (same engine GitHub Pages uses) so feed content matches
the wiki exactly; relative links/images are rewritten to absolute
wiki URLs first so they work inside feed readers.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from xml.sax.saxutils import escape
import re
import subprocess


WIKI_DIR = Path("wiki")
BLOG_MD = Path("blog.md")
FEED_XML = Path("feed.xml")

SITE_URL = "https://8hantanu.net"
WIKI_BASE = f"{SITE_URL}/wiki"
FEED_URL = f"{SITE_URL}/feed.xml"
FEED_TITLE = "Shantanu's Blog"
AUTHOR = "Shantanu Mishra"

TITLE_RE = re.compile(r"^\s*#\s+(.+?)\s*$")
DATE_RE = re.compile(r"^\s*\*\*(\d{4}-\d{2}-\d{2})\*\*\s*$")
LINK_RE = re.compile(r"\]\(([^)\s]+)(\s+[^)]*)?\)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


@dataclass(frozen=True)
class Post:
    title: str
    d: date
    relpath: str  # posix path within wiki repo, e.g. "self/travel.md"
    body: str  # markdown body after the title/date lines


def parse_post(md_path: Path) -> Post | None:
    try:
        text = md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None

    lines = text.splitlines()

    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines):
        return None

    m_title = TITLE_RE.match(lines[i])
    if not m_title:
        return None
    title = m_title.group(1).strip()

    i += 1
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines):
        return None

    m_date = DATE_RE.match(lines[i])
    if not m_date:
        return None

    try:
        d = date.fromisoformat(m_date.group(1))
    except ValueError:
        return None

    i += 1
    body = "\n".join(lines[i:]).strip() + "\n"
    relpath = md_path.relative_to(WIKI_DIR).as_posix()
    return Post(title=title, d=d, relpath=relpath, body=body)


def to_wiki_link(relpath: str) -> str:
    """Convert a wiki repo path into a public URL."""
    p = PurePosixPath(relpath)

    if p.name.lower() == "readme.md":
        if p.parent.as_posix() == ".":
            return WIKI_BASE
        return f"{WIKI_BASE}/{p.parent.as_posix()}"

    if p.suffix.lower() == ".md":
        return f"{WIKI_BASE}/{p.with_suffix('').as_posix()}"

    return f"{WIKI_BASE}/{p.as_posix()}"


def collect_posts() -> list[Post]:
    posts: list[Post] = []
    for md in WIKI_DIR.rglob("*.md"):
        post = parse_post(md)
        if post:
            posts.append(post)
    posts.sort(key=lambda p: (p.d, p.relpath), reverse=True)
    return posts


def rewrite_target(target: str, src_relpath: str, canonical: str) -> str:
    if re.match(r"^(https?://|mailto:|data:)", target):
        return target
    if target.startswith("#"):
        return canonical + target
    if target.startswith("/"):
        return f"{SITE_URL}{target}"
    resolved = PurePosixPath(src_relpath).parent.joinpath(target)
    parts: list[str] = []
    for part in resolved.parts:
        if part in (".", ""):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return to_wiki_link("/".join(parts))


def rewrite_body_links(body: str, src_relpath: str, canonical: str) -> str:
    def repl(m: re.Match[str]) -> str:
        target, rest = m.group(1), m.group(2) or ""
        return f"]({rewrite_target(target, src_relpath, canonical)}{rest})"

    return LINK_RE.sub(repl, body)


def plain_text(block: str) -> str:
    block = IMAGE_RE.sub("", block)
    block = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", block)
    block = re.sub(r"(\*\*|__)(.*?)\1", r"\2", block)
    block = re.sub(r"\b_(.*?)_\b", r"\1", block)
    block = re.sub(r"(?<!\w)\*(?!\s)(.*?)(?<!\s)\*(?!\w)", r"\1", block)
    block = block.replace("`", "")
    return re.sub(r"\s+", " ", block).strip()


def excerpt_of(body: str) -> str:
    for block in body.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(">"):
            continue
        text = plain_text(block)
        if text:
            return text[:297].rstrip() + "..." if len(text) > 300 else text
    return ""


def markdown_to_html(markdown: str) -> str:
    """Convert via kramdown (Pages' engine); fall back to plain kramdown."""
    converter = (
        "begin; require 'kramdown-parser-gfm'; "
        "puts Kramdown::Document.new(STDIN.read, input: 'GFM').to_html; "
        "rescue LoadError; "
        "require 'kramdown'; puts Kramdown::Document.new(STDIN.read).to_html; end"
    )
    result = subprocess.run(
        ["ruby", "-rkramdown", "-e", converter],
        input=markdown,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() + "\n"


def render_blog_md(posts: list[Post]) -> str:
    lines = [
        "---",
        "layout: default",
        'title: "Shantanu\'s Blog"',
        "permalink: /blog/",
        "---",
        "",
        "# Shantanu's Blog",
        "",
        "**Collection of the latest and greatest pages from the [wiki](https://8hantanu.net/wiki)**",
        "",
        "[Subscribe via RSS](/feed.xml)",
        "",
    ]
    by_year: dict[int, list[Post]] = defaultdict(list)
    for p in posts:
        by_year[p.d.year].append(p)
    for year in sorted(by_year.keys(), reverse=True):
        lines.append(f"## {year}")
        for p in by_year[year]:
            lines.append(f"- [{p.title}]({to_wiki_link(p.relpath)})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_feed(posts: list[Post], html_by_url: dict[str, str]) -> str:
    updated = max((p.d for p in posts), default=date.today()).isoformat()
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"  <title>{escape(FEED_TITLE)}</title>",
        f'  <link href="{FEED_URL}" rel="self" type="application/atom+xml" />',
        f'  <link href="{SITE_URL}/" rel="alternate" type="text/html" />',
        f"  <updated>{updated}T00:00:00Z</updated>",
        f"  <id>{FEED_URL}</id>",
        "  <author>",
        f"    <name>{escape(AUTHOR)}</name>",
        "  </author>",
    ]
    for p in posts:
        url = to_wiki_link(p.relpath)
        lines += [
            "  <entry>",
            f"    <title>{escape(p.title)}</title>",
            f'    <link href="{escape(url)}" rel="alternate" type="text/html" />',
            f"    <id>{escape(url)}</id>",
            f"    <updated>{p.d.isoformat()}T00:00:00Z</updated>",
            f"    <summary>{escape(excerpt_of(p.body))}</summary>",
            f"    <content type=\"html\">{escape(html_by_url[url])}</content>",
            "  </entry>",
        ]
    lines.append("</feed>")
    return "\n".join(lines) + "\n"


def main() -> None:
    if not WIKI_DIR.is_dir():
        raise SystemExit(
            "Expected wiki repo checked out at: "
            f"{WIKI_DIR.resolve()} (checkout 8hantanu/wiki first)"
        )

    posts = collect_posts()
    html_by_url = {
        to_wiki_link(p.relpath): markdown_to_html(
            rewrite_body_links(p.body, p.relpath, to_wiki_link(p.relpath))
        )
        for p in posts
    }

    BLOG_MD.write_text(render_blog_md(posts), encoding="utf-8")
    FEED_XML.write_text(render_feed(posts, html_by_url), encoding="utf-8")
    print(f"Found {len(posts)} blog posts. Wrote {BLOG_MD} and {FEED_XML}.")


if __name__ == "__main__":
    main()
