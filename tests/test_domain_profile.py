"""Integration tests for F7: domain profiles (small vs demo) and deterministic slice capping."""

import pytest
import networkx as nx
from luna.domain.generate import generate_domain, generate_insurance_dataset
from luna.domain.seed import seed_domain
from luna.orchestrator.slice import extract_subgraph_slice


def test_demo_is_deterministic():
    """Verify that demo profile generation is completely deterministic with the same seed."""
    d1, gt1 = generate_domain(seed=42, profile="demo")
    d2, gt2 = generate_domain(seed=42, profile="demo")

    assert len(d1["nodes"]) == len(d2["nodes"])
    assert len(d1["edges"]) == len(d2["edges"])
    assert gt1.ring_cids == gt2.ring_cids
    assert gt1.decoy_cids == gt2.decoy_cids
    assert [n["properties"]["cid"] for n in d1["nodes"]] == [n["properties"]["cid"] for n in d2["nodes"]]


@pytest.mark.integration
def test_demo_profile_counts(live_store):
    """Verify customer counts, popular providers, phone pairs, and address groups in demo profile."""
    gt = seed_domain(live_store, seed=42, profile="demo")

    # 1. Total customer count ~300
    cust_res = live_store.query("domain", "MATCH (c:Customer) RETURN count(c) AS cnt")
    total_customers = cust_res[0]["cnt"]
    assert 295 <= total_customers <= 305

    # 2. At least 3 popular providers each connected to 30+ customers
    prov_res = live_store.query(
        "domain",
        "MATCH (c:Customer)-[:FILED]->(:InsuranceClaim)-[:TREATED_BY]->(p:Provider) "
        "RETURN p.cid AS prov, count(DISTINCT c) AS cust_cnt "
        "ORDER BY cust_cnt DESC"
    )
    popular_provs = [p for p in prov_res if p["cust_cnt"] >= 30]
    assert len(popular_provs) >= 3

    # 3. At least 10 pairs of unrelated customers sharing a phone
    phone_res = live_store.query(
        "domain",
        "MATCH (c1:Customer)-[:USES_PHONE]->(ph:Phone)<-[:USES_PHONE]-(c2:Customer) "
        "WHERE c1.cid < c2.cid AND NOT c1.cid IN $ring_cids "
        "RETURN count(DISTINCT [c1.cid, c2.cid]) AS pair_cnt",
        {"ring_cids": list(gt.ring_cids)},
    )
    assert phone_res[0]["pair_cnt"] >= 10

    # 4. At least 5 benign shared-address groups of 2 to 3 customers
    addr_res = live_store.query(
        "domain",
        "MATCH (c:Customer)-[:LIVES_AT]->(a:Address) "
        "WHERE NOT c.cid IN $ring_cids AND a.cid <> 'addr_decoy' "
        "WITH a.cid AS addr, count(c) AS cust_cnt "
        "WHERE cust_cnt >= 2 "
        "RETURN addr, cust_cnt",
        {"ring_cids": list(gt.ring_cids)},
    )
    assert len(addr_res) >= 5

    # 5. Ring members also file at least one claim with a popular provider
    pop_prov_cids = [p["prov"] for p in popular_provs]
    ring_pop_res = live_store.query(
        "domain",
        "MATCH (c:Customer)-[:FILED]->(:InsuranceClaim)-[:TREATED_BY]->(p:Provider) "
        "WHERE c.cid IN $ring_cids AND p.cid IN $pop_cids "
        "RETURN count(c) AS cnt",
        {"ring_cids": list(gt.ring_cids), "pop_cids": pop_prov_cids},
    )
    assert ring_pop_res[0]["cnt"] >= 1


@pytest.mark.integration
def test_demo_ring_still_exactly_detectable_via_bank_account_and_phone(live_store):
    """Verify that components over BankAccount and Phone with min_size=5 exactly match the 8 ring members."""
    gt = seed_domain(live_store, seed=42, profile="demo")

    # Build graph over BankAccount and Phone connections
    edges = live_store.query(
        "domain",
        "MATCH (c1:Customer)-[r1:PAYS_FROM|USES_PHONE]->(attr)<-[r2:PAYS_FROM|USES_PHONE]-(c2:Customer) "
        "WHERE c1.cid < c2.cid "
        "RETURN c1.cid AS src, c2.cid AS tgt"
    )

    g = nx.Graph()
    for e in edges:
        g.add_edge(e["src"], e["tgt"])

    large_components = [c for c in nx.connected_components(g) if len(c) >= 5]
    assert len(large_components) == 1
    assert large_components[0] == gt.ring_cids


@pytest.mark.integration
def test_naive_any_shared_attribute_flags_false_positives(live_store):
    """Verify that naive components over all attributes (including Address) produce false positive clusters."""
    gt = seed_domain(live_store, seed=42, profile="demo")

    edges = live_store.query(
        "domain",
        "MATCH (c1:Customer)-[r1]->(attr)<-[r2]-(c2:Customer) "
        "WHERE c1.cid < c2.cid "
        "RETURN c1.cid AS src, c2.cid AS tgt"
    )

    g = nx.Graph()
    for e in edges:
        g.add_edge(e["src"], e["tgt"])

    clusters_gte_2 = [c for c in nx.connected_components(g) if len(c) >= 2]
    # Total entities in shared-attribute clusters includes way more than the 8 ring members
    clustered_customers = {cust for cluster in clusters_gte_2 for cust in cluster}
    assert len(clustered_customers) > len(gt.ring_cids)
    assert not clustered_customers.issubset(gt.ring_cids)


@pytest.mark.integration
def test_slice_cap_deterministic(live_store, tmp_graph):
    """Verify extract_subgraph_slice max_nodes cap sorts by CID and reports truncation."""
    seed_domain(live_store, seed=42, profile="small")

    # Extract with cap of 5 nodes
    summary1 = extract_subgraph_slice(
        store=live_store,
        source_graph="domain",
        target_graph=tmp_graph,
        seed_cids=["cust_ring_1"],
        k_hops=2,
        max_nodes=5,
    )

    assert summary1["truncated"] is True
    assert summary1["nodes_extracted"] == 5
    assert len(summary1["extracted_cids"]) == 5

    # Run again on a new graph to verify deterministic ordering
    tmp_graph2 = f"{tmp_graph}_2"
    try:
        summary2 = extract_subgraph_slice(
            store=live_store,
            source_graph="domain",
            target_graph=tmp_graph2,
            seed_cids=["cust_ring_1"],
            k_hops=2,
            max_nodes=5,
        )
        assert summary1["extracted_cids"] == summary2["extracted_cids"]
    finally:
        live_store.delete_graph(tmp_graph2)
