import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "wa", Path(__file__).parents[1] / "scripts/engines/wayback_available.py"
)
wa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wa)


def test_a_hit_is_the_exact_host_in_the_rows_year_and_www_folding_is_not_one():
    def c(ts, url):
        return {
            "timestamp": ts,
            "status": "200",
            "url": "http://web.archive.org/web/" + ts + "/" + url,
        }

    assert wa.verdict("2001", "www.aki.cz", c("20010516005039", "http://www.aki.cz:80/")) == "hit"
    assert (
        wa.verdict("1996", "www.info-s.com", c("19961227090727", "http://info-s.com:80/"))
        == "folded"
    )
    assert wa.verdict("2001", "www.x.de", c("20220628183447", "http://www.x.de/")) == "miss"
    assert wa.original("http://web.archive.org/web/2001/http://a.b/c") == "http://a.b/c"
