"""Guild-only slash commands. No human tokens, calendar input, or model client."""

import asyncio
import logging
import os

import discord
from discord import app_commands

from groupchat.api import API, APIError, identifier
from groupchat.publisher import Publisher

UNAVAILABLE = "CampusOS is unavailable. Try again later; no action has been confirmed here."


class Bot(discord.Client):
    def __init__(self, api: API, guild_id: int):
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.api = api
        self.guild_id = guild_id
        self.tree = app_commands.CommandTree(self)
        self.watches: dict[int, asyncio.Task[None]] = {}
        self.tree.add_command(
            app_commands.Command(
                name="schedule",
                description="Start a private CampusOS scheduling flow",
                callback=self.schedule,
            )
        )
        self.tree.add_command(
            app_commands.Command(
                name="watch",
                description="Publish consented CampusOS updates for up to 15 minutes",
                callback=self.watch,
            )
        )
        self.tree.error(self.command_error)

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    def room(self, interaction: discord.Interaction) -> discord.TextChannel | None:
        if interaction.guild_id == self.guild_id and isinstance(
            interaction.channel, discord.TextChannel
        ):
            return interaction.channel
        return None

    async def schedule(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        room = self.room(interaction)
        if room is None:
            await interaction.followup.send(
                "Use a text channel in the configured server.", ephemeral=True
            )
            return
        try:
            channel = await self.api.register(room.id)
        except APIError:
            await interaction.followup.send(UNAVAILABLE, ephemeral=True)
            return
        await interaction.followup.send(
            "Use the CampusOS student terminal client on your own device. "
            "Each student links their account and shares free/busy availability privately. "
            "One participant creates the plan and requests channel consent; everyone reviews "
            "and decides individually. No credentials or availability belong in this chat.\n"
            f"Channel reference: `{channel}`\n"
            "Follow groupchat/README.md, then run /watch with the negotiation reference "
            "after everyone has approved channel sharing.",
            ephemeral=True,
        )

    async def watch(self, interaction: discord.Interaction, negotiation: str) -> None:
        await interaction.response.defer(ephemeral=True)
        room = self.room(interaction)
        try:
            identifier(negotiation, "neg")
        except ValueError:
            await interaction.followup.send("Use a valid negotiation reference.", ephemeral=True)
            return
        if room is None:
            await interaction.followup.send(
                "Use a text channel in the configured server.", ephemeral=True
            )
            return
        active = self.watches.get(room.id)
        if active is not None and not active.done():
            await interaction.followup.send(
                "This channel already has an active watcher.", ephemeral=True
            )
            return
        try:
            channel = await self.api.register(room.id)
        except APIError:
            await interaction.followup.send(UNAVAILABLE, ephemeral=True)
            return
        # Same acknowledgement for missing, declined, pending and confirmed bindings.
        await interaction.followup.send(
            "Request received. Only authorized updates can appear in this channel.", ephemeral=True
        )
        self.watches[room.id] = asyncio.create_task(self.publish(room, negotiation, channel))

    async def publish(self, room: discord.TextChannel, negotiation: str, channel: str) -> None:
        publisher = Publisher(self.api)

        async def send(text: str) -> None:
            await room.send(text, allowed_mentions=discord.AllowedMentions.none())

        try:
            for _ in range(90):
                if not await publisher.update(negotiation, channel, send):
                    break
                await asyncio.sleep(10)
        except Exception:
            # Discord exceptions can contain response content; never log their repr/traceback.
            logging.getLogger(__name__).warning("Channel watcher stopped.")

    async def command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(UNAVAILABLE, ephemeral=True)
        else:
            await interaction.response.send_message(UNAVAILABLE, ephemeral=True)

    async def close(self) -> None:
        for task in self.watches.values():
            task.cancel()
        await asyncio.gather(*self.watches.values(), return_exceptions=True)
        await self.api.close()
        await super().close()


def main() -> None:
    # Disable third-party logs which may embed HTTP response details.
    logging.getLogger("discord").disabled = True
    logging.getLogger("httpx").disabled = True
    try:
        api = API(os.environ["CAMPUSOS_API_URL"], os.environ["CAMPUSOS_BOT_TOKEN"])
        bot = Bot(api, int(os.environ["DISCORD_GUILD_ID"]))
        bot.run(os.environ["DISCORD_BOT_TOKEN"], log_handler=None)
    except KeyError as missing:
        # A variable NAME, never its value.
        raise SystemExit(f"Bot startup failed: {missing.args[0]} is not set.") from None
    except (ValueError, discord.DiscordException) as failure:
        # The exception's class name, and nothing else. A Discord exception's message and
        # traceback can embed response content, so neither is reported -- but a bare
        # "startup failed" leaves an operator with nothing at all, which is how this bot
        # exited mid-session on 2026-10-25 with no way to tell a dropped gateway from a
        # bad credential. A class name carries no response content.
        raise SystemExit(
            f"Bot startup failed ({type(failure).__name__}). "
            "Check environment and Discord configuration."
        ) from None


if __name__ == "__main__":
    main()
