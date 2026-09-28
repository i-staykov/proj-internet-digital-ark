"""The funnel every name passes: one case per branch of `_canonicalize`, on the vendored PSL."""

import pytest

from ark.canonical import reject_reason, to_registrable


# fmt: off
@pytest.mark.parametrize("raw,registrable,reason", [
    # case, scheme, userinfo, port, path, query and fragment go; a subdomain collapses
    ("http://u:pw@WWW.Example.COM:80/p.html?id=1#top", "example.com", None),
    ("//cdn.example.org", "example.org", None),
    ("%20agfood-alliance.ab.ca", "agfood-alliance.ab.ca", None),  # a mis-encoded seed line
    (",.www.comdo-it.com.", "comdo-it.com", None),  # stray separators, never a leading hyphen
    ("a_ashe.howard.edu", "howard.edu", None),  # an underscore in a discarded subdomain
    ("adder.labis.fon.bg.ac.yu", "bg.ac.yu", None),  # a retired ccTLD of the early web
    ("   ", None, "empty line"),
    ("192.168.0.1", None, "ip address"),
    ("206.in-addr.arpa", None, "reverse-dns zone"),
    ("-s-love.com", None, "invalid hostname syntax"),
    ("localhost", None, "no known public suffix"),
    ("ab.ca", None, "bare public suffix"),
    ("ace_daikin.com.sg", None, "registered label"),
])
# fmt: on
def test_a_name_reduces_to_its_registrable_or_says_why_not(raw, registrable, reason) -> None:
    assert to_registrable(raw) == registrable
    assert (reason is None) is (reject_reason(raw) is None)
    assert reason is None or reason in reject_reason(raw)
