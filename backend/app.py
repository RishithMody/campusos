import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from backend.agents.workflow import Workflow
from backend.auth import authenticate
from backend.channels.discord import DiscordREST
from backend.common import Problem, identifier, instant, now
from backend.config import Settings
from backend.db.ephemeral import Ephemeral
from backend.db.models import Grant, Negotiation
from backend.db.session import database
from backend.inference.base import CompletionRequest, InferenceError
from backend.inference.mock import MockInference
from backend.inference.vllm_client import VLLMClient
from backend.protocol.validation import API, disclosure, temporal, validate
from backend.service import Service


def api_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve local OpenAPI references against the frozen document, not the network."""
    return cast(
        dict[str, Any],
        json.loads(json.dumps(schema).replace('"#/components/', '"urn:campusos:api#/components/')),
    )


def frame(event: str, payload: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def create_app(
    settings: Settings | None = None, *, sessions=None, ephemeral=None, inference=None, discord=None
) -> FastAPI:
    config = settings or Settings.from_env()
    if config.inference_mode not in {"mock", "vllm"}:
        raise ValueError("Explicit inference mode required")
    engine = None
    if sessions is None:
        engine, sessions = database(config.database_url)
    notifications = ephemeral or Ephemeral.connect(config.redis_url, config.redis_ttl)
    model = inference or (
        MockInference()
        if config.inference_mode == "mock"
        else VLLMClient(config.vllm_url, config.vllm_key, config.vllm_model)
    )
    workflow = Workflow(model)
    channel_client = discord or DiscordREST(config.discord_token)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if engine is not None:
            engine.dispose()
        if ephemeral is None:
            await notifications.client.aclose()

    # A synchronous SQL transaction may span an awaited model/Discord call. Serialize
    # handlers within this worker so another request cannot block its event loop on
    # that transaction's row lock. PostgreSQL locks coordinate separate workers.
    transaction_gate = asyncio.Lock()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        try:
            request.state.identity = authenticate(request.headers.get("authorization", ""), config)
            length = request.headers.get("content-length", "0")
            if not length.isdigit():
                raise Problem(400, "Invalid content length")
            if int(length) > 1_000_000:
                raise Problem(413, "Request too large")
            async with transaction_gate:
                return await call_next(request)
        except Problem as error:
            return JSONResponse(
                error.payload(), status_code=error.status, media_type="application/problem+json"
            )
        except (SQLAlchemyError, StaleDataError):
            failure = Problem(503, "Durable state unavailable")
            return JSONResponse(
                failure.payload(), status_code=503, media_type="application/problem+json"
            )

    @app.exception_handler(Problem)
    async def problem_handler(request: Request, error: Problem):
        return JSONResponse(
            error.payload(), status_code=error.status, media_type="application/problem+json"
        )

    def svc(session, identity):
        return Service(session, identity, workflow, channel_client)

    async def stream(request: Request, negotiation: str):
        identity = request.state.identity
        with sessions.begin() as session:
            service = svc(session, identity)
            _, data = service.load(negotiation)
            initial = service.view(data)
            dependencies = {
                g.id
                for g in session.scalars(
                    select(Grant).where(
                        Grant.negotiation == negotiation,
                        Grant.agent == initial["viewer"]["agent_id"],
                        Grant.revoked.is_(False),
                    )
                )
                if instant(g.expires) > now()
            }
            initial_visible = {x["agent_id"] for x in initial.get("transcript", [])}
        await notifications.ping()

        async def events():
            yield frame("state", initial)
            version = initial["state_version"]
            try:
                async with notifications.client.pubsub() as subscription:
                    await subscription.subscribe(f"updates:{negotiation}")
                    while not await request.is_disconnected():
                        if identity.expires <= now().timestamp():
                            raise Problem(401, "Authentication required")
                        # Poll DB too: durable state remains authoritative if publish failed after commit.
                        await subscription.get_message(ignore_subscribe_messages=True, timeout=0.25)
                        async with transaction_gate:
                            with sessions.begin() as session:
                                service = svc(session, identity)
                                _, data = service.load(negotiation)
                                for grant_id in dependencies:
                                    grant = session.get(Grant, grant_id)
                                    if (
                                        grant is None
                                        or grant.revoked
                                        or instant(grant.expires) <= now()
                                    ):
                                        raise Problem(403)
                                state = service.view(data)
                                visible = {x["agent_id"] for x in state.get("transcript", [])}
                                if not initial_visible.issubset(visible):
                                    raise Problem(403)
                        if state["state_version"] != version:
                            version = state["state_version"]
                            yield frame("state", state)
                        await asyncio.sleep(0.05)
            except (Problem, SQLAlchemyError, RedisError) as error:
                problem = (
                    error if isinstance(error, Problem) else Problem(503, "Stream unavailable")
                )
                yield frame("error", problem.payload())

        return StreamingResponse(
            events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"}
        )

    async def chat(request: Request, body: dict[str, Any]):
        intent = "explain" if "why" in body["message"].lower() else "coordinate"
        context: dict[str, Any] = {"intent": intent}
        notes = []
        with sessions.begin() as session:
            service = svc(session, request.state.identity)
            service.student()
            if body.get("negotiation_id"):
                _, data = service.load(body["negotiation_id"])
                context.update(status=data["status"], round=data["round"])
                if intent == "explain":
                    notes = [
                        r["envelope"]["payload"]["note_for_own_student"]
                        for r in data["messages"]
                        if r["owner"] == service.identity.subject
                        and "note_for_own_student" in r["envelope"]["payload"]
                    ][-3:]

        async def events():
            try:
                # Chat text may itself contain private calendar details; never forward it to inference.
                result = await model.complete(
                    CompletionRequest(
                        messages=[
                            {
                                "role": "user",
                                "content": json.dumps(context),
                            }
                        ],
                        max_tokens=256,
                        temperature=0,
                        seed=0,
                        response_schema=None,
                        trace_id=identifier("trc"),
                        timeout_s=10,
                    )
                )
                yield frame("delta", {"text": result.text})
                for note in notes:
                    yield frame("delta", {"text": "\n" + note})
                yield frame(
                    "done",
                    {
                        "message_id": identifier("msg"),
                        "finish_reason": result.finish_reason,
                    },
                )
            except InferenceError:
                yield frame("error", Problem(503, "Agent unavailable").payload())

        return StreamingResponse(events(), media_type="text/event-stream")

    def endpoint(path: str, method: str, operation: dict[str, Any]):
        async def handle(request: Request):
            body: dict[str, Any] = {}
            if "requestBody" in operation:
                raw = await request.body()
                if len(raw) > 1_000_000:
                    raise Problem(413, "Request too large")
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    raise Problem(400, "Invalid JSON") from None
                if not isinstance(body, dict):
                    raise Problem(400, "Invalid request")
                if path == "/me/availability":
                    with sessions() as session:
                        disclosure(body, svc(session, request.state.identity).student().ceiling)
                if path.endswith("/messages"):
                    from backend.protocol.validation import message

                    message(body)
                validate(
                    body,
                    api_schema(operation["requestBody"]["content"]["application/json"]["schema"]),
                )
                temporal(body)
            elif method in {"post", "put", "delete"} and await request.body():
                raise Problem(400, "This operation takes no body")
            params = {**request.path_params, **dict(request.query_params)}
            for parameter in API["paths"][path].get("parameters", []) + operation.get(
                "parameters", []
            ):
                name = parameter["name"]
                if parameter.get("required") and name not in params:
                    raise Problem(400, "Missing parameter")
                if name in params and parameter["schema"].get("type") == "string":
                    validate(params[name], parameter["schema"])
            if path.endswith("/stream"):
                return await stream(request, params["negotiation_id"])
            if path == "/me/chat":
                return await chat(request, body)
            changed = None
            status = 200
            result: Any = None
            if method != "get":
                await notifications.ping()
            with sessions.begin() as session:
                service = svc(session, request.state.identity)
                if path == "/health":
                    result = {"status": "ok", "version": "1.0.0"}
                elif path == "/me":
                    student = service.student()
                    if method == "post":
                        service.identity.human()
                        from backend.common import identifier

                        student.contact_handle = identifier("cnt")
                    result = {"contact_handle": student.contact_handle}
                elif path == "/me/availability":
                    changed = await service.availability(body)
                    status = 204
                elif path == "/negotiations" and method == "post":
                    result = await service.create(body)
                    changed, status = result["negotiation_id"], 201
                elif path == "/negotiations":
                    service.student()
                    try:
                        limit = int(params.get("limit", 20))
                    except ValueError:
                        raise Problem(400, "Invalid limit") from None
                    if not 1 <= limit <= 100:
                        raise Problem(400, "Invalid limit")
                    statuses = request.query_params.getlist("status")
                    if any(
                        s
                        not in {
                            "gathering",
                            "negotiating",
                            "awaiting_approval",
                            "converged",
                            "failed",
                            "expired",
                            "cancelled",
                        }
                        for s in statuses
                    ):
                        raise Problem(400, "Invalid status")
                    values = []
                    for row in session.scalars(select(Negotiation)):
                        if service.identity.subject not in row.data["members"]:
                            continue
                        _, data = service.load(row.id)
                        state = service.view(data)
                        if statuses and state["status"] not in statuses:
                            continue
                        item = {
                            k: state[k]
                            for k in ("negotiation_id", "status", "state_version", "updated_at")
                        }
                        item["awaiting_me"] = state["viewer"]["awaiting_me"]
                        if state.get("outcome", {}).get("agreed_slot"):
                            item["agreed_slot"] = state["outcome"]["agreed_slot"]
                        values.append(item)
                    result = {
                        "negotiations": sorted(values, key=lambda v: v["updated_at"], reverse=True)[
                            :limit
                        ]
                    }
                elif path == "/negotiations/{negotiation_id}":
                    _, data = service.load(params["negotiation_id"])
                    result = service.view(data)
                elif path.endswith("/messages"):
                    result = service.submit(params["negotiation_id"], body)
                    changed, status = params["negotiation_id"], 202
                elif path == "/approvals/{approval_id}":
                    result = service.decide(params["approval_id"], body)
                    changed = result["negotiation_id"]
                elif path == "/grants":
                    result = await service.grant(body)
                    changed, status = body["negotiation_id"], 201
                elif path == "/grants/{grant_id}":
                    changed = service.revoke(params["grant_id"])
                    status = 204
                elif path == "/channels":
                    result, status = await service.register_channel(body), 201
                elif path == "/channels/{channel_id}/members":
                    await service.link(params["channel_id"])
                    status = 204
                elif path.endswith("/channel-bindings"):
                    if method == "post":
                        result = await service.bind(params["negotiation_id"], body["channel_id"])
                        changed, status = params["negotiation_id"], 201
                    else:
                        _, data = service.load(params["negotiation_id"])
                        result = {
                            "bindings": [
                                service.binding_view(params["negotiation_id"], key, val)
                                for key, val in data["bindings"].items()
                            ]
                        }
                elif path.endswith("/channel-bindings/{channel_id}"):
                    service.withdraw(params["negotiation_id"], params["channel_id"])
                    changed, status = params["negotiation_id"], 204
                elif path.endswith("/channel-summary"):
                    result = await service.channel_summary(
                        params["negotiation_id"], params["channel_id"]
                    )
                    if result.get("denied"):
                        changed = params["negotiation_id"]
                else:
                    raise Problem(404, "Not found")
                if changed:
                    row = session.get(Negotiation, changed)
                    version = row.data["state_version"] if row else 0
                if status != 204 and not (isinstance(result, dict) and result.get("denied")):
                    response_schema = operation["responses"][str(status)]["content"][
                        "application/json"
                    ]["schema"]
                    validate(result, api_schema(response_schema))
            if changed:
                await notifications.publish(changed, version)
            if isinstance(result, dict) and result.get("denied"):
                raise Problem(403)
            return (
                Response(status_code=204)
                if status == 204
                else JSONResponse(result, status_code=status)
            )

        return handle

    for path, definition in API["paths"].items():
        for method, operation in definition.items():
            if method in {"get", "post", "put", "delete"}:
                app.add_api_route(
                    "/v1" + path, endpoint(path, method, operation), methods=[method.upper()]
                )
    return app
