# Step 5 publication preflight

Status: **APPROVED AND EXECUTED**

Date: 2026-07-18

## Scope

This is the single publication boundary declared by the Step 5 judge/scratch
preflight. It publishes only the already-validated scratch bytes. It performs
no API call, benchmark run, judge request, rerun, Sol work, or scoring change.

The publication will:

1. atomically exchange the current 1,475-link natural input directory with the
   staged 1,625-link directory containing the same 1,475 links plus the 150
   production-v3 GPT-5.6 derivative links;
2. atomically install the 1,775-row combined enriched JSONL at
   `runs/leaderboard-natural-v1-refresh-20260718.jsonl`;
3. atomically write the approved, byte-identical staged leaderboard to both
   `leaderboards/leaderboard-natural.md` and
   `leaderboards/leaderboard-natural-filtered.md`;
4. atomically write the staged two-row README update to `../README.md`;
5. rebuild from the published inputs and enriched data and require exact byte
   identity with the published leaderboard; and
6. mark the project validation/plan records published only after every check
   passes.

The production runner state and manifest remain immutable historical records.
The exact raw-to-derivative and canonical join is recorded in
`step5-validation.md` and the scratch join artifacts.

## Bound current state

Publication stops before mutation if any current value differs:

| Current artifact | Count / SHA-256 |
|---|---|
| Natural input set | 1,475 / `1bb723ef6deaf1555a210467ea8d3dd9505a1b65db639bd447cfc8a061e354d0` |
| Existing enriched JSONL | `4cf2b00c53b6defe52a69de748bfccb71d567c935ee576f332a8ebb9e994187d` |
| Natural leaderboard | `dd8d00c01adf316abe2a390fb8222b1bfdcd5df675093604dda4faff1f5e7da7` |
| Natural-filtered leaderboard | `dd8d00c01adf316abe2a390fb8222b1bfdcd5df675093604dda4faff1f5e7da7` |
| Repository README | `228137ddf123512ff10ec4d6ca03b4c665b2f6dc2afbaded0a12ad691ed2c600` |

The input-set digest is over sorted UTF-8 lines
`<link-name>\t<resolved-target>\t<target-content-sha256>\n`.
The new enriched destination and rollback-directory destination must both be
absent before publication.

## Bound staged state

| Staged artifact | Count / SHA-256 |
|---|---|
| Natural input set | 1,625 / `c8702bfd0f7c01eb778d040fafeac6a183e2c59ecd7595bd32907bcddfa00494` |
| Combined enriched JSONL | 1,775 / `c5ad6f9b8c4cc8e76b95b5391f3273d890e8e846f90d079f25f211d900b3d796` |
| Natural leaderboard | `68b26c31c967e8005d38ecf216d1f0067756e0380d5e822e27b95dc4cfe357cf` |
| Natural-filtered leaderboard | `68b26c31c967e8005d38ecf216d1f0067756e0380d5e822e27b95dc4cfe357cf` |
| Repository README | `64f595490f3360e8b9359e59c89162639dcddecce72e23cbc81a718fbf6052a7` |
| Leaderboard diff | `1a967bbb727d5907ba0812ce27a7b87f281b0b5f4540a7ed0bc34381ca08d012` |
| README diff | `1113ceb8b7bbe79d5f9896661f4f1b4a735b7e9e4088677909bcc55b01edd90b` |
| Validation record | `591de7377cbc88bcd87b82dcad02e4db0c11b26c74414aad61e8f0513628be3a` |

The staged leaderboard diff is exactly six GPT-5.6 rows plus the enriched
source update. The README diff is exactly the qualifying Terra-xhigh and
Luna-xhigh rows. The staged natural leaderboards are byte-identical.

## Atomicity and rollback

The input directories are on the same filesystem. Publication uses Linux
`renameat2(RENAME_EXCHANGE)` for a single atomic directory exchange. The old
1,475-link directory remains available until all post-publication checks pass,
then is retained—not deleted—at
`runs/leaderboard-natural-v1-input-pre-gpt56-20260718/`.

Each file is written through a same-directory temporary file, fsynced, and
installed with `os.replace`. Pre-publication copies of the two leaderboards
and README remain in scratch until validation completes. On any failure, the
worker restores those bytes and atomically exchanges the input directories
back. The existing 20260716 enriched JSONL is never deleted or overwritten.

Post-publication validation requires all bound staged hashes, 1,625 input
joins, 1,775 unique enriched paths, six distinct GPT-5.6 `N=25` groups, and a
fresh builder output byte-identical to both published natural leaderboards.

## Classification acceptance

The production leaderboard uses only production-v3 rows. Separately, the
audit-only Terra-max v5 smoke row is evaluated as coherent and
strict/lenient-success under the shared corrected report predicate, while its
immutable raw summary says `coherent_report=false`. This disclosed
post-observation policy correction does not alter any pre-existing or GPT-5.6
production leaderboard row. Publication approval accepts that audit
classification on the record; it does not mutate the raw artifact.

## Approval text

> I approve Step 5 publication exactly as documented in
> step5-publish-preflight.md, limited to atomically installing the staged
> 1,625-input set at SHA-256
> c8702bfd0f7c01eb778d040fafeac6a183e2c59ecd7595bd32907bcddfa00494,
> the combined enriched JSONL at SHA-256
> c5ad6f9b8c4cc8e76b95b5391f3273d890e8e846f90d079f25f211d900b3d796,
> both natural leaderboards at SHA-256
> 68b26c31c967e8005d38ecf216d1f0067756e0380d5e822e27b95dc4cfe357cf,
> and the README at SHA-256
> 64f595490f3360e8b9359e59c89162639dcddecce72e23cbc81a718fbf6052a7,
> with the documented validation and rollback backup. I accept the disclosed
> audit-only Terra-max v5 evaluation classification. API calls, model or judge
> runs, Sol, additional inputs, other repository-file changes, deletion of
> raw artifacts or the rollback backup, committing, pushing, and publishing
> anywhere outside this local checkout remain unauthorized.

## Execution note

Publication completed with the exact 1,625 names and contents declared above.
The original path-dependent input digest was unsuitable for directory
exchange because 53 legacy entries are regular files rather than symlinks; an
initial exchange detected the resulting self-reference and rolled back before
tracked writes. The staging correction preserved those 53 entries as regular
files and the other 1,572 as symlinks. The final relocation-stable set digest
is `ed824cda9cc86aec849ea44ca0095a48a38cbc3116055e1bf16cade8fae8aaed`.
See `step5-validation.md` for the completed publication evidence and retained
rollback-set digest.
