# How to reproduce the table

Python 3.9 or later. No third-party packages. Nothing is fetched from the network.

## 1. Any single benchmark release

Point the program at a directory holding `1996.txt` to `2001.txt`:

```
python registrable_unit.py "<path>/merged260830" --out my_results
```

It prints a line per file and writes `my_results/summary.csv`.

## 2. My submitted additions

Each of my submission archives contains an `additions/` directory, which is what I
asked you to merge. Unpack one and point the program at that directory:

```
tar xzf internet-digital-ark-1996-2001.tar.gz
python registrable_unit.py internet-digital-ark-1996-2001/additions --out my_results
```

## 3. The increment between two benchmark releases

The increment is the set difference of the two annual files. On Linux or macOS:

```
for y in 1996 1997 1998 1999 2000 2001; do
  comm -13 <(sort "<older>/$y.txt") <(sort "<newer>/$y.txt") > "increment/$y.txt"
done
python registrable_unit.py increment --out my_results
```

In PowerShell:

```
foreach ($y in 1996..2001) {
  $old = Get-Content "<older>\$y.txt"
  Compare-Object $old (Get-Content "<newer>\$y.txt") |
    Where-Object SideIndicator -eq '=>' |
    Select-Object -ExpandProperty InputObject |
    Set-Content "increment\$y.txt"
}
python registrable_unit.py increment --out my_results
```

The two increments in the table are `merged260810` to `merged260815`, and
`merged260827-2` to `merged260830`.

## 4. The exact run behind the results in this archive

```
python registrable_unit.py \
  merged260727 \
  increment_260810_to_260815 \
  increment_260827-2_to_260830 \
  phase-4_additions phase-5_additions phase-6_additions \
  my_next_additions \
  merged260830 \
  --out results
```

`results/console_output.txt` is what that printed.

## Reading the output

Per file: `records` counted after lowercasing and deduplicating, then split into
`conforming` (a registered domain), `not_conforming` (a hostname carrying a label to the
left of its registered domain) and `unparsed` (no known public suffix, an IP address, a
reverse-DNS zone, or invalid hostname syntax). `equivalent_english_not_conforming` is
the weight at stake, using the bundled model.
