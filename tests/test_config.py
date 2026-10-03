from jarvis.core.config import Settings
from jarvis.core.logging import setup_logging


def test_settings_read_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "abc")
    monkeypatch.setenv("JARVIS_PERSONALITY", "formal")
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    settings = Settings(_env_file=None)
    assert settings.elevenlabs_api_key == "abc"
    assert settings.personality == "formal"
    assert settings.data_dir == tmp_path


def test_logging_writes_to_file(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    logger = setup_logging(settings)
    logger.info("hello log")
    for handler in logger.handlers:
        handler.flush()
    assert "hello log" in (tmp_path / "jarvis.log").read_text(encoding="utf-8")
