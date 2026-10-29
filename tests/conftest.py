import pytest

from chaejeom.cli.i18n import set_language


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    # Evaluation writes .chaejeom_cache to the working directory, so isolate each test's cache.
    monkeypatch.chdir(tmp_path)
    # Keep the user settings file out of the real home directory.
    monkeypatch.setattr("chaejeom.cli.settings.SETTINGS_PATH", tmp_path / "settings.yaml")


@pytest.fixture(autouse=True)
def _english_screen():
    # The UI language is module-global state; reset it so a test that switches to Korean cannot leak.
    set_language("en")
    yield
    set_language("en")
