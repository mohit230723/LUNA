"""Deterministic synthetic insurance claims dataset generator with planted fraud clusters."""

import random
from dataclasses import dataclass, field
from typing import Any, Literal
from luna.graph.schema import (
    LABEL_CUSTOMER,
    LABEL_PROVIDER,
    LABEL_CLAIM,
    LABEL_POLICY,
    LABEL_PHONE,
    LABEL_ADDRESS,
    LABEL_BANK_ACCOUNT,
    REL_HOLDS,
    REL_FILED,
    REL_TREATED_BY,
    REL_USES_PHONE,
    REL_LIVES_AT,
    REL_PAYS_FROM,
)


@dataclass(frozen=True)
class GroundTruth:
    """Benchmark ground truth for evaluation of fraud detection accuracy."""

    ring_cids: set[str] = field(default_factory=set)
    decoy_cids: set[str] = field(default_factory=set)
    provider_cid: str = "prov_ring"
    ring_bank_account: str = "ba_ring"
    ring_phones: tuple[str, ...] = ("ph_ring_1", "ph_ring_2")
    decoy_address: str = "addr_decoy"


def _generate_small(seed: int = 42) -> tuple[dict[str, list[dict[str, Any]]], GroundTruth]:
    """Generate small domain dataset matching Phase 1 baseline."""
    rng = random.Random(seed)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(label: str, cid: str, **props: Any) -> None:
        props["cid"] = cid
        nodes.append({"label": label, "properties": props})

    def add_edge(rel_type: str, source_cid: str, target_cid: str, **props: Any) -> None:
        edges.append({
            "rel_type": rel_type,
            "source_cid": source_cid,
            "target_cid": target_cid,
            "properties": props,
        })

    # 1. Providers (~10 providers)
    add_node(LABEL_PROVIDER, "prov_ring", name="Apex Health Associates", specialty="Physical Therapy")
    for i in range(1, 10):
        add_node(
            LABEL_PROVIDER,
            f"prov_{i}",
            name=f"Metro Medical Group {i}",
            specialty=rng.choice(["Orthopedics", "Chiropractic", "Radiology", "General Practice"]),
        )

    # 2. Planted Shared Entities
    add_node(LABEL_BANK_ACCOUNT, "ba_ring", account_number="ACCT-987654", bank_name="First Metro Bank")
    add_node(LABEL_PHONE, "ph_ring_1", number="555-0191")
    add_node(LABEL_PHONE, "ph_ring_2", number="555-0192")
    add_node(LABEL_ADDRESS, "addr_decoy", street="742 Evergreen Terrace", city="Springfield", zip="97477")

    # 3. Fraud Ring Members (8 customers)
    ring_cids: set[str] = set()
    claim_counter = 1000

    for i in range(1, 9):
        cid = f"cust_ring_{i}"
        ring_cids.add(cid)
        add_node(LABEL_CUSTOMER, cid, name=f"Ring Subject {i}", flagged=False)

        pol_cid = f"pol_ring_{i}"
        add_node(LABEL_POLICY, pol_cid, policy_type="Comprehensive", coverage_limit=100000.0)
        add_edge(REL_HOLDS, cid, pol_cid)

        add_edge(REL_PAYS_FROM, cid, "ba_ring")

        phone_cid = "ph_ring_1" if i <= 4 else "ph_ring_2"
        add_edge(REL_USES_PHONE, cid, phone_cid)

        addr_cid = f"addr_ring_{i}"
        add_node(LABEL_ADDRESS, addr_cid, street=f"{100 + i} Industrial Blvd", city="Springfield", zip="97477")
        add_edge(REL_LIVES_AT, cid, addr_cid)

        num_claims = rng.randint(1, 3)
        for _ in range(num_claims):
            claim_counter += 1
            claim_cid = f"claim_{claim_counter}"
            amount = round(rng.uniform(25000.0, 65000.0), 2)
            add_node(LABEL_CLAIM, claim_cid, amount=amount, date="2026-03-15", status="filed")
            add_edge(REL_FILED, cid, claim_cid)
            add_edge(REL_TREATED_BY, claim_cid, "prov_ring")

    # 4. Decoy Family Members (4 customers)
    decoy_cids: set[str] = set()
    for i in range(1, 5):
        cid = f"cust_decoy_{i}"
        decoy_cids.add(cid)
        add_node(LABEL_CUSTOMER, cid, name=f"Decoy Family Member {i}", flagged=False)

        pol_cid = f"pol_decoy_{i}"
        add_node(LABEL_POLICY, pol_cid, policy_type="Standard Auto", coverage_limit=50000.0)
        add_edge(REL_HOLDS, cid, pol_cid)

        add_edge(REL_LIVES_AT, cid, "addr_decoy")

        ph_cid = f"ph_decoy_{i}"
        add_node(LABEL_PHONE, ph_cid, number=f"555-030{i}")
        add_edge(REL_USES_PHONE, cid, ph_cid)

        ba_cid = f"ba_decoy_{i}"
        add_node(LABEL_BANK_ACCOUNT, ba_cid, account_number=f"ACCT-DEC-{i}", bank_name="Decoy Trust")
        add_edge(REL_PAYS_FROM, cid, ba_cid)

        claim_counter += 1
        claim_cid = f"claim_{claim_counter}"
        amount = round(rng.uniform(800.0, 4200.0), 2)
        normal_prov = f"prov_{i % 3 + 1}"
        add_node(LABEL_CLAIM, claim_cid, amount=amount, date="2026-02-10", status="settled")
        add_edge(REL_FILED, cid, claim_cid)
        add_edge(REL_TREATED_BY, claim_cid, normal_prov)

    # 5. Background Normal Population (288 customers -> total 300 customers)
    for i in range(1, 289):
        cid = f"cust_{i}"
        add_node(LABEL_CUSTOMER, cid, name=f"Customer {i}", flagged=False)

        pol_cid = f"pol_{i}"
        add_node(LABEL_POLICY, pol_cid, policy_type=rng.choice(["Basic", "Standard", "Premium"]), coverage_limit=50000.0)
        add_edge(REL_HOLDS, cid, pol_cid)

        ph_cid = f"ph_{i}"
        add_node(LABEL_PHONE, ph_cid, number=f"555-1{i:04d}")
        add_edge(REL_USES_PHONE, cid, ph_cid)

        addr_cid = f"addr_{i}"
        add_node(LABEL_ADDRESS, addr_cid, street=f"{i * 12} Maple Street", city="Springfield", zip="97477")
        add_edge(REL_LIVES_AT, cid, addr_cid)

        ba_cid = f"ba_{i}"
        add_node(LABEL_BANK_ACCOUNT, ba_cid, account_number=f"ACCT-{i:06d}", bank_name="National Bank")
        add_edge(REL_PAYS_FROM, cid, ba_cid)

        if rng.random() < 0.7:
            num_claims = 1 if rng.random() < 0.8 else 2
            for _ in range(num_claims):
                claim_counter += 1
                claim_cid = f"claim_{claim_counter}"
                amount = round(rng.uniform(500.0, 9500.0), 2)
                provider_cid = f"prov_{rng.randint(1, 9)}"
                add_node(LABEL_CLAIM, claim_cid, amount=amount, date="2026-01-20", status="approved")
                add_edge(REL_FILED, cid, claim_cid)
                add_edge(REL_TREATED_BY, claim_cid, provider_cid)

    gt = GroundTruth(
        ring_cids=ring_cids,
        decoy_cids=decoy_cids,
        provider_cid="prov_ring",
        ring_bank_account="ba_ring",
        ring_phones=("ph_ring_1", "ph_ring_2"),
        decoy_address="addr_decoy",
    )

    return {"nodes": nodes, "edges": edges}, gt


