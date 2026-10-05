# Aegis Series-7 HCS — Knowledge Base

> **Two accuracy numbers — read both before citing either one.**
>
> | Label | Score | Questions |
> |-------|-------|-----------|
> | **Development-set accuracy** | **23/23 (100%)** — status + fact ≥ 0.8 + citation recall > 0 | 23 questions written during development (gold answers tuned alongside system) |
> | **Held-out accuracy — Set 1** | **10/15 (67%)** | 15 unseen adversarial questions, frozen, NOT tuned after |
> | **Held-out accuracy — Set 2** | **11/15 (73%)** | 15 new unseen questions (different authors), NOT tuned after |

---

## Architecture

```mermaid
flowchart LR
    A[Query text] --> B[Entity Resolver]
    B -->|canonical IDs + predicates| C[Claim Scorer]
    C -->|top-K scored claims| D[Gap Suppression]
    D -->|entity+predicate keyed| E[Status Determination]
    E --> F[Answer Synthesis]
    F --> G[Evidence Collection]
    G -->|entity-canonical sources first| H[Result dict]
    H --> I[API /api/search]
    I --> J[UI result card]
```

### Schema

| Layer | Description |
|-------|-------------|
| **Source** | One of 20 files, trust tier T1-T7, extraction method |
| **Entity** | Canonical ID (HPU, PS-04A, A17, ECN-1042…) |
| **Claim** | `{subject, predicate, value, version_scope, status, trust_tier, evidence[]}` |
| **Evidence** | `{source_file, section, page, block_text, trust_tier, extraction_method, confidence}` |
| **Trust tiers** | T1=manuals, T2=ECN bulletins, T3=config, T4=component register, T5=slides/screenshots, T6=field notes (unreviewed), T7=noise/SDS |

### Pipeline steps

| Step | Method | Reason |
|------|--------|--------|
| PDF text extraction | **Rule-based** (pdfplumber) | Deterministic layout parsing |
| Scanned PDF OCR | **Model-based** (RapidOCR) | Requires vision model |
| HTML/JSON/XLSX parse | **Rule-based** | Format is structured |
| PPTX extract | **Rule-based** (python-pptx) | Slide DOM traversal |
| Diagram line extraction | **Model-based** (PyMuPDF vector shapes) | Requires visual parsing |
| Entity resolution | **Rule-based** (alias table) | All aliases cited to source doc |
| Claim scoring | **Rule-based** (weighted scoring) | W_entity=10, W_pred=6, W_text=1×5 |
| Gap suppression | **Rule-based** (entity+predicate keyed) | No question-number logic |
| Answer synthesis | **Rule-based** (string join + version notes) | No LLM at inference time |

---

## Entity Resolution Decisions

All aliases are cited to the source document that first uses them.

| Alias | Canonical | Source |
|-------|-----------|--------|
| "Hydraulic Power Unit", "HP unit" | HPU | `manuals/operator_manual.pdf` |
| "PS04A", "P.S.04-A", "ps 04 a" | PS-04A | `reference/component_register.xlsx` |
| "HCS controller", "aegis controller" | PLC-03 | `component_register.xlsx` |
| "engineering change notice 1042" | ECN-1042 | `engineering_bulletins/ECN-1042.pdf` |
| "training slide", "slide deck" | training_slides | `extra/training_slide_excerpt.pptx` |

**PS-04 vs PS-04A vs PS-40 vs P.S.04-A:**
- PS-04 = original sensor (pre sw_rev 3.2). Legacy, replaced by ECN-1042.
- PS-04A = replacement sensor (sw_rev ≥ 3.2). Active spec.
- PS-40 = coolant loop sensor on Skid B. **Different circuit entirely.**
- P.S.04-A = physical unit label format of PS-04A. Observed on diagnostics screen.

**ECN-1042 vs ECN-1058:**
- ECN-1042: Changes PS-04→PS-04A, 180→200 bar. **Version-scoped supersession** (not a conflict).
- ECN-1058: Corrects A17 alarm text description only. **Does NOT change setpoint, does NOT supersede ECN-1042.**

**180 bar → 200 bar:**
Version-scoped supersession. 180 bar applies to sw_rev < 3.2. 200 bar applies to sw_rev ≥ 3.2. NOT a conflict — different revision scopes.

**175 bar field note (CLM-030):**
The ONLY real conflict. T6 unreviewed field note contradicts T1 spec. Do not adopt. Appears in "Version history / Conflicts" section only.

---

## What Was NOT Done and Why

| Item | Status | Reason |
|------|--------|--------|
| Citation precision ≥ 0.7 | **0.44** | Cap at 4 sources; some gold sources are secondary |
| A99 alarm → not_found | **Returns `answered`** (false positive) | Text overlap with A17 causes incorrect match |
| KA1 → not_found | **Returns `partial`** | TB-7 wiring references score above not_found threshold |
| "175 bar field note correct?" → "unverified" | **Not in answer string** | Answer states field note conflicts but doesn't say "unverified" |
| "Reset time for A17 after 200 bar" → not_found | **Returns answered** | False premise (no such reset time) not caught; A17 claim matches |
| "Which doc corrected A17?" → ECN-1058 | **ECN-1058 not in answer string** | CLM for ECN-1058 has `document_clarifies` predicate, not returned for this phrasing |
| PLC-03→HPU confirmation | **LOW confidence** | IV-21/PS-04A drawn inside HPU box in diagram; wiring diagram has no HPU |
| Section 8 bleed procedure | **Gap documented** | Not in package; mentioned in Q8 notes but not in answer text |
| Production WSGI | **Dev server only** | Flask dev server used |
| PDF of architecture_report | **Markdown only** | No headless Chrome/Pandoc in environment |

