"""Autonomous sub-agent execution loop operating within private graph slices."""

import json
from typing import Any, Optional
from luna.agents.models import Finding, SubAgentRunConfig
from luna.llm.client import LLMClient
from luna.mcp.client import AgentMCPClient


class SubAgent:
    """Specialized investigator sub-agent equipped with isolated FastMCP tools."""

    def __init__(
        self,
        config: SubAgentRunConfig,
        mcp_client: AgentMCPClient,
        llm_client: LLMClient,
    ) -> None:
        self.config = config
        self.mcp_client = mcp_client
        self.llm_client = llm_client

    async def _gather_observations(self, target_cid: str) -> tuple[dict[str, Any], set[str]]:
        """Query scoped FastMCP tools to observe graph patterns and collect evidence CIDs."""
        observations: dict[str, Any] = {}
        evidence_cids: set[str] = set()
        tools = await self.mcp_client.list_tools()
        available_tool_names = {t["name"] for t in tools}

        if "shared_attribute_links" in available_tool_names:
            try:
                res = await self.mcp_client.call_tool("shared_attribute_links", {"cid": target_cid})
                observations["shared_attribute_links"] = res
                if isinstance(res, list):
                    for link in res:
                        if isinstance(link, dict):
                            if link.get("shared_cid"):
                                evidence_cids.add(str(link["shared_cid"]))
                            if link.get("attribute_cid"):
                                evidence_cids.add(str(link["attribute_cid"]))
            except Exception as e:
                observations["shared_attribute_links_error"] = str(e)

        if "connected_components" in available_tool_names:
            try:
                res = await self.mcp_client.call_tool(
                    "connected_components", {"cids": self.config.target_cids}
                )
                observations["connected_components"] = res
                if isinstance(res, list):
                    for cluster in res:
                        if isinstance(cluster, list) and target_cid in cluster:
                            for c in cluster:
                                evidence_cids.add(str(c))
            except Exception as e:
                observations["connected_components_error"] = str(e)

        if "pagerank_top" in available_tool_names:
            try:
                res = await self.mcp_client.call_tool("pagerank_top", {"limit": 10})
                observations["pagerank_top"] = res
                if isinstance(res, list):
                    for entry in res:
                        if isinstance(entry, dict) and entry.get("cid"):
                            if entry.get("score", 0) > 0.05:
                                evidence_cids.add(str(entry["cid"]))
            except Exception as e:
                observations["pagerank_top_error"] = str(e)

        if "claim_amount_outliers" in available_tool_names:
            try:
                res = await self.mcp_client.call_tool(
                    "claim_amount_outliers", {"std_dev_threshold": 2.0}
                )
                observations["claim_amount_outliers"] = res
                if isinstance(res, list):
                    for outlier in res:
                        if isinstance(outlier, dict) and outlier.get("cid"):
                            evidence_cids.add(str(outlier["cid"]))
            except Exception as e:
                observations["claim_amount_outliers_error"] = str(e)

        if "ask_graph" in available_tool_names:
            try:
                res = await self.mcp_client.call_tool(
                    "ask_graph",
                    {"question": f"Who shares accounts or addresses with customer {target_cid}?"},
                )
                observations["ask_graph"] = res
            except Exception as e:
                observations["ask_graph_error"] = str(e)

        return observations, evidence_cids

    def _heuristic_evaluate(
        self,
        target_cid: str,
        observations: dict[str, Any],
        evidence_cids: set[str],
    ) -> Finding:
        """Deterministic evaluation fallback based on graph observations."""
        shared_links = observations.get("shared_attribute_links")
        clusters = observations.get("connected_components")
        outliers = observations.get("claim_amount_outliers")

        # Check for dense shared links (fraud ring indicator)
        if isinstance(shared_links, list) and len(shared_links) >= 1:
            # Check attribute types
            has_shared_bank = any(
                isinstance(x, dict) and x.get("attribute_type") == "BankAccount"
                for x in shared_links
            )
            has_shared_phone = any(
                isinstance(x, dict) and x.get("attribute_type") == "Phone"
                for x in shared_links
            )
            if has_shared_bank or has_shared_phone or len(shared_links) >= 2:
                return Finding(
                    agent_id=self.config.agent_id,
                    skill_id=self.config.skill_id,
                    target_cid=target_cid,
                    verdict="suspicious",
                    confidence=0.92,
                    reasoning=(
                        f"Customer {target_cid} shares high-risk financial/contact attributes "
                        f"(bank accounts or phone numbers) with {len(shared_links)} other entities."
                    ),
                    evidence_cids=sorted(evidence_cids),
                )

        # Check for large connected components
        if isinstance(clusters, list):
            target_cluster = next((cl for cl in clusters if target_cid in cl), None)
            if target_cluster and len(target_cluster) >= 4:
                return Finding(
                    agent_id=self.config.agent_id,
                    skill_id=self.config.skill_id,
                    target_cid=target_cid,
                    verdict="suspicious",
                    confidence=0.88,
                    reasoning=(
                        f"Customer {target_cid} is part of a densely connected component "
                        f"of {len(target_cluster)} entities in the slice graph."
                    ),
                    evidence_cids=sorted(evidence_cids),
                )

        # Check for claim amount outliers
        if isinstance(outliers, list) and len(outliers) > 0:
            target_outliers = [o for o in outliers if isinstance(o, dict) and o.get("cid") == target_cid]
            if target_outliers:
                return Finding(
                    agent_id=self.config.agent_id,
                    skill_id=self.config.skill_id,
                    target_cid=target_cid,
                    verdict="suspicious",
                    confidence=0.86,
                    reasoning=f"Customer {target_cid} filed claim amounts exceeding 2.0 standard deviations.",
                    evidence_cids=sorted(evidence_cids),
                )

        # Benign baseline
        return Finding(
            agent_id=self.config.agent_id,
            skill_id=self.config.skill_id,
            target_cid=target_cid,
            verdict="benign",
            confidence=0.85,
            reasoning=(
                f"Customer {target_cid} exhibits isolated, standard behavior with no shared high-risk "
                f"financial attributes or suspicious ring topology."
            ),
            evidence_cids=sorted(evidence_cids),
        )

    async def run(self) -> list[Finding]:
        """Execute autonomous observe-orient-decide-act loop over target CIDs."""
        findings: list[Finding] = []

        for target_cid in self.config.target_cids:
            observations, evidence_cids = await self._gather_observations(target_cid)

            # Try LLM synthesis first
            system_prompt = (
                f"You are sub-agent '{self.config.agent_id}' equipped with skill '{self.config.skill_id}'. "
                f"Skill instructions: {self.config.prompt_fragment}\n"
                "Evaluate the target entity based on observed graph evidence. "
                "Output JSON with keys: verdict ('suspicious' or 'benign'), confidence (0.0 to 1.0), "
                "reasoning (string), and evidence_cids (list of string CIDs)."
            )
            user_prompt = (
                f"Target entity CID: {target_cid}\n"
                f"Graph Tool Observations: {json.dumps(observations, default=str)}\n"
                f"Observed Evidence CIDs: {sorted(evidence_cids)}"
            )

            try:
                llm_response = self.llm_client.complete(
                    prompt=user_prompt,
                    system=system_prompt,
                    json_schema={"type": "object", "properties": {"verdict": {"type": "string"}}},
                )

                if isinstance(llm_response, dict) and "verdict" in llm_response:
                    verdict_val = str(llm_response.get("verdict", "")).lower()
                    if verdict_val in ("suspicious", "benign"):
                        findings.append(
                            Finding(
                                agent_id=self.config.agent_id,
                                skill_id=self.config.skill_id,
                                target_cid=target_cid,
                                verdict=verdict_val,  # type: ignore
                                confidence=float(llm_response.get("confidence", 0.85)),
                                reasoning=str(llm_response.get("reasoning", "LLM evaluation")),
                                evidence_cids=list(
                                    set(llm_response.get("evidence_cids", [])) | evidence_cids
                                ),
                            )
                        )
                        continue
            except Exception:
                pass

            # Fallback to deterministic heuristic evaluation
            heuristic_finding = self._heuristic_evaluate(target_cid, observations, evidence_cids)
            findings.append(heuristic_finding)

        return findings
