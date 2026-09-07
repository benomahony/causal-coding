from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl


class EvidenceType(StrEnum):
    RANDOMIZED_EXPERIMENT = "randomized_experiment"
    QUASI_EXPERIMENT = "quasi_experiment"
    LONGITUDINAL = "longitudinal"
    OBSERVATIONAL = "observational"
    PREDICTIVE = "predictive"
    ABLATION = "ablation"
    MECHANISTIC = "mechanistic"
    THEORETICAL = "theoretical"


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MIXED = "mixed"
    ADJACENT = "adjacent"


class Directness(StrEnum):
    DIRECT = "direct"
    MEDIATED = "mediated"
    ANALOGOUS = "analogous"


class LiteratureEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    citation: str
    year: int
    url: HttpUrl
    evidence_type: EvidenceType
    relation: EvidenceRelation
    directness: Directness
    population: str
    intervention: str | None = None
    outcome: str
    finding: str
    notes: str | None = None


LITERATURE: dict[str, LiteratureEvidence] = {
    "peng2023": LiteratureEvidence(
        id="peng2023",
        citation="Peng et al. — The Impact of AI on Developer Productivity: Evidence from GitHub Copilot",
        year=2023,
        url="https://arxiv.org/abs/2302.06590",
        evidence_type=EvidenceType.RANDOMIZED_EXPERIMENT,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="Developers recruited to implement a bounded JavaScript HTTP-server task",
        intervention="Access to GitHub Copilot",
        outcome="Task completion time",
        finding="The Copilot treatment group completed the task 55.8% faster than control.",
        notes="Bounded greenfield-style task; should not be generalized to mature repository work without moderators.",
    ),
    "metr2025": LiteratureEvidence(
        id="metr2025",
        citation="Becker et al. — Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity",
        year=2025,
        url="https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/",
        evidence_type=EvidenceType.RANDOMIZED_EXPERIMENT,
        relation=EvidenceRelation.CONTRADICTS,
        directness=Directness.DIRECT,
        population="16 experienced maintainers working on 246 real tasks in large repositories they knew well",
        intervention="AI tools allowed versus disallowed",
        outcome="Task completion time",
        finding="Developers with AI access took 19% longer in this early-2025 setting.",
        notes="Strong evidence that treatment effect depends on setting, task and tool generation.",
    ),
    "sweagent2024": LiteratureEvidence(
        id="sweagent2024",
        citation="Yang et al. — SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering",
        year=2024,
        url="https://arxiv.org/abs/2405.15793",
        evidence_type=EvidenceType.ABLATION,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="Language-model agents solving repository-level software-engineering tasks",
        intervention="Purpose-built agent-computer interface with search/edit/view tools, guardrails and concise feedback",
        outcome="Task-solving performance",
        finding="LM-centric interface design materially changed downstream software-engineering task performance.",
    ),
    "dora2025_ai": LiteratureEvidence(
        id="dora2025_ai",
        citation="DORA — 2025 State of AI-assisted Software Development",
        year=2025,
        url="https://dora.dev/research/2025/dora-report/",
        evidence_type=EvidenceType.PREDICTIVE,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.MEDIATED,
        population="Software-development professionals and organizations in the DORA survey",
        intervention=None,
        outcome="Product, delivery, team, code-quality and individual outcomes",
        finding="AI effects vary with system capabilities including small batches, internal data and platform quality.",
        notes="Repeated observational/predictive relationships, not randomized causal identification.",
    ),
    "dora_small_batches": LiteratureEvidence(
        id="dora_small_batches",
        citation="DORA — Working in small batches",
        year=2025,
        url="https://dora.dev/capabilities/working-in-small-batches/",
        evidence_type=EvidenceType.PREDICTIVE,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="Software-development teams in DORA research",
        intervention=None,
        outcome="Product performance, friction and delivery outcomes",
        finding="Small-batch practice is associated with better outcomes and moderates AI-related effects.",
    ),
    "dora_capabilities2018": LiteratureEvidence(
        id="dora_capabilities2018",
        citation="Forsgren, Humble & Kim — Accelerate: The Science of Lean Software and DevOps (DORA capability model)",
        year=2018,
        url="https://dora.dev/capabilities/",
        evidence_type=EvidenceType.PREDICTIVE,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.MEDIATED,
        population="Software delivery teams and organizations across DORA's annual State of DevOps surveys",
        intervention=None,
        outcome="Software delivery and organizational performance",
        finding="A psychometrically validated set of technical, process and cultural capabilities predicts software delivery and organizational performance.",
        notes="Measures validated capability-practice scores, not raw self-assessed skill; supports software_delivery_skill only as a mediated, practice-based proxy, not a direct test of implementation efficiency.",
    ),
    "mockus_weiss2000": LiteratureEvidence(
        id="mockus_weiss2000",
        citation="Mockus & Weiss — Predicting Risk of Software Changes",
        year=2000,
        url="https://doi.org/10.1002/bltj.2229",
        evidence_type=EvidenceType.PREDICTIVE,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="Industrial software changes",
        intervention=None,
        outcome="Probability that a change is defect-inducing",
        finding="Change diffusion and developer experience were important predictors of risky changes.",
    ),
    "kamei2012": LiteratureEvidence(
        id="kamei2012",
        citation="Kamei et al. — A Large-Scale Empirical Study of Just-in-Time Quality Assurance",
        year=2012,
        url="https://doi.org/10.1109/TSE.2012.70",
        evidence_type=EvidenceType.PREDICTIVE,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="Six open-source and five commercial software projects",
        intervention=None,
        outcome="Defect-inducing change risk",
        finding="Change size, diffusion, history and developer-experience metrics predict defect-inducing changes.",
    ),
    "google_code_review": LiteratureEvidence(
        id="google_code_review",
        citation="Sadowski et al. — Modern Code Review: A Case Study at Google",
        year=2018,
        url="https://research.google/pubs/modern-code-review-a-case-study-at-google/",
        evidence_type=EvidenceType.OBSERVATIONAL,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="Code reviews at Google",
        intervention=None,
        outcome="Review process and latency",
        finding="Change size is a key practical dimension of reviewability; smaller changes are encouraged for faster, higher-quality review.",
    ),
    "little_law": LiteratureEvidence(
        id="little_law",
        citation="Little — A Proof for the Queuing Formula L = λW",
        year=1961,
        url="https://doi.org/10.1287/opre.9.3.383",
        evidence_type=EvidenceType.THEORETICAL,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="Stable queueing systems",
        intervention=None,
        outcome="Relationship between WIP, throughput and time in system",
        finding="Under stable conditions, average WIP equals throughput multiplied by average time in system.",
    ),
    "google_build_latency": LiteratureEvidence(
        id="google_build_latency",
        citation="Jaspan & Green — Developer Productivity for Humans, Part 4: Build Latency, Predictability, and Developer Productivity",
        year=2023,
        url="https://research.google/pubs/developer-productivity-for-humans-part-4-build-latency-predictability-and-developer-productivity/",
        evidence_type=EvidenceType.OBSERVATIONAL,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="Software developers using build systems",
        intervention=None,
        outcome="Developer behavior and productivity",
        finding="Build latency and predictability affect developer behavior and productivity.",
    ),
    "gloaguen2026": LiteratureEvidence(
        id="gloaguen2026",
        citation="Gloaguen et al. — Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?",
        year=2026,
        url="https://www.sri.inf.ethz.ch/publications/gloaguen2026agentsmd",
        evidence_type=EvidenceType.OBSERVATIONAL,
        relation=EvidenceRelation.CONTRADICTS,
        directness=Directness.DIRECT,
        population="Multiple coding agents and LLMs on SWE-bench and developer-provided repository tasks",
        intervention="Repository-level context files",
        outcome="Task success and inference cost",
        finding="Context files did not improve task success and increased inference cost by over 20%; unnecessary requirements made tasks harder.",
        notes="Evidence against treating context presence/volume as monotonically beneficial; supports decomposing relevance from volume.",
    ),
    "wang2020_familiarity": LiteratureEvidence(
        id="wang2020_familiarity",
        citation="Wang et al. — Examining the effects of developer familiarity on bug fixing",
        year=2020,
        url="https://doi.org/10.1016/j.jss.2020.110667",
        evidence_type=EvidenceType.OBSERVATIONAL,
        relation=EvidenceRelation.MIXED,
        directness=Directness.DIRECT,
        population="More than 9,000 confirmed bugs across six Apache Software Foundation projects",
        intervention=None,
        outcome="Bug-fixing efficiency and effectiveness",
        finding="Familiar developers fixed bugs faster but were more likely to introduce future bugs.",
        notes="Supports a positive familiarity-to-efficiency path while warning against assuming familiarity improves quality.",
    ),
    "huang2026_ci": LiteratureEvidence(
        id="huang2026_ci",
        citation="Huang et al. — Unrelated build failures in Continuous Integration",
        year=2026,
        url="https://arxiv.org/abs/2605.05564",
        evidence_type=EvidenceType.OBSERVATIONAL,
        relation=EvidenceRelation.SUPPORTS,
        directness=Directness.DIRECT,
        population="77,354 CI build failures from seven open-source projects",
        intervention=None,
        outcome="Developer diagnostic effort",
        finding="Developers likely invested a median of four hours determining whether failures were related to their changes.",
        notes="Supports separating feedback correctness/actionability from raw execution latency.",
    ),
    "roman2021": LiteratureEvidence(
        id="roman2021",
        citation="Roman & Mnich — Test-driven development with mutation testing: an experimental study",
        year=2021,
        url="https://doi.org/10.1007/s11219-020-09534-x",
        evidence_type=EvidenceType.RANDOMIZED_EXPERIMENT,
        relation=EvidenceRelation.ADJACENT,
        directness=Directness.MEDIATED,
        population="Student developer teams implementing the same software",
        intervention="TDD with mutation testing versus TDD",
        outcome="Test effectiveness and field-defect detection",
        finding="Mutation-enhanced tests achieved higher coverage and found more defects in cross-testing.",
        notes="Supports verification effectiveness as a mechanism, not the full production change-failure path.",
    ),
}
