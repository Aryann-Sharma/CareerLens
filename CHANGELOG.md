# Changelog

## 0.2.0 — 2026-10-31

First published release. The earlier application used the internal version
0.1.0 but had no Git tag or GitHub release. The additions below are compared
with that earlier catalog-based application at commit `f542e5e`.

### Added

- Guest analysis, with sign-in when saving a result.
- Local trained skill extraction with highlighted evidence and an editable
  skills list; local semantic matching alongside exact matching.
- An expanded catalog of 18 technologies, spelling suggestions, and handling
  for incomplete phrases and common workplace expressions.
- Job-description PDF, photo, and screenshot imports with section selection,
  the original extracted text, and an editable preview.
- Résumé PDF import and private account storage, reuse, download, replacement,
  and deletion.
- Learning guides, suggested foundations, optional learning directions,
  downloadable checklists, and saved roadmaps with progress tracking.
- Analysis deletion and saved extraction/matching evidence.
- Reproducible model training, source attribution, evaluation reports, and
  expanded API, document, account-isolation, and browser tests.

### Improved

- Responsive layouts, attachment controls, keyboard focus, and access to the
  skills editor.
- Short and coordinated skill phrases, case-insensitive spelling checks,
  explicit denials, and separation of inferred capabilities from scored skills.
- Setup, model limitations, testing, and upgrade documentation.

### Release preparation

- Set the default application version and example configuration to 0.2.0.
- Rechecked the application, installed models, document imports, migrations,
  and saved-account workflows before publishing.
- Kept candidate context and occupation classifiers outside app inference;
  their failed promotion checks remain documented.

See the [release notes](docs/releases/v0.2.0.md) for setup, upgrade instructions,
verification results, and known limits. This release does not deploy a public
demo or bundle model weights.
