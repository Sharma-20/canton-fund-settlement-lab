# Claim-to-evidence register

Fresh evidence generated on 24 November 2026. Same-machine fresh-ledger run: **7 Script tests, 99 HTTP checks, 48 live assertions passed**. Exact requests, responses, offsets, contract IDs and assertions are in `evidence/live-api.json`; command output is in `evidence/live-run.txt`. Script output is separately recorded in `evidence/daml-test.txt`. The live harness checks status codes and contents, not merely whether a request completed. A fresh ledger startup and repeated harness runs on the same machine were exercised; independent clean-machine installation was not.

| Claim | Test/query | Observed result | Limitation |
|---|---|---|---|
| Exact exchange succeeds | `successfulSettlement`; live `successful settlement`, before/after snapshots | PASS: buyer's 100 cash and seller's 10 fund units consumed; new seller cash 100 and buyer fund 10; proposal consumed | Exact quantities, one synchronizer, synthetic assets |
| Seller cannot accept buyer's choice | `missingAuthority`; live `missing buyer authority` | PASS: HTTP 400 `DAML_AUTHORIZATION_ERROR`; IDs and payloads unchanged for all four queried parties | Visible proposal deliberately rules out lack of proposal visibility as the rejection cause |
| Insufficient cash rejects | `insufficientCash`; live `insufficient cash` | PASS: Script uses 99 versus price 100; live uses 100 versus price 101; HTTP 400 with `exact cash quantity required`; unchanged snapshots | No aggregate balance calculation, combining holdings, change or partial fill |
| Second-leg failure rolls back first leg | `lateFailureRollback`; live `late fund mismatch` | PASS: HTTP 400 with `fund identifier mismatch` after cash exercise in program order; both original asset IDs/payloads and proposal remain | Tentative update is interpreter execution, not a committed intermediate debit |
| Consumed proposal cannot settle again | `repeatedSettlement`; live `consumed proposal new command id` | PASS: HTTP 404 `CONTRACT_NOT_FOUND`; post-success holdings unchanged | A fresh command ID avoids relying on command deduplication; no exactly-once processing claim |
| Positive amounts required | `positiveAmounts` | PASS: zero cash and negative fund units rejected; no holdings created | Script-only check; not exhaustive numeric-boundary testing |
| Issuer, asset and exact quantities checked | `matchingTerms`, `lateFailureRollback` | PASS: wrong proposal issuer/currency/units/price and a fund from a different issuer reject; original holdings remain | Most matching tests are Script-only; not exhaustive property testing |
| Buyer/seller/outsider see modeled active contracts | `/v2/state/active-contracts`, `before` and `after` | PASS: table below | Each request is bounded at a ledger-end offset; one serial harness, no competing writers |
| Queries cannot expand a user's rights | `outsider cannot query buyer`; `buyer cannot query seller` | PASS: HTTP 403 | These cross-party controls are tested; not an exhaustive API penetration test |
| Event visibility is broader than current holdings | `settlement flats ...`, `settlement trees ...` | PASS: buyer and seller each see Accept, TransferCash, TransferFund and both creates in the same update; outsider gets no transaction | Transaction history retains information; active-contract absence is not erasure |
| Appropriate query credentials | `verify rights ...`, party-specific requests | PASS: each user has only CanActAs of its own party; no ParticipantAdmin/CanReadAsAnyParty | Harness/operator controls test identity provider and signing key |
| Dependency baseline is identified | `versions.txt`, `run.json`, build output | SDK/runtime 3.4.11; LF 2.1; protocol 34; JSON schema version 3.4.11 | Local artifact fingerprints are not independently verified publisher signatures |

## Expected and observed active-contract visibility

Expectations follow signatories and observers. Issuer sees both holdings; seller/buyer see the proposal; buyer also sees the offered fund because it is an explicit reader. After transfer, extra fund readers are empty.

