# Research and data provenance

ScheduleNexus is an independent research implementation of the **Contract-First Production Scheduling** Version 7 computational artifact. Its engine is not imported from JSPLIB, and JSPLIB is not an application dependency. The research platform has two non-interchangeable tracks:

| Track | Inputs | Methods | Outcome | Applicable constraints |
|---|---|---|---|---|
| Synthetic production | Generated or explicitly supplied orders | Ready-time FIFO, SPT, EDD | Tardiness, on-time %, flow, makespan | Four named machines; material/order releases; machine outages; fixed routes |
| Classical job-shop | Six published FT/LA instances | Job-index FIFO, SPT, MWKR, ARK family | Makespan and gap to published no-setup optimum | Single capacity per machine, route precedence; no dues, release gates or outages |

Neither the synthetic production experiments nor the classical job-shop instances are actual plant data. Verification is a separate code path that shares the underlying time/resource assumptions. It establishes modeled feasibility only—not industrial suitability or the superiority of one algorithm on all problems.

## Upstream benchmark source

Benchmark collection: [JSPLIB repository](https://github.com/tamy0612/JSPLIB) maintained by the repository's respective contributors.

Original academic sources (as cited by JSPLIB):

- J. F. Muth and G. L. Thompson, *Industrial Scheduling*, Prentice-Hall, 1963. Fisher–Thompson FT06 is sometimes also called `mt06`.
- S. Lawrence, *Resource constrained project scheduling: an experimental investigation of heuristic scheduling techniques (Supplement)*, Carnegie Mellon University, 1984. LA01–LA05 are drawn from Lawrence's benchmark set.

The corresponding raw upstream paths are `instances/ft06`, `instances/la01`, … `instances/la05`. We independently compared each numeric row in ScheduleNexus `benchmarks/*.txt` with its source and found exact numeric equality (whitespace and comments excluded) on October 28, 2026. The files are bundled for offline experiment reproduction. These six datasets are **third-party data**, not original ScheduleNexus creations.

| Instance | Jobs × machines | Published no-setup optimum |
|---|---|---:|
| FT06 | 6 × 6 | 55 |
| LA01 | 10 × 5 | 666 |
| LA02 | 10 × 5 | 655 |
| LA03 | 10 × 5 | 597 |
| LA04 | 10 × 5 | 590 |
| LA05 | 10 × 5 | 593 |

The API endpoint `GET /api/research/provenance` reports each local file's SHA-256 digest, instance dimensions, original URL and reference optimum. The digest is an **integrity fingerprint**, not a license, not proof of authorship and not a checksum attested by JSPLIB.

### Rights and redistribution warning

No LICENSE file appeared in the upstream repository's root listing during the provenance check. This does **not** establish that the data are unlicensed or freely redistributable. Before selecting a software license or inviting unrestricted public redistribution, the owner should review source-specific rights and obtain appropriate permission or replace the bundled datasets with a clearly licensed alternative. Do not imply that a future software LICENSE automatically covers third-party benchmark files.

## Experiment reproducibility

For every result, record the exact repository commit SHA, environment/versions, requested model and algorithm, seed(s), search proposal budget, setup hours if used, benchmark source checksum, and exported evidence. For published comparisons, do not substitute the 500-proposal preview for the paper's 1,500-proposal ARK configuration. For statistical inference, use the separately documented multi-seed protocol rather than a one-seed screenshot.

## Claims ScheduleNexus does *not* make

- The scheduler is globally optimal except when a schedule matches a known optimum of an unchanged published instance.
- The verifier is mathematically independent of the research model.
- Synthetic outcomes generalize to real plants, SAP systems or deployed MES.
- An LLM or human-language inference system was experimentally evaluated.
- ARK parameter tuning was performed on an entirely independent benchmark set; the available history is insufficient to establish that.
- Third-party data may be redistributed under a ScheduleNexus software license without rights review.
