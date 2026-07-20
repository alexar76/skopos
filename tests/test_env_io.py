"""env_io helpers."""

from __future__ import annotations

from skopos.env_io import upsert_env_var


def test_upsert_env_var_creates_and_updates(tmp_path):
    env_path = tmp_path / ".env"
    upsert_env_var("TELEGRAM_BOT_TOKEN", "first", env_path=env_path)
    assert env_path.read_text(encoding="utf-8").strip() == "TELEGRAM_BOT_TOKEN=first"

    upsert_env_var("TELEGRAM_BOT_TOKEN", "second", env_path=env_path)
    text = env_path.read_text(encoding="utf-8")
    assert text.count("TELEGRAM_BOT_TOKEN=") == 1
    assert "TELEGRAM_BOT_TOKEN=second" in text

    upsert_env_var("OTHER_KEY", "x", env_path=env_path)
    text = env_path.read_text(encoding="utf-8")
    assert "OTHER_KEY=x" in text
    assert "TELEGRAM_BOT_TOKEN=second" in text
