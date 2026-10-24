"""Private terminal companion, run by the student, never imported by the bot."""

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from groupchat.api import API, APIError, identifier


async def decide(api: API, negotiation: str, approval_id: str) -> None:
    state = await api.request("GET", f"negotiations/{negotiation}")
    approval = next(
        (a for a in state["pending_approvals"] if a["approval_id"] == approval_id), None
    )
    if approval is None:
        print("No current approval matches. Read your state again.")
        return
    # JSON escaping prevents server text from injecting terminal control sequences.
    print(json.dumps(approval, indent=2, ensure_ascii=True))
    for proposal in state.get("proposals", []):
        if proposal["proposal_id"] == approval.get("proposal_id"):
            print(json.dumps(proposal["slot"], indent=2, ensure_ascii=True))
    choice = await asyncio.to_thread(input, "Type approve or decline (anything else cancels): ")
    if choice not in {"approve", "decline"}:
        print("Cancelled.")
        return
    await api.request(
        "POST",
        f"approvals/{approval_id}",
        {
            "decision": choice,
            "state_version": approval["state_version"],
        },
    )
    print("Decision recorded.")


async def run(args: argparse.Namespace) -> None:
    api = API(os.environ["CAMPUSOS_API_URL"], os.environ["CAMPUSOS_HUMAN_TOKEN"])
    try:
        neg = identifier(args.negotiation, "neg") if hasattr(args, "negotiation") else None
        channel = identifier(args.channel, "chn") if hasattr(args, "channel") else None
        result: Any = None
        if args.command == "me":
            result = await api.request("GET", "me")
        elif args.command == "list":
            result = await api.request("GET", "negotiations")
        elif args.command == "state":
            result = await api.request("GET", f"negotiations/{neg}")
        elif args.command == "link":
            result = await api.request("POST", f"channels/{channel}/members")
        elif args.command == "bind":
            result = await api.request(
                "POST", f"negotiations/{neg}/channel-bindings", {"channel_id": channel}
            )
        elif args.command == "bindings":
            result = await api.request("GET", f"negotiations/{neg}/channel-bindings")
        elif args.command == "withdraw":
            result = await api.request("DELETE", f"negotiations/{neg}/channel-bindings/{channel}")
        elif args.command == "decide":
            await decide(api, identifier(args.negotiation, "neg"), identifier(args.approval, "apr"))
            return
        elif args.command in {"create", "availability", "grant"}:
            body = json.loads(await asyncio.to_thread(Path(args.file).read_text))
            print(json.dumps(body, indent=2, ensure_ascii=True))
            answer = await asyncio.to_thread(input, "Send this to CampusOS? Type yes: ")
            if answer != "yes":
                print("Cancelled.")
                return
            method, path = {
                "create": ("POST", "negotiations"),
                "availability": ("PUT", "me/availability"),
                "grant": ("POST", "grants"),
            }[args.command]
            result = await api.request(method, path, body)
        print(
            json.dumps(result, indent=2, ensure_ascii=True) if result is not None else "Recorded."
        )
    finally:
        await api.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("me", "list"):
        commands.add_parser(name)
    for name in ("create", "availability", "grant"):
        commands.add_parser(name).add_argument("file", help="Private JSON file; never commit it")
    commands.add_parser("link").add_argument("channel")
    for name in ("state", "bindings", "bind", "withdraw", "decide"):
        sub = commands.add_parser(name)
        sub.add_argument("negotiation")
        if name in {"bind", "withdraw"}:
            sub.add_argument("channel")
        if name == "decide":
            sub.add_argument("approval")
    try:
        asyncio.run(run(parser.parse_args()))
    except APIError as error:
        message = (
            "State changed or decision expired. Read again and review a fresh preview."
            if error.status == 409
            else "Request failed. Check access or service availability."
        )
        raise SystemExit(message) from None
    except (KeyError, ValueError, OSError):
        raise SystemExit("Check environment, identifiers and input file format.") from None


if __name__ == "__main__":
    main()
