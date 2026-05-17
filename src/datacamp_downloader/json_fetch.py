import json
import re
from bs4 import BeautifulSoup


class JsonFetchError(Exception):
    def __init__(self, message: str, *, url: str = "", preview: str = ""):
        self.url = url
        self.preview = preview
        super().__init__(message)

    def __str__(self):
        parts = [super().__str__()]
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.preview:
            parts.append(f"Response preview: {self.preview[:500]}")
        return "\n".join(parts)


def extract_json_text(page: str) -> str:
    """Extract JSON from a browser page (raw JSON, Chrome <pre> viewer, or script tags)."""
    page = (page or "").strip()
    if not page:
        return ""

    if page[0] in "{[":
        return page

    soup = BeautifulSoup(page, "html.parser")
    pre = soup.find("pre")
    if pre and pre.text.strip():
        return pre.text.strip()

    for script in soup.find_all("script", type="application/json"):
        text = (script.string or script.get_text() or "").strip()
        if text and text[0] in "{[":
            return text

    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data:
        text = (next_data.string or next_data.get_text() or "").strip()
        if text:
            return text

    match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", page)
    if match:
        return match.group(0)

    return page


def parse_json_response(body: str, *, url: str = ""):
    body = (body or "").strip()
    if not body:
        raise JsonFetchError(
            "Empty response from DataCamp (no JSON body).",
            url=url,
            preview="",
        )

    text = extract_json_text(body)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        lowered = body.lower()
        if "<html" in lowered or "<!doctype" in lowered or "just a moment" in lowered:
            hint = (
                "Received HTML instead of JSON. Your token may be expired, or "
                "DataCamp blocked the request (Cloudflare). Try `datacamp reset` "
                "and `datacamp set-token` with a fresh `_dct` cookie."
            )
        else:
            hint = "Response was not valid JSON."
        raise JsonFetchError(hint, url=url, preview=body[:500]) from exc
