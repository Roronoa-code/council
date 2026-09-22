# Post-publication CI results

Verified 2026-09-22 against implementation commit [`17cc59ed10a5d7342b210037a1f7b86e97a8a208`](https://github.com/Roronoa-code/council/commit/17cc59ed10a5d7342b210037a1f7b86e97a8a208).

[GitHub Actions run 35678608876](https://github.com/Roronoa-code/council/actions/runs/35678608876) completed its four matrix jobs successfully:

| Host / Python | Job ID | Result |
|---|---:|---|
| Windows / 3.11 | 106590370265 | Success |
| Windows / 3.13 | 106590370333 | Success |
| Ubuntu / 3.11 | 106590370403 | Success |
| Ubuntu / 3.13 | 106590370427 | Success |

Each job successfully checked out the published commit, built and installed the package, ran the offline test suite, executed a seven-stage demo from outside the checkout, resumed the completed demo, installed both native skill resource sets, and confirmed tracked files were unchanged. The Windows 3.11 log explicitly reports 62 discovered tests with one intentional Linux-only process-group test skipped, followed by successful demo/resume/installation. Windows process cancellation, timeout and Unicode subprocess tests did execute successfully.

Before publication, Git tree hashes for the package, tests, both skill directories, examples, evaluation documentation, research utility and CI configuration were compared with the locally tested source and matched exactly. The main branch was advanced without a force push.

This updates the earlier local-only Windows limitation in `03-verification.md`: Windows-native offline execution is now verified on GitHub's hosted runners. It does **not** establish authenticated live Codex/Claude execution, compatibility with the owner's particular installed CLI versions/accounts, or improved real-world decision quality. The CLI stand-ins and demo remain explicitly synthetic. No model credentials were supplied to CI and no private run artifacts were uploaded.

This documentation-only follow-up does not change the tested implementation or workflow. The implementation commit and run linked above are the exact objects to audit.
