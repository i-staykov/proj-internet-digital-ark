# ark: common tasks.
#
# Thin wrappers over the `uv run ...` commands in README.md. The raw commands
# remain the reproducibility contract, because they need nothing but uv
# installed; these recipes exist so the order is hard to get wrong, not to hide
# what runs. `just --list` shows everything.
#
# On naming: `ark check` validates the DATA (nine integrity invariants over
# the store) while the test suite validates the CODE. Naming either one plain
# "check" invites running one and believing the other passed, so they are
# `check-data` and `verify-repo` here, and `just check` runs BOTH.

# list available recipes
default:
    @just --list

# sync the locked environment (installs deps into .venv)
setup:
    uv sync

# run any CLI command directly, e.g. `just run stats` or `just run cdx --help`
run *args:
    uv run ark {{args}}

# --- validating the code -----------------------------------------------------

# run the test suite
test:
    uv run pytest

# lint
lint:
    uv run ruff check .

# auto-format the code
fmt:
    uv run ruff format .

# exactly what CI runs: lint + format-check + tests
verify-repo:
    uv run ruff check .
    uv run ruff format --check .
    uv run pytest

# --- validating the data -----------------------------------------------------

# the integrity gate: nine invariants over the store, non-zero exit on any failure
check-data:
    uv run ark check

# The reviewer's first priority in one command: unprocessed files, globs that
# match too little, downloaded bytes with no parser, and derived lists a newer
# baseline has invalidated. Read-only, no network, and NOT a gate: it reports and
# exits 0, because unread material is a fact about the round rather than a broken
# invariant. Run it before deciding what to collect. It exists because the same
# diff, run by hand on 2026-08-10, found 496 ISC survey shards worth 14,956
# equivalent-English that had been on disk for five days.
#
# what is on disk that nothing has read, and what the documented path would miss
residual *args:
    uv run python scripts/audit_residual.py {{args}}

# Does the proposal collide with one of the ~50 families already closed with a
# measurement, and what dates ONE of its items. The register is parsed out of
# docs/sources.md at run time rather than copied, so it cannot drift from the
# verdicts. Exits 2 if no dating claim is made, because a source whose items carry
# no date is seed-only and that decides what it can ever be. Example:
#   just screen --dating typed "1997 conference proceedings with affiliations"
#
# screen a source proposal against the closed register before it costs a request
screen *args:
    uv run python scripts/screen_hypothesis.py {{args}}

# Seed-only and permanently so: the index carries no date column, so nothing in it
# can evidence a year. 35,391 registrable domains, 29,432 of them unknown to the
# store when measured on 2026-08-10. Expect pool growth and no annual-file growth:
# a 60-domain sample on the AWA endpoint returned zero in-window captures.
#
# the National Library of Australia's PANDORA title index into the candidate pool
pandora-seed:
    uv run python scripts/seed_pandora_titles.py
    uv run ark seed data/raw/pandora-titles/pandora_hosts.txt

# the scoreboard: net-new domains, pairs and equivalent-English on top of the
# baseline named in `src/ark/baseline.py`. Net-new here means uncredited: the
# reviewer's merged release is loaded, so everything he has already taken is
# excluded by construction rather than subtracted by hand. Check the release it
# prints; if it is not the newest one he has sent, every figure is overstated.
#
# the scoreboard: uncredited net-new domains, pairs and equivalent-English
stats:
    uv run ark stats

# both kinds of validation, which is what "is everything fine?" should mean
check: verify-repo check-data

# --- reproducing the result --------------------------------------------------
# All six stages are offline. Stages 1 to 3 read the bulk files in data/raw/,
# stage 4 replays the journals the collectors already wrote, stage 5 rebuilds the
# hostname/URL seed pool, and stage 6 writes and proves the deliverable. To
# collect NEW evidence, see the network recipes further down.

# stage 1: create the stores, load the supplied baseline read-only (~2 min)
baseline:
    uv run ark init
    uv run ark ingest-legacy
    uv run ark legacy-review
    uv run ark audit

