# Reproducing the table

Python 3.9 or later. No third-party packages, no network access.

## A benchmark release, or my submitted additions

Point the script at any directory holding `1996.txt` to `2001.txt`:

```
python registrable_unit.py "<path>/merged260830" --out my_results
```

My submission archives each contain an `additions/` directory, which is what I asked you
to merge:

```
tar xzf internet-digital-ark-1996-2001.tar.gz
python registrable_unit.py internet-digital-ark-1996-2001/additions --out my_results
```

## An increment between two releases

The increment is the set difference of the annual files. On Linux or macOS:

```
for y in 1996 1997 1998 1999 2000 2001; do
  comm -13 <(sort "<older>/$y.txt") <(sort "<newer>/$y.txt") > "increment/$y.txt"
done
python registrable_unit.py increment --out my_results
```

In PowerShell:

```
foreach ($y in 1996..2001) {
  Compare-Object (Get-Content "<older>\$y.txt") (Get-Content "<newer>\$y.txt") |
    Where-Object SideIndicator -eq '=>' |
    Select-Object -ExpandProperty InputObject |
    Set-Content "increment\$y.txt"
}
python registrable_unit.py increment --out my_results
```

The two increments in the table are `merged260810` to `merged260815`, and
`merged260827-2` to `merged260830`.

## Reading the output

Records are counted after lowercasing and deduplicating, then split into `conforming`
(a registered domain), `not_conforming` (a label to the left of the registered domain)
and `unparsed` (no known public suffix, an IP address, a reverse-DNS zone, or invalid
syntax). `equivalent_english_not_conforming` is the weight at stake.

`results/console_output.txt` is the exact output of the run behind the shipped table.
