"""The attrition index parser, and the two rules that decide what it admits.

Loaded by path, like the other script tests: `scripts/` is not a package.
"""

import importlib.util
from collections import Counter
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "collect_attrition",
    Path(__file__).resolve().parents[1] / "scripts" / "collect_attrition.py",
)
collect_attrition = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(collect_attrition)


def _page(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "1999-11.html"
    path.write_text(body)
    return path


def test_reads_date_host_and_mirror_path(tmp_path: Path) -> None:
    stats: Counter = Counter()
    rows = collect_attrition.rows_in(
        _page(
            tmp_path,
            '[99.11.30] Li [potus] <a href="1999/11/30/www.coronus.com/">Coronus</a>'
            ' (<a href="http://www.coronus.com">www.coronus.com</a>)\n',
        ),
        stats,
    )
    assert rows == [("www.coronus.com", 1999, 11, 30, "1999/11/30/www.coronus.com")]
    assert stats["date_confirmed_twice"] == 1


def test_a_two_digit_year_maps_into_the_right_century(tmp_path: Path) -> None:
    stats: Counter = Counter()
    rows = collect_attrition.rows_in(
        _page(tmp_path, "[01.05.02] NT [x] Something ( www.example.com )\n"), stats
    )
    assert rows[0][1] == 2001


def test_a_year_disagreement_is_dropped(tmp_path: Path) -> None:
    """The two witnesses must agree on the YEAR, which is the claim being made."""
    stats: Counter = Counter()
    rows = collect_attrition.rows_in(
        _page(
            tmp_path,
            '[99.08.23] Li [x] <a href="1998/08/23/www.prim-nov.si/">Org</a> ( www.prim-nov.si )\n',
        ),
        stats,
    )
    assert rows == []
    assert stats["dropped_year_disagreement"] == 1


def test_a_day_disagreement_is_kept_and_counted(tmp_path: Path) -> None:
    """A day-level disagreement cannot move a record between annual files, so
    dropping it would discard a real observation to guard a risk it does not carry."""
    stats: Counter = Counter()
    rows = collect_attrition.rows_in(
        _page(
            tmp_path,
            '[99.08.09] Li [x] <a href="1999/08/08/www.phonefun.com/">Org</a>'
            " ( www.phonefun.com )\n",
        ),
        stats,
    )
    assert len(rows) == 1
    assert rows[0][1] == 1999
    assert stats["kept_day_disagreement"] == 1
    assert stats["dropped_year_disagreement"] == 0


def test_new_year_rows_are_counted_so_the_exposure_is_bounded(tmp_path: Path) -> None:
    """The mirror's date is when it recorded the defacement, a day or two after the
    host was seen live, which only crosses a year boundary at New Year."""
    stats: Counter = Counter()
    collect_attrition.rows_in(_page(tmp_path, "[00.01.02] NT [x] Org ( www.example.com )\n"), stats)
    assert stats["dated_1_or_2_january"] == 1


def test_navigation_lines_are_not_rows(tmp_path: Path) -> None:
    """The index pages open with bracketed navigation links that also start `[`."""
    stats: Counter = Counter()
    rows = collect_attrition.rows_in(
        _page(tmp_path, '[<a href="/news">Attrition News</a>]--[<a href="stats.html">Stats</a>]\n'),
        stats,
    )
    assert rows == []
    assert stats["rows"] == 0


def test_a_row_with_no_host_is_counted_not_guessed(tmp_path: Path) -> None:
    stats: Counter = Counter()
    rows = collect_attrition.rows_in(
        _page(tmp_path, "[99.11.30] Li [somebody] An organisation with no site listed\n"), stats
    )
    assert rows == []
    assert stats["row_without_host"] == 1


def test_only_index_pages_are_read(tmp_path: Path) -> None:
    """The mirror also publishes per-TLD and per-defacer breakouts that re-slice
    the same rows, so taking them too would count every defacement twice."""
    assert collect_attrition.INDEX.match("1999-11.html")
    assert collect_attrition.INDEX.match("1998.html")
    assert not collect_attrition.INDEX.match("com.html")
    assert not collect_attrition.INDEX.match("ytcracker.html")
