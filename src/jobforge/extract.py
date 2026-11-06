"""Turn a posting URL or pasted text into a Job.

Ground truth only (D-04, D-45): one posting the user handed us. Nothing here
lists a whole board.

Lessons carried from the private repo:
- Many pages publish a schema.org JobPosting in JSON-LD; prefer it.
- Without it, the page `<title>` carries a site suffix ("... | Acme Careers")
  and the company is unknown. The private code then used the hostname, and
  letters went out as "Dear google.com Hiring Team" (FINDINGS F23, F27). Here
  the suffix is stripped and a missing or domain-like company is an error that
  asks for --company.
- Template placeholders like %HEADER_COMPANY_WEBSITE% are removed (F27).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any, Callable

from .errors import JobforgeError
from .scan import clean

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")
MIN_DESCRIPTION_CHARS = 200

_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "tr", "table", "section", "article",
               "h1", "h2", "h3", "h4", "h5", "h6", "header", "footer", "blockquote"}
_DROP_TAGS = {"script", "style", "noscript", "svg", "head", "template"}


@dataclass
class Job:
    company: str
    title: str
    description: str
    url: str = ""
    location: str = ""
    source: str = "manual"   # "json-ld" | "page-text" | "manual"

    def to_dict(self) -> dict:
        return asdict(self)


class FetchBlocked(JobforgeError):
    pass


class _TextExtractor(HTMLParser):
    """Flatten HTML to readable text, keeping block boundaries as newlines,
    and collect JSON-LD blocks and a few meta tags on the way."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ld_json: list[str] = []
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self._suppress = 0
        self._in_ld = False
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content"):
                self.meta[key] = a["content"]
        if tag == "title":
            self._in_title = True
        if tag in _DROP_TAGS:
            self._suppress += 1
            if tag == "script" and a.get("type", "").strip().lower() == "application/ld+json":
                self._in_ld = True
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in _DROP_TAGS and self._suppress:
            self._suppress -= 1
            self._in_ld = False
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self._in_ld:
            self.ld_json.append(data)
            return
        if self._suppress or not data.strip():
            return
        self.parts.append(data)

    def text(self) -> str:
        joined = "".join(self.parts)
        joined = re.sub(r"[ \t\r\f\v]+", " ", joined)
        joined = re.sub(r" *\n *", "\n", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip()


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return p.text()


_PLACEHOLDER_RE = re.compile(r"%[A-Z][A-Z0-9_]{2,}%")


def clean_description(text: str) -> str:
    text = clean(text)
    text = _PLACEHOLDER_RE.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# Separators a site puts between a job title and its own name. A plain hyphen
# is not one of them: "Software Engineer - Infrastructure" is a real title.
_SUFFIX_SPLIT = re.compile(r"\s+(?:\||—|–|::|·)\s+")
_SITE_WORDS = re.compile(
    r"careers?|jobs?|job board|hiring|linkedin|indeed|glassdoor|ziprecruiter|"
    r"workday|greenhouse|lever|smartrecruiters|breezy", re.IGNORECASE)
_DOMAIN_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/.*)?$", re.IGNORECASE)


def looks_like_domain(name: str) -> bool:
    return bool(_DOMAIN_RE.match(name.strip()))


def strip_title_suffix(title: str) -> str:
    """Clean a page `<title>` down to the job title.

    'Process Engineer | Acme Careers' -> 'Process Engineer'
    'Welder - Jobs at Acme' -> 'Welder'
    'Data Analyst at Ironbark Compute Group' -> 'Data Analyst'
    'Software Engineer - Infrastructure' is left alone.
    """
    title = " ".join(title.split())
    first = _SUFFIX_SPLIT.split(title)[0]
    head, sep, tail = first.rpartition(" - ")
    if sep and _SITE_WORDS.search(tail):
        first = head
    first = re.sub(r"\s+at\s+[A-Z][\w&.,' -]+$", "", first)
    return first.strip()


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def find_job_posting(blocks: list[str]) -> dict | None:
    for raw in blocks:
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        for node in _walk(data):
            t = node.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(str(x).lower() == "jobposting" for x in types if x):
                return node
    return None


