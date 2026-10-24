import json
from datetime import timedelta
from typing import Any, TypedDict
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph

from backend.common import Problem, identifier, instant, timestamp
from backend.inference.base import CompletionRequest, InferenceClient, InferenceError
from backend.privacy.service import envelope
from backend.protocol.validation import SCHEMAS, message


class RunState(TypedDict):
    data: dict[str, Any]
    envelopes: list[dict[str, Any]]
    candidates: list[dict[str, str]]
    index: int
    done: bool


def fits(availability: dict[str, Any], slot: dict[str, str], duration: int) -> bool:
    start, end = instant(slot["start"]), instant(slot["end"])
    if end - start < timedelta(minutes=duration):
        return False
    if start < instant(availability["window"]["start"]) or end > instant(
        availability["window"]["end"]
    ):
        return False
    prefs = availability.get("constraints", {})
    local_start = start.astimezone(ZoneInfo(availability["timezone"]))
    local_end = end.astimezone(ZoneInfo(availability["timezone"]))
    if local_start.hour < prefs.get("earliest_hour", 0) or local_end.hour > prefs.get(
        "latest_hour", 23
    ):
        return False
    if end - start < timedelta(minutes=prefs.get("min_duration_minutes", 5)):
        return False
    if any(
        x["state"] != "free" and instant(x["start"]) < end and instant(x["end"]) > start
        for x in availability["slots"]
    ):
        return False
    return any(
        x["state"] == "free" and instant(x["start"]) <= start and instant(x["end"]) >= end
        for x in availability["slots"]
    )


class Workflow:
    def __init__(self, inference: InferenceClient):
        self.inference = inference
        graph = StateGraph(RunState)
        graph.add_node("propose", self.propose)
        graph.add_node("evaluate", self.evaluate)
        graph.add_edge(START, "propose")
        graph.add_edge("propose", "evaluate")
        graph.add_conditional_edges(
            "evaluate",
            lambda s: "done" if s["done"] else "retry",
            {"done": END, "retry": "propose"},
        )
        self.graph = graph.compile()

    async def run(self, data: dict[str, Any]) -> dict[str, Any]:
        envelopes = [
            envelope(p["availability"], p["ceiling"], prompt=True) for p in data["members"].values()
        ]
        start, end = instant(data["window"]["start"]), instant(data["window"]["end"])
        duration = data["duration"]
        starts = {start}
        for availability in envelopes:
            for slot in availability["slots"]:
                starts.update((instant(slot["start"]), instant(slot["end"])))
        candidates = [
            {"start": t.isoformat(), "end": (t + timedelta(minutes=duration)).isoformat()}
            for t in sorted(starts)
            if start <= t and t + timedelta(minutes=duration) <= end
        ]
        result = await self.graph.ainvoke(
            {
                "data": data,
                "envelopes": envelopes,
                "candidates": candidates,
                "index": 0,
                "done": False,
            },
            {"recursion_limit": 64},
        )
        return dict(result["data"])

    async def propose(self, state: RunState) -> dict[str, Any]:
        data = state["data"]
        data["status"] = "negotiating"
        if state["index"] >= len(state["candidates"]) or data["round"] >= data["max_rounds"]:
            data["status"] = "failed"
            data["outcome"] = {
                "kind": "max_rounds_exceeded"
                if data["round"] >= data["max_rounds"]
                else "no_overlap",
                "requires_human_approval": True,
            }
            return {"done": True}
        data["round"] += 1
        owner, participant = next(iter(data["members"].items()))
        candidate = {
            "schema_version": "1.0",
            "message_id": identifier("msg"),
            "trace_id": data["trace_id"],
            "issued_at": timestamp(),
            "sender": {"agent_id": participant["agent_id"], "agent_version": "1"},
            "represented_student": {"student_ref": participant["student_ref"]},
            "scope": {
                "negotiation_id": data["negotiation_id"],
                "actions": ["propose", "counter", "escalate"],
                "expires_at": data["window"]["end"],
                "max_disclosure_level": "free_busy",
                "granted_by": "standing",
            },
            "disclosure_level": "free_busy",
            "intent": "propose",
            "payload": {"proposed_slot": state["candidates"][state["index"]]},
        }
        if data["messages"]:
            candidate["intent"] = "counter"
            candidate["in_reply_to"] = data["messages"][-1]["envelope"]["message_id"]
        try:
            result = await self.inference.complete(
                CompletionRequest(
                    messages=[
                        {
                            "role": "system",
                            "content": "Propose the candidate slot using only the supplied filtered availability. Return the candidate envelope.",
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {"candidate": candidate, "availability": state["envelopes"]}
                            ),
                        },
                    ],
                    max_tokens=2048,
                    temperature=0,
                    seed=0,
                    response_schema=SCHEMAS["agent-protocol.schema"],
                    trace_id=data["trace_id"],
                    timeout_s=10,
                )
            )
            if result.parsed is None:
                raise ValueError("missing output")
            message(result.parsed)
            # The model cannot change authority, identities, disclosure, or the offered time.
            if result.parsed != candidate:
                raise ValueError("model changed candidate")
        except (
            InferenceError,
            ValueError,
            Problem,
        ):
            data["status"] = "failed"
            data["outcome"] = {"kind": "no_overlap", "requires_human_approval": True}
            data["failure_reason"] = "needs_human"
            return {"done": True}
        data["messages"].append({"owner": owner, "envelope": candidate})
        data["proposals"].append(
            {
                "proposal_id": identifier("prp"),
                "slot": candidate["payload"]["proposed_slot"],
                "proposed_by": participant["agent_id"],
                "votes": [],
            }
        )
        return {}

    def evaluate(self, state: RunState) -> dict[str, Any]:
        if state["done"]:
            return {}
        data = state["data"]
        proposal = data["proposals"][-1]
        votes = [
            {
                "student_ref": member["student_ref"],
                "vote": "abstain"
                if fits(member["availability"], proposal["slot"], data["duration"])
                else "reject",
            }
            for member in data["members"].values()
        ]
        proposal["votes"] = votes
        if all(v["vote"] == "abstain" for v in votes):
            data["status"] = "awaiting_approval"
            return {"done": True}
        return {"index": state["index"] + 1}
