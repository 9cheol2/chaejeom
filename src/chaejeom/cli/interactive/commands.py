"""Command names, usage strings and shared constants."""

from chaejeom.cli.i18n import t

LANGUAGE_ALIASES = {"english": "en", "korean": "ko", "한국어": "ko"}
# Returned by read_command on the first Ctrl+C in an empty input box; a second press exits.
EXIT_ARMED = "\x03"
QUOTES = '"\''

COMMANDS = [
    "/data",
    "/metrics",
    "/model",
    "/temperature",
    "/effort",
    "/embedding",
    "/domain",
    "/prompt",
    "/run",
    "/show",
    "/runs",
    "/config",
    "/language",
    "/help",
    "/exit",
]

# Usage column of /help: <> marks a required value, [] an optional one.
USAGE = {
    "/data": "/data [file]",
    "/metrics": "/metrics [metric ids]",
    "/model": "/model [model] [value]",
    "/temperature": "/temperature [0-2]",
    "/effort": "/effort [low|medium|high]",
    "/embedding": "/embedding [model]",
    "/domain": "/domain [file|off]",
    "/prompt": "/prompt [metric|file]",
    "/run": "/run [n]",
    "/show": "/show [all|sample [framework|axis]]",
    "/runs": "/runs [n]",
    "/config": "/config [file|save]",
    "/language": "/language [en|ko]",
    "/help": "/help",
    "/exit": "/exit",
}


def describe(command: str) -> str:
    return t(f"cmd.{command}")
