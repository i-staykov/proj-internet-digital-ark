"""A small release of his, laid out as his real one is, for the tests that diff through `held`.

His candidate files are left unsorted on purpose: his real `candidate_pool_unparsed_format.txt`
is, so the sorted-copy path runs in every test that prepares this release.
"""

import hashlib
from pathlib import Path

from ark.ingest import YEARS

MARKER = "merged260922"

HIS_YEARS = {
    1996: ["already-his.com", "early.his.org"],
    1997: ["already-his.com"],
    1998: ["already-his.com"],
    1999: ["already-his.com", "www.rolled.com"],
    2000: ["already-his.com"],
    2001: ["already-his.com", "deep.his-host.net"],
}
HIS_CANDIDATES = {
    "candidate_pool.txt": ["held-candidate.com", "another-held.org"],
    "candidate_pool_unparsed_format.txt": ["Unparsed.Example.Com", "abc.unparsed.net"],
    "isc_survey_hostnames/1999-01.txt": ["mail.isc-held.net"],
    "isc_survey_hostnames/2000-07.txt": ["ns.isc-held.net", "ftp.isc-held.net"],
}
README = "isc_survey_hostnames/README.md"


def text(names: list[str]) -> bytes:
    return "".join(f"{name}\n" for name in names).encode()


def stage(root: Path, files: dict[str, bytes] | None = None) -> Path:
    """Write the release under `root/<marker>/`: every default file, then `files` over them."""
    folder = root / MARKER
    contents = {f"{year}.txt": text(sorted(names)) for year, names in HIS_YEARS.items()}
    contents |= {rel: text(names) for rel, names in HIS_CANDIDATES.items()}
    contents[README] = b"not a list of names\n"
    for rel, data in (contents | (files or {})).items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder


def digests(folder: Path) -> dict[str, str]:
    """Every file of the release by its sha256, to prove nothing of his was written."""
    return {
        str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def all_names() -> set[str]:
    return {name for year in YEARS for name in HIS_YEARS[year]}
