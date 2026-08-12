"""Acceptance tests for the source-gated scientific uncertainty engine."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import scientific_uncertainty as su

ok = True


def check(name, cond):
    global ok
    print(("PASS" if cond else "FAIL"), name)
    ok = ok and bool(cond)


# Isolate propagation mechanics from the large domain fixtures.  The production
# function still calls the real scientific domains; here we substitute a tiny
# deterministic scientific evaluator to prove path setting, provenance and gating.
su._deterministic_gate_ready = lambda params: True
su.evaluate_scientific_metrics = lambda p: {
    "metric": float(p["model"]["x"]) * 2.0,
}

base = {"model": {"x": 10.0}}
spec = su.UncertaintySpec(
    parameter_path="model.x",
    distribution="triangular",
    parameters={"left": 8.0, "mode": 10.0, "right": 12.0},
    unit="test-unit",
    source_file="uncertainty_protocol.pdf",
    source_location="Table 1",
    geography="Cairo, Egypt",
    evidence_status="PROJECT-SPECIFIC",
)

r = su.run_scientific_uncertainty(
    base,
    [spec],
    n=200,
    seed=7,
    protocol_source_file="protocol.pdf",
    protocol_source_location="Section 4.2",
    protocol_evidence_status="PROJECT-SPECIFIC",
)
check("200 samples generated", len(r.samples) == 200)
check("all evaluations valid", r.publication_gate["all_samples_valid"] is True)
check("distribution evidence ready", r.publication_gate["distribution_evidence_ready"] is True)
check("protocol ready", r.publication_gate["protocol_ready"] is True)
check("publication gate opens for fully sourced test protocol", r.publication_gate["publication_ready"] is True)
check("summary contains propagated metric", set(r.summary["metric"]) == {"metric"})
check("fixed seed reproducible",
      r.samples.equals(su.run_scientific_uncertainty(
          base, [spec], n=200, seed=7,
          protocol_source_file="protocol.pdf",
          protocol_source_location="Section 4.2",
          protocol_evidence_status="PROJECT-SPECIFIC",
      ).samples))

weak = su.UncertaintySpec(
    parameter_path="model.x",
    distribution="uniform",
    parameters={"low": 9.0, "high": 11.0},
    unit="test-unit",
    source_file="literature.pdf",
    source_location="p.1",
    geography="foreign benchmark",
    evidence_status="REF-PROXY",
)
r2 = su.run_scientific_uncertainty(
    base, [weak], n=20, seed=1,
    protocol_source_file="protocol.pdf",
    protocol_source_location="Section 4.2",
    protocol_evidence_status="PROJECT-SPECIFIC",
)
check("proxy distribution still computes", len(r2.outputs) == 20)
check("proxy distribution blocks publication", r2.publication_gate["publication_ready"] is False)
check("proxy problem named", any("publication uncertainty requires" in x for x in r2.publication_gate["open_items"]))

r3 = su.run_scientific_uncertainty(base, [spec], n=20, seed=1)
check("missing protocol blocks publication", r3.publication_gate["publication_ready"] is False)
check("protocol gap named", any("protocol" in x for x in r3.publication_gate["open_items"]))

bad_path = su.UncertaintySpec(
    parameter_path="model.missing",
    distribution="normal",
    parameters={"mean": 1.0, "sd": 0.1},
    unit="u",
    source_file="p.pdf",
    source_location="T1",
    geography="Cairo, Egypt",
    evidence_status="PROJECT-SPECIFIC",
)
r4 = su.run_scientific_uncertainty(
    base, [bad_path], n=5, seed=1,
    protocol_source_file="protocol.pdf",
    protocol_source_location="Section 4.2",
    protocol_evidence_status="PROJECT-SPECIFIC",
)
check("invalid path produces failed samples", r4.publication_gate["all_samples_valid"] is False)
check("failed samples block publication", r4.publication_gate["publication_ready"] is False)

print("\nSCIENTIFIC UNCERTAINTY TESTS PASSED" if ok else "\nSCIENTIFIC UNCERTAINTY TESTS FAILED")
sys.exit(0 if ok else 1)