def _location_text(node: Any) -> str:
    for cand in _walk(node):
        addr = cand.get("address")
        if isinstance(addr, dict):
            country = addr.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name")
            bits = [addr.get("addressLocality"), addr.get("addressRegion"), country]
            joined = ", ".join(str(b) for b in bits if b)
            if joined:
                return joined
    return node if isinstance(node, str) else ""


def fetch_html(url: str, *, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise FetchBlocked(
            f"Could not read {url}: HTTP {exc.code} {exc.reason}.\n" + PASTE_HINT) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchBlocked(f"Could not reach {url}: {exc}.\n" + PASTE_HINT) from exc


PASTE_HINT = (
    "Many job boards block scripted requests or build the page with JavaScript.\n"
    "Copy the posting text into a file and run:\n"
    '  jobforge prepare --from-text posting.txt --company "Company" --title "Job title" --url <url>'
)


def from_url(url: str, *, company: str | None = None, title: str | None = None,
             location: str | None = None,
             fetch: Callable[[str], str] = fetch_html) -> tuple[Job, list[str]]:
    """Fetch and parse one posting. Returns the job and any warnings."""
    if not re.match(r"^https?://", url or ""):
        raise JobforgeError(f"{url!r} is not an http(s) URL.")
    html = fetch(url)
    parser = _TextExtractor()
    parser.feed(html)
    posting = find_job_posting(parser.ld_json)
    warnings: list[str] = []

    found_title = found_company = found_location = ""
    description = ""
    source = "page-text"
    if posting:
        source = "json-ld"
        found_title = str(posting.get("title") or "")
        org = posting.get("hiringOrganization")
        found_company = str(org.get("name") or "") if isinstance(org, dict) else str(org or "")
        found_location = _location_text(posting.get("jobLocation"))
        raw = posting.get("description")
        if isinstance(raw, str) and raw.strip():
            description = html_to_text(unescape(raw))
    if not description:
        description = parser.text()
        warnings.append(
            "No structured posting data on that page, so the description is the "
            "whole page's text and may include menus and other listings. Check "
            "job.json, or paste just the posting with --from-text.")
    if not found_title:
        found_title = strip_title_suffix(unescape("".join(parser.title_parts)))
    if not found_company:
        found_company = parser.meta.get("og:site_name", "")

    job = _finish(
        company=company or found_company,
        title=title or found_title,
        location=location or found_location,
        url=url,
        description=description,
        source=source,
    )
    return job, warnings


def from_text(text: str, *, company: str | None, title: str | None,
              location: str | None = None, url: str | None = None) -> tuple[Job, list[str]]:
    if not text or not text.strip():
        raise JobforgeError("The posting text is empty.")
    if not company or not title:
        raise JobforgeError("--from-text needs --company and --title; nothing in "
                            "pasted text can be trusted to name them.")
    if re.search(r"<(p|div|li|br|span|h[1-6]|ul)\b", text, re.IGNORECASE):
        text = html_to_text(text)
    return _finish(company=company, title=title, location=location or "",
                   url=url or "", description=text, source="manual"), []


def _finish(*, company: str, title: str, location: str, url: str,
            description: str, source: str) -> Job:
    company = " ".join(clean(company or "").split())
    title = " ".join(clean(title or "").split())
    description = clean_description(description)
    if not company:
        raise JobforgeError("Could not tell which company this posting is for. "
                            "Pass --company \"Company name\".")
    if looks_like_domain(company):
        raise JobforgeError(
            f"The company came out as {company!r}, which is a web address, not a "
            f"company name. It would end up in your letter as \"Dear {company} "
            f"Hiring Team\". Pass --company \"Company name\".")
    if not title:
        raise JobforgeError("Could not tell the job title. Pass --title \"Job title\".")
    if len(description) < MIN_DESCRIPTION_CHARS:
        raise JobforgeError(
            "That page gave almost no description text; it is probably built with "
            "JavaScript or behind a login.\n" + PASTE_HINT)
    if url and not re.match(r"^https?://", url):
        raise JobforgeError(f"--url {url!r} is not an http(s) URL.")
    return Job(company=company, title=title, description=description, url=url,
               location=" ".join(clean(location or "").split()), source=source)
