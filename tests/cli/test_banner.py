from pathlib import Path

import pytest
from rich.console import Console

from chaejeom.cli import banner


def _width(line):
    return sum(banner.display_width(text) for text, _ in line)


def _text(line):
    return "".join(t for t, _ in line)


def test_hat_grid_is_rectangular_and_symmetric():
    assert len({len(r) for r in banner.HAT}) == 1
    assert {ch for row in banner.HAT for ch in row} <= set(banner.HAT_COLORS) | {"."}
    assert all([ch != "." for ch in row] == [ch != "." for ch in reversed(row)] for row in banner.HAT)


def test_hat_uses_only_background_colored_spaces():
    lines = banner.hat_lines()

    assert len(lines) == len(banner.HAT)
    assert {_width(line) for line in lines} == {len(banner.HAT[0])}
    # Half-block glyphs vary in width between fonts; plain spaces line up in every terminal.
    assert {ch for line in lines for text, _ in line for ch in text} == {" "}
    for row, line in zip(banner.HAT, lines):
        painted = [bool(style) for text, style in line for _ in text]
        assert painted == [ch != "." for ch in row]


def test_header_shows_name_models_and_path():
    lines = banner.header_lines(100, "gpt-4o-mini", "text-embedding-3-large", "0.1.0", Path.home() / "work")
    text = "\n".join(_text(line) for line in lines)

    assert "Chaejeom CLI v0.1.0" in text
    assert "gpt-4o-mini" in text and "text-embedding-3-large" in text
    assert "~/work" in text


@pytest.mark.parametrize("width", [70, 80, 110, 160])
def test_screen_fits_width(width):
    long_path = Path.home() / "projects" / ("아주긴폴더이름" * 5)
    lines = banner.startup_lines(width, "gpt-4o-mini", "text-embedding-3-large", "0.1.0", long_path)

    assert all(_width(line) <= min(width, banner.MAX_WIDTH) for line in lines)


def test_header_shortens_long_path():
    long_path = Path.home() / "projects" / ("아주긴폴더이름" * 5)
    lines = banner.header_lines(80, "gpt-4o-mini", "text-embedding-3-large", "0.1.0", long_path)
    path_line = next(line for line in lines if "directory:" in _text(line))

    assert "…" in _text(path_line)
    assert _width(path_line) <= 80


def _status(width=100, chosen=frozenset({"ragas.faithfulness", "trulens.groundedness", "deepeval.answer_relevancy"}), runs=3):
    from chaejeom.cli.views import metrics_grid

    return banner.status_lines(width, "gpt-4o-mini", ("temperature:", "0"), "text-embedding-3-large", metrics_grid(chosen), runs)


def test_status_lists_settings_with_aligned_labels():
    lines = [_text(line) for line in _status()]

    assert lines[0].split()[:4] == ["model:", "gpt-4o-mini", "temperature:", "0"] and lines[0].rstrip().endswith("exit")
    assert lines[1].split() == ["embedding:", "text-embedding-3-large"]
    assert lines[2].split() == ["domain:", "none"]
    assert lines[3].split() == ["metrics:", "Groundedness", "[RAGAS]", "DeepEval", "[TruLens]", "Chaejeom"]
    assert lines[4].split() == ["Context", "relevance", "RAGAS", "DeepEval", "TruLens", "Chaejeom"]
    assert lines[5].split() == ["Answer", "relevance", "RAGAS", "[DeepEval]", "TruLens", "Chaejeom"]
    assert lines[6].split() == ["runs:", "3"]
    assert len({line.index("gpt") if "gpt" in line else line.index("text") for line in lines[:2]}) == 1
    assert len({line.index("RAGAS") for line in lines[3:6]}) == 1


def test_status_drops_hint_when_narrow():
    wide, narrow = _status(100), _status(60)

    assert _width(wide[0]) == 99 and "exit" in _text(wide[0])
    assert "exit" not in _text(narrow[0])


def test_korean_screen_keeps_names_and_aligns():
    from chaejeom.cli.i18n import set_language

    set_language("ko")
    header = "\n".join(_text(line) for line in banner.header_lines(100, "gpt-4o-mini", "text-embedding-3-large", "0.1.0"))
    lines = _status(runs=2)

    assert "model:" in header and "embedding:" in header and "directory:" in header
    assert "/data로 데이터를 불러오거나 /help로 명령을 확인하세요" in header
    assert [text for text, style in banner.highlight("/data로 시작 /help로 확인") if style == banner.MODEL] == ["/data", "/help"]
    assert "Ctrl+C 종료" in _text(lines[0])
    assert _text(lines[3]).split()[:3] == ["metrics:", "Groundedness", "[RAGAS]"]
    assert _text(lines[6]).split() == ["runs:", "2"]
    starts = {_width(line[:2]) for line in lines}
    assert len(starts) == 1


@pytest.mark.parametrize(("version", "preview"), [("0.1.0.dev0", True), ("0.2.0rc1", True), ("0.2.0b3", True), ("0.1.0", False), ("1.0.0", False)])
def test_preview_label_only_for_pre_release(version, preview):
    from chaejeom.cli.i18n import set_language

    title = next(_text(line) for line in banner.header_lines(100, "m", "e", version) if "Chaejeom CLI" in _text(line))
    assert (" Preview" in title or " Beta" in title or " Release Candidate" in title) is preview
    assert ".dev" not in title

    set_language("ko")
    title = next(_text(line) for line in banner.header_lines(100, "m", "e", version) if "Chaejeom CLI" in _text(line))
    assert ("프리뷰" in title or "베타" in title or "출시 후보" in title) is preview


def test_display_version():
    assert _text(banner.display_version("0.1.0.dev0")) == "v0.1.0 Preview"
    assert _text(banner.display_version("0.2.0b1")) == "v0.2.0 Beta"
    assert _text(banner.display_version("1.0.0")) == "v1.0.0"
    assert _text(banner.display_version("1.0.0+local")) == "v1.0.0+local"


def test_key_hint_brightens_only_keys():
    line = banner.key_hint("↑↓←→ to move · Space to toggle · Enter to confirm · Esc to cancel")
    keys = [text for text, style in line if style == banner.TEXT]

    assert keys == ["↑↓←→", "Space", "Enter", "Esc"]
    assert [text for text, style in banner.key_hint("/ for commands · Ctrl+C to exit") if style == banner.TEXT] == ["/", "Ctrl+C"]


def test_print_startup_runs():
    console = Console(width=90, record=True, color_system="truecolor")

    banner.print_startup(console)

    assert "Chaejeom CLI" in console.export_text()



def test_hat_keeps_its_shape_in_16_color_terminals():
    lines = banner.hat_lines("standard")

    styles = {style for line in lines for _, style in line if style}
    assert styles <= {f"on {name}" for name in banner.HAT_COLORS_16.values()}
    for row, line in zip(banner.HAT, lines):
        assert [bool(style) for text, style in line for _ in text] == [ch != "." for ch in row]
