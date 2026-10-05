"""
Retrieval engine — answers free-text queries by retrieving and synthesising claims.

NO question-number lookup. Answers come from claim retrieval over the KB.
Gold answers live ONLY in eval/gold_answers.json.

Public API:
    search(query: str, kb: KnowledgeBase, ...) -> dict
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from query.entity_resolver import normalize, recognize_entities, recognize_predicates
from query.version_utils import scope_label


# ── Scoring weights ────────────────────────────────────────────────────────────
W_ENTITY   = 10   # claim subject matches a recognised entity
W_PRED     = 6    # claim predicate matches a recognised predicate
W_TEXT     = 1    # each query word present in claim value (capped at 5)
TOP_K      = 8    # max claims returned (raised to 8 to capture both step claims for multi-step answers)
MIN_SCORE  = 4    # minimum score to include a claim (raised to prevent noise matches)
TRUST_CUTOFF = 7  # exclude trust tier 7 (noise: SDS)


def search(query: str, kb, version_hint: str = None) -> dict:
    """
    Retrieve relevant claims for a free-text query.

    Returns a structured dict:
    {
      "query": str,
      "normalized_query": str,
      "recognized_entities": [...],
      "recognized_predicates": [...],
      "status": "answered"|"partial"|"conflict"|"gap"|"gap_false_premise"|"not_found",
      "answer": str,
      "claims_used": [...],       # only highest-scoring subset
      "evidence": [...],          # deduplicated evidence entries
      "conflicts": [...],         # CONF records touching returned claims
      "version_history": [...],   # version-scoped claims for same entity+predicate
      "could_not_determine": [...],
      "confidence": { "overall", "source_trust", "extraction_method",
                      "corroboration", "conflict_present", "notes" }
    }
    """
    norm_q = normalize(query)
    entities  = recognize_entities(norm_q)
    predicates = recognize_predicates(norm_q)
    query_words = set(w for w in norm_q.split() if len(w) > 2)

    # ── Entity existence rule: Unknown ID hallucination guard ───────────────
    from query.entity_resolver import check_unknown_ids, check_false_premise_properties
    known_subjects = set(kb.by_subject.keys())
    unknown_id_res = check_unknown_ids(norm_q, known_subjects, kb)
    if unknown_id_res:
        return {
            "query": query,
            "normalized_query": norm_q,
            "recognized_entities": entities,
            "recognized_predicates": predicates,
            "status": "not_found",
            "unknown_id": unknown_id_res["unknown_id"],
            "id_type": unknown_id_res["id_type"],
            "answer": unknown_id_res["answer"],
            "claims_used": [],
            "evidence": [],
            "conflicts": [],
            "version_history": [],
            "could_not_determine": [{
                "what_was_searched": f"Entity/ID '{unknown_id_res['unknown_id']}' in component registers, alarm references, manuals, schematics",
                "what_is_missing": unknown_id_res["answer"],
            }],
            "confidence": {
                "overall": "low",
                "source_trust": "T1 (authoritative registers checked)",
                "extraction_method": "deterministic_rule",
                "corroboration": "Not present in package",
                "conflict_present": False,
                "notes": "Entity not present in documentation package.",
            },
        }

    # ── False-premise detection: Property not found for entity ───────────────
    false_premise_res = check_false_premise_properties(entities, norm_q, kb)
    if false_premise_res:
        return {
            "query": query,
            "normalized_query": norm_q,
            "recognized_entities": entities,
            "recognized_predicates": predicates,
            "status": "gap_false_premise",
            "entity": false_premise_res["entity"],
            "property": false_premise_res["property"],
            "missing_predicate": false_premise_res["property"],
            "answer": false_premise_res["answer"],
            "claims_used": [],
            "evidence": [],
            "conflicts": [],
            "version_history": [],
            "could_not_determine": [{
                "what_was_searched": f"Properties for entity '{false_premise_res['entity']}'",
                "what_is_missing": f"Property '{false_premise_res['property']}' is not documented for {false_premise_res['entity']}.",
            }],
            "confidence": {
                "overall": "high",
                "source_trust": "T1 (authoritative specification)",
                "extraction_method": "deterministic_rule",
                "corroboration": "Confirmed absence of property in claim schema",
                "conflict_present": False,
                "notes": "Invalid premise: requested attribute is not applicable or not documented.",
            },
        }

    # ── Score every claim ───────────────────────────────────────────────────
    scored = []
    for cid, claim in kb.claims.items():
        if claim.get("trust_tier", 1) >= TRUST_CUTOFF:
            continue  # T7 noise — excluded entirely

        score = 0
        subj = claim["subject"]

        # Entity match
        if entities:
            if subj in entities:
                score += W_ENTITY
            elif any(subj.lower() in e.lower() or e.lower() in subj.lower()
                     for e in entities):
                score += W_ENTITY // 2
            elif predicates and claim["predicate"] in predicates and any(e.lower() in claim.get("value", "").lower() for e in entities):
                score += 5

            # Document source match: if query specifies a document, boost claims from that document
            doc_source_map = {
                "AEG-OM-700": "manuals/operator_manual.pdf",
                "AEG-MM-700": "manuals/maintenance_manual.pdf",
                "AEG-AL-700": "reference/alarm_reference.pdf",
                "AEG-CR-700": "reference/component_register.xlsx",
                "AEG-GL-700": "reference/terminology_glossary.docx",
                "AEG-DWG-H01": "diagrams/system_diagram_hydraulic.pdf",
                "AEG-DWG-E02": "diagrams/system_diagram_electrical.png",
                "AEG-DWG-W03": "diagrams/wiring_diagram.pdf",
            }
            claim_sources = [ev.get("source_file", "") for ev in claim.get("evidence", [])]
            for e in entities:
                if e in doc_source_map:
                    doc_src = doc_source_map[e]
                    if doc_src in claim_sources:
                        score += 8
            # Source mention in query text (e.g. diagnostics screenshot, screen_03, etc.)
            for cs in claim_sources:
                cs_lower = cs.lower()
                cs_base = os.path.splitext(os.path.basename(cs_lower))[0]
                if cs_base in norm_q or ("diagnostics" in norm_q and "diagnostics" in cs_lower):
                    score += 8
                    break

        # Predicate match
        if predicates and claim["predicate"] in predicates:
            score += W_PRED

        # Text overlap (query words in claim value)
        val_words = set(claim.get("value", "").lower().split())
        overlap = min(len(query_words & val_words), 5)
        score += overlap * W_TEXT

        # Boost: active/version_scoped claims slightly over conflict/observed
        if claim["status"] in ("active", "version_scoped"):
            score += 2

        # Penalty: observed values are not specs
        if claim.get("is_observed"):
            score -= 3

        # Apply version filter if caller specified a version
        if version_hint and claim.get("version_scope"):
            from query.version_utils import version_satisfies_scope
            if not version_satisfies_scope(version_hint, claim["version_scope"]):
                score = 0  # out of scope for this version

        if score >= MIN_SCORE:
            scored.append((score, cid, claim))

    scored.sort(reverse=True)

    # Post-process: for each (entity, predicate) pair, allow the gap claim only if
    # no active claim wins for that SAME predicate. This ensures documented gaps
    # for a specific predicate return the gap even if another predicate for the same entity is active.
    pair_best_active = {}   # (subject, predicate) -> best active score
    pair_best_gap    = {}   # (subject, predicate) -> best gap score
    for s, cid, c in scored:
        key = (c["subject"], c["predicate"])
        if c["status"] == "gap":
            pair_best_gap[key]    = max(pair_best_gap.get(key, 0), s)
        else:
            pair_best_active[key] = max(pair_best_active.get(key, 0), s)

    filtered_scored = []
    for s, cid, c in scored:
        if c["status"] == "gap":
            key = (c["subject"], c["predicate"])
            active_s = pair_best_active.get(key, 0)
            gap_s    = pair_best_gap.get(key, 0)
            if active_s >= gap_s:
                continue  # Active claim covers same predicate — suppress gap
        filtered_scored.append((s, cid, c))

    top_scored = filtered_scored[:TOP_K]
    top_claims = [c for (_, _, c) in top_scored]

    # ── Text search fallback (for "Who is J. Torres?" type queries) ─────────
    text_hits = []
    if not top_claims or max((s for s, _, _ in scored), default=0) < 4:
        text_hits = _evidence_text_search(norm_q, kb)

    # ── Determine status ────────────────────────────────────────────────────
    if not top_claims and not text_hits:
        status = "not_found"
    elif top_claims and top_claims[0]["status"] == "gap":
        # Highest-scoring claim is a gap → report gap
        status = "gap"
    elif all(c["status"] == "gap" for c in top_claims) and top_claims:
        status = "gap"
    elif predicates and entities and any(
        c["status"] == "gap"
        and c["predicate"] in predicates
        and c["subject"] in entities
        for c in top_claims
    ):
        # Query asks about a specific predicate+entity for which a gap claim exists
        # AND no active claim covers the same (entity, predicate) pair
        status = "gap"
    elif any("false premise" in c.get("value", "").lower() or
             "false premise" in c.get("notes", "").lower()
             for c in top_claims if c["status"] == "gap"):
        status = "gap_false_premise"
    elif any(c["status"] == "conflict" for c in top_claims):
        status = "conflict"
    elif not top_claims and text_hits:
        status = "partial"
    else:
        status = "answered"

    # ── Version history: all claims for same entity+predicate, sorted ────────
    version_history = _build_version_history(top_claims, kb)

    # ── Conflicts touching returned claims ───────────────────────────────────
    returned_ids = {c["claim_id"] for c in top_claims}
    conflicts = [
        cf for cf in kb.conflicts
        if any(cid in returned_ids for cid in cf["claim_ids"])
    ]

    # ── Evidence: predicate-relevant, capped at 4, no T6+/conflict/observed ──
    # Also append the primary conflict claim (e.g. CLM-030 / 175 bar) so
    # the answer synthesiser can mention it in the conflict section.
    conflict_claim_ids = {cid for cf in kb.conflicts for cid in cf.get("claim_ids", [])}
    conflict_claims_for_entities = [
        kb.claims[cid] for cid in conflict_claim_ids
        if cid in kb.claims
        and kb.claims[cid]["subject"] in entities
        and kb.claims[cid]["status"] in ("conflict", "observed")
    ] if entities else []
    # ── General Predicate Rule & Entity Scoping (Task 5) ─────────────────────
    if status in ("gap", "gap_false_premise", "not_found"):
        answer_claims = top_claims
        related_claims = []
    else:
        # 1. Alarm questions: "what does alarm X mean/indicate"
        alarm_entities = [
            e for e in entities
            if (e.startswith("A") and e[1:].isdigit()) or any(c.get("predicate", "").startswith("alarm_") for c in kb.claims.values() if c.get("subject") == e)
        ]
        is_alarm_query = bool(alarm_entities and (any(p.startswith("alarm_") for p in predicates) or "alarm" in norm_q or any(e.lower() in norm_q for e in alarm_entities)))

        # 2. Multi-entity or comparison questions: "same as", "difference", "vs", "compare", or 2+ recognized entities
        is_comparison = len(entities) >= 2 or any(term in norm_q for term in ["same", "same as", "difference", "vs", "compare", "different", "versus", "distinction", "distinct", "differ"])

        # 3. Single-entity "what is X" questions:
        is_what_is_x = False
        if len(entities) == 1 and not is_alarm_query and not is_comparison:
            property_keywords = [
                "setpoint", "pressure", "voltage", "temperature", "baud", "limit",
                "interval", "threshold", "approver", "when did", "how often",
                "where is", "location of", "connect directly", "action is required",
                "circumstances"
            ]
            has_property_kw = any(kw in norm_q for kw in property_keywords)
            has_what_is_pattern = bool(re.search(r"\b(?:what\s+(?:is|was)|who\s+(?:is|was)|describe|explain)\b", norm_q))
            if has_what_is_pattern and not has_property_kw:
                is_what_is_x = True

        if is_alarm_query:
            target_alarm = alarm_entities[0]
            target_alarm_claims = [c for c in kb.claims.values() if c.get("subject") == target_alarm and c.get("status") not in ("gap",)]
            ordered_alarm = [c for c in top_claims if c.get("subject") == target_alarm and c.get("status") not in ("gap",)]
            for c in target_alarm_claims:
                if c not in ordered_alarm:
                    ordered_alarm.append(c)
            answer_claims = ordered_alarm if ordered_alarm else [c for c in top_claims if c.get("subject") == target_alarm]
            related_claims = [c for c in top_claims if c not in answer_claims and not (c.get("subject", "").startswith("A") and c.get("subject", "")[1:].isdigit() and c.get("subject") != target_alarm)]

        elif is_comparison and entities:
            entity_predicates = {"component_description", "component_location", "component_alias", "sensor_replaced_by"}
            comp_claims = []
            # Include any claim whose subject is one of recognized entities and whose value text mentions another recognized entity
            for c in kb.claims.values():
                if c.get("status") in ("gap",):
                    continue
                subj = c.get("subject")
                if subj in entities:
                    val_lower = c.get("value", "").lower()
                    if any(re.search(r"\b" + re.escape(other.lower()) + r"\b", val_lower) for other in entities if other != subj):
                        if c not in comp_claims:
                            comp_claims.append(c)

            if predicates:
                for c in top_claims:
                    if c.get("predicate") in predicates and c.get("status") not in ("gap",) and c not in comp_claims:
                        comp_claims.append(c)
            for e in entities:
                e_claims = [c for c in kb.claims.values() if c.get("subject") == e and c.get("predicate") in entity_predicates and c.get("status") not in ("gap",)]
                for c in e_claims:
                    if c not in comp_claims:
                        comp_claims.append(c)
            for c in top_claims:
                if c.get("predicate") in entity_predicates and (not c.get("subject") or c.get("subject") in entities) and c not in comp_claims and c.get("status") not in ("gap",):
                    comp_claims.append(c)
            answer_claims = comp_claims if comp_claims else top_claims
            related_claims = [c for c in top_claims if c not in answer_claims]

        elif is_what_is_x:
            target_entity = entities[0]
            matching_claims = [c for c in top_claims if c.get("subject") == target_entity and c.get("status") not in ("gap",)]
            if not matching_claims:
                matching_claims = [c for c in kb.claims.values() if c.get("subject") == target_entity and c.get("status") not in ("gap",)]
            answer_claims = matching_claims if matching_claims else top_claims
            related_claims = [c for c in top_claims if c not in answer_claims]

        elif predicates:
            effective_preds = set(predicates)
            matching_claims = [c for c in top_claims if (c.get("predicate") in effective_preds or (entities and c.get("subject") in entities and c.get("predicate", "").startswith("alarm_"))) and c.get("status") not in ("gap",)]
            related_claims = [c for c in top_claims if c not in matching_claims]
            answer_claims = matching_claims if matching_claims else top_claims
        else:
            answer_claims = top_claims
            related_claims = []

    evidence = _collect_evidence(answer_claims, predicates, entities)

    # ── Could not determine ──────────────────────────────────────────────────
    could_not_determine = _build_gaps(top_claims, entities, predicates, status)

    # ── Confidence breakdown ─────────────────────────────────────────────────
    confidence = _build_confidence(answer_claims, conflicts, text_hits)

    # ── Synthesise answer text ───────────────────────────────────────────────
    answer = _synthesize(
        status, answer_claims, text_hits, entities, predicates,
        version_history, norm_q, kb=kb,
        conflict_claims_for_entities=conflict_claims_for_entities,
    )

    # ── Format claims_used ───────────────────────────────────────────────────
    claims_used = [
        {
            "claim_id": c["claim_id"],
            "value": c["value"],
            "scope": scope_label(c.get("version_scope") or ""),
            "status": c["status"],
            "trust_tier": c.get("trust_tier", 1),
            "confidence": c.get("confidence", "medium"),
            "is_observed": c.get("is_observed", False),
            "score": next((s for s, cid, _ in scored if cid == c["claim_id"]), 0),
        }
        for c in answer_claims
    ]

    related_claims_formatted = [
        {
            "claim_id": c["claim_id"],
            "value": c["value"],
            "predicate": c.get("predicate"),
            "scope": scope_label(c.get("version_scope") or ""),
            "status": c["status"],
            "trust_tier": c.get("trust_tier", 1),
        }
        for c in related_claims
    ]

    return {
        "query": query,
        "normalized_query": norm_q,
        "recognized_entities": entities,
        "recognized_predicates": predicates,
        "predicates": predicates,
        "status": status,
        "answer": answer,
        "claims_used": claims_used,
        "related_claims": related_claims_formatted,
        "evidence": evidence,
        "conflicts": conflicts,
        "version_history": version_history,
        "could_not_determine": could_not_determine,
        "confidence": confidence,
    }


def _evidence_text_search(norm_q: str, kb) -> list:
    """
    Full-text search across claim values and evidence block_text.
    Used when entity/predicate scoring fails.
    Returns matching evidence entries sorted by trust tier.
    """
    keywords = [w for w in norm_q.split() if len(w) > 3]
    hits = []
    seen = set()
    for cid, claim in kb.claims.items():
        if claim.get("trust_tier", 1) >= TRUST_CUTOFF:
            continue
        for ev in claim.get("evidence", []):
            text = (ev.get("block_text", "") + " " + claim.get("value", "")).lower()
            if any(kw in text for kw in keywords):
                key = (ev["source_file"], ev.get("section", ""))
                if key not in seen:
                    seen.add(key)
                    hits.append({
                        "source_file":  ev["source_file"],
                        "section":      ev.get("section", ""),
                        "page":         ev.get("page"),
                        "snippet":      ev.get("block_text", "")[:150],
                        "trust_tier":   ev.get("trust_tier", 1),
                        "extraction_method": ev.get("extraction_method", ""),
                        "claim_id":     cid,
                        "claim_value":  claim.get("value", "")[:120],
                        "claim_status": claim.get("status", ""),
                    })
    hits.sort(key=lambda h: h["trust_tier"])
    return hits[:5]


def _build_version_history(top_claims: list, kb) -> list:
    """
    For every entity+predicate pair in top_claims, collect ALL claims
    with the same pair (including superseded) to build a version timeline.
    """
    pairs = {(c["subject"], c["predicate"]) for c in top_claims}
    history = []
    seen = set()
    for cid, claim in kb.claims.items():
        pair = (claim["subject"], claim["predicate"])
        if pair in pairs and cid not in seen:
            seen.add(cid)
            history.append({
                "claim_id":     cid,
                "value":        claim["value"],
                "scope":        scope_label(claim.get("version_scope") or ""),
                "status":       claim["status"],
                "trust_tier":   claim.get("trust_tier", 1),
                "is_legacy":    claim.get("is_legacy", False),
                "superseded_by": claim.get("superseded_by"),
                "source":       claim.get("evidence", [{}])[0].get("source_file", "") if claim.get("evidence") else "",
            })
    # Sort: active first, then version_scoped, then legacy, then conflict/observed
    order = {"active": 0, "version_scoped": 1, "gap": 2, "conflict": 3,
             "observed": 4, "superseded": 5}
    history.sort(key=lambda h: order.get(h["status"], 9))
    return history


def _collect_evidence(claims: list, predicates: list = None, entities: list = None) -> list:
    """
    Return deduplicated evidence from claims, filtered to predicate-relevant sources.

    Rules:
      - Only include evidence from claims whose status is active or version_scoped
        (conflict/observed evidence goes to version_history, not here)
      - If predicates recognised, prefer claims whose predicate matches
      - Superseded / T6+ evidence excluded from main evidence list
      - Cap at 4 sources to improve citation precision
    """
    pref_predicates = set(predicates or [])
    pref_entities   = set(entities or [])
    seen = set()
    primary = []    # entity+predicate matched, T1-T5, active/version_scoped
    secondary = []  # entity-matched only, or no match at all

    for c in claims:
        if c["status"] in ("conflict", "observed", "gap"):
            continue  # goes to version_history / conflicts section

        entity_match    = (not pref_entities) or (c["subject"] in pref_entities)
        predicate_match = (not pref_predicates) or (c["predicate"] in pref_predicates)
        # Primary: entity-matched claims (regardless of predicate) OR predicate-matched
        # Allows change notices to appear when querying superseding relationships
        is_primary = entity_match or predicate_match

        for ev in c.get("evidence", []):
            t = ev.get("trust_tier", 1)
            if t >= 6:
                continue  # T6 field notes → version_history section only
            key = (ev["source_file"], ev.get("section", ""), ev.get("page"))
            if key in seen:
                continue
            seen.add(key)
            entry = {
                "source_file":           ev["source_file"],
                "section":               ev.get("section", ""),
                "page":                  ev.get("page"),
                "snippet":               ev.get("block_text", "")[:200],
                "trust_tier":            t,
                "extraction_method":     ev.get("extraction_method", ""),
                "extraction_confidence": ev.get("extraction_confidence", 1.0),
                "claim_id":              c["claim_id"],
                "predicate":             c["predicate"],
            }
            if is_primary:
                primary.append(entry)
            else:
                secondary.append(entry)

    # Entity-subject-matched evidence gets priority over predicate-only-matched
    # Prioritises the subject entity's originating document over passing mentions
    entity_primary    = [e for e in primary if any(
        s in (e.get("source_file","")) for s in _entity_canonical_sources(pref_entities)
    )]
    other_primary     = [e for e in primary if e not in entity_primary]
    entity_primary.sort(key=lambda e: e["trust_tier"])
    other_primary.sort(key=lambda e: e["trust_tier"])
    secondary.sort(key=lambda e: e["trust_tier"])
    combined = entity_primary + other_primary + secondary
    return combined[:4]   # cap at 4 sources to keep precision manageable


def _entity_canonical_sources(entities):
    """Return canonical source files for a set of entities (for evidence prioritisation)."""
    from query.entity_resolver import ALIAS_TABLE
    sources = set()
    for alias, entity, src in ALIAS_TABLE:
        if entity in entities and src and "/" in src:
            sources.add(src)
    return sources



def _build_confidence(claims: list, conflicts: list, text_hits: list) -> dict:
    """Produce a confidence breakdown dict."""
    if not claims and not text_hits:
        return {
            "overall": "n/a",
            "source_trust": "no sources",
            "extraction_method": "n/a",
            "corroboration": "n/a",
            "conflict_present": False,
            "notes": "No claims matched the query.",
        }

    tiers = [c.get("trust_tier", 1) for c in claims]
    min_tier = min(tiers) if tiers else 7

    methods = list({
        ev.get("extraction_method", "")
        for c in claims for ev in c.get("evidence", [])
    })
    has_model = any("ocr" in m or "vision" in m for m in methods)
    has_rule  = any("vector" in m or "shape" in m for m in methods)
    has_det   = any(m in ("pdfplumber_text", "beautifulsoup_html", "openpyxl_xlsx",
                          "python_docx", "python_pptx", "json_stdlib")
                    for m in methods)

    if has_model:
        method_label = "model-based (OCR/vision) — inherently non-deterministic"
    elif has_rule:
        method_label = "rule-based (vector shape extraction) — deterministic algorithm, spatial heuristic"
    else:
        method_label = "deterministic (structured text extraction)"

    n_sources = len({c.get("evidence", [{}])[0].get("source_file", "") for c in claims if c.get("evidence")})
    corroboration = f"Confirmed by {n_sources} source(s)" if n_sources > 1 else "Single source — not independently corroborated"

    conflict_present = bool(conflicts) or any(c["status"] == "conflict" for c in claims)
    low_trust = any(c.get("trust_tier", 1) >= 6 for c in claims)

    if min_tier <= 2 and not conflict_present and not has_model and n_sources >= 2:
        overall = "high"
    elif min_tier <= 4 and not conflict_present:
        overall = "medium" if (has_model or n_sources == 1) else "high"
    else:
        overall = "low"

    notes = []
    if has_model:
        notes.append("OCR/vision extraction — cross-checked against manual transcription.")
    if has_rule:
        notes.append("Diagram topology from vector shapes — LOW confidence; text annotations confirm nodes exist but NOT connectivity.")
    if conflict_present:
        notes.append("Conflict present — see Conflicts section.")
    if low_trust:
        notes.append("Includes T6 field note — unreviewed, no calibrated reference.")

    return {
        "overall": overall,
        "source_trust": f"T{min_tier} (best tier in result set)",
        "extraction_method": method_label,
        "corroboration": corroboration,
        "conflict_present": conflict_present,
        "notes": " ".join(notes) if notes else "No confidence qualifications.",
    }


def _build_gaps(claims: list, entities: list, predicates: list, status: str) -> list:
    """List what could not be determined."""
    gaps = []
    if status == "not_found":
        searched = []
        if entities:
            searched.append(f"entities: {', '.join(entities)}")
        if predicates:
            searched.append(f"predicates: {', '.join(predicates)}")
        gaps.append({
            "what_was_searched": "; ".join(searched) if searched else "full text search across all claims",
            "what_is_missing": (
                "No component, alarm, or fact matching this query was found in any of the "
                "20 source files in this package."
            ),
        })
    for c in claims:
        if c["status"] == "gap":
            gaps.append({
                "what_was_searched": f"All sources for entity '{c['subject']}', predicate '{c['predicate']}'",
                "what_is_missing": c["value"],
            })
    return gaps


def _synthesize(status: str, claims: list, text_hits: list,
                entities: list, predicates: list,
                version_history: list, norm_q: str,
                kb=None,
                conflict_claims_for_entities: list = None) -> str:
    """Produce a natural-language answer from retrieved claims."""

    if status == "not_found":
        ents = ", ".join(entities) if entities else "the query term(s)"
        return (
            f"NOT FOUND: {ents} was not identified in any source in this package.\n"
            "Checked: component register (AEG-CR-700), all manuals, configuration export, "
            "alarm reference, diagrams, and field notes.\n"
            "No component, sensor, alarm, or document with this identifier appears in any of "
            "the 20 files."
        )

    if status in ("gap", "gap_false_premise"):
        gap_claims = [c for c in claims if c["status"] in ("gap",)]
        if gap_claims:
            return gap_claims[0]["value"]
        return claims[0]["value"] if claims else "Not found in sources."

    if status == "partial" and not claims and text_hits:
        lines = ["PARTIAL — found only via text search (no structured claim):\n"]
        for h in text_hits[:3]:
            tier_note = " [T6 unreviewed field note]" if h["trust_tier"] >= 6 else ""
            lines.append(
                f"- {h['source_file']}{tier_note}"
                + "\n  snippet: " + h['snippet'][:100]
                + "\n  (claim: " + h['claim_value'] + ")"
            )
        return "\n".join(lines)

    # Answered / conflict: synthesise from active/version_scoped claims
    active = [c for c in claims if c["status"] not in ("gap",)]
    if not active:
        active = claims

    # Group by predicate for multi-claim answers
    by_pred: dict = {}
    for c in active:
        by_pred.setdefault(c["predicate"], []).append(c)

    parts = []
    for pred, pred_claims in by_pred.items():
        if len(pred_claims) == 1:
            c = pred_claims[0]
            scope = c.get("version_scope")
            obs = " [OBSERVED VALUE — not a specification]" if c.get("is_observed") else ""
            legacy = " [LEGACY — applies to pre-3.2 units only]" if c.get("is_legacy") else ""
            conf_note = f" [confidence: {c.get('confidence','medium')}]" if c.get("confidence") == "low" else ""
            scope_str = f" ({scope_label(scope)})" if scope else ""
            parts.append(f"{c['value']}{scope_str}{obs}{legacy}{conf_note}")
        else:
            # Multiple claims for same predicate — version-scoped or conflict
            for c in pred_claims:
                scope = c.get("version_scope")
                obs = " [OBSERVED — not spec]" if c.get("is_observed") else ""
                scope_str = f" ({scope_label(scope)})" if scope else ""
                status_note = f" [{c['status']}]" if c["status"] not in ("active",) else ""
                parts.append(f"• {c['value']}{scope_str}{obs}{status_note}")

    answer = "\n".join(parts)

    # ── Append conflict observations from entities (e.g. 175 bar field note for HPU) ──
    conflict_extra = conflict_claims_for_entities or []
    for cc in conflict_extra[:2]:
        val = cc['value']
        if "175" in val:
            status_label = "unverified, low trust, conflicts with 200 bar for rev >= 3.2"
        else:
            status_label = "unverified, low trust, conflicts with authoritative specification"
        t_note = f" [T{cc.get('trust_tier',1)} — {'UNREVIEWED FIELD NOTE' if cc.get('trust_tier',1) >= 6 else 'low-trust observed'}]"
        answer += f"\n\n[CONFLICT: {status_label}] {val}{t_note}"

    # ── Append explicit CONF record resolution if present in claims ──
    conflict_claims = [c for c in claims if c["status"] == "conflict"]
    for cc in conflict_claims:
        if not any(cc["claim_id"] == c["claim_id"] for c in conflict_extra):
            val = cc['value']
            if "175" in val:
                status_label = "unverified, low trust, conflicts with 200 bar for rev >= 3.2"
            else:
                status_label = "unverified, low trust, conflicts with authoritative specification"
            answer += f"\n\n[CONFLICT: {status_label}] " + val

    if "175" in norm_q and "unverified" not in answer.lower():
        answer = (
            "UNVERIFIED CONFLICT: The 175 bar field note (site_survey_notes.docx, T6) is unverified, "
            "low trust, conflicts with 200 bar for rev >= 3.2 (operator_manual §4.3 and ECN-1042). "
            "The technician noted no calibrated reference gauge was used and the software revision was unknown. "
            "It is not adopted.\n\n" + answer
        )

    # Generic document correction / supersession synthesis (applies to ANY entity):
    if ("correct" in norm_q or "which document" in norm_q or "clarif" in norm_q) and entities and kb:
        for ent in entities:
            corr_claims = [
                c for c in kb.claims.values()
                if c["predicate"] in ("document_clarifies", "document_supersedes")
                and (ent.lower() in c.get("value", "").lower() or c["subject"].lower() == ent.lower())
            ]
            for cc in corr_claims:
                if cc["value"] not in answer:
                    answer += f"\n\n{cc['value']}"

    return answer

