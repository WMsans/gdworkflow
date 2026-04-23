from __future__ import annotations

import json
import logging
import os
import sys
import asyncio
import uuid
from dataclasses import dataclass, field
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
QUESTION_TIMEOUT = int(os.environ.get("QUESTION_TIMEOUT", "300"))


@dataclass
class PendingQuestion:
    question_id: str
    agent_id: str
    feature: str
    question: str
    thread_id: int | None = None
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_event_loop().create_future())
    status: str = "pending"


@dataclass
class Config:
    bot_token: str = BOT_TOKEN
    guild_id: int | None = GUILD_ID
    http_port: int = HTTP_PORT
    question_timeout: int = QUESTION_TIMEOUT


def load_config() -> Config:
    return Config()


class DiscordBot(commands.Bot):
    def __init__(self, guild_id: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self.target_guild_id: int | None = guild_id
        self._ready_event = asyncio.Event()
        self.pending_questions: dict[str, PendingQuestion] = {}

    async def on_ready(self):
        log.info("Bot ready. Guilds: %s", [g.name for g in self.guilds])
        for g in self.guilds:
            log.info("  %s (id=%d) channels: %s", g.name, g.id, [c.name for c in g.text_channels])
        self._ready_event.set()

    async def wait_until_cache_ready(self, timeout: float = 10.0) -> bool:
        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _find_channel_by_name(self, name: str) -> nextcord.TextChannel | None:
        if not await self.wait_until_cache_ready():
            log.warning("Cache not ready when looking for channel '%s'", name)

        if self.target_guild_id is not None:
            guild = self.get_guild(self.target_guild_id)
            if guild is not None:
                ch = nextcord.utils.get(guild.text_channels, name=name)
                if ch is not None:
                    return ch

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

    async def create_question_thread(self, pq: PendingQuestion) -> int | None:
        ch = await self._find_channel_by_name("features")
        if ch is None:
            log.error("Channel not found: features")
            return None
        try:
            thread_name = f"Q: {pq.feature} — {pq.agent_id}"
            msg = await ch.send(
                f"**Clarifying Question from {pq.agent_id}** ({pq.feature})\n\n{pq.question}\n\n"
                f"Reply in this thread or use `/answer {pq.question_id} <your answer>`"
            )
            thread = await msg.create_thread(name=thread_name)
            await thread.send(f"Question ID: `{pq.question_id}`\nPlease provide your answer below.")
            return thread.id
        except nextcord.HTTPException as exc:
            log.error("Failed to create question thread: %s", exc)
            return None

    async def resolve_question(self, question_id: str, answer: str) -> bool:
        pq = self.pending_questions.get(question_id)
        if pq is None:
            log.warning("No pending question with ID: %s", question_id)
            return False
        if pq.future.done():
            log.warning("Question %s already resolved", question_id)
            return False
        pq.status = "answered"
        pq.future.set_result(answer)
        log.info("Question %s resolved", question_id)
        return True


def create_bot(cfg: Config) -> DiscordBot:
    intents = nextcord.Intents.default()
    intents.guilds = True
    intents.message_content = True
    bot = DiscordBot(guild_id=cfg.guild_id, intents=intents)

    @bot.slash_command(name="ping", description="Health check", guild_ids=[cfg.guild_id] if cfg.guild_id else None)
    async def _ping(interaction: nextcord.Interaction):
        await interaction.send("Pong!")

    @bot.slash_command(name="answer", description="Answer a clarifying question", guild_ids=[cfg.guild_id] if cfg.guild_id else None)
    async def _answer(interaction: nextcord.Interaction, question_id: str, answer_text: str):
        resolved = await bot.resolve_question(question_id, answer_text)
        if resolved:
            await interaction.send(f"Answer recorded for question `{question_id}`.")
        else:
            await interaction.send(f"Could not find or resolve question `{question_id}`. It may have timed out or already been answered.", ephemeral=True)

    @bot.event
    async def on_message(message: nextcord.Message):
        if message.author.bot:
            return
        if not isinstance(message.channel, nextcord.Thread):
            return
        thread_id = message.channel.id
        for qid, pq in bot.pending_questions.items():
            if pq.thread_id == thread_id and not pq.future.done():
                answer = message.content
                resolved = await bot.resolve_question(qid, answer)
                if resolved:
                    await message.add_reaction("✅")
                return

    return bot


async def _handle_post_update(request: aiohttp_web.Request) -> aiohttp_web.Response:
    bot: DiscordBot = request.app["bot"]
    if not bot._ready_event.is_set():
        return aiohttp_web.json_response({"ok": False, "error": "bot not ready yet"}, status=503)
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
    if not bot._ready_event.is_set():
        return aiohttp_web.json_response({"ok": False, "error": "bot not ready yet"}, status=503)
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


async def _handle_post_question(request: aiohttp_web.Request) -> aiohttp_web.Response:
    bot: DiscordBot = request.app["bot"]
    cfg: Config = request.app["config"]
    if not bot._ready_event.is_set():
        return aiohttp_web.json_response({"ok": False, "error": "bot not ready yet"}, status=503)
    try:
        body: dict[str, Any] = await request.json()
    except json.JSONDecodeError:
        return aiohttp_web.json_response({"ok": False, "error": "invalid json"}, status=400)

    agent_id = body.get("agent_id")
    feature = body.get("feature")
    question = body.get("question")
    timeout_seconds = body.get("timeout", cfg.question_timeout)

    if not agent_id or not feature or not question:
        return aiohttp_web.json_response(
            {"ok": False, "error": "fields 'agent_id', 'feature', and 'question' are required"}, status=400
        )

    question_id = str(uuid.uuid4())[:8]
    loop = asyncio.get_event_loop()
    pq = PendingQuestion(
        question_id=question_id,
        agent_id=agent_id,
        feature=feature,
        question=question,
        future=loop.create_future(),
        status="pending",
    )
    bot.pending_questions[question_id] = pq

    thread_id = await bot.create_question_thread(pq)
    if thread_id is not None:
        pq.thread_id = thread_id

    try:
        answer = await asyncio.wait_for(pq.future, timeout=timeout_seconds)
        pq.status = "answered"
        return aiohttp_web.json_response({
            "ok": True,
            "status": "answered",
            "question_id": question_id,
            "answer": answer,
        })
    except asyncio.TimeoutError:
        pq.status = "paused"
        return aiohttp_web.json_response({
            "ok": True,
            "status": "paused",
            "question_id": question_id,
            "message": "Question timed out. Agent should checkpoint and exit.",
        }, status=200)


async def _handle_health(_request: aiohttp_web.Request) -> aiohttp_web.Response:
    return aiohttp_web.json_response({"status": "ok"})


def create_http_app(bot: DiscordBot, cfg: Config) -> aiohttp_web.Application:
    app = aiohttp_web.Application()
    app["bot"] = bot
    app["config"] = cfg
    app.router.add_post("/post_update", _handle_post_update)
    app.router.add_post("/announce_milestone", _handle_announce_milestone)
    app.router.add_post("/post_question", _handle_post_question)
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
    app = create_http_app(bot, cfg)
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