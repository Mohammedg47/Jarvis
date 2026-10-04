import pytest

from jarvis.core.config import Settings
from jarvis.google.auth import GoogleError, get_credentials


def test_background_use_without_token_does_not_open_browser(tmp_path):
    settings = Settings(data_dir=tmp_path)
    with pytest.raises(GoogleError, match="python -m jarvis.google"):
        get_credentials(settings, interactive=False)


def test_login_without_credentials_file_explains_setup(tmp_path):
    settings = Settings(data_dir=tmp_path)
    with pytest.raises(GoogleError, match="google-setup.md"):
        get_credentials(settings)