# stage 2: ingest every bulk source already downloaded into data/raw/
#
# `arquivo_ia` is deliberately absent. `data/raw/arquivo/IA.cdxj` is 47 GB and was
# deleted to reclaim disk once its 28,247 evidence rows were in the store, so its
# evidence is present and its input file is not. Leaving the line in aborted this
# whole stage on a missing file, which broke the reviewer-facing reproduction path.
# To re-derive it rather than trust the store, download it first (the command is in
# docs/sources.md) and run the commented line by hand. Same reason
# `data/raw/checksums.sha256` verifies 234 files rather than 235.
#
# stage 2: ingest every bulk source already downloaded into data/raw/
sources:
    uv run ark ingest early_web         data/raw/early_web/*.cdx.gz
    uv run ark ingest isc_survey        data/raw/isc_survey/*.gz
    uv run ark ingest arquivo_roteiro   data/raw/arquivo/Roteiro.cdxj
    # uv run ark ingest arquivo_ia      data/raw/arquivo/IA.cdxj   # see above
    uv run ark ingest afnic_fr          data/raw/afnic/*NomsDeDomaineEnPointFr.csv
    uv run ark ingest internet_scout    data/raw/scout/scout_oai.xml
    uv run ark ingest odp               data/raw/odp/*.gz
    uv run ark ingest ukwa_link_source  data/raw/ukwa/host-linkage.tsv.gz
    uv run ark ingest ukwa_link_target  data/raw/ukwa/host-linkage.tsv.gz
    uv run ark ingest ncsa_whats_new    data/raw/ncsa-whats-new/ncsa_1996_domain_date_pairs.tsv

# stage 3: grow the candidate pool from the year-unlabelled host lists
candidates:
    uv run ark seed data/raw/webbase/hosts.txt
    uv run ark seed legacy-data/deduplicated_urls_2001-2002.txt
    uv run ark seed seeds/100hot_hosts.txt

# This is the reproduction path for the two network stages: it re-derives
# evidence from the stored responses, so it needs no network and gives the same
# result every time. To collect MORE, see the network recipes below.
# stage 4: replay the network journals already collected in data/raw/
journals:
    uv run ark ingest cdx_snapshot  data/raw/cdx/cdx_*.jsonl.gz
    uv run ark ingest rdap_snapshot data/raw/rdap/rdap_*.jsonl.gz
    uv run ark ingest expansion_links     data/raw/expand/expand_*.jsonl.gz --round 1
    uv run ark ingest expansion_directory data/raw/expand/round2/expand_round2.jsonl.gz --round 2
    uv run ark ingest expansion_directory data/raw/expand/wwwvl/expand_wwwvl_corroborated.jsonl.gz --round 3
    uv run ark ingest expansion_links     data/raw/expand/wwwvl/expand_wwwvl_unverified.jsonl.gz --round 3
    uv run ark ingest expansion_directory data/raw/expand/round4/expand_round4_corroborated.jsonl.gz --round 4
    uv run ark ingest expansion_links     data/raw/expand/round4/expand_round4_unverified.jsonl.gz --round 4
    uv run ark ingest usenet_dated        data/raw/usenet/usenet_dated*.jsonl.gz
    uv run ark ingest usenet_candidates   data/raw/usenet/usenet_candidates*.jsonl.gz
    uv run ark ingest tucows_dated        data/raw/tucows/tucows_dated.jsonl.gz
    uv run ark ingest tucows_candidates   data/raw/tucows/tucows_candidates.jsonl.gz
    # `_r2` is the second split of the recovered-address journals, run after the
    # extractor was widened. The first split is in the ledger but no longer on
    # disk; the second is a superset, so replaying it alone reconstructs the same
    # evidence. Regenerate with `just usenet-addresses`, which writes the
    # untagged names, then rename.
    uv run ark ingest usenet_addr_dated      data/raw/usenet_addr/usenet_addr_dated_r2.jsonl.gz
    uv run ark ingest usenet_addr_candidates data/raw/usenet_addr/usenet_addr_candidates_r2.jsonl.gz
    # The machine-written header seam. Same two source keys, because the headers
    # carry the same kind of claim as a typed address and no `usenet_hdr` spec
    # exists. Without these two lines a rebuild is 19,224 evidence rows short.
    uv run ark ingest usenet_addr_dated      data/raw/usenet_hdr/usenet_hdr_dated.jsonl.gz
    uv run ark ingest usenet_addr_candidates data/raw/usenet_hdr/usenet_hdr_candidates.jsonl.gz
    uv run ark ingest uucp_listing        data/raw/uucp/uucp_listing.jsonl.gz
    uv run ark ingest uucp_creation       data/raw/uucp/uucp_creation.jsonl.gz
    uv run ark ingest uucp_mentions       data/raw/uucp/uucp_mentions.jsonl.gz
    uv run ark ingest rtfm_dated          data/raw/rtfm/rtfm_dated.jsonl.gz
    uv run ark ingest rtfm_candidates     data/raw/rtfm/rtfm_candidates.jsonl.gz
    uv run ark ingest rtfm_dated          data/raw/rtfm/rtfm_dated_reextract.jsonl.gz
    uv run ark ingest rtfm_candidates     data/raw/rtfm/rtfm_candidates_reextract.jsonl.gz
    uv run ark ingest usenet_bare_dated      data/raw/usenet_bare/usenet_bare_dated.jsonl.gz
    uv run ark ingest usenet_bare_candidates data/raw/usenet_bare/usenet_bare_candidates.jsonl.gz
    uv run ark ingest attrition_dated     data/raw/attrition/attrition_dated.jsonl.gz
    uv run ark ingest enron_dated         data/raw/enron/enron_dated.jsonl.gz
    uv run ark ingest enron_candidates    data/raw/enron/enron_candidates.jsonl.gz
    uv run ark ingest maillist_dated      data/raw/maillists/maillist_dated.jsonl.gz
    uv run ark ingest maillist_candidates data/raw/maillists/maillist_candidates.jsonl.gz
    uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated.jsonl.gz
    uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates.jsonl.gz
    uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_reextract.jsonl.gz
    uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_reextract.jsonl.gz
    uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american.jsonl.gz
    uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american.jsonl.gz
    uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american_bare.jsonl.gz
    uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american_bare.jsonl.gz
    # The archived 1996-1997 Yahoo directory walk. Measured and rejected as a
    # route (55 requests bought 11 pairs), but its three journals were ingested,
    # so a rebuild without them is 670 records short of the store.
    uv run ark ingest expansion_directory data/raw/yahoo96/yahoo96_pilot1996_corroborated.jsonl.gz --round 5
    uv run ark ingest expansion_directory data/raw/yahoo96/yahoo96_fatpages1996_corroborated.jsonl.gz --round 5
    uv run ark ingest expansion_directory data/raw/yahoo96/yahoo96_expand_corroborated.jsonl.gz --round 5

# stage 5: rebuild the auxiliary seed pool, the hostnames and URLs that the
# registered-domain counting unit drops. Reads the same source files again.
#
# stage 5: rebuild the auxiliary hostname and URL seed pool
seeds:
    uv run ark seed-pool isc_survey       data/raw/isc_survey/*.gz
    uv run ark seed-pool odp              data/raw/odp/*.gz
    uv run ark seed-pool internet_scout   data/raw/scout/scout_oai.xml
    uv run ark seed-pool ukwa_link_source data/raw/ukwa/host-linkage.tsv.gz
    uv run ark seed-pool early_web        data/raw/early_web/*.cdx.gz

# stage 6: write the deliverable, then prove it. The order is not cosmetic:
# `check`'s `additions_not_double_counted` invariant reads the exported annual
# files, so running it before `export` compares this round's files against last
# round's store and reports every already-credited pair as a violation. Export
# first, always.
#
# stage 6: write the deliverable, then prove it
deliver:
    uv run ark export
    uv run ark stats
    uv run ark check

# tier 3: the whole result from an empty store. Needs the bulk sources in
# data/raw/ AND the supplied baseline in legacy-data/, since the annual masters
# are baseline plus additions and net-new is defined against it.
#
# tier 3: rebuild the whole result from the source data, offline
reproduce: baseline sources candidates journals seeds deliver

# tier 2: regenerate every result file from a provenance export instead, which
# needs no source data at all. About a minute, and byte-identical.
#
# tier 2: regenerate every result file from a provenance export
rebuild dir="output/provenance":
    uv run ark rebuild {{dir}}
    uv run ark check

# --- collecting more (network) -----------------------------------------------
# Each of these appends a journal to data/raw/ and writes no evidence, so they
# never hold the store's write lock and can run concurrently with each other.

# one archive-verification batch: which in-window years hold a capture
cdx-batch n="1200" workers="8":
    uv run ark gaps
    uv run ark cdx data/raw/cdx/gap_candidates.txt -n {{n}} --workers {{workers}} --timeout 70

# split the gap list across machines: disjoint by content hash, so no domain is
# ever queried twice and each slice keeps its share of the high-value head.
#
# split the gap list N ways for N machines (superseded by query-queue)
gap-shards n="2":
    #!/usr/bin/env bash
    set -euo pipefail
    for i in $(seq 0 $(({{n}} - 1))); do
        uv run ark gaps --shards {{n}} --shard "$i" --out "data/raw/cdx/gap_shard${i}.txt"
    done

# Supersedes running `gap-shards` and `build_pool_candidates.py` as two separate
# lists: the allocation between them was the expensive decision and it was being
# made by hand. Rebuild after a large ingest, since new evidence creates gaps as
# well as filling them, and a stale queue cannot reach what it does not list.
# one queue from both populations, best expected equivalent-English first
query-queue weights="78,22" rates="916,262":
    uv run python scripts/build_query_queue.py --weights {{weights}} --rates {{rates}}

# what the queue is expected to return, without writing anything
query-queue-preview:
    uv run python scripts/build_query_queue.py --dry-run

# the candidate pool instead of the gap pool: domains held with no year at all,
# so a capture adds a name rather than a year. Best English yield first, and the
# supervisor runs batches until the deadline epoch you give it.
#
# sweep the candidate pool at the archive, unattended until a deadline epoch
cdx-pool until batch="1200" workers="8":
    uv run python scripts/build_pool_candidates.py
    bash scripts/supervise_cdx_pool.sh {{until}} {{batch}} {{workers}} 900

# what both CDX engines are doing right now, and whether the VPS journals are home
engines:
    bash scripts/engine_status.sh

# Takes a deadline epoch, e.g. `just engines-start $(date -u -v+12d +%s)`.
# start this machine's collector and the ingest loop, both detached
engines-start until batch="600" workers="8":
    #!/usr/bin/env bash
    set -uo pipefail
    ARK_TARGETS=data/raw/cdx/queue_shard0.txt ARK_PREFIX=cdx_q0 \
        nohup caffeinate -i bash scripts/supervise_cdx_pool.sh \
        {{until}} {{batch}} {{workers}} 900 > /dev/null 2>&1 < /dev/null &
    nohup bash scripts/maintain.sh 900 150 > /dev/null 2>&1 < /dev/null &
    sleep 5
    ps -eo pid,args | grep -E "supervise_cdx_poo[l]|maintain_phase[3]" || true

# TERM to the supervisor runs its trap, which asks the batch to stop and lets it
# publish what it has: a stopped batch still writes its journal, so the only thing
# lost is the queries it had not made yet. Never `kill -9` here, that strands the
# `.part` and the work in it is unreachable.
# stop this machine's collector and ingest loop, keeping the batch in flight
engines-stop:
    #!/usr/bin/env bash
    set -uo pipefail
    pkill -TERM -f "supervise_cdx_pool[.]sh" 2>/dev/null || true
    pkill -TERM -f "maintain[.]sh" 2>/dev/null || true
    echo "waiting for the batch in flight to publish its journal"
    until ! pgrep -f "[a]rk cdx " >/dev/null && ! pgrep -f "[a]rk ingest" >/dev/null; do
        sleep 5
    done
    pkill -f "caffeinate -i bash scripts/supervise" 2>/dev/null || true
    echo "stopped; nothing left running:"
    ps -eo pid,args | grep -E "supervise_cdx_poo[l]|maintain_phase[3]|ar[k] cdx" || echo "  confirmed idle"
    ls data/raw/cdx/*.part 2>/dev/null && echo "WARNING: a .part was stranded" || echo "  no stranded .part files"

# one registry-date batch: creation year for domains adjacent to a held year
rdap-batch n="2500":
    uv run ark gaps --creation --out data/raw/rdap/creation_candidates.txt
    uv run ark rdap data/raw/rdap/creation_candidates.txt -n {{n}}

# sweep the candidate pool at the registries, which competes with no CDX engine.
# Direct endpoints from the IANA bootstrap file: measured 75 q/s with no refusals,
# against 0.83 q/s and 18.8% refused through the rdap.org redirector.
#
# sweep the candidate pool at the registries direct, competing with no CDX engine
rdap-pool tlds="com,net" batches="6" limit="100000" workers="32":
    uv run python scripts/build_rdap_pool_list.py --tlds {{tlds}} \
        --out data/raw/rdap/pool_targets_{{tlds}}.txt
    LIST=data/raw/rdap/pool_targets_{{tlds}}.txt \
        bash scripts/rdap_pool_sweep.sh {{batches}} {{limit}} {{workers}}
    uv run ark ingest rdap_snapshot data/raw/rdap/rdap_pool_*.jsonl.gz

# one page-expansion round (brief section VII). Pass a seed list and a round
# number, e.g. `just expand-round seeds/expansion/seeds_round4.txt 5`. The split
# step is not optional: it keeps a curated page's transcription typos out of
# master evidence by demoting names no other source attests.
#
# one page-expansion round: fetch archived pages, split, ingest both halves
expand-round seeds round:
    uv run ark download {{seeds}} -n 250 --workers 3 --captures 2 \
        --out data/raw/expand/round{{round}}/expand_round{{round}}.jsonl.gz
    uv run python scripts/split_expansion_journal.py \
        data/raw/expand/round{{round}}/expand_round{{round}}.jsonl.gz --write
    uv run ark ingest expansion_directory \
        data/raw/expand/round{{round}}/expand_round{{round}}_corroborated.jsonl.gz --round {{round}}
    uv run ark ingest expansion_links \
        data/raw/expand/round{{round}}/expand_round{{round}}_unverified.jsonl.gz --round {{round}}

# --- the per-source collectors ------------------------------------------------
# Each pair is collect-then-split: the collector writes a journal and touches no
# database, the split sorts the journal into a dated half and a candidate half,
# and only then does anything reach the store. The split is the evidence wall for
# every free-text source, so it is not optional.

# measure a Usenet archive's yield against the store BEFORE ingesting it.
# The one source assessed without doing this was estimated at 27,276 net-new
# domains and measured at 53, so this is not optional caution.
# measure a Usenet archive's net-new yield before committing to it
usenet-measure *archives:
    uv run python scripts/measure_usenet_yield.py {{archives}}

# split and ingest whatever has finished downloading
usenet-ingest tag="auto":
    bash scripts/ingest_new_usenet.sh {{tag}}

# Sources added 8 August, all from data already on disk or free to fetch.

# UUCP maps from comp.mail.maps: a .CA registry dump the Usenet parser read as prose
uucp-maps:
    uv run python scripts/split_uucp_maps.py --write
    uv run ark ingest uucp_listing  data/raw/uucp/uucp_listing.jsonl.gz
    uv run ark ingest uucp_creation data/raw/uucp/uucp_creation.jsonl.gz
    uv run ark ingest uucp_mentions data/raw/uucp/uucp_mentions.jsonl.gz

# mode=headers instead reads Message-ID, Reply-To, Sender and NNTP-Posting-Host.
# The mode has to be threaded all the way through, because it changes the output
# DIRECTORY as well as the extractor: `addresses` writes data/raw/usenet_addr and
# `headers` writes data/raw/usenet_hdr. Passing it only to the collector, as this
# recipe once did, collected into one directory and then split and ingested the
# other, so `mode=headers` silently re-ingested the address journals.
# ftp://, mailto: and body addresses the Usenet extractor never read
usenet-addresses mode="addresses" workers="10":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{mode}}" in
        addresses) dir=data/raw/usenet_addr; prefix=usenet_addr ;;
        headers)   dir=data/raw/usenet_hdr;  prefix=usenet_hdr  ;;
        *) echo "mode must be 'addresses' or 'headers'" >&2; exit 1 ;;
    esac
    uv run python scripts/collect_usenet_addresses.py --mode {{mode}} --workers {{workers}}
    uv run python scripts/split_usenet_addresses.py --in-dir "$dir" --out-prefix "$prefix" --write
    uv run ark ingest usenet_addr_dated      "$dir/${prefix}_dated.jsonl.gz"
    uv run ark ingest usenet_addr_candidates "$dir/${prefix}_candidates.jsonl.gz"

# Sends no request and takes about three hours of CPU at 8 workers. Run
# `--sample 400` first if you want the projection before committing to it.
# bare `foo.com` in the Usenet bodies, the form no extractor has ever read
usenet-bare workers="8":
    uv run python scripts/collect_usenet_bare.py --workers {{workers}}
    uv run python scripts/split_usenet_addresses.py --in-dir data/raw/usenet_bare --out-prefix usenet_bare --write
    uv run ark ingest usenet_bare_dated      data/raw/usenet_bare/usenet_bare_dated.jsonl.gz
    uv run ark ingest usenet_bare_candidates data/raw/usenet_bare/usenet_bare_candidates.jsonl.gz

# Pass a tag on any re-run: it imports `probe_texts_corpus.domains_in`, so it
# inherits that extractor's fixes, and the ledger refuses a rewritten journal.
# the rtfm.mit.edu FAQ mirror, dated by revision header rather than repost date
rtfm-faqs tag="":
    #!/usr/bin/env bash
    set -euo pipefail
    suffix=""; [ -n "{{tag}}" ] && suffix="_{{tag}}"
    uv run python scripts/split_rtfm_faqs.py --write --tag "{{tag}}"
    uv run ark ingest rtfm_dated      "data/raw/rtfm/rtfm_dated${suffix}.jsonl.gz"
    uv run ark ingest rtfm_candidates "data/raw/rtfm/rtfm_candidates${suffix}.jsonl.gz"

# Run --discover first: several plausible collection names do not exist and
# silently return zero when queried with a collection: prefix.
# scanned computer magazines on archive.org, dated by issue
trade-press limit="5000":
    uv run python scripts/collect_trade_press.py --discover
    uv run python scripts/collect_trade_press.py --limit {{limit}}
    uv run python scripts/split_trade_press.py --write
    uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated.jsonl.gz
    uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates.jsonl.gz

# Both corpora are already worked and ingested; this is here to reproduce, not to
# re-run. The collector writes a fresh timestamped journal, so pass its name to
# the split. --tag keeps the ledger happy: tradepress_dated.jsonl.gz is taken.
# the American trade weeklies, the second corpus and now the collector default
trade-press-american journal="data/raw/tradepress/tradepress_20260808T172417Z.jsonl.gz":
    uv run python scripts/collect_trade_press.py --limit 1400 --delay 0.6
    uv run python scripts/split_trade_press.py --journal {{journal}} --tag american --write
    uv run ark ingest tradepress_dated      data/raw/tradepress/tradepress_dated_american.jsonl.gz
    uv run ark ingest tradepress_candidates data/raw/tradepress/tradepress_candidates_american.jsonl.gz

# Sends no request: it re-reads the OCR under data/raw/texts/cache. Worth running
# after any trade-press or rtfm collection, since both share the extractor that
# used to drop bare two-label domains.
# re-read cached trade-press OCR with the corrected domain extractor
trade-press-reextract:
    uv run python scripts/reextract_trade_press.py --write
    @echo "now split the journal it names, with --tag reextract, then ingest both halves"

# Pause `maintain` first: the extraction runs for minutes before it writes, and
# it has no store-lock retry, so a maintain pass landing mid-run loses the work.
# the FERC-released Enron mail corpus, dated by each message's Date header
enron:
    uv run python scripts/collect_enron.py --write
    uv run ark ingest enron_dated      data/raw/enron/enron_dated.jsonl.gz
    uv run ark ingest enron_candidates data/raw/enron/enron_candidates.jsonl.gz

# Harvest first, then parse: `--harvest` fetches about 2,600 month files from
# two pipermail hosts, which takes six minutes and no archive.org budget.
# public pipermail list archives, dated by each message's Date header
maillists:
    uv run python scripts/collect_mailing_lists.py --harvest --write
    uv run ark ingest maillist_dated      data/raw/maillists/maillist_dated.jsonl.gz
    uv run ark ingest maillist_candidates data/raw/maillists/maillist_candidates.jsonl.gz

# Reads 33 index pages already on disk and sends no request. `artifact_listing`
# and no corroboration split: the mirror saved a copy of the page at that host on
# that date, so a name that did not resolve could not be in the index.
# the attrition.org defacement mirror, dated by the mirror's own index
attrition:
    uv run python scripts/collect_attrition.py --write
    uv run ark ingest attrition_dated data/raw/attrition/attrition_dated.jsonl.gz
    uv run ark seed data/raw/attrition/attrition_out_of_window_hosts.txt

# the Tucows software catalogue: release date plus vendor home page
tucows:
    uv run python scripts/split_tucows.py --write
    uv run ark ingest tucows_dated data/raw/tucows/tucows_dated.jsonl.gz
    uv run ark ingest tucows_candidates data/raw/tucows/tucows_candidates.jsonl.gz

# One loop rather than several, because DuckDB takes a single writer.
# fold everything the collectors have finished into the store, on a loop
maintain iterations="26" pause="900":
    bash scripts/maintain.sh {{iterations}} {{pause}}

# --- shipping ----------------------------------------------------------------

# Lands in submissions/<round>/, defaulting the round to the git branch, so a new
# round no longer overwrites the last one.
# build the delivery archive (refuses a dirty tree or a stale output/)
package round="":
    bash scripts/package_delivery.sh {{round}}

# check a built delivery the way a reviewer would: checksums, pair counts, and
# that every shipped pair traces to an observation
verify-delivery dir="output/internet-digital-ark-1996-2001":
    bash scripts/verify_delivery.sh {{dir}}
