"""Traceability enforcement for the scientific Benefits registry and core.

The registry is prose that claims to be checkable. This suite makes the claim
real by reading `benefits_scientific_core.py` as text and confirming that the
two halves of the traceability contract agree:

  Level A — every equation line carries an inline `# EQ=... | REF=... | TITLE=...
             | LOC=... | DOI=... | URL=...` comment;
  Level B — every `REF-*` cited in those comments resolves to a full registry
             record with a title, an exact location and a DOI or official URL.

It also enforces the negative rules: no bare `# source: World Bank` comment, no
hard-coded journal-quartile claim, no SOURCE-OPEN equation smuggled in as
publication-ready, and the PLOS LUD formula keeping its leading minus sign.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from benefits_reference_registry import (
    ALL_EVIDENCE_CLASSES,
    BLOCKED_TOPICS,
    EQUATIONS,
    METHOD_EVIDENCE_CLASSES,
    PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE,
    REFERENCES,
    equation,
    equation_audit_rows,
    reference,
    reference_registry_rows,
    validate_registry,
)

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


CORE_PATH = os.path.join(ROOT, "benefits_scientific_core.py")
CORE_SRC = open(CORE_PATH, encoding="utf-8").read()
CORE_LINES = CORE_SRC.splitlines()

# Only lines that actually cite an equation are equation lines. The module
# docstring mentions the comment shape without being one.
EQ_LINE_RE = re.compile(r"#\s*EQ=(?P<eq>BEN-[A-Z0-9-]+)\s*\|(?P<rest>.*)$")
EQ_LINES = []
for lineno, line in enumerate(CORE_LINES, start=1):
    m = EQ_LINE_RE.search(line)
    if m:
        EQ_LINES.append((lineno, line, m.group("eq"), m.group("rest")))

check("core contains at least one traceable equation line", len(EQ_LINES) > 0)

# ---------------------------------------------------------------------------
# Registry self-integrity
# ---------------------------------------------------------------------------

problems = validate_registry()
for problem in problems:
    print("     registry problem:", problem)
check("registry passes its own integrity checks", not problems)

check("registry holds every reference cited by an equation", all(
    ref_id in REFERENCES for eq in EQUATIONS.values() for ref_id in eq.method_ref_ids
))

for ref_id, ref in REFERENCES.items():
    check(f"{ref_id}: has a title", bool(ref.title.strip()))
    check(f"{ref_id}: has an exact location", bool(ref.exact_location.strip()))
    has_doi = ref.doi.strip() and ref.doi.strip().lower() != "n/a"
    has_url = ref.official_url.strip() and ref.official_url.strip().lower() != "n/a"
    check(f"{ref_id}: resolves via DOI or official URL", bool(has_doi or has_url))
    check(f"{ref_id}: writes an absent DOI explicitly as 'n/a'", bool(ref.doi.strip()))
    check(f"{ref_id}: evidence status is a known class", ref.evidence_status in ALL_EVIDENCE_CLASSES)

for eq_id, eq in EQUATIONS.items():
    check(f"{eq_id}: has a unit contract", bool(eq.output_unit_contract.strip()))
    check(f"{eq_id}: has at least one method reference", bool(eq.method_ref_ids))
    check(f"{eq_id}: has at least one exact source location", bool(eq.exact_source_locations))

# ---------------------------------------------------------------------------
# Level A <-> Level B agreement
# ---------------------------------------------------------------------------

cited_eq_ids = {eq_id for _, _, eq_id, _ in EQ_LINES}
missing_in_core = sorted(set(EQUATIONS) - cited_eq_ids)
for eq_id in missing_in_core:
    print("     registered but never implemented with a source comment:", eq_id)
check("every registered equation appears on a source-commented core line", not missing_in_core)

unregistered = sorted(cited_eq_ids - set(EQUATIONS))
for eq_id in unregistered:
    print("     cited in core but absent from the registry:", eq_id)
check("every equation cited in the core is registered", not unregistered)

# Each inline comment must carry the fields a reviewer needs, and must cite the
# same references the registry records for that equation.
for lineno, line, eq_id, rest in EQ_LINES:
    ctx = f"core line {lineno} ({eq_id})"
    check(f"{ctx}: comment carries REF=", "REF=" in rest)
    check(f"{ctx}: comment carries TITLE=", "TITLE=" in rest)
    check(f"{ctx}: comment carries LOC=", "LOC=" in rest)
    check(f"{ctx}: comment carries DOI=", "DOI=" in rest)
    check(f"{ctx}: comment carries URL=", "URL=" in rest)

    ref_match = re.search(r"REF=([A-Z0-9;.\-]+)", rest)
    inline_refs = set(ref_match.group(1).split(";")) if ref_match else set()
    check(f"{ctx}: names at least one reference id", bool(inline_refs))
    unknown = sorted(r for r in inline_refs if r not in REFERENCES)
    check(f"{ctx}: every inline reference resolves in the registry ({unknown})", not unknown)

    registered_refs = set(EQUATIONS[eq_id].method_ref_ids) if eq_id in EQUATIONS else set()
    check(
        f"{ctx}: inline references match the registry record",
        inline_refs == registered_refs,
    )

    loc_match = re.search(r"LOC=([^|]*)", rest)
    loc_text = loc_match.group(1).strip() if loc_match else ""
    check(f"{ctx}: LOC is not blank", bool(loc_text))

    doi_match = re.search(r"DOI=([^|]*)", rest)
    doi_text = doi_match.group(1).strip() if doi_match else ""
    check(f"{ctx}: DOI is present or explicitly 'n/a'", bool(doi_text))

    url_match = re.search(r"URL=(\S+)", rest)
    check(f"{ctx}: URL is a resolvable link", bool(url_match) and url_match.group(1).startswith("http"))

# ---------------------------------------------------------------------------
# Forbidden comment styles
# ---------------------------------------------------------------------------

# A comment that names a publisher, a vibe or a ranking instead of a document.
VAGUE_COMMENT_RE = re.compile(
    r"#\s*(source\s*:\s*)?(world bank|literature|q1 (source|paper)|per the standard|"
    r"see reference|as published|from the paper)\s*$",
    re.IGNORECASE,
)
vague = [
    (lineno, line.strip())
    for lineno, line in enumerate(CORE_LINES, start=1)
    if VAGUE_COMMENT_RE.search(line)
]
for lineno, text in vague:
    print("     vague source comment at line", lineno, ":", text)
check("core contains no vague source comment", not vague)

# A quartile or impact-factor claim is a ranking assertion, not evidence.
QUARTILE_RE = re.compile(r"\b(quartile|jcr|impact\s*factor|scimago|sjr)\b", re.IGNORECASE)
for path in ("benefits_scientific_core.py", "benefits_reference_registry.py"):
    src = open(os.path.join(ROOT, path), encoding="utf-8").read()
    hits = QUARTILE_RE.findall(src)
    # The registry's own guard list names these markers in order to forbid them;
    # exclude the guard block itself from the scan.
    if path == "benefits_reference_registry.py":
        guarded = src.split("_QUARTILE_CLAIM_MARKERS")[0]
        hits = QUARTILE_RE.findall(guarded)
    check(f"{path} makes no hard-coded journal-ranking claim", not hits)

check(
    "no reference record sets a quartile field",
    not re.search(r"quartile\s*=", open(os.path.join(ROOT, 'benefits_reference_registry.py'), encoding='utf-8').read(), re.IGNORECASE),
)

# ---------------------------------------------------------------------------
# The LUD minus sign — the single most fragile transcription in this domain
# ---------------------------------------------------------------------------

lud_lines = [line for _, line, eq_id, _ in EQ_LINES if eq_id == "BEN-LUD-01"]
check("BEN-LUD-01 has exactly one implementation line", len(lud_lines) == 1)
if lud_lines:
    lud_line = lud_lines[0]
    expr = lud_line.split("#")[0]
    check("BEN-LUD-01 expression carries the leading minus sign", "= -sum(" in expr)
    check("BEN-LUD-01 normalises by ln(n)", "math.log(n_classes)" in expr)
    check("BEN-LUD-01 excludes zero shares instead of calling log(0)", "if p > 0.0" in expr)
    check(
        "BEN-LUD-01 comment records the visual verification of the minus sign",
        "minus sign" in lud_line.lower(),
    )

check(
    "registry formula text for BEN-LUD-01 keeps the minus sign",
    EQUATIONS["BEN-LUD-01"].formula_text.strip().startswith("LUD = -"),
)

# ---------------------------------------------------------------------------
# Method evidence is never numeric evidence
# ---------------------------------------------------------------------------

check(
    "method and publication-numeric evidence classes are disjoint",
    not (METHOD_EVIDENCE_CLASSES & PUBLICATION_ACCEPTABLE_NUMERIC_EVIDENCE),
)

# Authority is a registry property, not a user choice. Without this a reviewer
# could select a method reference in the form and type PROJECT-SPECIFIC beside it.
from benefits_reference_registry import reference_permits, permitted_statuses_for  # noqa: E402

for ref_id, ref in REFERENCES.items():
    check(f"{ref_id}: declares which statuses it may back",
          bool(ref.permitted_evidence_statuses))
    check(f"{ref_id}: permits its own declared role",
          ref.evidence_status in ref.permitted_evidence_statuses)
    check(f"{ref_id}: does not permit PROJECT-SPECIFIC",
          "PROJECT-SPECIFIC" not in ref.permitted_evidence_statuses)
    check(f"{ref_id}: reference_permits agrees with the record",
          all(reference_permits(ref_id, s) for s in ref.permitted_evidence_statuses))
    check(f"{ref_id}: permitted_statuses_for round-trips",
          permitted_statuses_for(ref_id) == ref.permitted_evidence_statuses)

check(
    "a foreign method study may back nothing but its method role",
    permitted_statuses_for("REF-TRD-MODAL-2024") == ("METHOD-REFERENCE",),
)
check(
    "the cross-country jobs benchmark stays a proxy",
    permitted_statuses_for("REF-MOSZORO-2024") == ("REF-PROXY",),
)
check(
    "the historical I-O table may not back current project data",
    not reference_permits("REF-EGY-IO-ALAYOUTY-2022", "OFFICIAL-PROJECT-DATA"),
)
check(
    "only a document reporting this project may back official project data",
    all(
        "project" in r.evidence_role.lower() or "project" in r.notes.lower()
        for r in REFERENCES.values()
        if "OFFICIAL-PROJECT-DATA" in r.permitted_evidence_statuses
    ),
)
check("an unknown reference backs nothing", not reference_permits("REF-NOT-REAL", "METHOD-REFERENCE"))

for eq_id, eq in EQUATIONS.items():
    method_only = all(
        REFERENCES[r].evidence_status in METHOD_EVIDENCE_CLASSES
        for r in eq.method_ref_ids
        if r in REFERENCES
    )
    if method_only:
        check(
            f"{eq_id}: a method-only equation declares the numeric evidence it needs",
            bool(eq.required_numeric_evidence),
        )

check(
    "no equation is marked publication-ready without naming its numeric evidence",
    not [
        eq_id
        for eq_id, eq in EQUATIONS.items()
        if eq.publication_status.upper() in {"PUBLICATION-READY", "READY"}
    ],
)

# ---------------------------------------------------------------------------
# Blocked topics stay blocked
# ---------------------------------------------------------------------------

check("formalization is recorded as blocked", "BEN-FORMALIZATION" in BLOCKED_TOPICS)
check("carbon monetisation is recorded as blocked", "BEN-CARBON-MONEY" in BLOCKED_TOPICS)
check("noise monetisation is recorded as blocked", "BEN-NOISE-MONEY" in BLOCKED_TOPICS)
check(
    "every blocked topic states what would close it",
    all(len(v.strip()) > 40 for v in BLOCKED_TOPICS.values()),
)
check(
    "no blocked topic is also a registered equation",
    not (set(BLOCKED_TOPICS) & set(EQUATIONS)),
)
# The word appears in the module docstring explaining the deliberate absence, so
# the check is on definitions and equation lines, not on the word itself.
check(
    "core defines no formalization function",
    not re.search(r"^\s*def\s+\w*formaliz\w*\s*\(", CORE_SRC, re.MULTILINE | re.IGNORECASE),
)
check(
    "no core equation line cites a formalization equation id",
    not [eq_id for _, _, eq_id, _ in EQ_LINES if "FORMALIZ" in eq_id.upper()],
)

# ---------------------------------------------------------------------------
# Resolver behaviour and export shape
# ---------------------------------------------------------------------------

check("reference() resolves a known id", reference("REF-PLOS-TOD-2023").year == 2023)
check("equation() resolves a known id", equation("BEN-PKM-01").equation_id == "BEN-PKM-01")

for resolver, bad in ((reference, "REF-DOES-NOT-EXIST"), (equation, "BEN-DOES-NOT-EXIST")):
    try:
        resolver(bad)
        check(f"{resolver.__name__}() rejects an unknown id", False)
    except KeyError:
        check(f"{resolver.__name__}() rejects an unknown id", True)

eq_rows = equation_audit_rows()
check("equation audit exports one row per equation", len(eq_rows) == len(EQUATIONS))
check(
    "every audit row carries a resolvable source chain",
    all(r["method_ref_ids"] and r["source_titles"] and r["exact_source_locations"] for r in eq_rows),
)

ref_rows = reference_registry_rows()
check("reference export covers every record", len(ref_rows) == len(REFERENCES))
check("reference export carries titles and locations", all(r["title"] and r["exact_location"] for r in ref_rows))

print()
print(f"references: {len(REFERENCES)}   equations: {len(EQUATIONS)}   traceable core lines: {len(EQ_LINES)}")
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
