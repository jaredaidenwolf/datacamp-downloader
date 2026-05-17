import json
import unittest

from datacamp_downloader.json_fetch import (
    JsonFetchError,
    extract_json_text,
    parse_json_response,
)


class TestJsonFetch(unittest.TestCase):
    def test_raw_json(self):
        payload = {"completed_courses": [{"id": 1}]}
        text = json.dumps(payload)
        self.assertEqual(extract_json_text(text), text)
        self.assertEqual(parse_json_response(text), payload)

    def test_chrome_pre_viewer(self):
        html = '<html><body><pre>{"user":{"slug":"test"},"completed_courses":[]}</pre></body></html>'
        data = parse_json_response(extract_json_text(html))
        self.assertEqual(data["user"]["slug"], "test")

    def test_empty_raises(self):
        with self.assertRaises(JsonFetchError):
            parse_json_response("")

    def test_html_challenge_hint(self):
        html = "<!DOCTYPE html><html><title>Just a moment...</title></html>"
        with self.assertRaises(JsonFetchError) as ctx:
            parse_json_response(html)
        self.assertIn("HTML", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