| Party | Before successful exchange | After successful exchange |
|---|---|---|
| issuer | original cash, original fund | replacement cash, replacement fund |
| buyer | original cash, original fund, proposal | replacement fund |
| seller | original fund, proposal | replacement cash |
| outsider | none | none |

These are actual server-side party filters with restricted credentials. No administrator result was filtered to manufacture a privacy result. The issuer query is itself scoped to the issuer user; it is an additional party-scoped check of the complete asset set in this model.

## Events are a separate question

Both traders witness the consuming Accept and its consequences. Each sees both output creates in history even though only its own output is in its active-contract snapshot. The transaction endpoints named `flats` and `trees` in this pinned API both expose those consequences in the observed responses. Do not infer ACS-only semantics from the word “flats”: the response includes exercised events and `acsDelta=false` for non-stakeholder consequences. The command response defaults to an ACS-delta shape and is narrower. The harness asserts the actual consequence set, common update ID and party-specific witness list.

Outsider history queries bound to the successful settlement offset return an empty list. This does not prove absence of all metadata leakage: the authenticated outsider can obtain ledger-end offsets. No privacy against the operator, process owner or signing-key holder is claimed.

## Explicit exclusions and warnings

- SKIPPED / UNIMPLEMENTED: lost responses, uncertain outcomes, application idempotency, command deduplication window tests, restart reconciliation, multi-participant privacy, upgrades and regression across versions.
- NOT TESTED: clean-machine SDK installation, Linux/Windows reproduction, crash durability, production IAM/TLS, performance, supply conservation against the issuer, exhaustive numeric and authorization cases.
- Compiler warnings retained: the fixture uses a seven-element tuple; Script and templates share one small educational package, so uploading it also uploads Script dependencies. No claim of 100% choice coverage: implicit archive paths are not all exercised by Script.
- Earlier historical runs and private progress notes remain outside this minimal public package. Only the final reviewed run is included. Evidence requires a completion marker and all assertions passing.

## Review and integrity

Code review found no demonstrated settlement-model bug within this edition's scope. It found an offline reporting gap: repeated HTTP checks/assertions could replace missing rows while preserving counts, and missing party entries could bypass per-party rights verification. The checker now rejects duplicate labels, missing/unexpected roles and non-distinct party identities. Six regression tests cover valid evidence, these missing/duplicate cases, incomplete runs and corrupt assertion values; eight existing tests cover configuration protections.

The checker verifies saved result consistency, not cryptographic authenticity of ledger execution or exhaustive scenario coverage. The [Python test transcript](evidence/python-tests.txt) records 14 passing tests. [Runtime version](evidence/runtime-version.txt) and [dependency fingerprints](evidence/dependencies.json) identify the installed baseline. Source and evidence SHA-256 fingerprints are recorded in [run.json](evidence/run.json). Check the command exit codes, completion marker, individual status/error/state assertions and `ledgerStopped`; counts alone are insufficient. The Daml source and rebuilt DAR remain unchanged from the original 21 November baseline.

The original historical evidence is retained privately without modification. During 24 November review, an initial sandbox run failed to bind local sockets, and an immediate rerun after a completed run failed the port preflight with “Address already in use.” Neither is counted as passing. A subsequent fresh run completed with the reviewed scripts. Only the process group created by that runner was stopped.

## Reproducibility

The retained run used a fresh source directory, fresh credentials and fresh in-memory ledger on the same macOS arm64 machine. It reused installed SDK/Java/Python and user caches. **This is not independent reproduction.** Build and test output retain tuple and deprecated-Assistant warnings. No skipped check is counted as passing.

To verify saved results without a ledger:

```sh
python3 scripts/check-evidence.py --evidence-dir evidence
```

A clone has no private local signing key, so the exact-key scan reports **SKIPPED**. JWT-pattern scanning and evidence consistency still run. During the executed fresh run, the exact local signing-key scan ran against that run's key. A separate publication scan checked the allowlisted public files against locally retained keys and common credential patterns. Pattern scanning is not a general secret-audit guarantee.

For independent reproduction (still pending):

