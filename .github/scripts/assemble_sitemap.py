"""Assemble the domain sitemap at _site/sitemap.xml.

Combines root pages discovered from the built _site/ with every
wiki page from the 8hantanu/wiki checkout (the whole-domain
coverage the old crawler sitemap had), in one artifact that is
never committed. Runs after `jekyll build`, before artifact
upload (see .github/workflows/pages.yml).

The jekyll-sitemap gem stays installed (the theme auto-requires
its gemspec dependencies) but its output is not used — this
script overwrites _site/sitemap.xml deterministically.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from urllib.parse import quote
from xml.sax.saxutils import escape


WIKI_DIR = Path("wiki")
SITE_DIR = Path("_site")
SITEMAP_XML = SITE_DIR / "sitemap.xml"

SITE_URL = "https://8hantanu.net"
WIKI_BASE = f"{SITE_URL}/wiki"


def site_url_for(html_path: Path) -> str | None:
    """Map a built _site/**/*.html file to its public URL."""
    rel = html_path.relative_to(SITE_DIR).as_posix()
    if rel == "404.html":
        return None
    if html_path.name == "index.html":
        parent = PurePosixPath(rel).parent.as_posix()
        return f"{SITE_URL}/{parent}/" if parent != "." else f"{SITE_URL}/"
    return f"{SITE_URL}/{rel}"


def wiki_url_for(md_path: Path) -> str | None:
    """Map a wiki checkout *.md file to its public URL."""
    if md_path.name.lower() in ("agents.md",):
        # Mirrors wiki _config.yml excludes (AGENTS.md, **/AGENTS.md):
        # never built, must not be listed.
        return None
    rel = md_path.relative_to(WIKI_DIR)
    parts = [quote(part) for part in rel.parts]
    if rel.name.lower() == "readme.md":
        parent = PurePosixPath(*parts[:-1]).as_posix() if len(parts) > 1 else ""
        return f"{WIKI_BASE}/{parent}/" if parent not in ("", ".") else f"{WIKI_BASE}/"
    p = PurePosixPath(*parts)
    if p.suffix.lower() == ".md":
        p = p.with_suffix("")
    return f"{WIKI_BASE}/{p.as_posix()}"


def collect() -> list[str]:
    urls: set[str] = set()

    for html in SITE_DIR.rglob("*.html"):
        url = site_url_for(html)
        if url:
            urls.add(url)

    if WIKI_DIR.is_dir():
        for md in WIKI_DIR.rglob("*.md"):
            url = wiki_url_for(md)
            if url:
                urls.add(url)

    return sorted(urls)


def render(urls: list[str]) -> str:
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        lines += ["  <url>", f"    <loc>{escape(url)}</loc>", "  </url>"]
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def main() -> None:
    if not SITE_DIR.is_dir():
        raise SystemExit(f"Expected built site at: {SITE_DIR.resolve()}")

    urls = collect()
    SITEMAP_XML.write_text(render(urls), encoding="utf-8")
    print(f"Found {len(urls)} URLs. Wrote {SITEMAP_XML}.")


if __name__ == "__main__":
    main()
