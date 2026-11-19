"""Official Canadian employment/labour legislation sources for independent legal Q&A.

The registry is deliberately explicit: the application never accepts arbitrary URLs
from users, which avoids turning law retrieval into an SSRF surface.
"""
from __future__ import annotations

import asyncio
import html
import re
import time
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException


@dataclass(frozen=True)
class LawSource:
    code: str
    jurisdiction: str
    act_title: str
    official_url: str
    language_note: str = "Official legislation source"
    level: Literal["federal", "provincial", "territorial", "municipal"] = "provincial"
    parent_code: str | None = None


@dataclass(frozen=True)
class LawPassage:
    source_id: str
    jurisdiction_code: str
    jurisdiction: str
    act_title: str
    official_url: str
    section_label: str | None
    page_number: int | None
    text: str


LAW_SOURCES: dict[str, LawSource] = {
    "CA": LawSource("CA", "Federal (federally regulated workplaces)", "Canada Labour Code", "https://laws-lois.justice.gc.ca/eng/acts/L-2/FullText.html", level="federal"),
    "AB": LawSource("AB", "Alberta", "Employment Standards Code", "https://kings-printer.alberta.ca/1266.cfm?page=1997_014.cfm&leg_type=Regs&isbncln=9780779858910&display=html"),
    "BC": LawSource("BC", "British Columbia", "Employment Standards Act", "https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/00_96113_01"),
    "MB": LawSource("MB", "Manitoba", "The Employment Standards Code", "https://web2.gov.mb.ca/laws/statutes/ccsm/_pdf.php?cap=e110"),
    "NB": LawSource("NB", "New Brunswick", "Employment Standards Act", "https://laws.gnb.ca/en/pdf/cs/E-7.2.pdf"),
    "NL": LawSource("NL", "Newfoundland and Labrador", "Labour Standards Act", "https://www.assembly.nl.ca/Legislation/sr/statutes/l02.htm"),
    "NS": LawSource("NS", "Nova Scotia", "Labour Standards Code", "https://www.nslegislature.ca/sites/default/files/legc/statutes/labour%20standards%20code.pdf"),
    "NT": LawSource("NT", "Northwest Territories", "Employment Standards Act", "https://www.justice.gov.nt.ca/en/files/legislation/employment-standards/employment-standards.a.pdf", level="territorial"),
    "NU": LawSource("NU", "Nunavut", "Labour Standards Act", "https://www.gov.nu.ca/sites/default/files/policies-legislations/2025-11/Labour_Standards_Act__2022_.pdf", level="territorial"),
    "ON": LawSource("ON", "Ontario", "Employment Standards Act, 2000", "https://www.ontario.ca/laws/statute/00e41"),
    "PE": LawSource("PE", "Prince Edward Island", "Employment Standards Act", "https://www.princeedwardisland.ca/sites/default/files/b281/E-6.3-Employment%20Standards%20Act.pdf"),
    "QC": LawSource("QC", "Quebec", "Act respecting labour standards", "https://www.legisquebec.gouv.qc.ca/en/pdf/cs/N-1.1.pdf"),
    "SK": LawSource("SK", "Saskatchewan", "The Saskatchewan Employment Act", "https://publications.saskatchewan.ca/api/v1/products/70351/formats/78194/download"),
    "YT": LawSource("YT", "Yukon", "Employment Standards Act", "https://laws.yukon.ca/cms/images/LEGISLATION/PRINCIPAL/2002/2002-0072/2002-0072.pdf", level="territorial"),
}

# Municipal sources are deliberately curated and keyed by parent province/territory,
# normalized municipality name and law type. Populate only with verified official
# municipal URLs. The current Employment law release has no municipal entries, so a
# municipal query uses its parent employment statute and reports that source level.
MUNICIPAL_LAW_SOURCES: dict[tuple[str, str, str], LawSource] = {}


def _municipality_registry_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")


def _resolve_law_source(
    jurisdiction_code: str,
    *,
    municipality_name: str | None = None,
    law_type: str = "employment",
) -> LawSource | None:
    parent = LAW_SOURCES.get(jurisdiction_code.upper())
    if parent is None:
        return None
    if municipality_name:
        key = (parent.code, _municipality_registry_key(municipality_name), law_type)
        municipal = MUNICIPAL_LAW_SOURCES.get(key)
        if municipal and municipal.level == "municipal" and municipal.parent_code == parent.code:
            return municipal
    return parent

MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 350
MAX_PASSAGES = 10
PASSAGE_CHARS = 2_200
CACHE_SECONDS = 60 * 60
_CACHE: dict[str, tuple[float, list[tuple[str | None, int | None, str]]]] = {}
_CACHE_LOCK = asyncio.Lock()


class _TextExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "br"}
    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
        elif not self.skip_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        elif not self.skip_depth and tag in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def _clean_blocks(text: str) -> list[str]:
    text = html.unescape(text).replace("\xa0", " ")
    blocks = []
    for raw in re.split(r"\n+", text):
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) < 35:
            continue
        if line.lower() in {"table of contents", "contents", "skip to content", "print"}:
            continue
        blocks.append(line)
    return blocks