---

## Per-File Confidence Table

| File | Trust | Extraction | Confidence |
|------|-------|-----------|------------|
| operator_manual.pdf | T1 | pdfplumber | 0.95 |
| maintenance_manual.pdf | T1 | pdfplumber | 0.95 |
| legacy_manual_v1.html | T1 | bs4 | 0.90 |
| ECN-1042.pdf | T2 | pdfplumber | 0.95 |
| ECN-1058.pdf | T2 | pdfplumber | 0.95 |
| configuration_export.json | T3 | json.load | 1.00 |
| component_register.xlsx | T4 | openpyxl | 0.98 |
| revision_history.xlsx | T4 | openpyxl | 0.98 |
| alarm_reference.pdf | T4 | pdfplumber | 0.92 |
| system_diagram_hydraulic.pdf | T3 | PyMuPDF vector | 0.50 (shape-derived) |
| wiring_diagram.pdf | T3 | PyMuPDF vector | 0.50 (shape-derived) |
| training_slide_excerpt.pptx | T5 | python-pptx | 0.95 |
| screen_0[1-3].png | T5 | manual annotation | 0.90 |
| scanned_appendix_calibration.pdf | T4 | RapidOCR | 0.85 (numeric corrected) |
| site_survey_notes.docx | T6 | python-docx | 0.95 (LOW trust content) |
| safety_data_sheet_*.pdf | T7 | excluded | — |

---

## Q6 Diagram Analysis (AEG-DWG-H01, AEG-DWG-W03)

Rendered to PNG at 200 DPI using PyMuPDF (`docs/figures/`). 37 line segments extracted from H01, 29 from W03.

**H01 component text block**: `"(HPU) PS-04A IV-21"` at bbox=(114,314,457,333) — PS-04A and IV-21 are labelled **inside** the HPU bounding box.

**Verdict**: PLC-03 → HPU is a **proximity artifact risk** (LOW confidence). The purple control lines from PLC-03 terminate at IV-21 (J-15) and PS-04A (TB-7/J-14), which happen to be inside the HPU box. There is no separate HPU terminus.

W03 (wiring diagram) contains **no HPU component** → cannot corroborate PLC-03→HPU. Corroborated edges: PLC-03→IV-21 (J-15), PLC-03→PS-04A (TB-7/J-14).

---

## OCR Known Issues (Retracted "No Errors" Claim)

Raw OCR of `scans/scanned_appendix_calibration.pdf` contains:
- **Numeric concatenation**: "0.1bar", "199.4bar" (no space). Fixed by regex `(\d+\.?\d*)(?:bar|Bar|BAR)`.
- **O-for-0 substitution**: "2OObar" → corrected to "200 bar" in numeric context only.
- **"HCs"**: OCR for "HCS" (capitalisation). Normalised to "HCS" via `re.sub(r'HCs\b','HCS',text)`.

Values confirmed in scan after correction: **200, 180, 99.6, 199.4, 2026-01-09**.

---

## Running the System

```bash
pip install -r requirements.txt
python api/server.py          # Open http://localhost:5000
python eval/evaluator.py      # Development-set evaluation (23 q)
python adversarial_new.py     # Held-out set 1 (15 q, frozen)
python adversarial_set2.py    # Held-out set 2 (15 q, frozen)
python ablation.py            # Ablation study
python render_diagrams.py     # Render AEG-DWG-H01 and W03 to PNG
python ocr_fix.py             # OCR numeric fix tests
python -m pytest tests/ -v    # 59 unit tests
```

**Windows**: `run.bat serve` | `run.bat eval` | `run.bat test`  
**Unix/Mac**: `./run.sh serve` | `./run.sh eval` | `./run.sh test`

> This system runs entirely **deterministically** — no LLM at inference time. All facts are extracted offline into `extract/gold_claims.py`.

---

## Development-Set Eval Table (All 23 Questions)

```
Q   Expected           Got                OK  Facts   CiteP  CiteR
1   answered           answered           YES  1.00    —      —
2   answered           answered           YES  1.00    —      —
3   answered           answered           YES  1.00    —      —
4   answered           answered           YES  1.00    —      —
5   answered           answered           YES  1.00    —      —
6   answered           answered           YES  1.00    —      —
7   answered           answered           YES  0.80  (borderline; 'isolation' missing)
8   answered           answered           YES  1.00    —      —
9   answered           answered           YES  1.00    —      —
10  answered           answered           YES  1.00    —      —
11  answered           answered           YES  1.00    —      —
12  answered           answered           YES  1.00    —      —
13  answered           answered           YES  1.00    —      —
14  answered           answered           YES  0.83  ('180 bar' missing from answer)
15  answered           answered           YES  1.00    —      —
16  answered           answered           YES  1.00    —      —
17  answered           answered           YES  1.00    —      —
18  answered           answered           YES  1.00    —      —
19  not_found          gap                YES  n/a     n/a    n/a
20  gap_false_premise  gap_false_premise  YES  n/a     n/a    n/a
21  not_found          gap                YES  n/a     n/a    n/a
22  not_found          gap                YES  n/a     n/a    n/a
23  not_found          gap                YES  n/a     n/a    n/a

Overall: 23/23 (100.0%)  | Status: 23/23 | Fact avg: 0.89
CitPrec: 0.44            | CitRecall: 0.78
Abstention not_found: 4/4 | false_premise: 1/1 | gap_missing_doc: 0/0
```

> **Caution**: Gold answers were written during development. Development-set accuracy is not the system's generalisation accuracy. See held-out sets above.
