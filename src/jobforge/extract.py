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

Per board (issue #4, fixtures in `fixtures/html/`): Lever, Ashby, and Workday
publish JSON-LD, but Workday names an internal legal entity ("2100 Acme USA"),
so a company starting with an entity number is refused. SmartRecruiters uses
schema.org microdata instead. Greenhouse and Breezy have no structured data
and name the company only in the page title ("... at Acme").
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
# schema.org microdata address fields, in display order (SmartRecruiters).
_MICRODATA_ADDRESS = ("addressLocality", "addressRegion", "addressCountry")


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


# What a person never sees on the page is not part of the posting (#28, F4):
# a planted instruction hidden in a job page would otherwise reach the agent.
_HIDING_STYLE = re.compile(
    r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden"
    r"|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?|opacity\s*:\s*0(?:\.0+)?)\s*(?:;|$)",
    re.IGNORECASE)
_HIDING_CLASSES = {"sr-only", "visually-hidden", "d-none", "hidden", "invisible"}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
              "source", "track", "wbr"}
# A class that shows the element again at some screen size, so "hidden" or
# "d-none" next to it means hidden on phones only: Tailwind's `md:block`,
# `lg:not-sr-only`, `md:hover:visible`, Bootstrap's `d-md-flex`. One that
# hides at every size (`md:hidden`, `d-md-none`) does not count.
_SHOWING_CLASS = re.compile(
    r"(?:[\w-]+:)+(?:block|inline|inline-block|flex|inline-flex|grid|inline-grid|table"
    r"|table-row|table-cell|contents|flow-root|list-item|visible|not-sr-only)"
    r"|d-(?:sm|md|lg|xl|xxl)-(?:block|inline|inline-block|flex|inline-flex|grid"
    r"|inline-grid|table|table-row|table-cell)")
# End tags a page may leave out, closed the way a browser closes them, so a
# hidden <p> or <li> never swallows the rest of the page and a stray </p>
# never ends a hidden section early. A block element (or a new <p>) ends an
# open <p>; a new <li> ends an open <li> in the same list.
_ENDS_P = {"address", "article", "aside", "blockquote", "details", "div", "dl", "fieldset",
           "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6",
           "header", "hr", "li", "main", "menu", "nav", "ol", "p", "pre", "section",
           "table", "ul"}
_P_SCOPE = {"button", "caption", "html", "table", "td", "th", "template"}
_LIST_SCOPE = {"ol", "ul", "menu"}


def _hides(attrs: dict[str, str]) -> bool:
    if ("hidden" in attrs or attrs.get("aria-hidden", "").lower() == "true"
            or _HIDING_STYLE.search(attrs.get("style", ""))):
        return True
    classes = attrs.get("class", "").lower().split()
    return (bool(_HIDING_CLASSES.intersection(classes))
            and not any(_SHOWING_CLASS.fullmatch(c) for c in classes))


