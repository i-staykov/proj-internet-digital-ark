# Retired code

One line per capability removed from the tree, so a later run knows it existed and why it went.
The code itself is recoverable from git by the commit named here.

- **The RDAP client** (`src/ark/rdap.py`, the `ark rdap` command, `tests/test_rdap.py`, the
  `rdap-batch` recipe): querying is closed for good on the registries' own terms, so bootstrap,
  routing, retries and journal writing had no caller left. `attested_years` and `RDAP_REDIRECTOR`
  stayed, in `src/ark/sources.py`, because `parse_rdap_snapshot` still replays the journals the
  client wrote. Removed in this commit.
