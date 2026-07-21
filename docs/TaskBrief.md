**Domain Data Collection Task Brief**

Update time：2026-07-21 18:07:04

**I. Task Background**

The central objective of the current work is to maximize the completeness of subsequent historical web content acquisition. Under publicly available conditions, it is impossible to perform a genuinely exhaustive enumeration of the Internet Archive. The preliminary phase must therefore expand the coverage of historical domain names and historical URL seeds as far as possible.

This task aims to obtain, to the greatest extent possible, reliable annual domain lists for 1996-2001 and to provide high-quality seeds for subsequent webpage downloads. Quantity is important, but year-specific evidence is equally important.

**II. Task Objectives**

This task focuses on collecting and organizing historical domains from 1996 through 2001. While sources should be expanded as broadly as possible, every domain included in an annual file must have a traceable basis for its year assignment or a documented acquisition method.

Objective 1: Continue expanding the coverage of historical domains from 1996 to 2001, increasing both the total volume and breadth of coverage as much as possible.

Objective 2: Organize annual master results that can be used directly in subsequent processing.

Objective 3: Proactively identify new sources, entry points, and domain-extraction methods that have not yet been listed.

Objective 4: Establish a clear chain of evidence so that every annual result explains why a domain belongs to that year, including a description of the acquisition method.

**III. Most Important Scope and Evidence Requirements**

The following rules have the highest priority. All subsequent methods must comply with them.

1.  Annual master results may include only domains supported by evidence for the corresponding year. Here, evidence for the corresponding year means factual material demonstrating that the domain actually existed, was in use, or was active during the specific calendar year in which it is to be included, or an acquisition method whose year scope itself clearly establishes that fact. Such evidence may include a CDX timestamp from that year, a historical webpage snapshot, a dated directory page, a dated index file, a WHOIS record demonstrating registration status in that year, or equivalent material. Evidence from an earlier year alone does not automatically establish that the domain continued to exist or remain active in later years. If a previous task has already recorded item-level evidence for each relevant year, that evidence may be reused without repeating the verification from scratch.

