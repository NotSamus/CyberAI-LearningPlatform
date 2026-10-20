"""The light and dark versions of every theme, read from the frontend's stylesheets (no database).

The dark colours are written twice, for a device set to dark and for an account that chose dark
(frontend/app/globals.css explains why): the two copies must stay the same. Every version of a theme
must set every colour the others set, or Standard's would show through. And every text colour must
stay at least 4.5:1 on what it stands on (3:1 for the outlines of fields), in all six versions."""
import re
from pathlib import Path

import pytest

STYLES = Path(__file__).resolve().parents[1] / "frontend" / "app"
DARK_DEVICE = "@media (prefers-color-scheme: dark)"


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (STYLES / name).read_text(), flags=re.S)


def _end(css: str, start: int) -> int:
    """Where the block whose { is just before `start` ends."""
    depth, end = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(css[end], 0)
        end += 1
    return end


def _block(css: str, selector: str, inside_media: bool = False) -> dict[str, str]:
    """The custom properties set by the rules with exactly this selector: those inside the dark
    @media block when `inside_media`, otherwise those outside it."""
    dark = [(m.end(), _end(css, m.end())) for m in re.finditer(re.escape(DARK_DEVICE) + r"\s*\{", css)]
    found: dict[str, str] = {}
    rules = 0
    for rule in re.finditer(re.escape(selector) + r"\s*\{", css):
        if css[rule.start() - 1:rule.start()] not in ("", "\n", " ", "}", "{"):
            continue                        # part of a longer selector
        if any(a <= rule.start() < b for a, b in dark) != inside_media:
            continue
        rules += 1
        body = css[rule.end():_end(css, rule.end()) - 1]
        found.update({m.group(1): " ".join(m.group(2).split()) for m in re.finditer(r"--([a-z0-9-]+)\s*:\s*([^;]+);", body)})
    assert rules, f"no rule for {selector}"
    return found


GLOBALS, LEARN, THEMES = _css("globals.css"), _css("styles/learn.css"), _css("styles/themes.css")

STANDARD_LIGHT = {**_block(GLOBALS, ":root"), **_block(LEARN, ":root")}
STANDARD_DARK_DEVICE = {**_block(GLOBALS, ':root:not([data-mode="light"])', True), **_block(LEARN, ':root:not([data-mode="light"])', True)}
STANDARD_DARK_CHOSEN = {**_block(GLOBALS, ':root[data-mode="dark"]'), **_block(LEARN, ':root[data-mode="dark"]')}


def _theme(theme: str) -> tuple[dict, dict, dict]:
    """(light, dark for a dark device, dark when chosen) as the theme writes them."""
    return (
        _block(THEMES, f':root[data-theme="{theme}"]'),
        _block(THEMES, f':root[data-theme="{theme}"]:not([data-mode="light"])', True),
        _block(THEMES, f':root[data-theme="{theme}"][data-mode="dark"]'),
    )


def test_the_two_dark_copies_are_the_same():
    assert STANDARD_DARK_DEVICE == STANDARD_DARK_CHOSEN
    for theme in ("halloween", "retro"):
        _, device, chosen = _theme(theme)
        assert device == chosen, theme


@pytest.mark.parametrize("theme", ["halloween", "retro"])
def test_every_version_of_a_theme_sets_every_colour(theme):
    light, dark, _ = _theme(theme)
    assert set(STANDARD_DARK_DEVICE) - set(dark) == set(), "Standard's dark colours would show through"
    assert set(dark) - set(light) == set(), "the light version leaves these to Standard"


# What stands on what. A role that a theme does not have (only Retro 95 has --field) is left out.
PAIRS = [
    ("text", "bg"), ("text", "card"), ("text", "tint"), ("muted", "bg"), ("muted", "card"),
    ("accent", "bg"), ("accent", "card"), ("accent-text", "accent"), ("info", "accent-tint"),
    ("gpu", "card"), ("gpu", "good-tint"), ("error", "card"), ("error", "bad-tint"),
    ("warn", "card"), ("warn", "warn-tint"), ("bar-text", "navy"), ("bar-muted", "navy"),
    ("text", "field"), ("muted", "field"),
    *[(f"code-{part}", "code-bg") for part in ("text", "muted", "keyword", "string", "number", "comment", "function", "builtin", "type", "meta")],
]
OUTLINES = [("border-strong", "card"), ("border-strong", "bg")]


def _luminance(colour: str) -> float:
    h, s, light = (float(n) for n in re.match(r"hsla?\(\s*([\d.]+),\s*([\d.]+)%,\s*([\d.]+)%", colour).groups())
    s, light = s / 100, light / 100
    chroma = (1 - abs(2 * light - 1)) * s
    x = chroma * (1 - abs((h / 60) % 2 - 1))
    r, g, b = [(chroma, x, 0), (x, chroma, 0), (0, chroma, x), (0, x, chroma), (x, 0, chroma), (chroma, 0, x)][int(h // 60) % 6]
    channels = [c + light - chroma / 2 for c in (r, g, b)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _versions():
    yield "standard light", STANDARD_LIGHT
    yield "standard dark", {**STANDARD_LIGHT, **STANDARD_DARK_DEVICE}
    for theme in ("halloween", "retro"):
        light, dark, _ = _theme(theme)
        yield f"{theme} light", {**STANDARD_LIGHT, **light}
        yield f"{theme} dark", {**STANDARD_LIGHT, **STANDARD_DARK_DEVICE, **light, **dark}


@pytest.mark.parametrize(("name", "colours"), list(_versions()), ids=[name for name, _ in _versions()])
def test_text_stays_readable(name, colours):
    too_faint = []
    for pairs, least in ((PAIRS, 4.5), (OUTLINES, 3.0)):
        for front, back in pairs:
            if front in colours and back in colours and colours[front].startswith("hsl") and colours[back].startswith("hsl"):
                if (found := _contrast(colours[front], colours[back])) < least:
                    too_faint.append(f"--{front} on --{back}: {found:.2f}, needs {least}")
    assert too_faint == []
