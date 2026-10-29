"""User settings that interactive mode remembers across sessions (currently only the UI language).

Everything else (model, metrics, ...) belongs in a config file saved with ``/config save``, so runs stay reproducible.
"""

from pathlib import Path

import yaml

SETTINGS_PATH = Path.home() / ".chaejeom" / "settings.yaml"


def load_settings(path: Path | None = None) -> dict:
    """Return the saved settings, or an empty dict if the file is missing or invalid."""
    path = path or SETTINGS_PATH
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(values: dict, path: Path | None = None) -> None:
    """Merge ``values`` into the saved settings. Write errors are ignored so interactive mode keeps going."""
    path = path or SETTINGS_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({**load_settings(path), **values}, allow_unicode=True), encoding="utf-8")
    except OSError:
        pass
