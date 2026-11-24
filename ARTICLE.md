# Understanding Canton and Daml: A Practical Guide to Atomic Settlement

*By Shagun Sharma. First edition, 24 November 2026. A locally tested educational experiment with synthetic assets; independent reproduction remains pending.*

How can a buyer pay for fund units without either side completing only half of the trade? In this tutorial, we exchange **100 synthetic cash for 10 synthetic fund units**, then inspect what changed and who can see it.

This guide is for developers who know basic programming but are new to Canton and Daml. You will learn to read a small contract model, run its tests, and explain successful settlement, authorization and rollback. No real money, wallet or public-network account is involved.

## 1. What Canton and Daml do here

Daml defines the contracts, their data, who authorizes actions and what those actions do. Canton runs the ledger that validates and commits those transactions. Our local environment hosts four parties on one participant: issuer, buyer, seller and outsider. A party is a ledger identity; it is not necessarily a separate node or a separate human.

The example uses a trusted issuer to create synthetic cash and fund holdings. These are teaching contracts, not legal fund shares, a stablecoin or a Token Standard implementation.

| Daml term | Meaning in this example |
|---|---|
| Template | A contract type, such as `Cash` or `FundUnit` |
| Contract | One instance: the buyer's particular cash holding |
| Contract ID | The identifier for that instance |
| Choice | An action a contract exposes, such as `TransferCash` |
| Signatory | A party whose authority is required to create the contract; signatories also authorize consequences within its choices |
| Observer | A party entitled to see the contract; visibility alone does not authorize a choice |
| Controller | A party whose authority is required to exercise a particular choice |

Signatories are stakeholders too. Transaction consequences can reveal information beyond a party's current holdings; we will return to that distinction.

## 2. Start with the trade

The issuer creates a cash holding owned by the buyer and a fund holding owned by the seller. The seller creates a proposal specifying the buyer, the fund contract ID and exact exchange terms. The buyer accepts it, supplying the cash contract ID.

```text
BEFORE                         ONE ACCEPT TRANSACTION                 AFTER
Buyer: 100 synthetic cash   ───────────────────────────────────►  Buyer: 10 fund units
Seller: 10 fund units      ───────────────────────────────────►  Seller: 100 synthetic cash
                              both transfers commit together
                              or the transaction is rejected
```

“Transfer” means consuming the old holding and creating a replacement with a new owner. It does not edit the existing contract in place. Successful acceptance consumes the proposal as well.

## 3. Read the smallest building block

This excerpt from [Settlement.daml](daml/Settlement.daml) defines the cash holding:

```daml
template Cash
  with
    issuer : Party
    owner : Party
    currency : Text
    amount : Decimal
  where
    signatory issuer
    observer owner
    ensure amount > 0.0
    choice TransferCash : ContractId Cash
      with newOwner : Party
      controller owner
      do create this with owner = newOwner
```

The issuer authorizes issuance, while the owner controls transfer. `ensure` rejects non-positive holdings. The choice is consuming by default: on successful execution, the old cash contract is replaced. The issuer remains trusted and can also archive holdings through the implicit Archive choice. This model deliberately does not enforce supply limits or recipient onboarding.

## 4. Compose the exchange

`Proposal` is signed by the seller; its `Accept` choice is controlled by the buyer. Acceptance checks the cash owner, issuer, currency and exact amount, exercises `TransferCash`, then checks and transfers the fund holding.

