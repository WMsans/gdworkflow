from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from aiohttp import web as aiohttp_web
import nextcord
from nextcord.ext import commands

log = logging.getLogger("gdworkflow.bot")

GUILD_ID = int(os.environ["DISCORD_GUILD_ID"]) if os.environ.get("DISCORD_GUILD_ID") else None
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
HTTP_PORT = int(os.environ.get("BOT_HTTP_PORT", "8080"))


@dataclass
class Config:
    bot_token: str = BOT_TOKEN
    guild_id: int | None = GUILD_ID
    http_port: int = HTTP_PORT


def load_config() -> Config:
    return Config()


class DiscordBot(commands.Bot):
    async def _find_channel_by_name(self, name: str) -> nextcord.TextChannel | None:
        for guild in self.guilds:
            ch = nextcord.utils.get(guild.text_channels, name=name)
            if ch is not None:
                return ch
        return None

    async def post_to_channel(self, channel_name: str, message: str) -> bool:
        ch = await self._find_channel_by_name(channel_name)
        if ch is None:
            log.error("Channel not found: %s", channel_name)
            return False
        try:
            await ch.send(message)
        except nextcord.HTTPException as exc:
            log.error("Failed to send to #%s: %s", channel_name, exc)
            return False
        return True

    async def announce_milestone(self, tag: str, summary: str) -> bool:
        ch = await self._find_channel_by_name("milestones")
        if ch is None:
            log.error("Channel not found: milestones")
            return False
        content = (
            f"**Milestone Reached: {tag}**\n"
            f">{summary}"
        )
        try:
            await ch.send(content)
        except nextcord.HTTPException as exc:
            log.error("Failed to announce milestone: %s", exc)
            return False
        return True


def create_bot(cfg: Config) -> DiscordBot:
    intents = nextcord.Intents.default()
    intents.guilds = True
    intents.message_content = True
    bot = DiscordBot(intents=intents)

    @bot.slash_command(name="ping", description="Health check")
    async def _ping(interaction: nextcord.Interaction):
        await interaction.send("Pong!")

    return bot


async def _handle_post_update(request: aiohttp_web.Request) -> aiohttp_web.Response:
    bot: DiscordBot = request.app["bot"]
    try:
        body: dict[str, Any] = await request.json()
    except json.JSONDecodeError:
        return aiohttp_web.json_response({"ok": False, "error": "invalid json"}, status=400)

    channel = body.get("channel")
    message = body.get("message")
    if not channel or not message:
        return aiohttp_web.json_response(
            {"ok": False, "error": "fields 'channel' and 'message' are required"}, status=400
        )

    ok = await bot.post_to_channel(channel, message)
    if not ok:
        return aiohttp_web.json_response(
            {"ok": False, "error": f"channel '{channel}' not found or send failed"}, status=404
        )
    return aiohttp_web.json_response({"ok": True})


async def _handle_announce_milestone(request: aiohttp_web.Request) -> aiohttp_web.Response:
    bot: DiscordBot = request.app["bot"]
    try:
        body: dict[str, Any] = await request.json()
    except json.JSONDecodeError:
        return aiohttp_web.json_response({"ok": False, "error": "invalid json"}, status=400)

    tag = body.get("tag")
    summary = body.get("summary")
    if not tag or not summary:
        return aiohttp_web.json_response(
            {"ok": False, "error": "fields 'tag' and 'summary' are required"}, status=400
        )

    ok = await bot.announce_milestone(tag, summary)
    if not ok:
        return aiohttp_web.json_response(
            {"ok": False, "error": "milestone channel not found or send failed"}, status=404
        )
    return aiohttp_web.json_response({"ok": True})


async def _handle_health(_request: aiohttp_web.Request) -> aiohttp_web.Response:
    return aiohttp_web.json_response({"status": "ok"})


def create_http_app(bot: DiscordBot) -> aiohttp_web.Application:
    app = aiohttp_web.Application()
    app["bot"] = bot
    app.router.add_post("/post_update", _handle_post_update)
    app.router.add_post("/announce_milestone", _handle_announce_milestone)
    app.router.add_get("/health", _handle_health)
    return app


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cfg = load_config()
    if not cfg.bot_token:
        log.error("DISCORD_BOT_TOKEN is required")
        sys.exit(1)

    bot = create_bot(cfg)
    app = create_http_app(bot)
    runner = aiohttp_web.AppRunner(app)
    await runner.setup()
    site = aiohttp_web.TCPSite(runner, "0.0.0.0", cfg.http_port)
    await site.start()
    log.info("HTTP server listening on port %d", cfg.http_port)

    try:
        await bot.start(cfg.bot_token)
    finally:
        await runner.cleanup()
        await bot.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())