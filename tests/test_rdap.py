"""RDAP creation-year extraction and retry logic (offline, injected fetch)."""

import json

from ark.rdap import creation_year, registration_year

_BODY = json.dumps(
    {
        "events": [
            {"eventAction": "last changed", "eventDate": "2020-01-01T00:00:00Z"},
            {"eventAction": "registration", "eventDate": "1998-03-15T00:00:00Z"},
        ]
    }
)


def _no_sleep(_seconds: float) -> None:
    return None


def test_registration_year_reads_the_registration_event() -> None:
    assert registration_year(_BODY) == 1998


def test_registration_year_none_when_absent_or_garbage() -> None:
    assert registration_year(json.dumps({"events": []})) is None
    assert registration_year("not json at all") is None


def test_creation_year_on_200() -> None:
    assert creation_year("x.com", fetch=lambda _u: (200, _BODY), sleep=_no_sleep) == 1998


def test_creation_year_none_on_404() -> None:
    assert creation_year("x.com", fetch=lambda _u: (404, ""), sleep=_no_sleep) is None


def test_creation_year_retries_a_transient_error_then_succeeds() -> None:
    calls = {"n": 0}

    def flaky(_url: str) -> tuple[int, str]:
        calls["n"] += 1
        return (429, "") if calls["n"] == 1 else (200, _BODY)

    assert creation_year("x.com", fetch=flaky, sleep=_no_sleep) == 1998
    assert calls["n"] == 2


def test_creation_year_gives_up_after_retries() -> None:
    assert creation_year("x.com", fetch=lambda _u: (503, ""), retries=2, sleep=_no_sleep) is None
