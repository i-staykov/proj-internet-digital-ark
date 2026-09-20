"""Two clients on the same pages is one client.

`platform_sweep_loop.sh` runs twice, once per shard, and that is the whole of the
two-archive-clients budget. Under an ordinal split, `n % 2 == SHARD`, each shard ranks at its
own moment and `--net-new` drops what has been swept since, so one extra entry flips every
parent behind it: both shards once walked the same parent to the end, 391,338 rows each, 34
seconds apart, with every other parent unvisited. So the shard is a hash of the name, and
these hold the two properties the ordinal split lacked: the halves share no parent, and
between them they cover the list.
"""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts/engines/platform_sweep_loop.sh"

# A realistic slice: the shapes the ranker emits, including two names differing only in
# their last label and two that are anagrams of one another.
PARENTS = [
    "com.au",
    "net.au",
    "org.au",
    "co.uk",
    "ac.uk",
    "org.uk",
    "co.nz",
    "co.za",
    "com.br",
    "geocities.com",
    "angelfire.com",
    "tripod.com",
    "members.aol.com",
    "columbia.edu",
    "utoronto.ca",
    "mit.edu",
    "stanford.edu",
    "ox.ac.uk",
    "cam.ac.uk",
    "inria.fr",
    "cnrs.fr",
    "uni-berlin.de",
    "tu-muenchen.de",
    "waseda.ac.jp",
    "keio.ac.jp",
]


