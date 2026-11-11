#!/bin/bash
# One file through the report-URL grep, for .github/workflows/runner-grep.yml: URL the file,
# CONNECTIONS its ranges at once, OPEN its decompressor, PATTERN an ERE kept in place of
# report_urls.ere. out/hits.txt grows a line at a time, out/progress.txt says how far the
# download is, out/done holds the three exit codes at the end (a line a file under REDUCE).
here=$(dirname "$0")
# REDUCE set: each file of URL in turn to one capture per host and year (host_years.py), no grep.
if [ -n "$REDUCE" ]; then
  for u in $URL; do
    name=$(printf '%s' "${u#*://*/}" | tr -c 'A-Za-z0-9.-' '_' | tail -c 100)
    python3 "$here/fetch_ranges.py" "$u" "${CONNECTIONS:-4}" 2>> out/progress.txt \
      | ${OPEN:-cat} 2> /dev/null \
      | python3 "$here/host_years.py" "out/$name.jsonl.gz" 2>> out/counts.txt
    echo "$name ${PIPESTATUS[*]}" >> out/codes.txt
  done
  mv out/codes.txt out/done
  exit
fi
pattern="$here/report_urls.ere"
[ -n "$PATTERN" ] && pattern=pattern.ere && printf '%s\n' "$PATTERN" > pattern.ere
python3 "$here/fetch_ranges.py" "$URL" "${CONNECTIONS:-4}" ${LAST:+"$LAST"} 2> out/progress.txt \
  | ${OPEN:-cat} 2> /dev/null \
  | LC_ALL=C grep -a -i -E --line-buffered -f "$pattern" > out/hits.txt
echo "${PIPESTATUS[*]}" > out/done
