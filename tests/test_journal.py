"""`ark.journal.queried_domains`, which the tick's `pool_questions.py` reads: it keeps what it
read from a truncated or damaged journal."""

from ark import journal


def test_the_resume_scan_keeps_what_it_read_from_a_truncated_or_damaged_journal(tmp_path) -> None:
    """A hard kill can leave the gzip stream unterminated, or its last block damaged, which
    raises `zlib.error` and not `OSError`; the records before it and beside it are answers."""
    journals = [tmp_path / f"rdap_2026010{day}T000000Z.jsonl.gz" for day in (1, 2, 3)]
    for day, count in ((1, 1), (2, 2), (3, 40_000)):
        with journal.journal_writer(journals[day - 1]) as fh:
            for i in range(count):
                journal.write_journal_line(fh, {"domain": f"{day}-{i}.com", "status": 200})
    journals[1].write_bytes(journals[1].read_bytes()[:-4])  # truncated
    # corrupted, not truncated, past several decompressor buffers: what a killed write leaves
    raw = journals[2].read_bytes()
    journals[2].write_bytes(raw[:-40] + b"\x00" * 40)
    assert {"1-0.com", "2-0.com", "3-0.com"} <= journal.queried_domains(tmp_path, "rdap")