def split(names: list[str], shard: int, tmp_path: Path) -> list[str]:
    """Run the script's own `shard_split` over a list, as refill does."""
    listing = tmp_path / f"parents_{shard}_{len(names)}.txt"
    listing.write_text("".join(f"{n}\n" for n in names))
    done = subprocess.run(
        [
            "bash",
            "-c",
            'ARK_SWEEP_LOOP_LIB=1 . "$1" 0 /dev/null 0; shard_split "$2" "$3"',
            "sweep-loop-under-test",
            str(SCRIPT),
            str(shard),
            str(listing),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.split()


def _dedupe(queue: list[str], refill: list[str], tmp_path: Path) -> list[str]:
    """The refill's own filter, lifted from the script: what is not already queued. The line is
    read out of the script rather than copied, so a change to it is tested rather than
    shadowed by a stale copy.
    """
    parents = tmp_path / "queue.txt"
    parents.write_text("".join(f"{n}\n" for n in queue))
    (tmp_path / "queue.txt.refill").write_text("".join(f"{n}\n" for n in refill))
    line = next(
        ln for ln in SCRIPT.read_text().splitlines() if ln.strip().startswith("awk 'FILENAME")
    )
    done = subprocess.run(
        ["bash", "-c", f'PARENTS="$1"; {line.strip().rstrip(chr(92))}', "dedupe", str(parents)],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.split()


def test_an_empty_queue_can_still_be_refilled(tmp_path: Path) -> None:
    """`NR==FNR` means "still reading the first file" only while that file has records: with an
    empty queue, NR and FNR stay equal for every line of the second file, so awk takes the
    whole refill list as the seen set and prints nothing. Both clients once idled nine hours
    on "found nothing" with 8,624 unswept parents on disk.
    """
    assert _dedupe([], ["a.com", "b.com"], tmp_path) == ["a.com", "b.com"]


def test_the_refill_does_not_re_queue_what_is_already_there(tmp_path: Path) -> None:
    assert _dedupe(["b.com"], ["a.com", "b.com", "c.com"], tmp_path) == ["a.com", "c.com"]


def test_the_two_shards_share_no_parent(tmp_path: Path) -> None:
    """The issue's test: one parent, at most one client."""
    zero = split(PARENTS, 0, tmp_path)
    one = split(PARENTS, 1, tmp_path)
    assert set(zero) & set(one) == set()


def test_the_two_shards_cover_the_whole_list(tmp_path: Path) -> None:
    """Disjoint alone is satisfied by sweeping nothing, so completeness is the other half."""
    zero = split(PARENTS, 0, tmp_path)
    one = split(PARENTS, 1, tmp_path)
    assert set(zero) | set(one) == set(PARENTS)
    assert len(zero) + len(one) == len(PARENTS)


def test_neither_shard_takes_the_whole_queue(tmp_path: Path) -> None:
    """A hash that answered a constant would pass both tests above and idle one client."""
    zero = split(PARENTS, 0, tmp_path)
    assert 0 < len(zero) < len(PARENTS)


def test_a_parent_keeps_its_shard_when_the_list_around_it_changes(tmp_path: Path) -> None:
    """The two shards never hold the same list: they rank at different moments, against a store
    that has grown in between, so the shard has to be a property of the name.
    """
    grown = ["akamai.net", *PARENTS, "yahoo.co.jp"]
    for shard in (0, 1):
        before = set(split(PARENTS, shard, tmp_path))
        after = set(split(grown, shard, tmp_path))
        assert before == after & set(PARENTS)


def test_reordering_the_list_does_not_move_a_parent(tmp_path: Path) -> None:
    """The park lists are prepended to the ranked list, and both grow between refills."""
    assert set(split(PARENTS, 0, tmp_path)) == set(split(list(reversed(PARENTS)), 0, tmp_path))


def test_comments_and_blank_lines_are_not_parents(tmp_path: Path) -> None:
    """The park lists carry hand-written notes; a comment must not reach a sweep."""
    listing = ["# parked 2026-09-07, expensive", "", "com.au", "   ", "co.uk"]
    both = split(listing, 0, tmp_path) + split(listing, 1, tmp_path)
    assert sorted(both) == ["co.uk", "com.au"]


def _bounded(limit: int, command: str) -> subprocess.CompletedProcess:
    """Run the script's own `bounded` over a shell command."""
    return subprocess.run(
        [
            "bash",
            "-c",
            f'ARK_SWEEP_LOOP_LIB=1 . "$1" 0 /dev/null 0; bounded {limit} {command}',
            "sweep-loop-under-test",
            str(SCRIPT),
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def test_a_command_inside_the_cap_keeps_its_own_exit_code() -> None:
    assert _bounded(30, "bash -c 'exit 3'").returncode == 3


def test_a_command_over_the_cap_is_stopped_rather_than_waited_on() -> None:
    """The refill's cost build held one of the two client slots for 79 minutes on
    2026-09-17 because nothing bounded it."""
    done = _bounded(5, "sleep 120")
    assert done.returncode == 124, done.stdout + done.stderr
    assert "was stopped" in done.stdout


def test_the_ranker_depth_is_a_knob_and_is_deeper_than_the_queue_it_feeds() -> None:
    """Both shards idled on 2026-09-20 with "refill found nothing" because the ranking was
    capped at 20,000 and every one of those parents was already queued or carried a `.done`
    marker. 32,734 markers existed against a 29,057-parent queue, so the cap was the binding
    constraint and not the corpus: the ranker's pool is every registrable parent carrying a
    hostname in his files. The number is read from the environment so the next exhaustion
    needs no code change, and the default has to exceed what the two queues can burn.
    """
    script = Path(__file__).resolve().parents[1] / "scripts/engines/platform_sweep_loop.sh"
    loop = script.read_text()
    assert 'RANK_TOP="${ARK_RANK_TOP:-' in loop, "the depth is hardcoded again"
    assert '--top "$RANK_TOP"' in loop, "the knob is set but not passed to the ranker"
    assert "--top 20000" not in loop, "the exhausted literal is still there"
    default = int(loop.split('RANK_TOP="${ARK_RANK_TOP:-')[1].split("}")[0])
    assert default >= 40000, f"{default} is not deeper than the 29,057 parents already burned"


def test_the_shard_hash_is_taken_modulo_the_lane_count():
    """`h % 2` was hardcoded, so `shard_of` could never return 2 and a third lane matched
    no parent at all. Measured 2026-09-20: a full 150,000 parent pool sat on disk while the
    lane reported "refill found nothing"."""
    loop = (
        Path(__file__).resolve().parents[1] / "scripts/engines/platform_sweep_loop.sh"
    ).read_text()
    assert 'SHARDS="${ARK_CDX_BUDGET:-2}"' in loop
    assert "return h % shards" in loop, "the modulus is hardcoded again"
    assert "return h % 2" not in loop
