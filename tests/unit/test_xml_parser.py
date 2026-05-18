"""Unit tests for XML parser — no live API calls."""

from xmlriver_mcp.xml_parser import parse_search_xml

SAMPLE_SUCCESS_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
  <response date="20260518T120000">
    <found priority="all">12345</found>
    <results>
      <grouping>
        <page first="1" last="2">0</page>
        <group>
          <doccount>1</doccount>
          <doc>
            <url>https://example.com/page1</url>
            <title>Test <hlword>Page</hlword> One</title>
            <pubDate>2026-05-18T10:00:00</pubDate>
            <passages><passage>This is the first <hlword>passage</hlword>.</passage></passages>
          </doc>
        </group>
        <group>
          <doccount>1</doccount>
          <doc>
            <url>https://example.com/page2</url>
            <title>Test Page Two</title>
            <passages><passage>Second passage text.</passage></passages>
          </doc>
        </group>
      </grouping>
    </results>
    <addresults>
      <relatedSearches>
        <query><title>related search 1</title></query>
        <query><title>related search 2</title></query>
      </relatedSearches>
    </addresults>
  </response>
</yandexsearch>
"""


SAMPLE_ERROR_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
  <response>
    <error code="15">No results found</error>
  </response>
</yandexsearch>
"""


SAMPLE_KNOWLEDGE_GRAPH_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
  <response date="20260518T120000">
    <found priority="all">100</found>
    <addresults>
      <knowledge_graph>
        <name>Test Restaurant</name>
        <rating>4.5</rating>
        <countReviews>234</countReviews>
        <address>Moscow, Test St 1</address>
        <phone>+7 495 000-00-00</phone>
      </knowledge_graph>
    </addresults>
    <results><grouping><page>0</page></grouping></results>
  </response>
</yandexsearch>
"""


def test_parse_success_returns_results():
    """Successful response with 2 organic results."""
    result = parse_search_xml(SAMPLE_SUCCESS_XML)
    assert "results" in result
    assert len(result["results"]) == 2
    assert result["total_found"] == 12345
    assert result["results_count"] == 2


def test_parse_strips_hlword_tags():
    """<hlword> highlight tags are stripped from title and snippet."""
    result = parse_search_xml(SAMPLE_SUCCESS_XML)
    first = result["results"][0]
    assert "<hlword>" not in (first["title"] or "")
    assert first["title"] == "Test Page One"
    assert "<hlword>" not in (first["snippet"] or "")
    assert "passage" in (first["snippet"] or "")


def test_parse_includes_position():
    """Each result has 1-based position field."""
    result = parse_search_xml(SAMPLE_SUCCESS_XML)
    assert result["results"][0]["position"] == 1
    assert result["results"][1]["position"] == 2


def test_parse_includes_pubdate_when_present():
    """pubDate is included when present in source."""
    result = parse_search_xml(SAMPLE_SUCCESS_XML)
    assert result["results"][0].get("pub_date") == "2026-05-18T10:00:00"
    # Second result has no pubDate
    assert "pub_date" not in result["results"][1]


def test_parse_includes_related_searches():
    """addresults.related_searches is populated."""
    result = parse_search_xml(SAMPLE_SUCCESS_XML)
    assert "addresults" in result
    assert result["addresults"]["related_searches"] == ["related search 1", "related search 2"]


def test_parse_error_returns_structured_error():
    """XMLRiver error returns isError dict, not raise."""
    result = parse_search_xml(SAMPLE_ERROR_XML)
    assert result.get("isError") is True
    assert result.get("errorCode") == "XMLRIVER_15"
    assert "15" in result["content"][0]["text"]


def test_parse_knowledge_graph():
    """Knowledge graph fields are extracted."""
    result = parse_search_xml(SAMPLE_KNOWLEDGE_GRAPH_XML)
    assert "addresults" in result
    kg = result["addresults"]["knowledge_graph"]
    assert kg["name"] == "Test Restaurant"
    assert kg["rating"] == "4.5"
    assert kg["reviews_count"] == "234"


def test_parse_invalid_xml_returns_error():
    """Malformed XML returns structured error."""
    result = parse_search_xml("not actually xml <<<")
    assert result.get("isError") is True
    assert result.get("errorCode") == "INVALID_XML"


def test_parse_empty_response():
    """XML with no response element returns error."""
    result = parse_search_xml("<yandexsearch></yandexsearch>")
    assert result.get("isError") is True
    assert result.get("errorCode") == "NO_RESPONSE"