Why can acceptance transfer the seller's fund? The proposal supplies seller authority and acceptance supplies buyer authority to the nested choices. Within each holding's transfer, its issuer signatory supplies the authority for creating the replacement. This is an established [Daml choice-composition pattern](https://docs.digitalasset.com/build/3.4/tutorials/smart-contracts/compose.html).

The buyer must also be able to read the offered fund contract. We explicitly include the buyer in its `readers` at issuance. Our initial implementation omitted this and the happy path failed. Visibility and authority are separate requirements.

This lab requires exact quantities: a cash contract containing 101 cannot pay a price of 100. It does not combine balances, return change or support partial fills. A proposal does not reserve its assets; they can be consumed elsewhere before acceptance.

## 5. Run it yourself

Use **Daml SDK 3.4.11, its bundled Canton 3.4.11, Java 17 and Python 3.9+**. These pins reproduce the recorded experiment; they are not a claim to be the newest release. The legacy Assistant emits a deprecation warning. Follow the [README](README.md) for prerequisites and installation source links. Clean-machine installation has not yet been independently verified.

From the project root, with local ports 17601–17606 free:

```sh
python3 scripts/reproduce-local.py
```

This builds in a fresh local working directory, runs Daml Script tests, starts a fresh ledger, runs authenticated API checks and stops its own ledger. It preserves earlier evidence and creates `evidence/local-review-<UTC>/`. It reuses installed host tools and caches, so it is **same-machine reproduction**, not independent validation.

A passing run ends with:

```text
evidence/local-review-<UTC>: passed
```

Open that directory's `daml-test.txt`, `live-run.txt`, `check-evidence.txt` and `live-api.json`. The retained baseline records **7 Script tests, 99 HTTP status checks and 48 content assertions**. These are different checks, not 154 independent scenarios. A failure or skip must not be described as a pass.

For troubleshooting: ensure the exact SDK and Java are available, allow required loopback socket access, keep ports free, and inspect the failed step. Never print `.runtime/auth.conf`, tokens or authorization headers. Do not use Python optimization flags: the live harness requires assertions.

## 6. Check the result, not just a success message

For the successful exchange, inspect the `buyer receives exact fund` and `seller receives exact cash` assertions. Both parties' history refers to the same settlement update. The old holdings and proposal are consumed.

Then inspect `late fund mismatch reason` and `late fund mismatch unchanged issuer`. This scenario intentionally exercises the cash transfer before checking a wrong fund identifier. Rejection leaves the original cash and fund contract IDs and payloads unchanged. The cash movement was tentative interpreter work, not a committed debit that later needed a refund.

The suite also rejects seller acceptance without buyer authority and insufficient cash. Reusing a consumed proposal with a new command ID returns `CONTRACT_NOT_FOUND`; that does **not** establish command deduplication or reliable recovery after a lost response.

## 7. Who can see what?

| Party | Active contracts before settlement | Active contracts after settlement |
|---|---|---|
| Issuer | Cash and fund | Replacement cash and fund |
| Buyer | Cash, offered fund and proposal | Replacement fund |
| Seller | Fund and proposal | Replacement cash |
| Outsider | None of these | None of these |

These queries use separate users restricted to their own party. Two deliberately expanded cross-party queries return HTTP 403.

However, **current holdings are not the same as historical knowledge**. Both traders see both transfer consequences in transaction history. Removing extra readers from the replacement fund does not erase information already learned. The outsider sees no settlement transaction in the tested history query, but can read ledger-end offsets.

All parties share one participant. Its operator controls storage and the test signing key. This experiment does not demonstrate confidentiality against that operator, independent-participant privacy or covalidation.

## 8. A small exercise

In a separate working copy, change the malformed fund label in `lateFailureRollback` from `WRONG-FUND` to `FUND-SYN`, then run `daml test`. Predict the result first: `submitMustFail` should now complain because the trade can succeed. Restore the original label and rerun. Do not mix experimental outputs into the published baseline.

Explain in your own words: why can the seller see the proposal but not accept it? Why is the buyer listed as a fund reader? Why does rejected acceptance leave both holdings intact? What does transaction history reveal beyond the active-contract table?

## Scope, evidence and further learning

The complete [evidence register](EVIDENCE.md) maps claims to observations and exclusions. [Provenance and references](EVIDENCE.md#provenance-and-references) records dependencies and related work. OpenZeppelin already documents a broader [experimental Canton settlement engine](https://docs.openzeppelin.com/canton/settlement); our contribution is an accessible, runnable explanation, not a new settlement protocol.

The code is complete for this bounded educational experiment. Production IAM, real assets, asset reservation, lost-response recovery, multi-participant deployment, upgrades and performance studies remain outside it. Later articles can investigate these separately without implying this example already supports them.

## Author disclosures

AI tools assisted implementation, drafting and review. As of 24 November 2026, I hold no Canton Coin (CC), and no company or the Foundation has paid me for this article or project. This statement covers those confirmed facts; it makes no claim about other affiliations or interests. The work is not presented as Foundation-endorsed or independently audited. Independent clean-environment reproduction and final human review remain pending.
