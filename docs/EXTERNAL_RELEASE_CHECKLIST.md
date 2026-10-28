# External researcher/team release gate

**Status: NOT YET APPROVED FOR UNRESTRICTED PUBLIC SERVICE OR OPEN-SOURCE REDISTRIBUTION.**

ScheduleNexus is currently a publicly visible *source repository*, not a legally cleared open-source release and not a security-reviewed public production service. Public GitHub visibility does not grant redistribution rights or imply deployment readiness.

## Verified in the current working release

- [x] Published FT06 and LA01–LA05 numeric rows were cross-checked against upstream JSPLIB (October 28, 2026).
- [x] Research & Provenance page links to third-party sources and explains model boundaries and integrity fingerprints.
- [x] Bounded application endpoints, typed schemas, local Docker configuration, smoke tests and Python tests are included.
- [x] Separate feasibility verification is labeled accurately as sharing model assumptions.
- [x] Researcher runbook documents test scenarios, repeatability checks, exports and the difference between 500 and 1,500 ARK proposals.

## Owner approvals and engineering gates still REQUIRED

- [ ] **Third-party data rights:** establish permission to redistribute JSPLIB-derived instance files, or remove/replace them and document lawful retrieval for reproducibility.
- [ ] **Software license:** owner selects an explicit SPDX/OSI-approved license covering only software owned or licensed appropriately; add a LICENSE file and third-party notices.
- [ ] **External service identity:** implement a real authentication solution before public hosting; API-key-in-browser is not suitable for a multi-user external service.
- [ ] **Abuse controls:** reverse-proxy/body-size limits, distributed request quotas, job timeouts, cancellation and bounded concurrency; attack/load-tested externally.
- [ ] **Data privacy and retention:** publish a policy for uploaded or submitted order details, audit hashes, request/access logs, retention, abuse reporting and deletion.
- [ ] **Supply-chain security:** pinned dependencies and actions by verified digest/commit, dependency vulnerability scan, SAST and security review of deployed infrastructure.
- [ ] **Accessibility:** keyboard navigation, screen-reader review, contrast/mobile checks, verified in actual browsers.
- [ ] **Research validation:** third-party replication of exact paper inputs and data hashes; no industrial performance claims without independent plant-validation evidence.
- [ ] **Archival reproducibility:** signed/tagged release, change log, software and dataset licenses, environment lock, archive/DOI when authorized.
- [ ] **Operational readiness:** production TLS, back-up/restore testing, incident monitoring, logging, error budgets and rollback procedure.

## Allowed before completing these gates

**Controlled source review and a supervised research demonstration** on a trusted workstation or private Codespace, with no sensitive plant/customer data, subject to GitHub's access controls. Do not make the demo port public or solicit broad, unrestricted uploads. Code and data rights must still be resolved before promoting reuse or redistribution.