def _extract_html(content: bytes) -> list[tuple[str | None, int | None, str]]:
    parser = _TextExtractor()
    parser.feed(content.decode("utf-8", errors="replace"))
    blocks = _clean_blocks("\n".join(parser.parts))
    return _split_blocks(blocks)


def _split_blocks(blocks: list[str]) -> list[tuple[str | None, int | None, str]]:
    passages: list[tuple[str | None, int | None, str]] = []
    for block in blocks:
        if len(block) <= PASSAGE_CHARS:
            pieces = [block]
        else:
            pieces = [block[i:i + PASSAGE_CHARS] for i in range(0, len(block), PASSAGE_CHARS)]
        for piece in pieces:
            section = None
            match = re.match(r"^(?:Section|s\.|Article|PART|Part|Division)\s*([\dA-Za-z().-]+)", piece, re.IGNORECASE)
            if match:
                section = match.group(0)[:100]
            passages.append((section, None, piece))
    return passages


def _extract_pdf(content: bytes) -> list[tuple[str | None, int | None, str]]:
    try:
        from pypdf import PdfReader
        from io import BytesIO
        reader = PdfReader(BytesIO(content), strict=False)
        if len(reader.pages) > MAX_PDF_PAGES:
            raise HTTPException(status_code=502, detail="The official legislation PDF exceeds the supported page limit.")
        passages: list[tuple[str | None, int | None, str]] = []
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = re.sub(r"\s+", " ", page.extract_text() or "").strip()
            if not page_text:
                continue
            for _, _, piece in _split_blocks([page_text]):
                section = None
                match = re.search(r"\b(?:section|s\.|article)\s+([\dA-Za-z().-]+)", piece, re.IGNORECASE)
                if match:
                    section = f"Section {match.group(1)}"
                passages.append((section, page_number, piece))
        return passages
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The official legislation PDF could not be read as searchable text.") from exc


def _score(question: str, passage: str) -> int:
    tokens = {token for token in re.findall(r"[\wÀ-ÿ]{3,}", question.casefold())}
    if not tokens:
        return 0
    text = passage.casefold()
    return sum(1 + min(text.count(token), 3) for token in tokens if token in text)


async def _download_source(source: LawSource, http_client: httpx.AsyncClient | None = None) -> list[tuple[str | None, int | None, str]]:
    now = time.monotonic()
    cached = _CACHE.get(source.code)
    if cached and cached[0] > now:
        return cached[1]

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(
        timeout=httpx.Timeout(22.0, connect=8.0),
        follow_redirects=True,
        headers={"User-Agent": "Mataba-Legal-Information/1.0 (official legislation retrieval)"},
    )
    try:
        async with _CACHE_LOCK:
            cached = _CACHE.get(source.code)
            if cached and cached[0] > time.monotonic():
                return cached[1]
            async with client.stream("GET", source.official_url) as response:
                response.raise_for_status()
                final_host = (urlparse(str(response.url)).hostname or "").lower()
                source_host = (urlparse(source.official_url).hostname or "").lower()
                if final_host != source_host and not final_host.endswith("." + source_host):
                    raise HTTPException(status_code=502, detail="The official legislation source redirected outside its government domain.")
                content_type = response.headers.get("content-type", "").lower()
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > MAX_SOURCE_BYTES:
                        raise HTTPException(status_code=502, detail="The official legislation source exceeds the supported download size.")
                    chunks.append(chunk)
            content = b"".join(chunks)
            if "pdf" in content_type or content.startswith(b"%PDF") or source.official_url.lower().endswith(".pdf"):
                extracted = await asyncio.to_thread(_extract_pdf, content)
            else:
                extracted = _extract_html(content)
            if not extracted:
                raise HTTPException(status_code=502, detail="No searchable text was extracted from the official legislation source.")
            _CACHE[source.code] = (time.monotonic() + CACHE_SECONDS, extracted)
            return extracted
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="The official legislation source is temporarily unavailable. Please try again later.") from exc
    finally:
        if owns_client:
            await client.aclose()


async def retrieve_law_passages(
    jurisdiction_code: str,
    question: str,
    *,
    municipality_name: str | None = None,
    law_type: str = "employment",
    http_client: httpx.AsyncClient | None = None,
) -> tuple[LawSource, list[LawPassage]]:
    source = _resolve_law_source(
        jurisdiction_code,
        municipality_name=municipality_name,
        law_type=law_type,
    )
    if not source:
        raise HTTPException(status_code=422, detail="Select a supported Canadian federal, provincial or territorial jurisdiction.")
    available = await _download_source(source, http_client)
    ranked = sorted(
        ((_score(question, text), index, section, page, text) for index, (section, page, text) in enumerate(available)),
        key=lambda row: (row[0], -row[1]),
        reverse=True,
    )
    selected = [row for row in ranked if row[0] > 0][:MAX_PASSAGES]
    if not selected:
        raise HTTPException(status_code=422, detail="The selected official legislation source did not contain passages matching the question. Try a more specific question or another jurisdiction.")
    passages = [
        LawPassage(
            source_id=f"law-{source.code.lower()}-{index + 1}",
            jurisdiction_code=source.code,
            jurisdiction=source.jurisdiction,
            act_title=source.act_title,
            official_url=source.official_url,
            section_label=section,
            page_number=page,
            text=text,
        )
        for index, (_, _, section, page, text) in enumerate(selected)
    ]
    return source, passages
