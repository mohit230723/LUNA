"""Context graph builder orchestrating parsing, mapping, extraction, resolution, and loading."""

from __future__ import annotations

import concurrent.futures
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from luna.cases.store import CaseStore, CASE_DATA_ROOT
from luna.graph.store import GraphStore
from luna.ingest.extract import extract_chunk
from luna.ingest.loader import load_context_graph, sanitize_label, sanitize_rel
from luna.ingest.mapper import plan_table_mapping
from luna.ingest.models import ExtractionStats, ExtractedEntity, ExtractedRelation
from luna.ingest.parsers import parse_source_file, TableData
from luna.ingest.resolve import resolve_entities_and_relations, ResolvedNode, ResolvedEdge
from luna.ingest.summary import compute_graph_summary
from luna.llm.client import LLMClient


def build_context_graph(
    conversation_id: str,
    case_store: CaseStore,
    graph_store: GraphStore,
    llm: LLMClient,
    emit: Callable[[str, dict[str, Any]], None],
    is_cancelled: Callable[[], bool],
) -> dict[str, Any]:
    """Execute complete context graph build pipeline for a Case."""
    case = case_store.get_case(conversation_id)
    if not case:
        raise KeyError(f"Case {conversation_id} not found")

    case_store.set_case_status(conversation_id, "building")
    ctx_graph = case.get("context_graph") or f"ctx_{conversation_id}"
    cache_dir = CASE_DATA_ROOT / conversation_id / "cache"
    sources = case.get("sources", [])

    if not sources:
        case_store.set_case_status(conversation_id, "draft", build_error="No sources to build")
        emit("failed", {"error": "no_sources", "detail": "Case contains no sources to ingest"})
        return {}

    warnings: list[str] = []

    try:
        # Check cancellation
        if is_cancelled():
            emit("cancelled", {})
            case_store.set_case_status(conversation_id, "draft")
            return {}

        # ---------------------------------------------------------------------
        # Step 1: PARSE ALL SOURCES
        # ---------------------------------------------------------------------
        all_chunks = []
        all_tables: list[TableData] = []
        sources_info = []

        for src in sources:
            if is_cancelled():
                emit("cancelled", {})
                case_store.set_case_status(conversation_id, "draft")
                return {}

            src_id = src["id"]
            src_name = src["name"]
            src_kind = src["kind"]
            src_path = src.get("path") or str(CASE_DATA_ROOT / conversation_id / "sources" / src_id / src_name)

            sources_info.append({"id": src_id, "name": src_name, "kind": src_kind})

            try:
                chunks, tables, p_warnings = parse_source_file(
                    src_id, src_name, src_kind, src_path
                )
                warnings.extend(p_warnings)
                all_chunks.extend(chunks)
                all_tables.extend(tables)

                case_store.update_source_status(
                    src_id,
                    "parsed",
                    stats={"chunks": len(chunks), "rows": sum(t.total_rows for t in tables), "tables": len(tables)},
                )
                emit("source_parsed", {
                    "source_id": src_id,
                    "name": src_name,
                    "kind": src_kind,
                    "chunks": len(chunks),
                    "rows": sum(t.total_rows for t in tables),
                    "tables": len(tables),
                })
            except Exception as parse_ex:
                case_store.update_source_status(src_id, "failed", error=str(parse_ex))
                warnings.append(f"Failed parsing source '{src_name}': {parse_ex}")

        if not all_chunks and not all_tables:
            raise RuntimeError("No usable data could be parsed from any source")

        # ---------------------------------------------------------------------
        # Step 2: MAP TABULAR SOURCES
        # ---------------------------------------------------------------------
        table_plans = {}
        for tbl in all_tables:
            if is_cancelled():
                emit("cancelled", {})
                case_store.set_case_status(conversation_id, "draft")
                return {}

            try:
                plan = plan_table_mapping(llm, tbl)
                table_plans[tbl.name] = plan
                emit("mapping_planned", {
                    "table": tbl.name,
                    "node_label": plan.node_label,
                    "columns_used": [c.column for c in plan.columns if c.role != "ignore"],
                })
            except Exception as map_ex:
                warnings.append(f"Tabular mapping failed for table '{tbl.name}': {map_ex}")

        # ---------------------------------------------------------------------
        # Step 3: EXTRACT TEXT CHUNKS (ThreadPoolExecutor max 4)
        # ---------------------------------------------------------------------
        all_extracted_entities: list[ExtractedEntity] = []
        all_extracted_relations: list[ExtractedRelation] = []

        total_chunks = len(all_chunks)
        chunks_ok = 0
        total_ent_dropped = 0
        total_rel_dropped = 0

        if all_chunks:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_chunk = {
                    executor.submit(extract_chunk, llm, chunk, cache_dir): chunk
                    for chunk in all_chunks
                }
                done_count = 0
                for future in concurrent.futures.as_completed(future_to_chunk):
                    if is_cancelled():
                        executor.shutdown(wait=False, cancel_futures=True)
                        emit("cancelled", {})
                        case_store.set_case_status(conversation_id, "draft")
                        return {}

                    done_count += 1
                    try:
                        kept_ents, kept_rels, d_ents, d_rels = future.result()
                        chunks_ok += 1
                        all_extracted_entities.extend(kept_ents)
                        all_extracted_relations.extend(kept_rels)
                        total_ent_dropped += d_ents
                        total_rel_dropped += d_rels
                    except Exception as ex:
                        warnings.append(f"Chunk extraction error: {ex}")

                    emit("extract_progress", {
                        "done": done_count,
                        "total": total_chunks,
                        "entities": len(all_extracted_entities),
                        "relations": len(all_extracted_relations),
                        "dropped": total_ent_dropped + total_rel_dropped,
                    })

            # Check failure threshold: > 30% failure rate
            if total_chunks > 0 and (total_chunks - chunks_ok) / total_chunks > 0.30:
                raise RuntimeError(
                    f"Extraction failed: more than 30% of chunks failed ({total_chunks - chunks_ok}/{total_chunks})"
                )

        # ---------------------------------------------------------------------
        # Step 4: BUILD STRUCTURED NODES/EDGES FROM TABULAR PLANS
        # ---------------------------------------------------------------------
        tabular_nodes: list[ResolvedNode] = []
        tabular_edges: list[ResolvedEdge] = []

        # Lookup table rows for entity_ref resolution
        row_id_lookup: dict[tuple[str, str], str] = {}  # (table, id_val) -> cid

        for tbl in all_tables:
            plan = table_plans.get(tbl.name)
            if not plan:
                continue

            id_col = next((c.column for c in plan.columns if c.role == "id"), None)
            name_col = next((c.column for c in plan.columns if c.role == "name"), None)

            for idx, r in enumerate(tbl.rows, start=1):
                raw_id = str(r.get(id_col, "")).strip() if id_col else ""
                row_cid = f"{tbl.name}:{raw_id}" if raw_id else f"{tbl.name}:r{idx}"
                row_id_lookup[(tbl.name, raw_id or str(idx))] = row_cid

                disp_name = str(r.get(name_col, "")).strip() if name_col else ""
                final_name = disp_name if disp_name else row_cid

                # Properties
                props = {}
                for col_plan in plan.columns:
                    if col_plan.role in ("property", "date", "amount"):
                        val = r.get(col_plan.column)
                        if val is not None and str(val).strip():
                            props[col_plan.column] = str(val).strip()[:500]

                tabular_nodes.append(
                    ResolvedNode(
                        cid=row_cid,
                        name=final_name,
                        type=plan.node_label,
                        aliases=set(),
                        source_ids={tbl.source_id},
                        confidence=1.0,
                        props=props,
                        quotes=[{"quote": f"Row {idx} in {tbl.name}", "locator": f"{tbl.name} row {idx}", "source_id": tbl.source_id}],
                    )
                )

                # Shared values
                for col_plan in plan.columns:
                    if col_plan.role == "shared_value" and col_plan.value_label:
                        val = str(r.get(col_plan.column, "")).strip()
                        if val and len(val) <= 200:
                            v_label = col_plan.value_label
                            val_cid = f"{v_label.lower()}:{val.lower().replace(' ', '_')}"
                            tabular_nodes.append(
                                ResolvedNode(
                                    cid=val_cid,
                                    name=val,
                                    type=v_label,
                                    source_ids={tbl.source_id},
                                    confidence=1.0,
                                    props={"value": val},
                                )
                            )
                            tabular_edges.append(
                                ResolvedEdge(
                                    src_cid=row_cid,
                                    dst_cid=val_cid,
                                    rel=f"HAS_{sanitize_rel(v_label)}",
                                    confidence=1.0,
                                    source_id=tbl.source_id,
                                    locator=f"{tbl.name} row {idx}",
                                    quote=f"{col_plan.column}: {val}",
                                    method="deterministic",
                                )
                            )

        # Entity refs
        for tbl in all_tables:
            plan = table_plans.get(tbl.name)
            if not plan:
                continue
            ref_cols = [c for c in plan.columns if c.role == "entity_ref" and c.ref_table]
            for idx, r in enumerate(tbl.rows, start=1):
                src_cid = row_id_lookup.get((tbl.name, str(r.get(id_col or "", idx))))
                if not src_cid:
                    continue
                for c_plan in ref_cols:
                    ref_val = str(r.get(c_plan.column, "")).strip()
                    if not ref_val or not c_plan.ref_table:
                        continue
                    dst_cid = row_id_lookup.get((c_plan.ref_table, ref_val))
                    if dst_cid and dst_cid != src_cid:
                        tabular_edges.append(
                            ResolvedEdge(
                                src_cid=src_cid,
                                dst_cid=dst_cid,
                                rel=f"REFERENCES_{sanitize_rel(c_plan.ref_table)}",
                                confidence=1.0,
                                source_id=tbl.source_id,
                                locator=f"{tbl.name} row {idx}",
                                quote=f"{c_plan.column} -> {c_plan.ref_table}:{ref_val}",
                                method="deterministic",
                            )
                        )

        # ---------------------------------------------------------------------
        # Step 5: RESOLVE DUPLICATES
        # ---------------------------------------------------------------------
        text_nodes, text_edges, possible_duplicates, merged_count = resolve_entities_and_relations(
            all_extracted_entities, all_extracted_relations
        )

        all_final_nodes = tabular_nodes + text_nodes
        all_final_edges = tabular_edges + text_edges

        emit("resolve_done", {
            "merged": merged_count,
            "possible_duplicates": len(possible_duplicates),
        })

        # ---------------------------------------------------------------------
        # Step 6: LOAD INTO FALKORDB (ctx_<id>)
        # ---------------------------------------------------------------------
        # Drop previous graph if exists
        try:
            graph_store.delete_graph(ctx_graph)
        except Exception:
            pass

        nodes_loaded, edges_loaded = load_context_graph(
            graph_store,
            ctx_graph,
            all_final_nodes,
            all_final_edges,
            possible_duplicates,
            sources_info,
        )

        emit("load_done", {"nodes": nodes_loaded, "edges": edges_loaded})

        # ---------------------------------------------------------------------
        # Step 7: COMPUTE SUMMARY STATS & COMPLETE
        # ---------------------------------------------------------------------
        model_name = getattr(llm, "model", "default")
        ext_stats = ExtractionStats(
            chunks_total=total_chunks,
            chunks_ok=chunks_ok,
            entities_kept=len(all_extracted_entities),
            entities_dropped=total_ent_dropped,
            relations_kept=len(all_extracted_relations),
            relations_dropped=total_rel_dropped,
            model=model_name,
        ) if total_chunks > 0 else None

        stats = compute_graph_summary(
            graph_store,
            ctx_graph,
            sources_count=len(sources),
            extraction_stats=ext_stats,
            extra_warnings=warnings,
        )

        case_store.set_case_status(
            conversation_id,
            status="ready",
            stats=stats,
        )
        emit("completed", {"stats": stats})
        return stats

    except Exception as build_err:
        err_msg = str(build_err)
        case_store.set_case_status(
            conversation_id,
            status="failed",
            build_error=err_msg,
        )
        emit("failed", {"error": "build_error", "detail": err_msg})
        return {}
