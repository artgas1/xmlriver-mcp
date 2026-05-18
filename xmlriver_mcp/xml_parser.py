"""XML response parser for XMLRiver search results.

XMLRiver returns Yandex-XML-format extended with Google-specific blocks.
Response shape:

    <yandexsearch version="1.0">
      <response date="20120928T103130">
        <found priority="all">206775197</found>
        <addresults>
          <relatedQuestions>...</relatedQuestions>
          <knowledge_graph>...</knowledge_graph>
        </addresults>
        <results>
          <grouping>
            <page first="1" last="10">0</page>
            <group>
              <doc>
                <url>...</url>
                <title>...</title>
                <passages><passage>...</passage></passages>
                ...
              </doc>
            </group>
          </grouping>
        </results>
      </response>
    </yandexsearch>

Error response:
    <yandexsearch>
      <response>
        <error code="15">Not enough results</error>
      </response>
    </yandexsearch>
"""

from __future__ import annotations

import contextlib
import re
import xml.etree.ElementTree as ET
from typing import Any


def _text_or_none(elem: ET.Element | None) -> str | None:
    """Get full text content including text from child elements (e.g. <hlword>).

    XMLRiver wraps matched terms in <hlword>...</hlword> children, so plain
    `elem.text` returns only the prefix before the first child. We need
    `itertext()` to flatten all text nodes (children's text + tail) into one string.
    """
    if elem is None:
        return None
    parts = "".join(elem.itertext())
    return parts.strip() or None


def _strip_hlword(text: str | None) -> str | None:
    """Defensive: strip <hlword> tags if any survived (kept for safety)."""
    if text is None:
        return None
    return re.sub(r"</?hlword>", "", text)


def parse_search_xml(xml_text: str) -> dict[str, Any]:
    """Parse XMLRiver search response into structured dict.

    Returns:
        On success::
            {
                "query": str | None,
                "total_found": int | None,
                "page": int,
                "results": [
                    {"position": int, "url": str, "title": str, "snippet": str | None, ...},
                    ...
                ],
                "addresults": {...},  # extra blocks (knowledge_graph, related, etc)
            }

        On XMLRiver error::
            {"isError": True, "errorCode": "XMLRIVER_<code>", "content": [...]}
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return {
            "isError": True,
            "errorCode": "INVALID_XML",
            "content": [{"type": "text", "text": f"XML parse error: {e}"}],
        }

    response = root.find("response")
    if response is None:
        return {
            "isError": True,
            "errorCode": "NO_RESPONSE",
            "content": [{"type": "text", "text": "No <response> in XML"}],
        }

    # Check for XMLRiver error code
    error_elem = response.find("error")
    if error_elem is not None:
        code = error_elem.get("code", "unknown")
        msg = _text_or_none(error_elem) or "XMLRiver error"
        return {
            "isError": True,
            "errorCode": f"XMLRIVER_{code}",
            "content": [{"type": "text", "text": f"XMLRiver error {code}: {msg}"}],
        }

    found_elem = response.find("found")
    total = None
    if found_elem is not None and found_elem.text and found_elem.text.isdigit():
        total = int(found_elem.text)

    misspell = response.find("misspell/rule")
    suggested_query = _text_or_none(misspell)

    # Results: response/results/grouping/group[]/doc
    results: list[dict[str, Any]] = []
    grouping = response.find("results/grouping")
    page_num = 0
    if grouping is not None:
        page_elem = grouping.find("page")
        if page_elem is not None and page_elem.text:
            with contextlib.suppress(ValueError):
                page_num = int(page_elem.text)

        for position, group in enumerate(grouping.findall("group"), start=1):
            doc = group.find("doc")
            if doc is None:
                continue

            url = _text_or_none(doc.find("url"))
            title = _strip_hlword(_text_or_none(doc.find("title")))

            # Snippet: passages > passage (multiple lines) or extendedpassage
            # Use _text_or_none to flatten <hlword> children
            snippet_parts: list[str] = []
            for passage in doc.findall("passages/passage"):
                text = _text_or_none(passage)
                if text:
                    snippet_parts.append(text)
            if not snippet_parts:
                extended = _text_or_none(doc.find("extendedpassage"))
                if extended:
                    snippet_parts.append(extended)
            snippet = " ".join(p for p in snippet_parts if p) or None

            pub_date = _text_or_none(doc.find("pubDate"))

            # Sitelinks (subset of results)
            sitelinks = []
            for sl in doc.findall("sitelinks/sitelink"):
                sitelinks.append({
                    "url": _text_or_none(sl.find("url")),
                    "title": _strip_hlword(_text_or_none(sl.find("title"))),
                    "snippet": _strip_hlword(_text_or_none(sl.find("snippet"))),
                })

            result = {
                "position": position,
                "url": url,
                "title": title,
                "snippet": snippet,
            }
            if pub_date:
                result["pub_date"] = pub_date
            if sitelinks:
                result["sitelinks"] = sitelinks
            results.append(result)

    # addresults: knowledge_graph, related, faq, etc
    addresults: dict[str, Any] = {}
    addr = response.find("addresults")
    if addr is not None:
        # Zero position (featured snippet)
        zp = addr.find("zeroposition")
        if zp is not None:
            url = _text_or_none(zp.find("url"))
            title = _text_or_none(zp.find("title"))
            if url or title:
                addresults["featured_snippet"] = {"url": url, "title": title}

        # Related questions (FAQ-style)
        related_q = addr.findall("relatedQuestions/question")
        if related_q:
            addresults["related_questions"] = [
                _strip_hlword(_text_or_none(q.find("title"))) for q in related_q
                if _text_or_none(q.find("title"))
            ]

        # Related searches
        related_s = addr.findall("relatedSearches/query")
        if related_s:
            addresults["related_searches"] = [
                _text_or_none(q.find("title")) for q in related_s
                if _text_or_none(q.find("title"))
            ]

        # Knowledge graph
        kg = addr.find("knowledge_graph")
        if kg is not None:
            addresults["knowledge_graph"] = {
                "name": _text_or_none(kg.find("name")),
                "rating": _text_or_none(kg.find("rating")),
                "reviews_count": _text_or_none(kg.find("countReviews")),
                "address": _text_or_none(kg.find("address")),
                "phone": _text_or_none(kg.find("phone")),
            }

    out: dict[str, Any] = {
        "page": page_num,
        "results": results,
        "results_count": len(results),
    }
    if total is not None:
        out["total_found"] = total
    if suggested_query:
        out["suggested_query"] = suggested_query
    if addresults:
        out["addresults"] = addresults

    return out
