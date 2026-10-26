# Contributing to NeoConnect

Start with the [README](README.md), [architecture](docs/introduction.md), [development structure](docs/DEVELOPMENT.md) and [changelog](CHANGELOG.md).

## Contribution workflow

1. Create a focused branch from current `main`. Describe the requested behavior, payload and compatibility impact before implementation.
2. Put changes in the locations defined in the development guide. Keep business hooks separate from generic mapping, security, audit and document controllers.
3. Export standard metadata into source. Include required data migrations, configuration changes and upgrade notes with the implementation.
4. Update the API contract, OpenAPI, sample payload and Postman assertions when API behavior changes. Update feature diagrams when responsibilities or flows change.
5. Run the relevant unit suite and staging acceptance checks. Record actual versions, commands, counts and remaining gaps; never reuse old results as evidence for a new change.
6. Review the staged diff for credentials, private customer data, runtime files, unwanted generated files and changes outside the app.
7. Open a pull request with the problem, resulting behavior, tests and upgrade impact. Merge through the repository's normal review process.

## Required release structure

- Version source: `neo_connect/__init__.py` (`__version__`). Flit reads it dynamically.
- Change history: `CHANGELOG.md`, newest release first with Added/Changed/Fixed/Removed/Breaking sections as applicable.
- Frappe highlights: `neo_connect/change_log/v<major>/v<major>_<minor>_<patch>.md`.
- Feature documentation: `docs/introduction.md`, with a table of contents, architecture and DocType diagrams, feature workflows and edge cases.
- Setup and maintenance: keep `README.md`, `docs/MAGENTO_CONFIGURATION.md`, `docs/DEVELOPMENT.md` and `docs/VERIFICATION.md` consistent.
- Upgrade notes: `docs/RELEASE_vX.Y.Z.md` for changes requiring migration or configuration review.

Use semantic versioning: MAJOR for breaking API/schema/behavior, MINOR for compatible features, PATCH for fixes. No bump for documentation-only work unless a new release is explicitly requested. Keep any future branch version in `hooks.py` aligned; none currently exists. If a version is already tagged, use the next appropriate version rather than moving its tag.

## Release checklist

- [ ] Review and group changes; choose the correct version.
- [ ] Update version, changelog, Frappe highlights, README and feature documentation.
- [ ] Document migrations, compatibility limits and customer acceptance requirements.
- [ ] Run applicable tests and record actual results.
- [ ] Stage only intended source/documentation; check `git diff --cached --check`.
- [ ] Commit with a descriptive message such as `feat(neo_connect): add ... (vX.Y.Z)`.
- [ ] Create an annotated `vX.Y.Z` tag after the release commit.
- [ ] Push branch and tag through authorized credentials; never force-push `main`.
- [ ] Verify remote branch/tag and a clean, up-to-date working tree.

Never commit SSH keys, `.env` files, site/database configuration, native User credentials, private Postman environments, raw runner exports, production payloads, database dumps or operational logs. The checked-in example is synthetic, and committed test results are sanitized. Report security issues privately to the repository maintainers rather than posting active credentials in an issue.
