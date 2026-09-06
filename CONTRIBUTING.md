# Contributing to RMON

## Backend changes policy

Any backend code change must be covered by tests.

When changing backend logic:

- add new tests for new behavior;
- update existing tests for changed behavior;
- do not remove failing tests unless the tested behavior was intentionally removed;
- if a backend change does not need tests, explain why in the pull request.

## Contributor License Agreement

RMON uses a Contributor License Agreement so that contributions can be
distributed under the project's public source license and, where applicable,
under separate commercial terms.

Before a pull request can be merged, read [CLA.md](CLA.md) and accept it by
posting this exact comment on your pull request:

`/sign-cla`

Acceptance is recorded against your numeric GitHub user ID and the version of
`CLA.md` on the repository's default branch. You only need to sign once per CLA
version. A checked box or a statement in the pull request description does not
replace the signing comment.

The `CLA` status check verifies the pull request author's acceptance. If a pull
request contains contributions from other people, maintainers must also ensure
that those contributors have accepted the applicable CLA. Identify third-party
material and its license in the pull request.

Do not merge a contribution until the applicable contributors have expressly
accepted the CLA.

## Maintainer setup

The signing workflow reads `CLA.md` from the default branch. Publish the CLA and
`.github/workflows/cla.yml` there before relying on the signing workflow for
pull requests targeting `main` or `release/**`.

Configure the repository's branch protection or rulesets to require the `CLA`
status check. Adding the workflow alone does not enforce a merge restriction.

The workflow maintains a public `[CLA] Signature Registry` issue. Only signature
records written by the workflow's GitHub Actions bot are accepted. Changes to
the CLA on the default branch refresh open pull request statuses and require
contributors to accept the new version.