def _generate_demo(seed: int = 42) -> tuple[dict[str, list[dict[str, Any]]], GroundTruth]:
    """Generate richer demo profile (~300 customers) with realistic noise and planted clusters.

    Planted structure:
    - Fraud Ring: 8 customers (cust_ring_1..8) sharing ba_ring and 2 phones (ph_ring_1, ph_ring_2),
      filing high-value claims at prov_ring, PLUS routine claim at prov_1 (popular provider).
    - Decoy Family: 4 customers (cust_decoy_1..4) sharing addr_decoy, separate phones/bank accounts,
      normal claims.
    - Noise:
      (a) 3 popular providers (prov_1, prov_2, prov_3) each connected to >= 30 customers.
      (b) 12 pairs of unrelated customers sharing a phone (ph_shared_1..12).
      (c) 6 benign shared-address groups of 2 to 3 customers (addr_shared_1..6).
      (d) Ring members connected to wider graph via routine claim with popular provider (prov_1).
    """
    rng = random.Random(seed)

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add_node(label: str, cid: str, **props: Any) -> None:
        props["cid"] = cid
        nodes.append({"label": label, "properties": props})

    def add_edge(rel_type: str, source_cid: str, target_cid: str, **props: Any) -> None:
        edges.append({
            "rel_type": rel_type,
            "source_cid": source_cid,
            "target_cid": target_cid,
            "properties": props,
        })

    # 1. Providers (~10 providers)
    add_node(LABEL_PROVIDER, "prov_ring", name="Apex Health Associates", specialty="Physical Therapy")
    for i in range(1, 10):
        add_node(
            LABEL_PROVIDER,
            f"prov_{i}",
            name=f"Metro Medical Group {i}",
            specialty=rng.choice(["Orthopedics", "Chiropractic", "Radiology", "General Practice"]),
        )

    # 2. Planted Shared Entities
    add_node(LABEL_BANK_ACCOUNT, "ba_ring", account_number="ACCT-987654", bank_name="First Metro Bank")
    add_node(LABEL_PHONE, "ph_ring_1", number="555-0191")
    add_node(LABEL_PHONE, "ph_ring_2", number="555-0192")
    add_node(LABEL_ADDRESS, "addr_decoy", street="742 Evergreen Terrace", city="Springfield", zip="97477")

    # Shared noise phones (12 phones for 12 pairs of customers)
    for i in range(1, 13):
        add_node(LABEL_PHONE, f"ph_shared_{i}", number=f"555-08{i:02d}")

    # Shared noise addresses (6 addresses for groups of 2-3 customers)
    for i in range(1, 7):
        add_node(LABEL_ADDRESS, f"addr_shared_{i}", street=f"{200 + i * 10} Shared Way", city="Springfield", zip="97477")

    claim_counter = 1000

    # 3. Fraud Ring Members (8 customers)
    ring_cids: set[str] = set()
    for i in range(1, 9):
        cid = f"cust_ring_{i}"
        ring_cids.add(cid)
        add_node(LABEL_CUSTOMER, cid, name=f"Ring Subject {i}", flagged=False)

        pol_cid = f"pol_ring_{i}"
        add_node(LABEL_POLICY, pol_cid, policy_type="Comprehensive", coverage_limit=100000.0)
        add_edge(REL_HOLDS, cid, pol_cid)

        add_edge(REL_PAYS_FROM, cid, "ba_ring")

        phone_cid = "ph_ring_1" if i <= 4 else "ph_ring_2"
        add_edge(REL_USES_PHONE, cid, phone_cid)

        addr_cid = f"addr_ring_{i}"
        add_node(LABEL_ADDRESS, addr_cid, street=f"{100 + i} Industrial Blvd", city="Springfield", zip="97477")
        add_edge(REL_LIVES_AT, cid, addr_cid)

        # High-value claims treated by prov_ring
        num_claims = rng.randint(1, 3)
        for _ in range(num_claims):
            claim_counter += 1
            claim_cid = f"claim_{claim_counter}"
            amount = round(rng.uniform(25000.0, 65000.0), 2)
            add_node(LABEL_CLAIM, claim_cid, amount=amount, date="2026-03-15", status="filed")
            add_edge(REL_FILED, cid, claim_cid)
            add_edge(REL_TREATED_BY, claim_cid, "prov_ring")

        # Noise (d): Ring members also file at least one claim with a popular provider (prov_1)
        claim_counter += 1
        routine_claim_cid = f"claim_{claim_counter}"
        add_node(LABEL_CLAIM, routine_claim_cid, amount=1250.0, date="2026-01-10", status="approved")
        add_edge(REL_FILED, cid, routine_claim_cid)
        add_edge(REL_TREATED_BY, routine_claim_cid, "prov_1")

    # 4. Decoy Family Members (4 customers)
    decoy_cids: set[str] = set()
    for i in range(1, 5):
        cid = f"cust_decoy_{i}"
        decoy_cids.add(cid)
        add_node(LABEL_CUSTOMER, cid, name=f"Decoy Family Member {i}", flagged=False)

        pol_cid = f"pol_decoy_{i}"
        add_node(LABEL_POLICY, pol_cid, policy_type="Standard Auto", coverage_limit=50000.0)
        add_edge(REL_HOLDS, cid, pol_cid)

        add_edge(REL_LIVES_AT, cid, "addr_decoy")

        ph_cid = f"ph_decoy_{i}"
        add_node(LABEL_PHONE, ph_cid, number=f"555-030{i}")
        add_edge(REL_USES_PHONE, cid, ph_cid)

        ba_cid = f"ba_decoy_{i}"
        add_node(LABEL_BANK_ACCOUNT, ba_cid, account_number=f"ACCT-DEC-{i}", bank_name="Decoy Trust")
        add_edge(REL_PAYS_FROM, cid, ba_cid)

        claim_counter += 1
        claim_cid = f"claim_{claim_counter}"
        amount = round(rng.uniform(800.0, 4200.0), 2)
        normal_prov = f"prov_{i % 3 + 1}"
        add_node(LABEL_CLAIM, claim_cid, amount=amount, date="2026-02-10", status="settled")
        add_edge(REL_FILED, cid, claim_cid)
        add_edge(REL_TREATED_BY, claim_cid, normal_prov)

    # 5. Background Normal Population (288 customers -> total 300 customers)
    for i in range(1, 289):
        cid = f"cust_{i}"
        add_node(LABEL_CUSTOMER, cid, name=f"Customer {i}", flagged=False)

        pol_cid = f"pol_{i}"
        add_node(LABEL_POLICY, pol_cid, policy_type=rng.choice(["Basic", "Standard", "Premium"]), coverage_limit=50000.0)
        add_edge(REL_HOLDS, cid, pol_cid)

        # Noise (b): 12 pairs of unrelated customers sharing a phone
        if 1 <= i <= 24:
            pair_idx = (i - 1) // 2 + 1
            add_edge(REL_USES_PHONE, cid, f"ph_shared_{pair_idx}")
        else:
            ph_cid = f"ph_{i}"
            add_node(LABEL_PHONE, ph_cid, number=f"555-1{i:04d}")
            add_edge(REL_USES_PHONE, cid, ph_cid)

        # Noise (c): 6 benign shared-address groups of 2-3 customers
        if i in (25, 26):
            add_edge(REL_LIVES_AT, cid, "addr_shared_1")
        elif i in (27, 28):
            add_edge(REL_LIVES_AT, cid, "addr_shared_2")
        elif i in (29, 30, 31):
            add_edge(REL_LIVES_AT, cid, "addr_shared_3")
        elif i in (32, 33):
            add_edge(REL_LIVES_AT, cid, "addr_shared_4")
        elif i in (34, 35, 36):
            add_edge(REL_LIVES_AT, cid, "addr_shared_5")
        elif i in (37, 38):
            add_edge(REL_LIVES_AT, cid, "addr_shared_6")
        else:
            addr_cid = f"addr_{i}"
            add_node(LABEL_ADDRESS, addr_cid, street=f"{i * 12} Maple Street", city="Springfield", zip="97477")
            add_edge(REL_LIVES_AT, cid, addr_cid)

        # Bank Account: unique per background customer
        ba_cid = f"ba_{i}"
        add_node(LABEL_BANK_ACCOUNT, ba_cid, account_number=f"ACCT-{i:06d}", bank_name="National Bank")
        add_edge(REL_PAYS_FROM, cid, ba_cid)

        # Noise (a): 3 popular providers (prov_1, prov_2, prov_3) each connected to >= 30 customers
        if 1 <= i <= 40:
            provider_cid = "prov_1"
        elif 41 <= i <= 80:
            provider_cid = "prov_2"
        elif 81 <= i <= 120:
            provider_cid = "prov_3"
        else:
            provider_cid = f"prov_{rng.randint(1, 9)}"

        claim_counter += 1
        claim_cid = f"claim_{claim_counter}"
        amount = round(rng.uniform(500.0, 9500.0), 2)
        add_node(LABEL_CLAIM, claim_cid, amount=amount, date="2026-01-20", status="approved")
        add_edge(REL_FILED, cid, claim_cid)
        add_edge(REL_TREATED_BY, claim_cid, provider_cid)

        # Optional second claim
        if rng.random() < 0.2:
            claim_counter += 1
            claim_cid = f"claim_{claim_counter}"
            amount = round(rng.uniform(500.0, 5000.0), 2)
            extra_prov = f"prov_{rng.randint(1, 9)}"
            add_node(LABEL_CLAIM, claim_cid, amount=amount, date="2026-02-15", status="approved")
            add_edge(REL_FILED, cid, claim_cid)
            add_edge(REL_TREATED_BY, claim_cid, extra_prov)

    gt = GroundTruth(
        ring_cids=ring_cids,
        decoy_cids=decoy_cids,
        provider_cid="prov_ring",
        ring_bank_account="ba_ring",
        ring_phones=("ph_ring_1", "ph_ring_2"),
        decoy_address="addr_decoy",
    )

    return {"nodes": nodes, "edges": edges}, gt


def generate_domain(
    seed: int = 42,
    profile: Literal["small", "demo"] = "small",
) -> tuple[dict[str, list[dict[str, Any]]], GroundTruth]:
    """Generate deterministic connected insurance domain data.

    Args:
        seed: Random seed for deterministic generation.
        profile: 'small' for minimal baseline, 'demo' for richer graph with realistic noise.
    """
    if profile == "small":
        return _generate_small(seed=seed)
    elif profile == "demo":
        return _generate_demo(seed=seed)
    else:
        raise ValueError(f"Unknown domain profile: '{profile}'. Must be 'small' or 'demo'.")


# Public backward-compatible alias
generate_insurance_dataset = generate_domain
