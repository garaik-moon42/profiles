"""Load and validate the gdocs generator configuration."""

import yaml

REQUIRED_KEYS = ("targetFolderId", "templateId", "spreadsheetId")


class ConfigError(ValueError):
    """Invalid configuration; the message is user-facing (Hungarian)."""


def load_config(path):
    try:
        with open(path, encoding="utf-8") as source:
            config = yaml.safe_load(source)
    except FileNotFoundError:
        raise ConfigError(f"A konfigurációs fájl nem található: {path}") from None
    except yaml.YAMLError as error:
        raise ConfigError(f"Érvénytelen konfigurációs YAML ({path}): {error}") from None

    if not isinstance(config, dict):
        raise ConfigError(f"A konfiguráció gyökere YAML-objektum legyen: {path}")

    for key in REQUIRED_KEYS:
        value = config.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"Hiányzó vagy üres konfigurációs érték: {key} ({path})")
        config[key] = value.strip()
    return config
