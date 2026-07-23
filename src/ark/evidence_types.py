"""The signed-off evidence taxonomy (notes.md, "Definition: evidence types").

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
