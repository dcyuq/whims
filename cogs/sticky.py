import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

import embeds
from storage import IntKeyStore

log = logging.getLogger(__name__)

CONTENT_LIMIT = 2000

_store = IntKeyStore("stickynotes.json")
notes = _store.load()

locks = {}


def save():
    _store.save(notes)


class StickyNote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def repost(self, channel):
        entry = notes.get(channel.id)
        if not entry:
            return

        perms = channel.permissions_for(channel.guild.me)
        if not (perms.view_channel and perms.send_messages and perms.embed_links):
            return

        old_id = entry.get("message_id")
        if old_id:
            try:
                old = await channel.fetch_message(old_id)
                await old.delete()
            except discord.HTTPException:
                pass

        sent = await embeds.send(channel, embeds.note(entry["content"]))
        if sent is None:
            return

        entry["message_id"] = sent.id
        save()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.id == self.bot.user.id:
            return
        if message.channel.id not in notes:
            return

        lock = locks.setdefault(message.channel.id, asyncio.Lock())
        if lock.locked():
            return

        async with lock:
            await asyncio.sleep(2)
            try:
                await self.repost(message.channel)
            except discord.HTTPException as exc:
                log.warning("sticky repost failed in %s: %s", message.channel.id, exc)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        if notes.pop(channel.id, None) is not None:
            save()

    @app_commands.command(name="stick", description="Keep a note pinned to the bottom of a channel")
    @app_commands.describe(content="What the sticky note says", channel="Where to stick it")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def stick(self, interaction: discord.Interaction, content: str, channel: discord.TextChannel = None):
        target = channel or interaction.channel

        if len(content) > CONTENT_LIMIT:
            await embeds.send(interaction, embeds.error("That note is **too long**."), ephemeral=True)
            return

        perms = target.permissions_for(interaction.guild.me)
        if not (perms.view_channel and perms.send_messages and perms.embed_links):
            await embeds.send(interaction, embeds.error(f"I can't post in {target.mention}."), ephemeral=True)
            return

        entry = notes.setdefault(target.id, {})
        entry["content"] = content.replace("\\n", "\n")
        save()

        await self.repost(target)
        await embeds.send(interaction, embeds.ok(f"Sticky note set in {target.mention}."), ephemeral=True)

    @app_commands.command(name="unstick", description="Remove the sticky note from a channel")
    @app_commands.describe(channel="Where to remove it from")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.guild_only()
    async def unstick(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target = channel or interaction.channel
        entry = notes.pop(target.id, None)

        if entry is None:
            await embeds.send(interaction, embeds.error(f"No sticky note in {target.mention}."), ephemeral=True)
            return

        save()

        old_id = entry.get("message_id")
        if old_id:
            try:
                old = await target.fetch_message(old_id)
                await old.delete()
            except discord.HTTPException:
                pass

        await embeds.send(interaction, embeds.ok(f"Sticky note removed from {target.mention}."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(StickyNote(bot))