1. Record reviewer, date, OS/architecture, independence and preexisting tools/caches. Obtain this source repository and record its commit SHA.
2. Obtain SDK **3.4.11** from the [official release](https://github.com/digital-asset/daml/releases/tag/v3.4.11). Record the exact asset URL, digest, installation commands and any publisher signature/checksum verification actually performed. Do not silently substitute another version.
3. Install Java 17, Python 3.9+ and Bash. Record versions and warnings. No Docker, pip packages, wallet or external ledger is required.
4. Run the README's Python tests and `python3 scripts/reproduce-local.py` with ports 17601–17606 free. Retain installation transcript separately. The runner's conservative same-machine label does not itself attest independence.
5. Inspect every exit code and the seven named Daml tests, expected HTTP rejection codes, exact unchanged assets on failure, restricted rights, successful outputs and transaction visibility. Compare source/DAR fingerprints and investigate any differences.
6. Confirm the runner stopped its own ledger. Scan shareable outputs for local signing keys and JWTs; keep raw runtime logs and credentials private. Record failures, skipped checks, limitations and a reviewer verdict.

Linux/Windows installation, publisher artifact verification and independent human reproduction are untested. Human technical/editorial review and the author's spoken walkthrough remain separate steps.

## Provenance and references

Original model, harness and prose were written for this synthetic lab; no employer, client or assessment source was reused. AI assisted implementation, drafting and review. The installed SDK predates this review: local digests identify observed artifacts, not authenticated publisher provenance. No compiler, runtime binary, DAR or SDK dependency bundle is redistributed.

| Component | Pin / role | Licence and provenance |
|---|---|---|
| Daml SDK | 3.4.11; daml-prim, daml-stdlib, daml-script | [Upstream Apache-2.0 licence](https://github.com/digital-asset/daml/blob/v3.4.11/LICENSE); installed SDK NOTICES covers its transitive components |
| Canton Community | Bundled 3.4.11 runtime | [Preserved Canton licence](third-party/CANTON-LICENSE-DA.txt), extracted from the installed JAR; transitive components retain their notices |
| Ledger/API | LF 2.1, protocol 34; Ledger API v2 / JSON API 3.4.11 | Local runtime version output and API schema digest; legacy filters/tree endpoints intentionally pinned |
| Java / Python | OpenJDK 17.0.19 / Python 3.9.6 observed | Host tools, Python standard library only; respective upstream licences |

Original code and prose use the root [MIT licence](LICENSE). The preserved third-party licence retains its own terms. No OpenZeppelin code or DAR is included.

Established background and related work (descriptions reviewed for the original edition on 21 November; external pages may change):

- [Digital Asset: compose choices](https://docs.digitalasset.com/build/3.4/tutorials/smart-contracts/compose.html) explains asset swaps and delegated authorization. Atomic composition is established functionality, not a new protocol introduced here.
- [Ledger integrity](https://archived.docs.digitalasset.com/overview/3.4/explanations/ledger-model/ledger-integrity.html) explains signatory/controller authority for nested actions.
- [JWT API authentication](https://archived.docs.digitalasset.com/operate/3.4/howtos/secure/apis/jwt.html) informs the explicit test-only HMAC configuration.
- [JSON Ledger API](https://docs.digitalasset.com/build/3.4/explanations/json-api/index.html) provides API context; request shapes were also checked against the running pinned schema.
- The installed SDK's Apache-2.0 `CoinTransferWithAuthorization.daml` example was read for comparison, not copied. This smaller model deliberately omits its onboarding authorization and owner co-signature.
- [OpenZeppelin Canton settlement](https://docs.openzeppelin.com/canton/settlement) provides broader experimental multi-leg settlement tooling. This lab claims neither unique DvP tooling nor novelty in failure testing.

The contribution is a compact teaching example connecting authorization, a late rollback, exact contract equality and the difference between current holdings and transaction history. It is not a production registry, Token Standard implementation, compliance solution or independent audit.
