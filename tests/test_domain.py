"""Unit tests for synthetic domain generator, ground truth, and ontology."""

import json
from pathlib import Path
from unittest.mock import MagicMock
from luna.domain.generate import generate_insurance_dataset, GroundTruth
from luna.domain.seed import seed_domain


def test_domain_dataset_determinism():
    """Verify that identical seeds produce identical graph structures and CIDs."""
    data1, gt1 = generate_insurance_dataset(seed=42)
    data2, gt2 = generate_insurance_dataset(seed=42)

    assert len(data1["nodes"]) == len(data2["nodes"])
    assert len(data1["edges"]) == len(data2["edges"])
    assert gt1.ring_cids == gt2.ring_cids
    assert gt1.decoy_cids == gt2.decoy_cids
    assert len(gt1.ring_cids) == 8
    assert len(gt1.decoy_cids) == 4


def test_fraud_ring_structure():
    """Verify planted fraud ring has exact shared attributes and high claims at prov_ring."""
    data, gt = generate_insurance_dataset(seed=42)

    # All 8 ring members
    assert len(gt.ring_cids) == 8

    # Build adjacency maps
    pays_from = {e["source_cid"]: e["target_cid"] for e in data["edges"] if e["rel_type"] == "PAYS_FROM"}
    uses_phone = {e["source_cid"]: e["target_cid"] for e in data["edges"] if e["rel_type"] == "USES_PHONE"}
    claims_filed = {e["target_cid"]: e["source_cid"] for e in data["edges"] if e["rel_type"] == "FILED"}
    claim_treated_by = {e["source_cid"]: e["target_cid"] for e in data["edges"] if e["rel_type"] == "TREATED_BY"}
    claim_amounts = {
        n["properties"]["cid"]: n["properties"]["amount"]
        for n in data["nodes"]
        if n["label"] == "InsuranceClaim"
    }

    for cid in gt.ring_cids:
        # 1. Shares bank account ba_ring
        assert pays_from.get(cid) == gt.ring_bank_account
        # 2. Uses one of the two ring phones
        assert uses_phone.get(cid) in gt.ring_phones

    # Check claims filed by ring members
    ring_claims = [claim_cid for claim_cid, cust_cid in claims_filed.items() if cust_cid in gt.ring_cids]
    assert len(ring_claims) >= 8

    for claim_cid in ring_claims:
        # Must be treated by prov_ring
        assert claim_treated_by.get(claim_cid) == gt.provider_cid
        # Must be high value (>$25,000)
        assert claim_amounts[claim_cid] >= 25000.0


def test_decoy_family_structure():
    """Verify decoy family members legitimately share address but have clean, isolated profiles."""
    data, gt = generate_insurance_dataset(seed=42)

    assert len(gt.decoy_cids) == 4

    lives_at = {e["source_cid"]: e["target_cid"] for e in data["edges"] if e["rel_type"] == "LIVES_AT"}
    pays_from = {e["source_cid"]: e["target_cid"] for e in data["edges"] if e["rel_type"] == "PAYS_FROM"}
    uses_phone = {e["source_cid"]: e["target_cid"] for e in data["edges"] if e["rel_type"] == "USES_PHONE"}
    claims_filed = {e["target_cid"]: e["source_cid"] for e in data["edges"] if e["rel_type"] == "FILED"}
    claim_treated_by = {e["source_cid"]: e["target_cid"] for e in data["edges"] if e["rel_type"] == "TREATED_BY"}
    claim_amounts = {
        n["properties"]["cid"]: n["properties"]["amount"]
        for n in data["nodes"]
        if n["label"] == "InsuranceClaim"
    }

    # All 4 share addr_decoy
    for cid in gt.decoy_cids:
        assert lives_at.get(cid) == gt.decoy_address
        # Clean: NOT linked to ring bank account or ring phones
        assert pays_from.get(cid) != gt.ring_bank_account
        assert uses_phone.get(cid) not in gt.ring_phones

    # Check decoy claims
    decoy_claims = [claim_cid for claim_cid, cust_cid in claims_filed.items() if cust_cid in gt.decoy_cids]
    for claim_cid in decoy_claims:
        # Not treated by prov_ring
        assert claim_treated_by.get(claim_cid) != gt.provider_cid
        # Normal low claim amount (<$5,000)
        assert claim_amounts[claim_cid] <= 5000.0


def test_ontology_json_schema():
    """Verify ontology.json exists, parses, and defines required entities and relationships."""
    ontology_path = Path("luna/domain/ontology.json")
    assert ontology_path.exists()

    with open(ontology_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    assert "entities" in schema
    assert "relationships" in schema

    entity_names = {e["name"] for e in schema["entities"]}
    expected_entities = {"Customer", "Provider", "InsuranceClaim", "Policy", "Phone", "Address", "BankAccount"}
    assert expected_entities.issubset(entity_names)

    rel_types = {r["type"] for r in schema["relationships"]}
    expected_rels = {"HOLDS", "FILED", "TREATED_BY", "USES_PHONE", "LIVES_AT", "PAYS_FROM"}
    assert expected_rels.issubset(rel_types)


def test_seed_domain_execution():
    """Verify seed_domain executes batch deletions and insertions against GraphStore."""
    mock_store = MagicMock()
    gt = seed_domain(mock_store, seed=42)

    assert isinstance(gt, GroundTruth)
    assert len(gt.ring_cids) == 8
    assert len(gt.decoy_cids) == 4

    # delete_graph called to clear previous state
    mock_store.delete_graph.assert_called_once_with("domain")
    # query called multiple times for batch node and edge creation
    assert mock_store.query.call_count >= 10
