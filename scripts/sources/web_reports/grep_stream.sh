#!/bin/bash
# One file through the report-URL grep, for .github/workflows/runner-grep.yml: URL the file,
# CONNECTIONS its ranges at once, OPEN its decompressor. out/hits.txt grows a line at a time,
# out/progress.txt says how far the download is, out/done holds the three exit codes at the end.
here=$(dirname "$0")
python3 "$here/fetch_ranges.py" "$URL" "${CONNECTIONS:-4}" ${LAST:+"$LAST"} 2> out/progress.txt \
  | ${OPEN:-cat} 2> /dev/null \
  | LC_ALL=C grep -a -i -E --line-buffered -f "$here/report_urls.ere" > out/hits.txt
echo "${PIPESTATUS[*]}" > out/done
