"""Which archived pages the discovery loop chooses to seed.

Loaded by path, like the other script tests: `scripts/` is not a package.

The ranking is the whole value of the step. Seeding each dated domain's home page
was measured at 0.1 net-new names per page, because a small site of the period
links inward and nowhere else, so a builder that quietly fell back to roots would
look like it was working and return almost nothing.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "build_expand_seeds",
    Path(__file__).resolve().parents[1] / "scripts" / "build_expand_seeds.py",
)
build_expand_seeds = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_expand_seeds)

rank_pages = build_expand_seeds.rank_pages


def test_a_page_of_links_outranks_the_home_page():
    urls = [
        "http://x.com/",
        "http://x.com/about.html",
        "http://x.com/links.html",
    ]
    assert rank_pages(urls, 1) == ["http://x.com/links.html"]


def test_the_root_is_the_fallback_every_site_has():
    urls = ["http://x.com/products/widget3.html", "http://x.com/"]
    assert rank_pages(urls, 1) == ["http://x.com/"]


def test_images_are_not_pages():
    """A capture of a GIF costs a fetch and can never yield an outbound domain."""
    urls = ["http://x.com/banner.gif", "http://x.com/logo.JPG", "http://x.com/style.css"]
    assert rank_pages(urls, 5) == []


def test_it_returns_at_most_what_was_asked_for():
    urls = [f"http://x.com/links{i}.html" for i in range(10)]
    assert len(rank_pages(urls, 3)) == 3


def test_no_pages_means_no_seeds_rather_than_a_guessed_root():
    """A domain whose only captures are images contributes nothing, and saying so
    is what keeps the seed list honest about how many domains it really covers."""
    assert rank_pages([], 2) == []
