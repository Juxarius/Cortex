from config import config
from discord import ApplicationContext
import functools
from logger import info, warning

def ctx_info(ctx: ApplicationContext) -> str:
    alias = ''
    if config['approvedServers'].get(str(ctx.guild_id), None) is not None:
        alias = f' ({config['approvedServers'][str(ctx.guild_id)]['name']})'
    return f'{ctx.author.name} [{ctx.author.id}] - {ctx.guild}{alias} [{ctx.guild_id}]'

def requires_approved(func):
    @functools.wraps(func)
    async def wrapper(ctx: ApplicationContext, *args, **kwargs):
        server_data = config['approvedServers'].get(str(ctx.guild_id), None)
        cmd = f'/{ctx.command} ' + ' '.join(str(v) for v in kwargs.values())
        if server_data is None:
            warning(f"{ctx_info(ctx)} Unapproved server sent {cmd}")
            await ctx.respond("This server is not approved to use this command.")
            return
        info(f"{ctx_info(ctx)} Approved server sent {cmd}")
        ctx.server_data = server_data
        return await func(ctx, *args, **kwargs)
    return wrapper