2.  Data without item-level year evidence must not be written directly to \`1996.txt\` through \`2001.txt\`. Such data may be placed only in a candidate pool, pending-verification pool, or auxiliary seed pool.

3.  Although \`DMOZRDFdump\` is a high-value source, if only the aggregate snapshot dated \`2015-03-27\` is available, all domains in that snapshot must not be distributed indiscriminately across the annual files for 1996-2001. Doing so would undermine the authenticity of the annual results.

4.  If \`DMOZ\`, \`StanfordWebBase\`, certain historical webpage collections, or other data without item-level year labels are used, they must first be treated as candidate seeds. Each domain must then be checked through the IA CDX service or another source containing year-specific evidence to determine whether it actually appeared, existed, or was active in every specific year in which inclusion is proposed. A domain may be written only to the file for a year that has been successfully verified; verification for one year does not justify automatic inclusion in any other year.

5.  The final deliverables must clearly distinguish between two categories of results: annual master results and candidate results without precise year evidence. These categories must not be mixed.

6.  A WHOIS Creation Date is valid evidence of when a domain was created and can establish that the domain existed no later than that date. It may support inclusion in the annual file for the target year in which the creation date falls. However, a WHOIS Creation Date alone does not automatically establish that the domain remained registered, continued to exist, or was active in every subsequent year. Inclusion in later annual files still requires a WHOIS record demonstrating continued registration in that year, a CDX record, a historical snapshot, or other factual evidence tied to that specific year. Even if a domain currently has no usable archive in IA, it may be included in the relevant year when such year-specific evidence is available.

7.  The annual files are not limited to the year in which a domain first appeared. If factual evidence or a year-specific acquisition method independently demonstrates that a domain actually existed, was in use, or was active in multiple target years, the domain must appear in every annual file for which that status has been established. Cross-year duplication is therefore permitted and necessary. Deduplication is required within each year, not across different years. Every annual inclusion must have evidence for that year; the date of first appearance alone must not be used to infer presence in later years.

8.  By default, the final domain files should use registered domains as the output unit rather than full hostnames or user paths on hosting platforms. Unless otherwise explicitly required, output should therefore favor registered domains rather than \`www.example.com\`, \`foo.example.com\`, or specific user paths on platforms such as GeoCities or Tripod.

9.  An existing filename such as \`1996.txt\` represents the domains obtained to date for which there is evidence of actual existence, use, or activity during the period from 00:00:00 on January 1, 1996, through 23:59:59 on December 31, 1996. The same standard applies to every other annual file.

10. At the current stage, a separate preliminary CDX validation is not required before a domain enters the processing pool, because downloading CDX records from the IA servers for a specified year inherently performs year validation. A domain may enter an annual master result only after a CDX record has been successfully obtained within that year's date range or another year-specific acquisition method has established its presence in that year. If the acquisition method cannot establish a specific year, the domain may enter only the candidate pool.

11. Every collected domain list must be accompanied by an explanation of the acquisition method and the processing performed. It is strictly unacceptable to expand the lists without documenting the method.

**IV. Priority Workstreams**

Do not repeatedly focus on a single source. First, fully develop known high-value sources that contain time evidence. Then continue searching for new directory pages, navigation sites, yellow-page sites, historical indexes, and webpage collections. Convert large sources without year labels into candidate seed pools. Validate candidate seeds using CDX, historical snapshots, or other sources containing time evidence. Continue extracting outbound links from downloaded HTML, and feed newly discovered domains back into the next validation and download queues. Perform cross-source deduplication, cross-validation, and gap filling. Alternatively, identify high-quality web directory or yellow-page sites active from 1996 to 2001, use the IA CDX service to retrieve the complete CDX records for those sites' directory pages over a defined yearly period, then download the pages and extract domains from them; domains extracted through this route do not require subsequent CDX validation.

**V. Methods to Prioritize for Further Expansion**

The following methods should continue to receive priority, but their execution must comply with the year-specific rules above.

Historical directory and navigation-site sources: historical Yahoo Directory pages, DMOZ/Open Directory Project, NCSA Mosaic's What's New, early navigation pages, category pages, portal pages, link-exchange pages, and yellow-page sites.

Historical web-archive index sources: Arquivo.pt bulk CDXJ, annual CDX files from the UK Web Archive, UK Web Archive host/link graphs, IA/Wayback CDX results, and public indexes from other web archives.

Large historical web collections and seed packages: ArchiveTeam, GeoCities SEEDS/LISTS, Stanford WebBase 2001, Early Web Datasets, TREC WT2g/WT10g, and other publicly available historical URL lists or link graphs.

Continued outbound-link expansion based on downloaded webpages: extract external links, reciprocal links, navigation links, and site lists from HTML pages to create an iterative discovery mechanism.

**VI. Updated Requirements for IA/Wayback CDX**

Wayback CDX remains one of the key infrastructure components for this task. The public IA CDX API is currently in use; the occurrence of 504 errors or rate limits during large-scale online queries does not justify declaring this approach infeasible. For high-value sources such as directory pages, yellow-page pages, navigation-site pages, and category pages, existing tools should be used wherever possible to obtain their historical CDX indexes in batches through the public interface, after which snapshots from the target years should be selected. If the online interface returns 504 or 429 errors or imposes rate limits, adjust batch sizes, concurrency, pagination, and retry strategies instead of stopping outright. The explanatory materials must contain a dedicated section stating which CDX acquisition tools were used, which sites or seeds were retrieved, how requests were batched, the success rate, how failures were handled, and how many unique domains were ultimately added. A CDX route may be described as temporarily unworthy of further expansion only after tool-based retrieval has actually been completed and the incremental yield has been demonstrated to be very low.

**VII. How to Expand One Source into More Domains**

The following updated standard workflow illustrates how the work should proceed. First, obtain data from a high-value source, such as DMOZ, Yahoo Directory, a navigation site, a historical index file, or a batch of directory pages. Extract domains, hostnames, and URLs to create a candidate seed set. Submit those candidate seeds to sources with time evidence for validation, such as Early Web CDX, Wayback CDX, historical directory-page snapshots, or dated index files. Archive successfully validated results by year. Continue downloading the corresponding historical HTML and extract reciprocal links, recommended sites, outbound links from directory pages, and site lists from navigation pages. Feed newly discovered domains back into the next validation queue. Compare them against other sources, identify additions, and place them in the master dataset or candidate pool as appropriate. In other words, the workflow is not a one-time extraction followed by completion; it is a cycle of source discovery, time validation, page expansion, and secondary feedback.

**VIII. New Methods That Must Be Proactively Identified**

In addition to continuing the known approaches, every team member must proactively identify methods not yet listed and, wherever possible, validate their actual yield.

New data sources

New entry points to historical directories or navigation sites

New indexes, link graphs, or URL packages

New webpage collections or seed packages

New extraction, validation, or cross-source gap-filling approaches

Priority areas for consideration include early portals, category sites, award sites, resource aggregators, webmaster resource pages, yellow-page sites, site lists hosted by educational, governmental, or organizational websites, historical website rankings of various kinds, public indexes from national and regional web archives, and the derivation of outbound-link domains from large historical communities or personal-homepage hosting platforms.

**IX. Delivery Format and Documentation Requirements**

The final delivery must include more than several TXT files. It must also enable subsequent personnel to understand clearly how every component was produced.

Annual master results: Save separate yearly files as \`1996.txt\`, \`1997.txt\`, \`1998.txt\`, \`1999.txt\`, \`2000.txt\`, and \`2001.txt\`. Each line must contain one domain; duplicates must be removed within the same year; and year assignments must be clear and accurate. The annual files are not limited to first appearance. If factual evidence or a year-specific acquisition method establishes that a domain actually existed, was in use, or was active in multiple target years, the domain must be included in every annual file for which that status has been established. Each year requires its own evidentiary basis; an earlier appearance or a WHOIS Creation Date alone must not be used to infer presence in later years.

Candidate results (if any): All domains lacking precise year evidence but meriting further verification must be exported separately as candidate files and must not be mixed into the annual master results. The candidate pool should be expanded proactively and made as large as practicable to maximize overall coverage of historical domains.

Explanatory materials: In addition to the annual domain-list files, which must already be merged and deduplicated, provide a Word document explaining at minimum the methods used, newly identified methods, yield from each source, limitations, whether further expansion is worthwhile, and the evidentiary standard applied to each category of results.

Source contribution statistics: It is recommended that newly added domains be counted by source, with separate figures for additions eligible for direct inclusion in the annual master results and additions eligible only for the candidate pool.

CDX execution notes: Provide a dedicated explanation of the existing CDX acquisition tools used, the retrieval strategy, errors encountered, how those errors were handled, and the number of domains actually added.

**The final results submitted for this task must meet the following standards:**

1.  Domain TXT files organized by year.

2.  For every domain in each annual file, the Word documentation explains the acquisition method and the factual basis tied to that specific year. If the same domain appears in multiple annual files, the basis for each year is documented separately.

3.  Data without year evidence has been isolated in a separate candidate pool.

4.  Known high-value sources have been developed as fully as possible, and new sources and methods have been proactively tested.

5.  The explanatory materials enable subsequent personnel to reproduce the workflow and determine which directions merit further expansion.
