# ScheduleNexus security policy

This is a **research demonstration**. It is not a hosted service with production access controls. The default local server has no multi-user authentication. API key configuration is designed for an authenticated gateway and must **not** be embedded in the public browser JavaScript. Bind to `127.0.0.1` for local demonstrations, keep GitHub Codespaces forwarded ports **private**, and do not upload proprietary customer orders, SAP data, or other sensitive information.

Supported models and request dimensions are bounded; those validation checks and local in-memory request throttling **do not replace** distributed quotas, concurrency limits, resource timeouts, reverse-proxy upload limits, gateway authentication, TLS, observability and security review. Audit metadata may store input SHA-256 digests and aggregate measurements. When hosting externally, review logging/privacy and retention design.

Report suspected vulnerabilities via GitHub private vulnerability reporting if the repository has enabled it; otherwise contact the repository owner privately rather than opening a public issue with exploitation details. Do not run active security attacks against public services without authorization.