class _TextExtractor(HTMLParser):
    """Flatten HTML to readable text, keeping block boundaries as newlines,
    and collect JSON-LD blocks and a few meta tags on the way."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ld_json: list[str] = []
        self.meta: dict[str, str] = {}
        self.microdata: dict[str, str] = {}
        self.title_parts: list[str] = []
        self._suppress = 0
        self._open: list[str] = []  # the elements open around the parser now
        self._hidden_at: int | None = None  # where in _open the hidden one is
        self._in_ld = False
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "li":
            self._close_open("li", _LIST_SCOPE)
        if tag in _ENDS_P:
            self._close_open("p", _P_SCOPE)
        if tag not in _VOID_TAGS:
            if self._hidden_at is None and _hides(a):
                self._hidden_at = len(self._open)
            self._open.append(tag)
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content"):
                self.meta[key] = a["content"]
        prop = a.get("itemprop", "")
        if prop in _MICRODATA_ADDRESS and a.get("content"):
            self.microdata.setdefault(prop, a["content"])
        if tag == "title":
            self._in_title = True
        if tag in _DROP_TAGS:
            self._suppress += 1
            if tag == "script" and a.get("type", "").strip().lower() == "application/ld+json":
                self._in_ld = True
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def _close_open(self, tag: str, scope: set[str]) -> None:
        """Close the innermost open `tag`, unless a `scope` element lies
        between it and the parser (a <p> outside the table cell stays open)."""
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i] == tag:
                self._close_to(i)
                return
            if self._open[i] in scope:
                return

    def _close_to(self, index: int) -> None:
        """Close the element at `index` in `_open` and everything inside it.
        A hidden section ends with the element that began it, even when the
        page never writes that element's end tag."""
        del self._open[index:]
        if self._hidden_at is not None and self._hidden_at >= index:
            self._hidden_at = None

    def handle_endtag(self, tag):
        # An end tag with nothing open to match (a stray </span>) is ignored.
        if tag in self._open:
            self._close_to(len(self._open) - 1 - self._open[::-1].index(tag))
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
        if self._suppress or self._hidden_at is not None or not data.strip():
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
# Greenhouse titles read "Job Application for <title> at <company>".
_APPLICATION_PREFIX = re.compile(r"^job application for\s+", re.IGNORECASE)
_AT_COMPANY = re.compile(r"\s+at\s+([A-Z][\w&.,' -]+)$")
# Workday's hiringOrganization is often a legal entity: "2100 Acme USA".
_ENTITY_CODE_RE = re.compile(r"^\d{3,}\s")


def looks_like_domain(name: str) -> bool:
    return bool(_DOMAIN_RE.match(name.strip()))


def strip_title_suffix(title: str) -> str:
    """Clean a page `<title>` down to the job title.

    'Process Engineer | Acme Careers' -> 'Process Engineer'
    'Welder - Jobs at Acme' -> 'Welder'
    'Data Analyst at Ironbark Compute Group' -> 'Data Analyst'
    'Software Engineer - Infrastructure' is left alone.
    """
    first = _title_head(title)
    head, sep, tail = first.rpartition(" - ")
    if sep and _SITE_WORDS.search(tail):
        first = head
    first = _AT_COMPANY.sub("", first)
    return first.strip()


def _title_head(title: str) -> str:
    """The part of a page title before any site separator, without
    Greenhouse's "Job Application for" prefix."""
    first = _SUFFIX_SPLIT.split(" ".join(title.split()))[0]
    return _APPLICATION_PREFIX.sub("", first)


def company_from_title(title: str) -> str:
    """The company a page title names as "... at <Company>", or "".

    'Line Cook at Copperline Kitchen Group' -> 'Copperline Kitchen Group'
    'Welder - Jobs at Acme' -> 'Acme'
    'Field Applications Engineer — Google Careers' -> ''
    """
    m = _AT_COMPANY.search(_title_head(title))
    return m.group(1).strip() if m else ""


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
    page_title = unescape("".join(parser.title_parts))
    og_title = parser.meta.get("og:title", "")
    if not found_title:
        # og:title is usually just the job title; <title> often adds the
        # company or the board ("Acme Welder | SmartRecruiters").
        found_title = strip_title_suffix(og_title or page_title)
    if not found_company:
        site = parser.meta.get("og:site_name", "")
        found_company = (site if site and not looks_like_domain(site) else
                         company_from_title(page_title) or company_from_title(og_title) or site)
    if not found_location:
        found_location = ", ".join(parser.microdata[k] for k in _MICRODATA_ADDRESS
                                   if parser.microdata.get(k))
    if not company and _ENTITY_CODE_RE.match(found_company.strip()):
        raise JobforgeError(
            f"The company came out as {found_company.strip()!r}, which looks like an "
            f"internal entity code, not the name people know. It would end up in "
            f"your letter as \"Dear {found_company.strip()} Hiring Team\". Pass "
            f"--company \"Company name\".")

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
