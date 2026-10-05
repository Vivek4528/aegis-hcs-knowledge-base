# Aegis Series-7 HCS — Architecture Report

## 1. System Overview

The Aegis KB is a claim-based retrieval system. It does **not** use an LLM at inference time. All facts are extracted offline into typed claims; queries are matched to claims by entity + predicate + text overlap scoring.

```
Query text
    │
    ▼
Entity Resolver      ← alias table (every alias cited to source doc)
    │ entities[], predicates[]
    ▼
Retrieval Engine     ← scores claims: W_entity=10, W_pred=6, W_text=1×5
    │ top_k=8 scored claims
    ▼
Gap Suppression      ← (entity, predicate) pair: gap wins only if no active claim covers same pair
    │
    ▼
Status Determination ← answered / gap / gap_false_premise / conflict / partial / not_found
    │
    ▼
Answer Synthesis     ← groups by predicate, appends version scopes, conflict notes
    │
    ▼
Evidence Collection  ← predicate-relevant, T1-T5 only, capped at 4 sources
    │
    ▼
Result dict → API → UI
```

## 2. Knowledge Base

**38 active/version_scoped claims + 5 gap claims + 5 conflict records.**

Claims have:
- `subject`: canonical entity ID (e.g. HPU, A17, PS-04A, ECN-1058)
- `predicate`: typed relation (e.g. `normal_operating_pressure`, `alarm_trigger_condition`)
- `value`: natural-language fact string
- `version_scope`: semver expression (e.g. `sw_rev >= 3.2`)
- `status`: active | version_scoped | gap | conflict | observed
- `trust_tier`: T1–T7
- `evidence[]`: source file + section + page + block_text + extraction_method + confidence

## 3. Entity Resolution

Aliases are mapped to canonical IDs. Every alias is cited to the source document that introduced it:
- "Hydraulic Power Pack" → HPU (from `manuals/operator_manual.pdf`)
- "HCS controller" → PLC-03 (from `diagrams/system_diagram_hydraulic.pdf`)
- "PS04A", "ps 04 a", "P.S.04-A" → PS-04A (from `reference/component_register.xlsx`)

**No alias is assumed** — only what appears in the 20 source files.

## 4. Version History and Conflicts

| Change | Mechanism |
|--------|-----------|
| 180 bar → 200 bar (ECN-1042, sw_rev 3.2) | Version-scoped supersession. **NOT a conflict** — different revision scopes. |
| 175 bar field note | T6 unreviewed field note. **IS a conflict** — contradicts spec with no calibrated reference. Do not adopt. |
| PS-04 → PS-04A (sw_rev 3.2) | Component replacement, also version-scoped. |
| A17 alarm text (ECN-1058) | Documentation correction only. Setpoint unchanged. |

## 5. Citation Precision Analysis

**Before fix**: avg precision 1.00 (all evidence from all claims returned — overcounted)  
**After fix**: avg precision 0.42

Reason for 0.42: the system returns up to 4 sources, but gold expected_sources for some questions include only 1-2 files. Intersection is partial.

**Fix applied**: evidence filtered to:
- Active/version_scoped claims only (conflict/observed → version_history)
- T1-T5 only (T6 field notes excluded from main evidence)
- Predicate-matched sources preferred (primary vs secondary buckets)
- Hard cap at 4 sources

**Remaining gap**: precision would improve further by capping at 2 sources. Not done to preserve recall.

## 6. Q6 — Hydraulic Schematic (AEG-DWG-H01) Analysis

The hydraulic schematic is a scanned diagram (diagrams/system_diagram_hydraulic.pdf, T3).  
Extraction method: `pdfplumber_text` + proximity-based label parsing.

**Components connected directly to HCS controller (PLC-03)**:
- PLC-03 → IV-21 (isolation valve) via purple control/signal line, wiring J-15
- PLC-03 → PS-04A (pressure transducer) via purple line, TB-7/J-14
- PLC-03 → HPU via purple control/signal line

**PLC-03 → HPU proximity artifact question**: The HPU connection is drawn as a direct control line (not a hydraulic line) in the schematic. The claim source is `wiring_diagram.pdf` (T3) which confirms the control wiring. This is **not** a proximity artifact — it is corroborated by the wiring diagram independently of the hydraulic schematic.

**TB-7**: The wiring reference "TB-7/J-14" appears in the wiring diagram as a terminal block. TB-7 is the terminal block identifier, not a component. Querying "what is TB-7" returns `partial` status — correctly identified as a wiring reference.

**Note**: AEG-DWG-H01 was not rendered to PNG during this run (no graphical PDF renderer available without system dependencies). Line endpoint analysis was performed via pdfplumber text extraction. Proximity artifact classification is therefore text-based, not visual.

## 7. OCR — Known Issues

Source: `scans/scanned_appendix_calibration.pdf` (T4, rapidocr extraction)

**Known issues (not retracted — documented here)**:
1. **Numeric concatenation**: "0.1bar", "199.4bar" appear without spaces in raw OCR output. Regex `(\d+\.?\d*)\s*(bar)` normalised to `(value, "bar")`. Values confirmed: 200 bar, 180 bar, 150 bar, 99.6% are all present and correct after normalisation.
2. **O-for-0 substitution**: Character 'O' appears in place of '0' in some scan lines (e.g. "2OO bar" → corrected to "200 bar"). Cross-checked against T1 source (operator_manual.pdf). No incorrect numeric was adopted.
3. **"HCs"**: Appears as OCR output for "HCS" (capitalisation error). Normalised to "HCS" in entity resolver. No claim was built from this raw OCR string alone.

**Status**: No values were retracted. The affected cells were cross-checked against T1/T2 sources before inclusion in any claim.

## 8. Evaluation Correctness Definition

```
overall_correct = (
    status_correct           # for gap/not_found questions
    AND key_fact_score >= 0.8  # for answered questions
)
```

Abstention is split by type:
- `not_found`: entity not in any file (4 questions)
- `false_premise`: question has a false assumption (1 question — voltage sensor)
- `gap_missing_document`: specific fact not documented (not tested separately; folded into `gap`)

## 9. What Was Not Done

- AEG-DWG-H01 graphical rendering to PNG (no system PDF renderer)
- Section 8 (bleed-down procedure) gap not surfaced in answer text (claim exists in KB, not returned for Q8)
- Citation precision target 0.7+ not achieved (actual 0.42)
- Adversarial A6, A9, A12, A14 failures not fixed (honest generalization report)
- Production WSGI deployment (Flask dev server only)
