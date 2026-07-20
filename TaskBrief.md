**Domain Data Collection Task Brief**

**I. Task Background**

The core objective of the current work is to improve, as much as
possible, the completeness of subsequent historical web content
acquisition. Under public-access conditions, it is not possible to
perform a truly exhaustive enumeration of Internet Archive, so the
preparatory stage must expand the coverage of historical domain and
historical URL seeds as much as possible.

But \"as complete as possible\" does not mean \"put everything you can
get into yearly files first.\" The real goal of this task is to obtain,
to the greatest extent possible, a year-by-year domain list for
1996-2001 that is trustworthy, and to provide high-quality seeds for
subsequent web page downloading. Quantity matters, and year-level
evidence matters just as much.

**II. Task Objectives**

This task focuses on the collection and organization of historical
domain names from 1996 to 2001. While expanding sources as much as
possible, it is required that every domain included in each yearly file
must have traceable evidence for its assigned year.

Objective 1: Continue expanding coverage of historical domains from 1996
to 2001, maximizing both total volume and breadth of coverage.

Objective 2: Organize yearly primary outputs that can be directly used
for subsequent processing.

Objective 3: Proactively identify new sources, new entry points, and new
extraction methods that have not yet been listed.

Objective 4: Build a clear evidence chain so that every yearly result
can explain \"why it belongs to that year.\"

**III. Most Important Evidence and Classification Rules**

The following rules have the highest priority, and all subsequent
methods must comply with them.

1.  The yearly primary results may include only domains that have \"year
    evidence.\" Such evidence may come from CDX timestamps, historical
    webpage snapshot dates, dated directory pages, dated index files, or
    other materials that can prove the domain appeared in the target
    year.

