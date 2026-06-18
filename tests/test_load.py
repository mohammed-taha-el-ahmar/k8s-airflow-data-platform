"""Unit tests for shared/load.py — connection logic tested with mocks."""

from unittest.mock import MagicMock, patch

from shared.load import WAREHOUSE_TABLE_DDL, ensure_table, load_row


class TestEnsureTable:
    def test_executes_ddl_and_commits(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        ensure_table(mock_conn)

        mock_cursor.execute.assert_called_once_with(WAREHOUSE_TABLE_DDL)
        mock_conn.commit.assert_called_once()


class TestLoadRow:
    @patch("shared.load.get_connection")
    def test_inserts_row_and_returns_id(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (42,)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_get_conn.return_value = mock_conn

        row = {
            "ingested_at": "2026-06-18T12:00:00+00:00",
            "latitude": 48.86,
            "longitude": 2.36,
            "temperature_c": 25.0,
            "wind_speed_kmh": 12.0,
            "humidity_pct": 55,
        }

        result = load_row(row)

        assert result == 42
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called_once()

    def test_uses_provided_connection(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (7,)
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        row = {
            "ingested_at": "2026-06-18T12:00:00+00:00",
            "latitude": 48.86,
            "longitude": 2.36,
            "temperature_c": 25.0,
            "wind_speed_kmh": 12.0,
            "humidity_pct": 55,
        }

        result = load_row(row, conn=mock_conn)

        assert result == 7
        # Should NOT close the connection when one was provided
        mock_conn.close.assert_not_called()
