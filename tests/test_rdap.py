"""RDAP creation-year extraction, the attested-year rule, retries, and routing.

Network is never touched: `fetch` and `sleep` are injected.
"""

import json

from ark.rdap import (
    RDAP_REDIRECTOR,
    Router,
    attested_years,
    creation_year,
    journal_path,
    load_registries,
    lookup,
    open_journal_for_write,
    parse_bootstrap,
    queried_domains,
    rdap_url,
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
        write_journal_line(fh, {"domain": "a.com", "status": 200, "creation_year": 1997})
        write_journal_line(fh, {"domain": "b.com", "status": 404, "creation_year": None})
        # a transport failure is not an answer, so this one must be retried
        write_journal_line(fh, {"domain": "c.com", "status": 0, "creation_year": None})
    # a later run skips only what was actually answered: 200 (dated) and 404
    # ("no RDAP record", a finding), never a failed request
    assert queried_domains(tmp_path) == {"a.com", "b.com"}


def test_resume_set_is_empty_for_a_missing_folder(tmp_path) -> None:
    assert queried_domains(tmp_path / "nope") == set()


_BOOTSTRAP = json.dumps(
    {
        "version": "1.0",
        "services": [
            [["com", "net"], ["https://rdap.verisign.com/com/v1/"]],
            [["org"], ["http://legacy.example/", "https://rdap.pir.org/rdap/"]],
        ],
    }
)


def test_parse_bootstrap_maps_every_tld_and_prefers_https() -> None:
    registries = parse_bootstrap(_BOOTSTRAP)
    assert registries["com"] == "https://rdap.verisign.com/com/v1/"
    # a service entry naming several TLDs maps all of them
    assert registries["net"] == "https://rdap.verisign.com/com/v1/"
    # https wins over the http alternative the same service publishes
    assert registries["org"] == "https://rdap.pir.org/rdap/"


def test_parse_bootstrap_survives_garbage() -> None:
    assert parse_bootstrap("not json") == {}
    assert parse_bootstrap(json.dumps({"services": [["only-tlds"]]})) == {}


def test_rdap_url_goes_direct_when_the_registry_is_known() -> None:
    registries = parse_bootstrap(_BOOTSTRAP)
    assert rdap_url("x.com", registries) == "https://rdap.verisign.com/com/v1/domain/x.com"


def test_rdap_url_falls_back_to_the_redirector() -> None:
    # a TLD with no bootstrap entry, and a name with no dot at all
    assert rdap_url("x.example", parse_bootstrap(_BOOTSTRAP)) == f"{RDAP_REDIRECTOR}x.example"
    assert rdap_url("localhost", {}) == f"{RDAP_REDIRECTOR}localhost"


def test_load_registries_caches_the_bootstrap_and_reuses_it(tmp_path) -> None:
    cache = tmp_path / "dns.json"
    calls = {"n": 0}

    def fetch(_url: str) -> tuple[int, str]:
        calls["n"] += 1
        return 200, _BOOTSTRAP

    assert load_registries(cache, fetch)["com"].startswith("https://rdap.verisign.com")
    assert cache.exists()
    # a fresh cache is read from disk rather than re-fetched
    assert load_registries(cache, fetch)["net"]
    assert calls["n"] == 1


def test_load_registries_keeps_the_cache_when_the_refresh_fails(tmp_path) -> None:
    cache = tmp_path / "dns.json"
    cache.write_text(_BOOTSTRAP, encoding="utf-8")
    # stale by a year, and IANA refuses: the cached map is still better than none
    registries = load_registries(cache, lambda _u: (503, ""), max_age=0.0)
    assert registries["com"] == "https://rdap.verisign.com/com/v1/"


def test_load_registries_is_empty_with_no_cache_and_no_answer(tmp_path) -> None:
    # an empty map is a valid answer: every query then goes via the redirector
    assert load_registries(tmp_path / "missing.json", lambda _u: (0, "")) == {}


def test_router_paces_each_registry_separately() -> None:
    router = Router(parse_bootstrap(_BOOTSTRAP))
    com = router.governor(router.url("x.com"))
    net = router.governor(router.url("y.net"))
    org = router.governor(router.url("z.org"))
    # .com and .net share a registry host, so they share one pace
    assert com is net
    # a different registry gets its own, so one refusing never slows the others
    assert org is not com


def test_lookup_records_the_endpoint_it_used() -> None:
    router = Router(parse_bootstrap(_BOOTSTRAP))
    seen: list[str] = []

    def fetch(url: str) -> tuple[int, str]:
        seen.append(url)
        return 200, _BODY

    record = lookup("x.com", fetch, sleep=_no_sleep, router=router)
    assert seen == ["https://rdap.verisign.com/com/v1/domain/x.com"]
    # the journal keeps the endpoint, so the evidence URL is the one asked
    assert record["url"] == "https://rdap.verisign.com/com/v1/domain/x.com"
    assert record["creation_year"] == 1998


def test_lookup_without_a_router_still_uses_the_redirector() -> None:
    record = lookup("x.com", fetch=lambda _u: (200, _BODY), sleep=_no_sleep)
    assert record["url"] == f"{RDAP_REDIRECTOR}x.com"


def test_a_403_block_slows_the_registry_down_and_never_settles_the_domain() -> None:
    # PIR answered ~850 .org queries then returned 403 for 9,253 in a row on
    # 2026-08-08. A block has to reach the governor, or the run keeps asking.
    from ark.rdap import answered

    router = Router(parse_bootstrap(_BOOTSTRAP))
    governor = router.governor(router.url("x.org"))
    before = governor.delay
    record = lookup("x.org", fetch=lambda _u: (403, ""), retries=1, sleep=_no_sleep, router=router)
    assert record["status"] == 403
    assert governor.delay > before
    assert governor.throttles == 1
    # and a blocked query is not an answer, so the name stays queryable
    assert not answered(record)


def test_a_refusal_never_settles_a_domain_however_it_was_routed() -> None:
    router = Router(parse_bootstrap(_BOOTSTRAP))
    record = lookup("x.com", fetch=lambda _u: (429, ""), retries=1, sleep=_no_sleep, router=router)
    assert record["status"] == 429
    # the hard rule: a 429 is not an answer, so the domain stays queryable
    from ark.rdap import answered

    assert not answered(record)
