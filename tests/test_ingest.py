"""Unit tests for shared/ingest.py."""

import json
from unittest.mock import MagicMock, patch

from shared.ingest import fetch_data, raw_object_key, to_raw_record

# ── Sample API response (mirrors Open-Meteo structure) ───────────────
SAMPLE_API_RESPONSE = {
    "latitude": 48.86,
    "longitude": 2.3599997,
    "generationtime_ms": 0.05,
    "utc_offset_seconds": 0,
    "current": {
        "time": "2026-06-18T12:00",
        "interval": 900,
        "temperature_2m": 25.3,
        "wind_speed_10m": 12.1,
        "relative_humidity_2m": 55,
    },
}


class TestFetchData:
    @patch("shared.ingest.urllib.request.urlopen")
    def test_returns_parsed_json(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(SAMPLE_API_RESPONSE).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = fetch_data("https://example.com/api")
        assert result == SAMPLE_API_RESPONSE
        mock_urlopen.assert_called_once_with("https://example.com/api", timeout=10)


class TestToRawRecord:
    def test_wraps_payload_with_metadata(self):
        record = to_raw_record(SAMPLE_API_RESPONSE)

        assert "ingested_at" in record
        assert record["source"] == "open-meteo"
        assert record["payload"] == SAMPLE_API_RESPONSE

    def test_ingested_at_is_iso_format(self):
        record = to_raw_record(SAMPLE_API_RESPONSE)
        # Should be parseable as an ISO timestamp
        from datetime import datetime

        datetime.fromisoformat(record["ingested_at"])


class TestRawObjectKey:
    def test_default_prefix(self):
        key = raw_object_key()
        assert key.startswith("raw/year=")
        assert "/month=" in key
        assert "/day=" in key
        assert key.endswith(".json")

    def test_custom_prefix(self):
        key = raw_object_key(prefix="landing")
        assert key.startswith("landing/year=")
