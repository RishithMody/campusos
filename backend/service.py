from copy import deepcopy
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agents.workflow import Workflow, fits
from backend.auth import Identity
from backend.channels.discord import Discord
from backend.channels.summary import summary
from backend.common import Problem, identifier, instant, now, timestamp
from backend.db.models import Approval, Channel, Commitment, Grant, Negotiation, Student
from backend.privacy.service import audit, granted, outbound
from backend.protocol.validation import LEVELS, contract, disclosure, message

TERMINAL = {"converged", "failed", "expired", "cancelled"}


class Service:
    def __init__(self, session: Session, identity: Identity, workflow: Workflow, discord: Discord):
        self.session, self.identity, self.workflow, self.discord = (
            session,
            identity,
            workflow,
            discord,
        )

    def student(self) -> Student:
        student = self.session.get(Student, self.identity.subject)
        if student is None or self.identity.kind == "bot":
            raise Problem(403)
        if self.identity.kind == "agent" and self.identity.agent_id != student.agent_id:
            raise Problem(403)
        return student

    def load(
        self, negotiation: str, participant: bool = True
    ) -> tuple[Negotiation, dict[str, Any]]:
        row = self.session.scalar(
            select(Negotiation).where(Negotiation.id == negotiation).with_for_update()
        )
        if row is None:
            raise Problem(403)
        data = deepcopy(row.data)
        if participant:
            self.student()
            if self.identity.subject not in data["members"]:
                raise Problem(403)
        if data["status"] not in TERMINAL and instant(data["window"]["end"]) <= now():
            data["status"] = "expired"
            data["outcome"] = {"kind": "timed_out", "requires_human_approval": True}
            self.save(row, data)
        return row, data

    def pending(self, negotiation: str) -> list[Approval]:
        return list(
            self.session.scalars(
                select(Approval).where(
                    Approval.negotiation == negotiation, Approval.decision.is_(None)
                )
            )
        )

    def save(self, row: Negotiation, data: dict[str, Any]) -> None:
        data["state_version"] += 1
        data["updated_at"] = timestamp()
        row.data = deepcopy(data)
        # Refresh undecided previews after version movement; decisions stay immutable.
        for approval in self.pending(row.id):
            details = deepcopy(approval.data)
            details["state_version"] = data["state_version"]
            approval.data = details
        self.session.flush()

    def approval(
        self, data: dict[str, Any], owner: str, action: str, target: str | None = None
    ) -> None:
        ref = data["members"][owner]["student_ref"]
        recipients = [p["student_ref"] for p in data["members"].values() if p["student_ref"] != ref]
        details: dict[str, Any] = {
            "approval_id": identifier("apr"),
            "action": action,
            "discloses": {
                "disclosure_level": "free_busy",
                "to": [target] if target else recipients,
                "summary": "Share a fixed coordination summary with this channel."
                if target
                else "Confirm the proposed time with the other participants.",
                "fields": ["status", "participant_count", "agreed_slot"]
                if target
                else ["proposed_slot.start", "proposed_slot.end"],
            },
            "expires_at": min(
                now() + timedelta(hours=24), instant(data["window"]["end"])
            ).isoformat(),
            "state_version": data["state_version"],
        }
        if target:
            details["channel_id"] = target
            size = data["bindings"][target]["size"]
            details["discloses"]["summary"] = (
                f"Share a fixed coordination summary with {size} channel accounts, including nonparticipants."
            )
        else:
            details["proposal_id"] = data["proposals"][-1]["proposal_id"]
            slot = data["proposals"][-1]["slot"]
            details["discloses"]["summary"] = (
                f"Confirm {slot['start']} to {slot['end']} with the other participants."
            )
        self.session.add(
            Approval(
                id=details["approval_id"],
                owner=owner,
                negotiation=data["negotiation_id"],
                data=details,
            )
        )

    def retire_channel_approvals(self, negotiation: str, channel: str) -> None:
        for approval in self.pending(negotiation):
            if approval.data.get("channel_id") == channel:
                approval.decision = "superseded"
                audit(self.session, "system", "approval_superseded", approval.id)

    def view(self, data: dict[str, Any]) -> dict[str, Any]:
        caller = self.identity.subject
        member = data["members"][caller]
        pending = []
        for row in self.pending(data["negotiation_id"]):
            if (
                row.owner == caller
                and instant(row.data["expires_at"]) > now()
                and data["status"] not in {"expired", "cancelled"}
            ):
                pending.append({k: v for k, v in row.data.items() if k != "channel_id"})
        result = {
            k: deepcopy(data[k])
            for k in (
                "schema_version",
                "negotiation_id",
                "trace_id",
                "state_version",
                "status",
                "round",
                "max_rounds",
                "updated_at",
            )
        }
        result["viewer"] = {
            "student_ref": member["student_ref"],
            "agent_id": member["agent_id"],
            "max_disclosure_level": member["ceiling"],
            "awaiting_me": bool(pending),
            "state": member["state"],
        }
        result["participants"] = [
            {
                "student_ref": p["student_ref"],
                "agent_id": p["agent_id"],
                "state": p["state"],
                "disclosure_level": p["ceiling"],
            }
            for p in data["members"].values()
        ]
        result["pending_approvals"] = pending
        transcript = []
        visible_agents = {member["agent_id"]}
        for record in data["messages"]:
            msg = record["envelope"]
            try:
                payload, level = outbound(
                    self.session,
                    data,
                    record["owner"],
                    caller,
                    data["negotiation_id"],
                    msg["payload"],
                    msg["disclosure_level"],
                )
            except Problem as error:
                if error.status == 403:
                    continue
                raise
            visible_agents.add(msg["sender"]["agent_id"])
            transcript.append(
                {
                    "at": msg["issued_at"],
                    "agent_id": msg["sender"]["agent_id"],
                    "intent": msg["intent"],
                    "disclosure_level": level,
                    "message_id": msg["message_id"],
                    "disclosed": {
                        k: v for k, v in payload.items() if k in {"availability", "proposed_slot"}
                    },
                    **({"reason_code": payload["reason_code"]} if "reason_code" in payload else {}),
                }
            )
        result["transcript"] = transcript
        result["proposals"] = [
            deepcopy(p) for p in data["proposals"] if p["proposed_by"] in visible_agents
        ]
        # Votes also cross the boundary: do not publish a participant's vote after grant revocation.
        for proposal in result["proposals"]:
            proposal["votes"] = [
                v
                for v in proposal["votes"]
                if v["student_ref"] == member["student_ref"]
                or self.can_read_ref(data, v["student_ref"])
            ]
        if "outcome" in data:
            result["outcome"] = deepcopy(data["outcome"])
        contract(result, "negotiation-state")
        return result

    def can_read_ref(self, data: dict[str, Any], ref: str) -> bool:
        owner = next(k for k, p in data["members"].items() if p["student_ref"] == ref)
        try:
            granted(
                self.session,
                owner,
                data["members"][self.identity.subject]["agent_id"],
                data["negotiation_id"],
            )
            audit(self.session, self.identity.subject, "cross_student_vote", data["negotiation_id"])
            return True
        except Problem:
            return False

    async def advance(self, row: Negotiation, data: dict[str, Any]) -> None:
        if data["status"] != "gathering" or not all(
            "availability" in p for p in data["members"].values()
        ):
            return
        # Every cross-student read needs explicit, live grants. A creator cannot grant for invitees.
        try:
            for owner in data["members"]:
                for recipient, participant in data["members"].items():
                    if owner != recipient:
                        ceiling = granted(self.session, owner, participant["agent_id"], row.id)
                        if LEVELS.index(ceiling) < LEVELS.index(
                            data["members"][owner]["availability"]["disclosure_level"]
                        ):
                            return
                        audit(self.session, recipient, "negotiation_read", row.id, ceiling)
        except Problem:
            return
        data.update(await self.workflow.run(data))
        if data["status"] == "awaiting_approval":
            for owner in data["members"]:
                self.approval(data, owner, "commit_slot")
        self.save(row, data)

    async def create(self, body: dict[str, Any]) -> dict[str, Any]:
        self.identity.human()
        caller = self.student()
        members = {caller.id: caller}
        for handle in body["invitees"]:
            student = self.session.scalar(select(Student).where(Student.contact_handle == handle))
            if student is None or student.id in members:
                raise Problem(403)
            members[student.id] = student
        if instant(body["window"]["end"]) <= now():
            raise Problem(400, "Window has expired")
        data = {
            "schema_version": "1.0",
            "negotiation_id": identifier("neg"),
            "trace_id": identifier("trc"),
            "state_version": 0,
            "status": "gathering",
            "round": 0,
            "max_rounds": body["max_rounds"],
            "updated_at": timestamp(),
            "window": body["window"],
            "duration": body.get("min_duration_minutes", 60),
            "title": body.get("title"),
            "proposals": [],
            "messages": [],
            "bindings": {},
            "members": {
                key: {
                    "student_ref": identifier("stu"),
                    "agent_id": value.agent_id,
                    "ceiling": value.ceiling,
                    "state": "invited",
                }
                for key, value in members.items()
            },
        }
        row = Negotiation(id=data["negotiation_id"], data=data)
        self.session.add(row)
        self.session.flush()
        audit(self.session, caller.id, "create_negotiation", row.id)
        return self.view(data)

    async def availability(self, body: dict[str, Any]) -> str:
        student = self.student()
        disclosure(body, student.ceiling)
        contract(body, "availability")
        # The opaque reference is a subject identifier, never authentication.
        for row in self.session.scalars(select(Negotiation).with_for_update()):
            data = deepcopy(row.data)
            participant = data["members"].get(student.id)
            if participant and participant["student_ref"] == body["student_ref"]:
                if data["status"] != "gathering" or instant(data["window"]["end"]) <= now():
                    raise Problem(409, "Availability collection closed")
                if instant(body["window"]["start"]) != instant(data["window"]["start"]) or instant(
                    body["window"]["end"]
                ) != instant(data["window"]["end"]):
                    raise Problem(400, "Availability must match the negotiation window")
                participant["availability"] = body
                participant["state"] = "shared_availability"
                self.save(row, data)
                await self.advance(row, data)
                return row.id
        raise Problem(403)

    async def grant(self, body: dict[str, Any]) -> dict[str, Any]:
        self.identity.human()
        owner = self.student()
        row, data = self.load(body["negotiation_id"])
        if body["grantee_agent_id"] not in [
            p["agent_id"] for k, p in data["members"].items() if k != owner.id
        ]:
            raise Problem(403)
        if instant(body["expires_at"]) <= now() or instant(body["expires_at"]) > instant(
            data["window"]["end"]
        ):
            raise Problem(400, "Grant expiry outside negotiation window")
        if LEVELS.index(body["max_disclosure_level"]) > LEVELS.index(owner.ceiling):
            raise Problem(403)
        grant = Grant(
            id=identifier("grt"),
            owner=owner.id,
            agent=body["grantee_agent_id"],
            negotiation=row.id,
            level=body["max_disclosure_level"],
            expires=body["expires_at"],
        )
        self.session.add(grant)
        audit(self.session, owner.id, "grant_created", grant.id, row.id)
        self.session.flush()
        self.save(row, data)
        await self.advance(row, data)
        return {"grant_id": grant.id, "expires_at": grant.expires}

    def revoke(self, grant_id: str) -> str:
        self.identity.human()
        grant = self.session.get(Grant, grant_id)
        if grant is None or grant.owner != self.identity.subject:
            raise Problem(403)
        row, data = self.load(grant.negotiation)
        grant.revoked = True
        audit(self.session, self.identity.subject, "grant_revoked", grant.id)
        self.save(row, data)
        return row.id

    def submit(self, negotiation: str, body: dict[str, Any]) -> dict[str, Any]:
        message(body)
        row, data = self.load(negotiation)
        participant = data["members"][self.identity.subject]
        scope = body["scope"]
        if (
            (
                data["status"] in TERMINAL
                and not (data["status"] == "converged" and body["intent"] == "accept")
            )
            or (data["status"] == "awaiting_approval" and body["intent"] != "accept")
            or body["represented_student"]["student_ref"] != participant["student_ref"]
            or body["sender"]["agent_id"] != participant["agent_id"]
            or body["trace_id"] != data["trace_id"]
            or scope["negotiation_id"] != negotiation
            or instant(scope["expires_at"]) <= now()
            or instant(scope["expires_at"]) > instant(data["window"]["end"])
            or body["intent"] not in scope["actions"]
            or LEVELS.index(scope["max_disclosure_level"]) > LEVELS.index(participant["ceiling"])
        ):
            raise Problem(403)
        if any(
            record["envelope"]["message_id"] == body["message_id"] for record in data["messages"]
        ):
            raise Problem(409, "Duplicate message")
        if body["intent"] in {"accept", "counter"}:
            if not data["messages"] or body["in_reply_to"] != next(
                (
                    r["envelope"]["message_id"]
                    for r in reversed(data["messages"])
                    if r["envelope"]["intent"] in {"propose", "counter"}
                ),
                None,
            ):
                raise Problem(403)
        if body["intent"] == "accept":
            approvals = self.session.scalars(
                select(Approval).where(
                    Approval.owner == self.identity.subject,
                    Approval.negotiation == row.id,
                    Approval.decision == "approve",
                )
            )
            if not data["proposals"] or not any(
                a.data.get("proposal_id") == data["proposals"][-1]["proposal_id"] for a in approvals
            ):
                raise Problem(403)
            if set(body["payload"]) - {"note_for_own_student", "proposed_slot"}:
                raise Problem(403)
            if (
                body["payload"].get("proposed_slot", data["proposals"][-1]["slot"])
                != data["proposals"][-1]["slot"]
            ):
                raise Problem(403)
        if "availability" in body["payload"]:
            available = body["payload"]["availability"]
            if available["student_ref"] != participant["student_ref"] or any(
                instant(available["window"][key]) != instant(data["window"][key])
                for key in ("start", "end")
            ):
                raise Problem(403)
        if body["intent"] in {"propose", "counter"}:
            slot = body["payload"]["proposed_slot"]
            if instant(slot["start"]) < instant(data["window"]["start"]) or instant(
                slot["end"]
            ) > instant(data["window"]["end"]):
                raise Problem(400, "Proposal outside window")
        # Refuse an over-disclosing message loudly, never silently downgrade it.
        for owner, member in data["members"].items():
            if owner != self.identity.subject:
                ceiling = granted(self.session, self.identity.subject, member["agent_id"], row.id)
                if LEVELS.index(body["disclosure_level"]) > LEVELS.index(ceiling):
                    raise Problem(422, "Disclosure violation")
        if len(data["messages"]) >= 200 or (
            data["round"] >= data["max_rounds"] and body["intent"] != "accept"
        ):
            raise Problem(409, "Negotiation bound reached")
        data["messages"].append({"owner": self.identity.subject, "envelope": body})
        if body["intent"] == "accept":
            self.save(row, data)
            return self.view(data)
        data["round"] += 1
        data["status"] = "negotiating"
        if body["intent"] in {"propose", "counter"}:
            proposal = {
                "proposal_id": identifier("prp"),
                "slot": body["payload"]["proposed_slot"],
                "proposed_by": participant["agent_id"],
                "votes": [],
            }
            data["proposals"].append(proposal)
            # Authorise BEFORE inspecting anyone else's availability, including failed proposals.
            for owner in data["members"]:
                if owner != self.identity.subject:
                    granted(self.session, owner, participant["agent_id"], row.id)
                    audit(self.session, self.identity.subject, "proposal_availability_read", row.id)
            if all(
                "availability" in p and fits(p["availability"], proposal["slot"], data["duration"])
                for p in data["members"].values()
            ):
                data["status"] = "awaiting_approval"
                for owner in data["members"]:
                    self.approval(data, owner, "commit_slot")
        if body["intent"] == "escalate" or (
            data["round"] >= data["max_rounds"] and data["status"] == "negotiating"
        ):
            data["status"] = "failed"
            data["outcome"] = {
                "kind": "max_rounds_exceeded" if body["intent"] != "escalate" else "no_overlap",
                "requires_human_approval": True,
            }
        self.save(row, data)
        return self.view(data)

    def decide(self, approval_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self.identity.human()
        approval = self.session.get(Approval, approval_id)
        if approval is None or approval.owner != self.identity.subject:
            raise Problem(403)
        row, data = self.load(approval.negotiation)
        self.session.refresh(approval)
        if (
            approval.decision
            or instant(approval.data["expires_at"]) <= now()
            or body["state_version"] != data["state_version"]
            or data["status"] in {"cancelled", "expired"}
        ):
            raise Problem(409, "Approval expired, decided or stale")
        approval.decision = body["decision"]
        approval.decided_at = timestamp()
        approval.decided_version = data["state_version"]
        audit(self.session, self.identity.subject, "human_approval", approval.id, body["decision"])
        if approval.data["action"] == "commit_slot":
            if data["status"] != "awaiting_approval":
                raise Problem(409, "Proposal no longer current")
            proposal = data["proposals"][-1]
            ref = data["members"][self.identity.subject]["student_ref"]
            proposal["votes"] = [v for v in proposal["votes"] if v["student_ref"] != ref]
            proposal["votes"].append(
                {
                    "student_ref": ref,
                    "vote": "accept" if body["decision"] == "approve" else "reject",
                }
            )
            if body["decision"] == "decline":
                data["status"] = "cancelled"
                data["outcome"] = {"kind": "withdrawn", "requires_human_approval": False}
                data["members"][self.identity.subject]["state"] = "declined"
            else:
                data["members"][self.identity.subject]["state"] = "accepted"
                if all(p["state"] == "accepted" for p in data["members"].values()):
                    data["status"] = "converged"
                    slot = data["proposals"][-1]["slot"]
                    data["outcome"] = {
                        "kind": "agreed",
                        "agreed_slot": slot,
                        "requires_human_approval": False,
                    }
                    for owner in data["members"]:
                        self.session.add(
                            Commitment(
                                id=identifier("com"),
                                owner=owner,
                                data={**slot, "negotiation_id": row.id},
                            )
                        )
        else:
            binding = data["bindings"][approval.data["channel_id"]]
            if binding["status"] not in {"pending_consent", "pending_reconsent"}:
                raise Problem(409, "Consent no longer pending")
            binding["decisions"][self.identity.subject] = body["decision"]
            if body["decision"] == "decline":
                binding["status"] = "declined"
                self.session.flush()
                self.retire_channel_approvals(row.id, approval.data["channel_id"])
            elif all(v == "approve" for v in binding["decisions"].values()):
                binding["status"] = "confirmed"
                binding["confirmed_at"] = timestamp()
        self.save(row, data)
        return self.view(data)

    async def register_channel(self, body: dict[str, Any]) -> dict[str, Any]:
        if self.identity.kind != "bot" or not self.identity.guild:
            raise Problem(403)
        audience = await self.discord.audience(body["platform_channel_id"], self.identity.guild)
        existing = self.session.scalar(
            select(Channel).where(Channel.platform_id == body["platform_channel_id"])
        )
        if existing:
            if existing.bot != self.identity.subject:
                raise Problem(403)
            return {"channel_id": existing.id, "confirmed": False}
        channel = Channel(
            id=identifier("chn"),
            platform_id=body["platform_channel_id"],
            guild=audience.guild,
            bot=self.identity.subject,
            level=body["max_disclosure_level"],
            data={"timezone": audience.timezone, "members": []},
        )
        self.session.add(channel)
        audit(self.session, self.identity.subject, "register_channel", channel.id)
        return {"channel_id": channel.id, "confirmed": False}

    async def link(self, channel_id: str) -> None:
        self.identity.human()
        student = self.student()
        channel = self.session.get(Channel, channel_id)
        if (
            channel is None
            or not student.discord_id
            or not await self.discord.member(channel.platform_id, channel.guild, student.discord_id)
        ):
            raise Problem(403)
        data = deepcopy(channel.data)
        data["members"] = sorted(set(data["members"]) | {student.id})
        channel.data = data
        audit(self.session, student.id, "link_channel", channel.id)

    def binding_view(
        self, negotiation: str, channel: str, binding: dict[str, Any]
    ) -> dict[str, Any]:
        result = {
            "channel_id": channel,
            "negotiation_id": negotiation,
            "status": binding["status"],
            "confirmations_outstanding": sum(v is None for v in binding["decisions"].values()),
            "max_disclosure_level": binding["level"],
            "audience_size_at_consent": binding["size"],
        }
        if "confirmed_at" in binding:
            result["confirmed_at"] = binding["confirmed_at"]
        return result

    async def bind(self, negotiation: str, channel_id: str) -> dict[str, Any]:
        self.identity.human()
        row, data = self.load(negotiation)
        channel = self.session.get(Channel, channel_id)
        if channel is None or self.identity.subject not in channel.data["members"]:
            raise Problem(403)
        audience = await self.discord.audience(channel.platform_id, channel.guild)
        old = data["bindings"].get(channel_id)
        if old and old["status"] in {"pending_consent", "confirmed", "pending_reconsent"}:
            raise Problem(409, "Binding already active")
        if len(data["bindings"]) >= 10:
            raise Problem(409, "Binding limit reached")
        binding = {
            "status": "pending_consent",
            "level": channel.level,
            "size": audience.size,
            "decisions": {owner: None for owner in data["members"]},
        }
        self.retire_channel_approvals(negotiation, channel_id)
        data["bindings"][channel_id] = binding
        for owner in data["members"]:
            self.approval(data, owner, "post_to_channel", channel_id)
        self.save(row, data)
        return self.binding_view(negotiation, channel_id, binding)

    def withdraw(self, negotiation: str, channel_id: str) -> None:
        self.identity.human()
        row, data = self.load(negotiation)
        binding = data["bindings"].get(channel_id)
        if binding is None:
            raise Problem(403)
        self.retire_channel_approvals(negotiation, channel_id)
        binding["status"] = "withdrawn"
        audit(self.session, self.identity.subject, "channel_consent_withdrawn", channel_id)
        self.save(row, data)

    async def channel_summary(self, negotiation: str, channel_id: str) -> dict[str, Any]:
        channel = self.session.get(Channel, channel_id)
        if (
            self.identity.kind != "bot"
            or channel is None
            or channel.bot != self.identity.subject
            or channel.guild != self.identity.guild
        ):
            raise Problem(403)
        row, data = self.load(negotiation, participant=False)
        binding = data["bindings"].get(channel_id)
        if not binding or binding["status"] != "confirmed":
            raise Problem(403)
        audience = await self.discord.audience(channel.platform_id, channel.guild)
        if audience.size > binding["size"]:
            binding.update(
                status="pending_reconsent",
                size=audience.size,
                decisions={owner: None for owner in data["members"]},
            )
            binding.pop("confirmed_at", None)
            for owner in data["members"]:
                self.approval(data, owner, "post_to_channel", channel_id)
            self.save(row, data)
            # Caller commits this transition before emitting the uniform 403.
            return {"denied": True}
        audit(self.session, self.identity.subject, "channel_disclosure", row.id, channel.id)
        return summary(data, channel.data["timezone"])
