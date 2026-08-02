"""Select and download Usenet group archives that plausibly carry dated URLs.

The Giganews donation is 19,233 groups over 411 GB, and the previous round
proved that taking the big ones is a mistake: `alt.www.webmaster` cost 170 MB
and yielded a single in-window pair because the whole group is 2006 to 2013.
Size does not predict in-window yield, so this selects on **name** and takes the
cheap files first, which lets yield per megabyte be measured early and the
ranking corrected while the download queue is still long.

Two selection rules, both learned from defects in this project:

**Match on name components, not substrings.** `talk.bizarre` contains "biz" and
is not a commerce group. This is the same trap `is_moderated_announce` hit when
a suffix test reported `news.announce.conferences` as ordinary discussion, so
the short tokens are matched as whole dot-separated components and only the long
distinctive ones are allowed to match anywhere in the name.

**Cap the file size.** A group above the cap is not rejected as worthless, it is
deferred: the cap buys breadth first, and a large group can be fetched later on
evidence rather than on hope.

Usage:
    uv run python scripts/fetch_usenet_groups.py --catalog data/raw/usenet_catalog.json
    uv run python scripts/fetch_usenet_groups.py --max-mb 100 --budget-gb 8 --download
"""

import argparse
import json
import urllib.request
from pathlib import Path

USENET_DIR = Path("data/raw/usenet")
CATALOG = Path("data/raw/usenet_catalog.json")
DOWNLOAD_BASE = "https://archive.org/download"

# Whole-component tokens. Short and ambiguous as substrings.
#
# `net` was tried and removed. As a component it matches `alt.isd.net`,
# `alt.irc.gamez.net` and `alt.toxiccrisko.net`, which are vanity and chat
# groups rather than anything announcing a website, and it contributed nothing
# but noise to the head of the queue.
COMPONENT_TOKENS = frozenset(
    {
        "www",
        "web",
        "biz",
        "ads",
        "market",
        "isp",
        "domain",
        "shopping",
        "homepage",
    }
)

# Distinctive enough to match anywhere in the group name.
SUBSTRING_TOKENS = (
    "announce",
    "net-happenings",
    "commerce",
    "marketplace",
    "entrepreneur",
    "business",
    "internet",
    "hosting",
    "advertis",
    "promotion",
    "providers",
    "webmaster",
    "ecommerce",
)

# Excluded regardless of match. Adult marketplace groups are the largest thing
# the name filter catches, and they are advertising traffic rather than website
# announcements. Recorded here rather than silently dropped so the exclusion is
# reviewable and reversible.
EXCLUDE_PREFIXES = ("alt.sex", "alt.binaries", "alt.showbiz")


def selects(group: str) -> bool:
    """Whether a group name suggests it carries announced website URLs."""
    if group.startswith(EXCLUDE_PREFIXES):
        return False
    lowered = group.lower()
    if any(token in lowered for token in SUBSTRING_TOKENS):
        return True
    return bool(set(lowered.split(".")) & COMPONENT_TOKENS)


# Non-English language hierarchies. Kept in the queue, because a German
# announcement group still dates the English-language sites it links to, but
# ranked last: the English set is the priority and these yield toward it least.
FOREIGN_MARKERS = (".pl.", ".de.", ".fr.", ".it.", ".es.", ".nl.", ".ru.", ".jp.", ".br.")


def tier(group: str) -> int:
    """Expected yield rank, lowest first. Ordering by size alone was wrong.

    The cheapest files are overwhelmingly dead vanity groups, so a size-ascending
    queue spends its first hours on archives measured in kilobytes that announce
    nothing. What the previous round actually proved productive was moderated
    announcement forums first and commerce second, so the queue is ordered by
    that evidence and size only breaks ties within a tier.
    """
    lowered = group.lower()
    if any(marker in f".{lowered}." for marker in FOREIGN_MARKERS):
        return 3
    if "announce" in lowered or "net-happenings" in lowered:
        return 0
    if any(t in lowered for t in ("commerce", "marketplace", "business", "entrepreneur")):
        return 1
    return 2


def candidates(catalog: dict, held: set[str], max_bytes: int) -> list[tuple[int, int, str, str]]:
    """(tier, size, hierarchy, filename) for selectable groups, best first."""
    rows = []
    for hierarchy, files in catalog.items():
        for entry in files:
            name = entry["name"]
            if name in held or not name.endswith(".mbox.zip"):
                continue
            size = int(entry.get("size", 0))
            if size > max_bytes or size == 0:
                continue
            group = name[: -len(".mbox.zip")]
            if not selects(group):
                continue
            rows.append((tier(group), size, hierarchy, name))
    rows.sort()
    return rows


def download(hierarchy: str, name: str, dest: Path) -> bool:
    """Fetch one archive via a temporary name, so a partial file is never used.

    The rename is the same discipline the journal writers use: a consumer that
    globs for `*.mbox.zip` must never see a file that is still being written,
    because the ingest would read a truncated zip and mark the group done.
    """
    url = f"{DOWNLOAD_BASE}/usenet-{hierarchy}/{name}"
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with urllib.request.urlopen(url, timeout=300) as response, tmp.open("wb") as fh:
            while chunk := response.read(1 << 20):
                fh.write(chunk)
    except Exception as exc:  # noqa: BLE001 - one bad group must not end the run
        tmp.unlink(missing_ok=True)
        print(f"fail {name}: {exc}", flush=True)
        return False
    tmp.rename(dest)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--max-mb", type=float, default=100.0, help="per-group size cap")
    parser.add_argument("--budget-gb", type=float, default=8.0, help="total download budget")
    parser.add_argument("--download", action="store_true", help="fetch, rather than just list")
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text())
    held = {p.name for p in USENET_DIR.glob("*.mbox.zip")}
    rows = candidates(catalog, held, int(args.max_mb * 1e6))

    budget = int(args.budget_gb * 1e9)
    taken, spent = [], 0
    for rank, size, hierarchy, name in rows:
        if spent + size > budget:
            continue
        taken.append((rank, size, hierarchy, name))
        spent += size

    print(f"{len(rows)} selectable, {len(taken)} within budget, {spent / 1e9:.2f} GB")
    if not args.download:
        for rank, size, _, name in taken[:20]:
            print(f"  tier {rank}  {size / 1e6:8.2f} MB  {name}")
        return

    USENET_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    for index, (rank, size, hierarchy, name) in enumerate(taken, start=1):
        if download(hierarchy, name, USENET_DIR / name):
            ok += 1
            print(f"[{index}/{len(taken)}] tier {rank} {size / 1e6:.1f} MB {name}", flush=True)
    print(f"downloaded {ok} of {len(taken)}")


if __name__ == "__main__":
    main()
