#!/usr/bin/env bash
# Assemble the output-unit archive sent to the reviewer on 2026-08-31.
#
# **Why this is a script and not a one-off.** The archive is the evidence behind a
# question about the output unit, and CLAUDE.md's rule about temp directories applies to
# our own artifacts too: the first build of this pack lived only in a scratch directory.
# Everything here is derived, so the pack is never committed, only its generator.
#
# The measurement inputs are the reviewer's own annual files plus the `additions/`
# directory inside each of our submission archives. Nothing is fetched.
#
#     bash scripts/output_unit_pack/build.sh <workdir> [out.zip]

set -euo pipefail
cd "$(dirname "$0")/../.." || exit 1
REPO=$(pwd)
WORK="${1:?usage: build.sh <workdir> [out.zip]}"
OUT="${2:-$WORK/output_unit_check.zip}"
F="$REPO/feedback"
P7="$F/feedback-phase-7/Domain_Data_Collection_Task 3"
PACK="$WORK/output_unit_check"

mkdir -p "$PACK/results"
cp "$REPO/scripts/output_unit_pack/registrable_unit.py" "$PACK/"
cp "$REPO/scripts/output_unit_pack/PACK_README.md" "$PACK/README.md"
cp "$REPO/scripts/output_unit_pack/PACK_REPRODUCE.md" "$PACK/REPRODUCE.md"
# The list snapshot our pipeline is pinned to, so the reviewer resolves suffixes
# exactly as we do, and HIS weights rather than ours, so a disagreement in the
# weights can never be mistaken for a disagreement in the unit.
cp "$REPO/src/ark/data/public_suffix_list.dat" "$PACK/"
cp "$P7/equivalent_english_domain_calculator/q2_tld_top_langs.json" "$PACK/"

# Our submitted additions, straight out of the frozen submission archives.
for phase in 4 5 6; do
    mkdir -p "$WORK/subs/phase-$phase"
    tar xzf "$REPO/submissions/phase-$phase/internet-digital-ark-1996-2001.tar.gz" \
        -C "$WORK/subs/phase-$phase" --strip-components=2 \
        internet-digital-ark-1996-2001/additions
done

# An increment between two releases is the set difference of the annual files.
increment() {
    local older="$1" newer="$2" dest="$3" year
    mkdir -p "$dest"
    for year in 1996 1997 1998 1999 2000 2001; do
        comm -13 <(sort "$older/$year.txt") <(sort "$newer/$year.txt") > "$dest/$year.txt"
    done
}
increment "$F/feedback-phase-4/merged260810" "$F/feedback-phase-5/merged260815" \
    "$WORK/inc_a"
increment "$F/feedback-phase-7/Domain_Data_Collection_Task 2/merged260827-2" \
    "$P7/merged260830" "$WORK/inc_b"

# Labels, not paths, are what the reviewer reads in the summary, so the measurement
# runs over a tree of symlinks whose names say what each dataset is.
M="$WORK/measure"
rm -rf "$M"; mkdir -p "$M"
ln -s "$F/feedback-phase-1/Internet_Digital_Ark_Feedback_2026-07-27/merged260727" \
    "$M/1_original_benchmark_merged260727"
ln -s "$WORK/inc_a" "$M/2_increment_260810_to_260815_not_ours"
ln -s "$WORK/inc_b" "$M/3_increment_260827-2_to_260830_not_ours"
ln -s "$WORK/subs/phase-4" "$M/4_our_submission_2026-08-09_additions"
ln -s "$WORK/subs/phase-5" "$M/5_our_submission_2026-08-17_additions"
ln -s "$WORK/subs/phase-6" "$M/6_our_submission_2026-08-26_additions"
ln -s "$REPO/output/netnew" "$M/7_our_next_additions_unsubmitted"
ln -s "$P7/merged260830" "$M/8_current_benchmark_merged260830"

cd "$M"
python3 "$PACK/registrable_unit.py" 1_* 2_* 3_* 4_* 5_* 6_* 7_* 8_* \
    --out "$PACK/results" | tee "$PACK/results/console_output.txt"

rm -rf "$PACK/__pycache__"
cd "$WORK"
rm -f "$OUT"
zip -qr "$OUT" output_unit_check -x '*.DS_Store'
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
