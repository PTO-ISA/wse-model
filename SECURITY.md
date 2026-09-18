# Security policy

wse-model is a pre-alpha architecture model. It is a design and analysis tool,
not a security boundary.

## Report a vulnerability

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/PTO-ISA/wse-model/security/advisories/new).
Include the affected revision, environment, reproduction steps, impact, and any
suggested mitigation. Do not open a public issue or pull request before the
maintainers coordinate disclosure.

The maintainers will acknowledge the report through the advisory thread,
triage its scope, and coordinate remediation and disclosure there. This policy
does not promise a fixed response or release timeline.

## In scope

- code execution or path traversal from crafted model inputs, descriptors, or
  scenario files;
- unsafe file writes or archive extraction in `tools/`;
- dependency or pinned-revision integrity failures;
- disclosure of sensitive design data through logs, traces, or reports.

## Out of scope

- model accuracy, performance-prediction error, or a missing hardware feature;
- unresolved design items from whitepaper Appendix A or Calendar §6.3.

Those follow [`CONTRIBUTING.md`](CONTRIBUTING.md). Do not use this model as a
security boundary or feed it untrusted inputs.