2.  Any data that does not have item-level year evidence cannot be
    written directly into \`1996.txt\` through \`2001.txt\`. Such data
    may only go into the candidate pool, pending-verification pool, or
    auxiliary seed pool.

3.  \`DMOZ RDF dump\` is a high-value source, but if what you have is
    only the overall snapshot dated \`2015-03-27\`, you must not
    distribute all domains from it evenly into the years 1996-2001. This
    would destroy the authenticity of the yearly results and is
    explicitly prohibited.

4.  If you use \`DMOZ\`, \`StanfordWebBase\`, certain historical web
    collections, or other data sources without item-level year labels,
    you must first treat them as candidate seeds, and then use
    independent timestamped sources to verify whether they truly
    appeared in 1996-2001. Only after verification may they be written
    into the corresponding yearly files.

5.  The final deliverable must clearly distinguish between two types of
    outputs: one is the yearly primary results, and the other is
    candidate results without precise year evidence. These two must not
    be mixed together.

**IV. Priority Work Path**

Do not keep repeating work on only a single source. First, fully deepen
and exhaust the known high-value sources that include time evidence.
Then continue seeking new directory pages, navigation sites, yellow
pages, historical indexes, and web collections. Convert large sources
without year labels into candidate seed pools. Use CDX, historical
snapshots, or other time-evidenced sources to verify candidate seeds.
Continue expanding outbound links from already downloaded HTML, and feed
newly discovered domains back into the next round of verification and
download queues. Perform cross-source deduplication, cross-validation,
and gap-filling across different sources.

**V. Methods That Should Continue to Be Expanded First**

The following methods should still be given priority for further
expansion, but they must follow the year-classification rules above
during execution.

Historical directory/navigation sources: historical Yahoo Directory
pages, DMOZ/Open Directory Project, NCSA Mosaic\'s What\'s New, early
navigation pages, category pages, portal pages, link exchange pages, and
yellow-pages-style sites.

Historical web archive index sources: Arquivo.pt bulk CDXJ, UK Web
Archive annual CDX files, UK Web Archive host/link graph, IA/Wayback CDX
results, and other public indexes from historical web archives.

Large-scale historical web collections/seed packages: ArchiveTeam,
GeoCities SEEDS/LISTS, StanfordWebBase-2001, EarlyWebDatasets,
TRECWT2g/WT10g, and other publicly obtainable historical URL lists or
link graphs.

Continue outbound-link expansion based on already downloaded webpages:
keep extracting external links, link-exchange links, navigation links,
and site lists from HTML pages to form a rolling discovery mechanism.

**VI. Updated Notes on DMOZ**

DMOZ remains a high-value source, but it must be used more precisely in
this task. If what is obtained is an RDF dump or a WARC mirror on
archive.org, the data should first be treated as a \"high-value
candidate seed source,\" rather than as a yearly result source that can
be written directly into year files. Only when a given DMOZ domain can
be confirmed again in Wayback, EarlyWeb, historical directory pages,
historical index files, or other sources with time evidence may it be
written into the corresponding year. If the specific year cannot be
verified, it should instead be output separately as
\`dmoz_candidate_domains.txt\`, \`dmoz_unlabeled_domains.txt\`, or a
similar file for continued verification later, and must not be mixed
into the yearly primary files. The executing student must state clearly
in the explanatory document whether DMOZ was used in this work as a
\"candidate pool\" or whether year verification has already been
completed through independent evidence.

**VII. Updated Requirements for IA/Wayback CDX**

Wayback CDX remains one of the key pieces of infrastructure for this
task. You must not conclude that this path is infeasible merely because
large-scale online queries may trigger 504 errors or rate limiting. For
high-value sources such as directory pages, yellow pages, navigation
pages, and category pages, you should use existing tools as much as
possible to batch-retrieve their historical CDX indexes and then filter
snapshots for the target years. If the online interface triggers 504,
429, or rate limiting, you need to adjust batch size, concurrency,
pagination method, and retry strategy rather than stopping immediately.
The explanatory document must include a dedicated section stating
clearly: what CDX acquisition tools you used, which sites or seeds you
fetched, how you batched them, what the success rate was, how failures
were handled, and how many additional unique domains were ultimately
added. Only after tool-based retrieval has actually been carried out and
you can show that the incremental gain is very low may you conclude that
a given CDX path is temporarily not worth expanding further.

**VIII. How to Expand One Source into More Domains**

Below is an updated standard workflow to show how the work should
proceed. First obtain data from a high-value source, such as DMOZ, Yahoo
Directory, a certain type of navigation site, a historical index file,
or a batch of directory pages. Extract domains, hostnames, and URLs from
it to form a candidate seed set. Send these candidate seeds into sources
with time evidence for verification, such as EarlyWeb CDX, Wayback CDX,
historical directory page snapshots, or dated index files. Archive
verified results by year. Continue downloading the corresponding
historical HTML, and extract link-exchange links, recommended sites,
external links on directory pages, and site lists on navigation pages.
Feed newly discovered domains back into the next verification queue.
Compare across other sources, identify the newly added portion, and then
add it back into the master list or candidate pool. In other words, the
workflow is not \'extract everything once and stop,\' but rather a loop
of source discovery, time verification, page expansion, and second-round
feedback.

**IX. New Methods That Must Be Actively Sought**

In addition to continuing to use known paths, every executing student
must actively look for methods that have not yet been listed, and verify
their actual output as much as possible.

New data sources

New historical directory/navigation entry points

New indexes, link graphs, or URL packages

New web collections or seed packages

New extraction ideas, verification ideas, or cross-source gap-filling
ideas

Directions that can be prioritized include: early portal sites, category
sites, award sites, resource aggregation sites, webmaster resource
pages, yellow-pages-style sites, site lists on
educational/government/organizational websites, various historical site
rankings, public indexes from web archives in different countries and
regions, and inferring outbound-link domains from large historical
communities or personal homepage hosting platforms.

**X. Deliverable Format and Documentation Requirements**

The final deliverable cannot consist of only a few txt files; it must
also allow the next person taking over the work to clearly understand
where every part came from.

Yearly primary results: save them separately by year as \`1996.txt\`,
\`1997.txt\`, \`1998.txt\`, \`1999.txt\`, \`2000.txt\`, and
\`2001.txt\`. The requirement is one domain per line, deduplicated
within the same year, with clear and accurate year classification.

Candidate results (if any): all domains without precise year evidence
but still worth further verification should be output separately as
candidate files and must not be mixed into the yearly primary results.

Documentation: in addition to the yearly files, a Word explanatory
document must also be provided. It should at minimum clearly describe
the methods already used, newly found methods, output from each source,
limitations, whether each source is worth expanding further, and the
evidence standard for each type of result.

Source contribution statistics: it is recommended to count the number of
newly added domains by source, and distinguish between \"new additions
that can directly enter the yearly primary results\" and \"new additions
that enter only the candidate pool.\"

CDX execution notes: you must include a separate section explaining
which existing CDX acquisition tools were used, what the retrieval
strategy was, what errors were encountered, how they were handled, and
how many actual additions were obtained.

**XI. Final Delivery Standards**

The final outputs submitted for this task should satisfy the following
standards.

1.  The domain txt files organized by year can be used directly for the
    next step of aggregation and webpage downloading.

2.  Every domain in each yearly file can explain the evidence for its
    assigned year.

3.  Data without year evidence has been independently isolated into the
    candidate pool.

4.  Known high-value sources have been explored as deeply as possible,
    and new sources and methods have been actively attempted.

5.  The explanatory document enables subsequent personnel to reproduce
    your workflow and judge which directions are worth expanding
    further.
