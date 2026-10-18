"""Deterministic entity resolution, normalization, and duplicate merging."""

from __future__ import annotations

import hashlib
import re
import string
from dataclasses import dataclass, field
from typing import Any, Optional
from luna.ingest.models import ExtractedEntity, ExtractedRelation

# Robust token_set_ratio with rapidfuzz or standard library fallback
try:
    from rapidfuzz import fuzz
    def token_set_ratio(s1: str, s2: str) -> float:
        return float(fuzz.token_set_ratio(s1, s2))
except ImportError:
    import difflib
    def token_set_ratio(s1: str, s2: str) -> float:
        t1 = set(s1.lower().split())
        t2 = set(s2.lower().split())
        s1_clean = " ".join(sorted(t1))
        s2_clean = " ".join(sorted(t2))
        return difflib.SequenceMatcher(None, s1_clean, s2_clean).ratio() * 100.0


def slugify(text: str) -> str:
    """Create URL/CID friendly slug from name."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:30] if s else "entity"


def normalize_value(val_type: str, val: str) -> str:
    """Normalize values according to entity type."""
    t = val_type.lower()
    raw = val.strip()

    if t == "phone":
        digits = re.sub(r"\D", "", raw)
        if len(digits) > 10 and digits.startswith("1"):
            digits = digits[1:]
        return digits

    elif t == "email":
        return raw.lower()

    elif t == "address":
        s = raw.lower()
        s = re.sub(r"\bst\b", "street", s)
        s = re.sub(r"\bave\b", "avenue", s)
        s = re.sub(r"\brd\b", "road", s)
        s = re.sub(r"\bblvd\b", "boulevard", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    else:
        # Casefold and remove punctuation
        s = raw.lower()
        s = s.translate(str.maketrans("", "", string.punctuation))
        s = re.sub(r"\s+", " ", s).strip()
        return s


@dataclass
class ResolvedNode:
    cid: str
    name: str
    type: str
    aliases: set[str] = field(default_factory=set)
    source_ids: set[str] = field(default_factory=set)
    confidence: float = 0.8
    props: dict[str, str] = field(default_factory=dict)
    quotes: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ResolvedEdge:
    src_cid: str
    dst_cid: str
    rel: str
    confidence: float
    source_id: str
    locator: str
    quote: str
    method: str = "llm"


def resolve_entities_and_relations(
    entities: list[ExtractedEntity],
    relations: list[ExtractedRelation],
) -> tuple[list[ResolvedNode], list[ResolvedEdge], list[tuple[str, str, float]], int]:
    """Resolve extracted entities into unified nodes, merge duplicates, link edges.

    Returns:
        (resolved_nodes, resolved_edges, possible_duplicate_pairs, merged_count)
    """
    # 1. Exact match clustering by (type, normalized_name)
    clusters: dict[tuple[str, str], list[ExtractedEntity]] = {}
    for ent in entities:
        norm_key = normalize_value(ent.type, ent.name)
        key = (ent.type, norm_key)
        if key not in clusters:
            clusters[key] = []
        clusters[key].append(ent)

    # 2. Form initial nodes
    node_list: list[ResolvedNode] = []
    key_to_cid: dict[tuple[str, str], str] = {}  # (chunk_source_id, ent_key) -> cid

    for (ent_type, norm_key), group in clusters.items():
        primary_name = group[0].name
        first_6 = hashlib.sha1(f"{ent_type}:{norm_key}".encode("utf-8")).hexdigest()[:6]
        cid = f"{ent_type.lower()}:{slugify(primary_name)}-{first_6}"

        all_aliases = {e.name for e in group if e.name != primary_name}
        all_sources = {e.source_id for e in group}
        max_conf = max(e.confidence for e in group)

        merged_props: dict[str, str] = {}
        quotes = []
        for e in group:
            merged_props.update(e.props)
            if e.quote:
                quotes.append({"quote": e.quote, "locator": e.locator, "source_id": e.source_id})
            key_to_cid[(e.source_id, e.key)] = cid

        node_list.append(
            ResolvedNode(
                cid=cid,
                name=primary_name,
                type=ent_type,
                aliases=all_aliases,
                source_ids=all_sources,
                confidence=max_conf,
                props=merged_props,
                quotes=quotes[:10],
            )
        )

    # 3. Fuzzy match within Person / Organization
    merged_count = 0
    possible_duplicates: list[tuple[str, str, float]] = []

    # Map for redirecting cids if merged
    cid_remap: dict[str, str] = {}

    final_nodes: list[ResolvedNode] = []
    processed_cids = set()

    for i in range(len(node_list)):
        n1 = node_list[i]
        if n1.cid in processed_cids:
            continue

        if n1.type in ("Person", "Organization"):
            for j in range(i + 1, len(node_list)):
                n2 = node_list[j]
                if n2.cid in processed_cids or n2.type != n1.type:
                    continue

                t1_tokens = n1.name.split()
                t2_tokens = n2.name.split()
                shorter_len = min(len(t1_tokens), len(t2_tokens))

                sim = token_set_ratio(n1.name, n2.name)

                if sim >= 92.0 and shorter_len >= 2:
                    # Merge n2 into n1
                    n1.aliases.add(n2.name)
                    n1.aliases.update(n2.aliases)
                    n1.source_ids.update(n2.source_ids)
                    n1.confidence = max(n1.confidence, n2.confidence)
                    n1.props.update(n2.props)
                    n1.quotes.extend(n2.quotes)
                    cid_remap[n2.cid] = n1.cid
                    processed_cids.add(n2.cid)
                    merged_count += 1
                elif 80.0 <= sim < 92.0:
                    possible_duplicates.append((n1.cid, n2.cid, sim))

        final_nodes.append(n1)
        processed_cids.add(n1.cid)

    # 4. Map relations to resolved CIDs
    resolved_edges: list[ResolvedEdge] = []
    for rel in relations:
        src_cid = key_to_cid.get((rel.source_id, rel.src))
        dst_cid = key_to_cid.get((rel.source_id, rel.dst))

        if not src_cid or not dst_cid or src_cid == dst_cid:
            continue

        final_src = cid_remap.get(src_cid, src_cid)
        final_dst = cid_remap.get(dst_cid, dst_cid)

        if final_src == final_dst:
            continue

        resolved_edges.append(
            ResolvedEdge(
                src_cid=final_src,
                dst_cid=final_dst,
                rel=rel.rel,
                confidence=rel.confidence,
                source_id=rel.source_id,
                locator=rel.locator,
                quote=rel.quote,
                method=rel.method,
            )
        )

    return final_nodes, resolved_edges, possible_duplicates, merged_count
