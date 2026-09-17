"""The signed-off evidence taxonomy.

A type's disposition decides where its rows may go: master types may back
a (domain, year) assignment, candidate-only types never do. The schema's
CHECK constraint is generated from these sets, so code and schema cannot
drift apart.
"""

# master-eligible: a row of this type may create a domain_year assignment
MASTER_TYPES = frozenset(
    {
        "prior_reused",
        "cdx_timestamp",
        "artifact_listing",
        "link_source",
        "dated_directory",
        "whois_creation",
    }
)

# candidate-only: stored for provenance and verification priority, never a year
CANDIDATE_ONLY_TYPES = frozenset({"link_target"})

ALL_TYPES = MASTER_TYPES | CANDIDATE_ONLY_TYPES

# **Spec XIII, and the unit is the METHOD, not the type.** The annual masters are a
# website-evidence product: a row may enter the CLAIM only when the retained evidence
# shows the exact host serving the web in the target year. `artifact_listing` and
# `dated_directory` each land on both sides of that line, so the type cannot decide it.
#
# The list is an ALLOWLIST and unknown methods fail closed, into candidates. A method
# missing here costs a claim we can add back; a method wrongly here is a claim he
# refuses, and refusals are what the screen exists to prevent.
#
# Not applied to `prior_task`: that is his own merged baseline, its remediation is his
# under XIII's legacy section, and it is never part of our net-new claim anyway.
WEB_METHODS = frozenset(
    {
        # IA CDX, the reference standard: an exact-host capture with its stamp
        "ia_cdx_collapsed_query",
        "ia_cdx_domain_sweep",
        "ia_cdx_year_query",
        "ia_cdx_gap_hostgrain",
        "ia_domain_year_census",
        "bulk_cdx_file",
        "wayback_availability",
        # TimeMap, the same index read through Memento. `nypw_timemap_non_200` is NOT
        # here: XIII asks for a non-error capture and that method is defined by not
        # being one.
        "nypw_timemap",
        "nypw_timemap_hostgrain",
        "nypw_firstcdx_hostgrain",
        # a custodian's own per-host/year web-capture extract
        "arquivo_cdxj",
        "arquivo_ia_cdxj_hostgrain",
        "poland_pl_extract_hostgrain",
        "early_web_hostgrain",
        # a dated web link graph naming the target host
        "ukwa_host_link_graph",
        "ukwa_hostgrain",
        "bl_geoindex_extract",
    }
)


def web_evidence_sql(alias: str = "e") -> str:
    """The XIII predicate, for a query that has `evidence` joined as `alias`."""
    allowed = ", ".join(f"'{method}'" for method in sorted(WEB_METHODS))
    return f"{alias}.acquisition_method IN ({allowed})"
