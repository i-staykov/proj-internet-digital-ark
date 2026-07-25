"""RDAP creation-year extraction, the attested-year rule, and retry logic.

Network is never touched: `fetch` and `sleep` are injected.
"""

import json

from ark.rdap import (
    attested_years,
    creation_year,
    journal_path,
    lookup,
    open_journal_for_write,
    queried_domains,
    registration_year,
    write_journal_line,
)

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


def test_attested_years_is_the_creation_year_alone() -> None:
    # brief III.6: the creation date attests its own year and no later one
    assert attested_years(1998) == (1998,)
    assert attested_years(1996) == (1996,)
    assert attested_years(2001) == (2001,)


def test_attested_years_empty_outside_the_window() -> None:
    # created before the window: existed by then, but no single year is attested
    assert attested_years(1995) == ()
    assert attested_years(1970) == ()
    assert attested_years(2004) == ()


def test_lookup_returns_a_journal_record() -> None:
    record = lookup("x.com", fetch=lambda _u: (200, _BODY), sleep=_no_sleep)
    assert record["domain"] == "x.com"
    assert record["status"] == 200
    assert record["creation_year"] == 1998
    # the whole response is kept, so a later standard change is a re-parse
    assert record["response"]["events"][1]["eventAction"] == "registration"
    assert record["queried_at"]


def test_lookup_journals_failures_too() -> None:
    record = lookup("gone.com", fetch=lambda _u: (404, ""), sleep=_no_sleep)
    assert record["status"] == 404
    assert record["creation_year"] is None
    assert record["response"] is None


def test_lookup_keeps_status_when_the_body_is_not_json() -> None:
    record = lookup("x.com", fetch=lambda _u: (200, "<html>nope"), sleep=_no_sleep)
    assert record["status"] == 200
    assert record["creation_year"] is None
    assert record["response"] is None


def test_journal_round_trip_and_resume_set(tmp_path) -> None:
    path = journal_path(tmp_path)
    assert path.name.startswith("rdap_") and path.name.endswith(".jsonl.gz")
    with open_journal_for_write(path) as fh:
        write_journal_line(fh, {"domain": "a.com", "creation_year": 1997})
        write_journal_line(fh, {"domain": "b.com", "creation_year": None})
    # a later run skips everything any journal in the folder already covers
    assert queried_domains(tmp_path) == {"a.com", "b.com"}


def test_resume_set_is_empty_for_a_missing_folder(tmp_path) -> None:
    assert queried_domains(tmp_path / "nope") == set()
