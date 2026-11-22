"""Unit tests for the community feature (pure logic, no Flask app or DB)."""

from types import SimpleNamespace

import pytest

from app.features.community.models import Community
from app.features.community.services import (
    build_logo_storage_filename,
    is_allowed_logo_filename,
    normalize_community_name,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("  Music Lab  ", "Music Lab"),
        ("DiversoLab", "DiversoLab"),
        ("   ", ""),
        (None, ""),
    ],
)
def test_normalize_community_name_strips_whitespace(raw, expected):
    assert normalize_community_name(raw) == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("logo.png", True),
        ("banner.JPG", True),
        ("emblem.jpeg", True),
        ("crest.svg", True),
        ("avatar.webp", True),
        ("anim.gif", True),
        ("notes.txt", False),
        ("script.py", False),
        ("no_extension", False),
        ("", False),
        (None, False),
    ],
)
def test_is_allowed_logo_filename_checks_extension(filename, expected):
    assert is_allowed_logo_filename(filename) is expected


def test_build_logo_storage_filename_generates_unique_safe_name():
    first = build_logo_storage_filename("My Logo.PNG")
    second = build_logo_storage_filename("My Logo.PNG")

    assert first.startswith("community_")
    assert first.endswith(".png")
    assert second.endswith(".png")
    assert first != second


def test_build_logo_storage_filename_rejects_disallowed_extension():
    with pytest.raises(ValueError):
        build_logo_storage_filename("malware.exe")


def test_community_is_curator_checks_authenticated_curator_ids():
    curator = SimpleNamespace(id=10, is_authenticated=True)
    outsider = SimpleNamespace(id=20, is_authenticated=True)
    anonymous = SimpleNamespace(id=None, is_authenticated=False)
    community = SimpleNamespace(curators=[curator])

    assert Community.is_curator(community, curator) is True
    assert Community.is_curator(community, outsider) is False
    assert Community.is_curator(community, anonymous) is False
    assert Community.is_curator(community, None) is False


def test_community_get_logo_url_handles_none_and_external_paths():
    assert Community.get_logo_url(SimpleNamespace(logo=None)) is None
    assert Community.get_logo_url(SimpleNamespace(logo="/static/img/logo.svg")) == "/static/img/logo.svg"
    assert (
        Community.get_logo_url(SimpleNamespace(logo="https://example.com/logo.png")) == "https://example.com/logo.png"
    )
