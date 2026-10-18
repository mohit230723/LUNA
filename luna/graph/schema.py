"""Graph naming helpers, label constants, and relationship types for LUNA OS."""

import re

# Base static graph names
GRAPH_ATLAS: str = "atlas"
GRAPH_DOMAIN: str = "domain"
GRAPH_CONVERSATIONS: str = "conversations"

# Dynamic graph name helpers
def run_graph_name(run_id: str) -> str:
    """Generate normalized shared run graph name."""
    clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", run_id)
    return f"run_{clean_id}"


def agent_graph_name(run_id: str, agent_id: str) -> str:
    """Generate normalized private agent slice graph name."""
    clean_run = re.sub(r"[^a-zA-Z0-9_]", "_", run_id)
    clean_agent = re.sub(r"[^a-zA-Z0-9_]", "_", agent_id)
    return f"agent_{clean_run}_{clean_agent}"


# Domain Graph Node Labels
LABEL_CUSTOMER = "Customer"
LABEL_PROVIDER = "Provider"
LABEL_CLAIM = "InsuranceClaim"
LABEL_POLICY = "Policy"
LABEL_PHONE = "Phone"
LABEL_ADDRESS = "Address"
LABEL_BANK_ACCOUNT = "BankAccount"

# Atlas Catalog Node Labels
LABEL_CAPABILITY = "Capability"
LABEL_SKILL = "Skill"
LABEL_TOOL = "Tool"
LABEL_TASK_TYPE = "TaskType"
LABEL_PACK = "Pack"
LABEL_TECHNOLOGY = "Technology"

# Run Memory Graph Node Labels
LABEL_TASK = "Task"
LABEL_SUBTASK = "Subtask"
LABEL_AGENT = "Agent"
LABEL_SKILL_REF = "SkillRef"
LABEL_DECISION = "Decision"
LABEL_FINDING = "Finding"
LABEL_EVIDENCE_REF = "EvidenceRef"
LABEL_ACTION = "Action"
LABEL_OUTCOME = "Outcome"
LABEL_TRAVERSAL_STEP = "TraversalStep"
LABEL_ANSWER = "Answer"
LABEL_COMPONENT = "Component"
LABEL_CONTRACT = "Contract"
LABEL_ARTIFACT = "Artifact"

# Domain Relationship Types
REL_HOLDS = "HOLDS"
REL_FILED = "FILED"
REL_TREATED_BY = "TREATED_BY"
REL_USES_PHONE = "USES_PHONE"
REL_LIVES_AT = "LIVES_AT"
REL_PAYS_FROM = "PAYS_FROM"

# Atlas Relationship Types
REL_PROVIDES = "PROVIDES"
REL_REQUIRES = "REQUIRES"
REL_EXPOSES = "EXPOSES"
REL_SUCCEEDED_ON = "SUCCEEDED_ON"
REL_IN_PACK = "IN_PACK"
REL_TARGETS = "TARGETS"

# Run Memory Relationship Types
REL_HAS_SUBTASK = "HAS_SUBTASK"
REL_FOR = "FOR"
REL_CHOSE = "CHOSE"
REL_REJECTED = "REJECTED"
REL_EQUIPPED = "EQUIPPED"
REL_PRODUCED_BY = "PRODUCED_BY"
REL_PROMOTED_FROM = "PROMOTED_FROM"
REL_ASSESSES = "ASSESSES"
REL_SUPPORTED_BY = "SUPPORTED_BY"
REL_CONFLICTS_WITH = "CONFLICTS_WITH"
REL_SUPERSEDES = "SUPERSEDES"
REL_UPHELD = "UPHELD"
REL_BASED_ON = "BASED_ON"
REL_RESULTED_IN = "RESULTED_IN"
REL_ABOUT = "ABOUT"
REL_HAS_STEP = "HAS_STEP"
REL_ANSWERED_BY = "ANSWERED_BY"
REL_CITES = "CITES"
REL_CONSUMES = "CONSUMES"
REL_DEPENDS_ON = "DEPENDS_ON"
REL_HAS_COMPONENT = "HAS_COMPONENT"
REL_PRODUCED = "PRODUCED"

# Conversation Memory Node Labels & Relationships
LABEL_CONVERSATION = "Conversation"
LABEL_TURN = "Turn"
LABEL_RUN_REF = "RunRef"

REL_HAS_TURN = "HAS_TURN"
REL_TRIGGERED = "TRIGGERED"
REL_FOLLOWS = "FOLLOWS"
