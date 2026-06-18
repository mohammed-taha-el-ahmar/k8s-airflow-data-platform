"""Unit tests for shared/transform.py."""

from shared.transform import transform_record

SAMPLE_RAW = {
    "ingested_at": "2026-06-18T12:00:00+00:00",
    "source": "open-meteo",
    "payload": {
        "latitude": 48.86,
        "longitude": 2.3599997,
        "current": {
            "temperature_2m": 25.3,
            "wind_speed_10m": 12.1,
            "relative_humidity_2m": 55,
        },
    },
}


class TestTransformRecord:
    def test_flattens_to_expected_keys(self):
        row = transform_record(SAMPLE_RAW)
        expected_keys = {
            "ingested_at",
            "latitude",
            "longitude",
            "temperature_c",
            "wind_speed_kmh",
            "humidity_pct",
        }
        assert set(row.keys()) == expected_keys

    def test_values_match_payload(self):
        row = transform_record(SAMPLE_RAW)
        assert row["ingested_at"] == "2026-06-18T12:00:00+00:00"
        assert row["latitude"] == 48.86
        assert row["longitude"] == 2.3599997
        assert row["temperature_c"] == 25.3
        assert row["wind_speed_kmh"] == 12.1
        assert row["humidity_pct"] == 55

    def test_handles_missing_current(self):
        raw = {
            "ingested_at": "2026-06-18T12:00:00+00:00",
            "source": "open-meteo",
            "payload": {"latitude": 48.86, "longitude": 2.36},
        }
        row = transform_record(raw)
        assert row["temperature_c"] is None
        assert row["wind_speed_kmh"] is None
        assert row["humidity_pct"] is None

    def test_handles_partial_current(self):
        raw = {
            "ingested_at": "2026-06-18T12:00:00+00:00",
            "source": "open-meteo",
            "payload": {
                "latitude": 48.86,
                "longitude": 2.36,
                "current": {"temperature_2m": 30.0},
            },
        }
        row = transform_record(raw)
        assert row["temperature_c"] == 30.0
        assert row["wind_speed_kmh"] is None
        assert row["humidity_pct"] is None
