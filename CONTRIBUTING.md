# Contributing to ScheduleNexus

ScheduleNexus is undergoing licensing and benchmark-data rights review. **Public GitHub visibility alone is not an open-source license.** Contact the repository owner before contributing code or submitting artifacts for potential redistribution.

When preparing an issue or authorized pull request:

1. Clearly label whether a finding concerns the synthetic production model or the classical job-shop track.
2. Describe a minimal reproducible example, seed, algorithm, search proposal budget, input data source and actual versus expected results.
3. Include an automated regression test for every behavior change. Run `python -m pytest -q` locally.
4. Preserve data provenance and distinguish modeled feasibility from optimality. Do not introduce AI/LLM or industrial accuracy claims without corresponding empirical evidence.
5. Do not upload sensitive business data or third-party code/datasets without documented permission.

Refer to `docs/RESEARCHER_GUIDE.md` and `docs/RESEARCH_PROVENANCE.md` for more detail.
