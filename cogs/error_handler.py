"""
The IdleRPG Discord Bot
Copyright (C) 2018-2019 Diniboy and Gelbpunkt

This software is dual-licensed under the GNU Affero General Public License for non-commercial and the Travitia License for commercial use.
For more information, see README.md and LICENSE.md.
"""
import sys
import traceback
from datetime import timedelta

import discord
from aiohttp import ClientOSError, ContentTypeError, ServerDisconnectedError
from asyncpg.exceptions import DataError as AsyncpgDataError
from discord.ext import commands

import utils.checks
from utils.paginator import NoChoice

try:
    from raven import Client
    from raven_aiohttp import AioHttpTransport
except ModuleNotFoundError:
    SENTRY_SUPPORT = False
else:
    SENTRY_SUPPORT = True


class Errorhandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.on_command_error = self._on_command_error
        self.client = None
        bot.queue.put_nowait(self.initialize_cog())

    async def _on_command_error(self, ctx, error, bypass=False):
        if (
            hasattr(ctx.command, "on_error")
            or (ctx.command and hasattr(ctx.cog, f"_{ctx.command.cog_name}__error"))
            and not bypass
        ):
            # Do nothing if the command/cog has its own error handler
            return
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                _("Oops! You forgot a required argument: `{arg}`").format(
                    arg=error.param.name
                )
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(_("You used a malformed argument!"))
        elif isinstance(error, commands.CommandOnCooldown):
            return await ctx.send(
                _("You are on cooldown. Try again in {time}.").format(
                    time=timedelta(seconds=int(error.retry_after))
                )
            )
        elif hasattr(error, "original") and isinstance(
            error.original, discord.HTTPException
        ):
            return  # not our fault
        elif isinstance(error, commands.NotOwner):
            await ctx.send(
                embed=discord.Embed(
                    title=_("Permission denied"),
                    description=_(
                        ":x: This command is only avaiable for the bot owner."
                    ),
                    colour=0xFF0000,
                )
            )
        elif isinstance(error, commands.CheckFailure):
            if type(error) == utils.checks.NoCharacter:
                await ctx.send(_("You don't have a character yet."))
            elif type(error) == utils.checks.NoGuild:
                await ctx.send(_("You need to have a guild to use this command."))
            elif type(error) == utils.checks.NeedsNoGuild:
                await ctx.send(_("You need to be in no guild to use this command."))
            elif type(error) == utils.checks.NoGuildPermissions:
                await ctx.send(
                    _("Your rank in the guild is too low to use this command.")
                )
            elif type(error) == utils.checks.NeedsNoGuildLeader:
                await ctx.send(
                    _("You mustn't be the owner of a guild to use this command.")
                )
            elif type(error) == utils.checks.NeedsNoAdventure:
                await ctx.send(
                    _(
                        "You are already on an adventure. Use `{prefix}status` to see how long it lasts."
                    ).format(prefix=ctx.prefix)
                )
            elif type(error) == utils.checks.NeedsAdventure:
                await ctx.send(
                    _(
                        "You need to be on an adventure to use this command. Try `{prefix}adventure`!"
                    ).format(prefix=ctx.prefix)
                )
            else:
                await ctx.send(
                    embed=discord.Embed(
                        title=_("Permission denied"),
                        description=_(
                            ":x: You don't have the permissions to use this command. It is thought for other users."
                        ),
                        colour=0xFF0000,
                    )
                )
        elif isinstance(error, NoChoice):
            await ctx.send(_("You did not choose anything."))
        elif isinstance(error, commands.CommandInvokeError) and hasattr(
            error, "original"
        ):
            if isinstance(
                error.original,
                (ClientOSError, ServerDisconnectedError, ContentTypeError),
            ):
                # Called on 500 HTTP responses
                return
            elif isinstance(error.original, AsyncpgDataError):
                return await ctx.send(
                    _(
                        "An argument or value you entered was far too high for me to handle properly!"
                    )
                )
            print("In {}:".format(ctx.command.qualified_name), file=sys.stderr)
            traceback.print_tb(error.original.__traceback__)
            print(
                "{0}: {1}".format(error.original.__class__.__name__, error.original),
                file=sys.stderr,
            )
            if self.client:
                try:
                    raise error.original
                except Exception:
                    if ctx.guild:
                        guild_id = ctx.guild.id
                    else:
                        guild_id = "None"
                    self.client.captureException(
                        data={
                            "message": ctx.message.content,
                            "tags": {"command": ctx.command.name},
                        },
                        extra={
                            "guild_id": str(guild_id),
                            "channel_id": str(ctx.channel.id),
                            "message_id": str(ctx.message.id),
                            "user_id": str(ctx.author.id),
                        },
                    )
                await ctx.send(
                    _(
                        "The command you tried to use ran into an error. The incident has been reported and the team will work hard to fix the issue!"
                    )
                )
        await ctx.bot.reset_cooldown(ctx)

    async def initialize_cog(self):
        """Saves the original cmd error handler"""
        if SENTRY_SUPPORT:
            self.client = Client(self.bot.config.sentry_url, transport=AioHttpTransport)

    async def unload_cog(self):
        """Readds the original error handler"""
        if SENTRY_SUPPORT:
            await self.client.remote.get_transport().close()

    def cog_unload(self):
        self.bot.queue.put_nowait(self.unload_cog())


def setup(bot):
    bot.add_cog(Errorhandler(bot))