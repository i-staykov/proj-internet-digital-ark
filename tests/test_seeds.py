"""The auxiliary seed pool: what counts as a seed, and what a consumer can read."""

import csv
from collections import Counter
from pathlib import Path

import duckdb

from ark.bulk import BulkRecord, SourceSpec
from ark.seeds import combine_parts, write_source_part


def _spec(key: str, records: list[BulkRecord]) -> SourceSpec:
    def parse(_path: Path, _stats: Counter):
        yield from records

    return SourceSpec(
        key=key,
        source_name=key,
        evidence_type="cdx_timestamp",
        acquisition_method="test",
        parse=parse,
    )


def _rec(raw: str, year: int = 1998) -> BulkRecord:
    return BulkRecord(raw=raw, year=year, evidence_value=f"{year}0101000000")


def _run(tmp_path: Path, spec: SourceSpec) -> tuple[Counter, dict]:
    parts, out = tmp_path / "parts", tmp_path / "seeds"
    stats = write_source_part(spec, [tmp_path / "input"], parts_dir=parts)
    result = combine_parts(seed_dir=out, parts_dir=parts)
    return stats, result


def test_a_raw_value_that_is_already_the_domain_is_not_a_seed(tmp_path: Path) -> None:
    stats, result = _run(tmp_path, _spec("s", [_rec("example.com")]))
    # the annual files already carry it, so it adds nothing to a download list
    assert stats["no_extra_granularity"] == 1
    assert stats["seeds"] == 0
    assert result["seeds"] == 0


def test_a_subdomain_is_a_seed_carrying_its_registered_domain(tmp_path: Path) -> None:
    _, result = _run(tmp_path, _spec("s", [_rec("shop.example.com")]))
    rows = list(csv.DictReader((tmp_path / "seeds" / "download_seeds.csv").open()))
    assert rows == [
        {"seed": "shop.example.com", "domain": "example.com", "year": "1998", "source": "s"}
    ]
    assert result["domains"] == 1


def test_out_of_window_years_never_reach_the_pool(tmp_path: Path) -> None:
    spec = _spec("s", [_rec("a.example.com", 1995), _rec("b.example.com", 1999)])
    _, result = _run(tmp_path, spec)
    assert result["seeds"] == 1
    assert (tmp_path / "seeds" / "download_seeds.txt").read_text() == "b.example.com\n"


def test_the_same_seed_in_two_years_is_two_rows_but_one_download(tmp_path: Path) -> None:
    spec = _spec("s", [_rec("www.example.com", 1997), _rec("www.example.com", 2000)])
    _, result = _run(tmp_path, spec)
    # the table keeps both years as evidence of when it was seen; the download
    # list is what a crawler consumes, so it holds the URL once
    assert result["rows"] == 2
    assert result["seeds"] == 1


def test_rerunning_one_source_replaces_only_its_own_rows(tmp_path: Path) -> None:
    parts, out = tmp_path / "parts", tmp_path / "seeds"
    write_source_part(_spec("first", [_rec("a.example.com")]), [tmp_path / "in"], parts_dir=parts)
    write_source_part(_spec("second", [_rec("b.example.org")]), [tmp_path / "in"], parts_dir=parts)
    write_source_part(_spec("first", [_rec("c.example.net")]), [tmp_path / "in"], parts_dir=parts)

    result = combine_parts(seed_dir=out, parts_dir=parts)
    seeds = (out / "download_seeds.txt").read_text().split()
    assert seeds == ["b.example.org", "c.example.net"]
    assert result["parts"] == 2


def test_a_url_containing_commas_survives_the_round_trip(tmp_path: Path) -> None:
    url = "http://books.example.co.uk/news/0,6109,393333,00.html"
    _run(tmp_path, _spec("s", [_rec(url)]))

    # a reader that sniffs quoting from the first rows must still get 4 columns,
    # which is why the seed column is always quoted
    table = (
        duckdb.connect()
        .execute(
            f"SELECT seed, domain FROM read_csv_auto('{tmp_path / 'seeds' / 'download_seeds.csv'}')"
        )
        .fetchall()
    )
    assert table == [(url, "example.co.uk")]


def test_an_empty_pool_reports_itself_rather_than_writing_files(tmp_path: Path) -> None:
    result = combine_parts(seed_dir=tmp_path / "seeds", parts_dir=tmp_path / "parts")
    assert result == {"parts": 0, "seeds": 0}
    assert not (tmp_path / "seeds" / "download_seeds.txt").exists()
