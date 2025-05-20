import discord
from discord.commands import Option
from discord.ext import tasks
from discord.ui import View, Select
from pymongo import MongoClient
from pydantic_mongo import PydanticObjectId
import datetime as dt

from models.dbmodels import *
from utils.context import ctx_info, requires_approved
from utils.cartography import est_traveling_time_seconds, translated_djikstra, best_guess, best_guesses
from logger import debug, info, warning, error, logger
from config import config

# Discord does not allow >25 choices
COLOUR_CHOICES = ["Green", "Blue", "Purple", "Gold"]
DISCORD_OPTIONS_LIMIT = 25

bot = discord.Bot()

# MongoDB setup
db = MongoClient(f"mongodb://{config['mongoDbHostname']}:{config['mongoDbPort']}/")["cortex"]
debug("Connected to MongoDB")
REMINDERS = Reminders(database=db)
PORTALS = Portals(database=db, logger=logger)

def utc_now():
    return dt.datetime.now(dt.timezone.utc)

def make_dc_time(dt: dt.datetime):
    return f"<t:{int(dt.timestamp())}:R>"

@tasks.loop(seconds=config['dbPollingIntervalSeconds'])
async def check_mongo_updates():
    query = {'time_to_ping': {'$lt': utc_now()}}
    pending_reminders = REMINDERS.find_by(query)
    
    for reminder in pending_reminders:
        msg = [
            f"{reminder.roleMention} {reminder.objective} in {reminder.location} {make_dc_time(reminder.time_unlocked)} {reminder.time_unlocked.strftime('%H:%M UTC')}",
            f"- Submitted by {reminder.submitter} at {reminder.time_submitted.strftime('%H:%M UTC (%d/%m/%y)')}"
        ]
        channel = bot.get_channel(reminder.pingChannelId)
        try:
            info(f"Pinging {reminder.objective} in {reminder.location} | {reminder.submitter} [{reminder.pingChannelId}]")
            await channel.send('\n'.join(msg))
        except Exception as e:
            error(f"Failed to ping channel {reminder.pingChannelId} | submitted by {reminder.submitter} at {reminder.time_submitted.strftime('%H:%M UTC (%d/%m/%Y)')}")
            error(e)
        REMINDERS.delete(reminder)
        debug(f"Deleted {reminder.objective} in {reminder.location}")

@bot.slash_command(name="core", description="Set a ping timer for a core")
@requires_approved
async def set_core_reminder(
    ctx: discord.ApplicationContext,
    color: Option(str, choices=COLOUR_CHOICES, required=True),
    location: Option(str, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    home_map = ctx.server_data.get('homeMap', None)
    guess = best_guess(location, home_map)
    if not guess:
        warning(f"Failed to guess location for {ctx.guild} ({ctx.guild_id}): {location}")
        await ctx.respond("Unable to guess exact map name. Please retry command", ephemeral=True)
        return
    location = guess
    lead_time = int(est_traveling_time_seconds(location, home_map)) + config['reminderLeadTimeSeconds']
    reminder = Reminder(
        objective=f"{color} Core",
        location=location,
        time_unlocked=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now(),
        pingChannelId=ctx.server_data['pingChannelId'],
        roleMention=ctx.server_data['roleMention'],
        time_to_ping=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds-lead_time),
    )
    await submit_reminder(ctx, reminder)

@bot.slash_command(name="vortex", description="Set a ping timer for a vortex")
@requires_approved
async def set_vortex_reminder(
    ctx: discord.ApplicationContext,
    color: Option(str, choices=COLOUR_CHOICES, required=True),
    location: Option(str, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    home_map = ctx.server_data.get('homeMap', None)
    guess = best_guess(location, home_map)
    if not guess:
        warning(f"Failed to guess location for {ctx.guild} ({ctx.guild_id}): {location}")
        await ctx.respond("Unable to guess exact map name. Please retry command", ephemeral=True)
        return
    location = guess
    lead_time = int(est_traveling_time_seconds(location, home_map)) + config['reminderLeadTimeSeconds']
    reminder = Reminder(
        objective=f"{color} Vortex",
        location=location,
        time_unlocked=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now(),
        pingChannelId=ctx.server_data['pingChannelId'],
        roleMention=ctx.server_data['roleMention'],
        time_to_ping=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds-lead_time),
    )
    await submit_reminder(ctx, reminder)

@bot.slash_command(name="remind", description="Set a ping timer")
@requires_approved
async def set_free_reminder(
    ctx: discord.ApplicationContext,
    reminder_text: Option(str, required=True),
    location: Option(str, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    home_map = ctx.server_data.get('homeMap', None)
    guess = best_guess(location, home_map)
    lead_time = config['reminderLeadTimeSeconds']
    if guess:
        location = guess
        lead_time += int(est_traveling_time_seconds(location, home_map))
    reminder = Reminder(
        objective=reminder_text,
        location=location,
        time_unlocked=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now(),
        pingChannelId=ctx.server_data['pingChannelId'],
        roleMention=ctx.server_data['roleMention'],
        time_to_ping=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds-lead_time),
    )
    await submit_reminder(ctx, reminder)

async def submit_reminder(ctx: discord.ApplicationContext, reminder: Reminder):
    existing_reminders = list(REMINDERS.find_by({"objective": reminder.objective, "location": reminder.location}))
    exist_msg = ""
    if existing_reminders:
        info(f'Deleting existing {len(existing_reminders)} reminders for {reminder.objective} in {reminder.location}')
        exist_msg = "Reminder already exists, updated reminder!\n"
        [REMINDERS.delete(r) for r in existing_reminders]
    REMINDERS.save(reminder)
    info(f'{ctx_info(ctx)} Saved reminder {reminder.objective} in {reminder.location}')
    await ctx.respond(f"{exist_msg}New reminder set: {reminder.objective} at {reminder.location} {make_dc_time(reminder.time_unlocked)} {reminder.time_unlocked.strftime('%H:%M UTC')}", ephemeral=True)

def format_route(route: list[str]):
    def inline_format(route: list[str]) -> str:
        msg = [f'**{route[0]}**']
        for idx, step in enumerate(route):
            if idx == 0: continue
            portal = PORTALS.find_portal(route[idx-1], step)
            if portal:
                msg.append(f"--{make_dc_time(portal.time_expire)}-->")
            else:
                msg.append(f"-->")
            msg.append(f'**{step}**')
        return '   '.join(msg)
    def earliest_expire_format(route: list[str]) -> str:
        all_portals = [PORTALS.find_portal(*pair) for pair in zip(route[:-1], route[1:])]
        next_expire_str = ""
        if all_portals:
            next_expire = min(portal.time_expire for portal in all_portals if portal)
            next_expire_str = f'\nNext portal expires {make_dc_time(next_expire)} {next_expire.strftime("%H:%M UTC (%d/%m/%y)")}'
        return '   -->   '.join(f"**{step}**" for step in route) + next_expire_str
    return inline_format(route)

@bot.slash_command(name="upcoming", description="List upcoming reminders")
@requires_approved
async def upcoming(ctx: discord.ApplicationContext):
    server_name = ctx.server_data['name']
    info(f'{ctx.author.name} ({ctx.author.id}) from {server_name} sent /upcoming')
    pending_reminders = list(REMINDERS.find_by({'pingChannelId': ctx.server_data['pingChannelId']}, sort=[("time_to_ping", 1)]))
    msg = [
        f"{reminder.objective} in {reminder.location} {make_dc_time(reminder.time_unlocked)} {reminder.time_unlocked.strftime('%H:%M UTC (%d/%m/%Y)')}"
    for reminder in pending_reminders] or ["No upcoming reminders"]

    notable_routes = []
    upcoming_config = ctx.server_data.get('upcomingConfig', None)
    if upcoming_config:
        for zone in upcoming_config['notableMaps']:
            route = translated_djikstra(zone, ctx.server_data['homeMap'], list(PORTALS.get_all()))
            if not route or len(route)-1 > upcoming_config['maxMapsOut']: continue
            notable_routes.append(route)
    if notable_routes:
        msg.append(f"\n**Notable roads from {ctx.server_data['homeMap']}:**")
        for route in notable_routes:
            msg.append(format_route(route))

    await ctx.respond("\n".join(msg))

@bot.slash_command(name="depo", description="Set a timer for leechers on depo time, sends immediately")
@requires_approved
async def depo(
    ctx: discord.ApplicationContext,
    color: Option(str, choices=COLOUR_CHOICES, required=True),
    type: Option(str, choices=("Core", "Vortex"), required=True),
    location: Option(str, required=True),
    minutes: Option(int, required=True, min_value=0, max_value=59),
):
    location = best_guess(location, ctx.server_data.get('homeMap', None)) or location
    info(f'{ctx.author.name} ({ctx.author.id}) from {ctx.server_data["name"]} sent /depo {color} {type} {location} {minutes}')
    utc_depo_time = utc_now() + dt.timedelta(minutes=minutes)
    msg = [
        f"{ctx.server_data['roleMention']} Come leech {color} {type} in {location}", 
        f"Depo {make_dc_time(utc_depo_time)} {utc_depo_time.strftime('%H:%M UTC')}  -- {ctx.author.mention}",
    ]
    await ctx.respond("Sending ping...", ephemeral=True)
    await bot.get_channel(ctx.server_data['pingChannelId']).send("\n".join(msg))

@bot.slash_command(name="delete", description="Delete a reminder")
async def delete(ctx: discord.ApplicationContext):
    # TODO: Allow delete for submitted portals
    if ctx.author.id == config['juxId']:
        user_reminders = list(REMINDERS.find_by({}))
        user_portals = list(PORTALS.find_by({}))
    else:
        user_reminders = list(REMINDERS.find_by({"submitter": ctx.author.mention}))
        user_portals = list(PORTALS.find_by({"submitter": ctx.author.mention}))
    info(f'{ctx_info(ctx)} Sent /delete, {len(user_reminders)} reminders and {len(user_portals)} portals available')
    if len(user_portals) + len(user_reminders) == 0:
        await ctx.respond("No reminders/portals available to you...", ephemeral=True)
        return
    view = View()
    reminder_options = [
        discord.SelectOption(label=f"{reminder.objective} in {reminder.location}", value=f'reminder@{str(reminder.id)}') 
    for reminder in user_reminders]
    portal_options = [
        discord.SelectOption(label=f"{portal.from_map} -> {portal.to_map} ({portal.time_expire.strftime('%H:%M UTC')})", value=f'portal@{str(portal.id)}') 
    for portal in user_portals]
    select = Select(
        placeholder="Choose object to delete...",
        options=reminder_options + portal_options,
    )
    async def callback(interaction: discord.Interaction):
        obj_type, id_str = interaction.data['values'][0].split('@')
        id = PydanticObjectId(id_str)
        if obj_type == 'portal':
            portal = PORTALS.find_one_by_id(id)
            obj_str = [p for p in portal_options if p.value == interaction.data['values'][0]][0].label
            delete_result = PORTALS.delete(portal)
        elif obj_type == 'reminder':
            reminder = REMINDERS.find_one_by_id(id)
            obj_str = [r for r in reminder_options if r.value == interaction.data['values'][0]][0].label
            delete_result = REMINDERS.delete(reminder)
        else:
            error(f"{ctx_info(ctx)} Unknown /delete callback {obj_type}@{id_str}")
            return
        if not delete_result:
            error(f"{ctx_info(ctx)} Failed to delete {obj_type} {obj_str} ({id_str})")
            await interaction.response.edit_message(content=f"Failed to delete {obj_str}", view=None)
            return
        info(f'{ctx_info(ctx)} deleted {obj_type}: {obj_str}')
        await interaction.response.edit_message(content=f"Deleted {obj_type}: {obj_str}", view=None)
    select.callback = callback

    view.add_item(select)
    await ctx.respond(view=view,ephemeral=True)

@bot.slash_command(name="roads", description="Add a an ava portal connection")
@requires_approved
async def roads(
    ctx: discord.ApplicationContext,
    portal_type: Option(str, choices=("Blue", "Gold")),
    from_map: Option(str, required=True),
    to_map: Option(str, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    home_map = ctx.server_data.get('homeMap', None)
    ctx.data = {}
    time_expire = utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds)
    from_guesses, to_guesses = best_guesses(from_map, home_map), best_guesses(to_map, home_map)

    failed_to_guess = (not from_guesses, from_map), (not to_guesses, to_map)
    if any(i[0] for i in failed_to_guess):
        failed_prompts = ', '.join(i[1] for i in failed_to_guess if i[0])
        info(f'Failed to guess map names from "{failed_prompts}"')
        await ctx.respond(f"Failed to guess map from {failed_prompts}", ephemeral=True)
        return
    
    ambiguous_guesses = (len(from_guesses) > DISCORD_OPTIONS_LIMIT, from_map), (len(to_guesses) > DISCORD_OPTIONS_LIMIT, to_map)
    if any(i[0] for i in ambiguous_guesses):
        ambiguous_prompts = ', '.join(f'"{i[1]}"' for i in ambiguous_guesses if i[0])
        info(f'Map query is too ambiguous: {ambiguous_prompts}')
        await ctx.respond(f"Map query is too ambiguous: {ambiguous_prompts}", ephemeral=True)
        return

    async def submit_portal(interaction: discord.Interaction):
        from_map, to_map = ctx.data['from_map'], ctx.data['to_map']
        info(f'{ctx_info(ctx)} submitted {portal_type} Portal from {from_map} to {to_map}, expires {time_expire}')
        msg = [
            f"Submitted {portal_type} Portal from {from_map} to {to_map}",
            f"Expires {make_dc_time(time_expire)} {time_expire.strftime('%H:%M UTC')}  -- {ctx.author.mention}"
        ]
        PORTALS.save(Portal(
            from_map=from_map,
            to_map=to_map,
            time_expire=time_expire,
            submitter=ctx.author.mention,
            time_submitted=utc_now(),
        ))
        if isinstance(interaction, discord.ApplicationContext):
            await interaction.respond('\n'.join(msg), ephemeral=True)
            return
        await interaction.response.edit_message(content="\n".join(msg), view=None)
    
    from_is_ambiguous, to_is_ambiguous = len(from_guesses) > 1, len(to_guesses) > 1
    ctx.data['from_map'], ctx.data['to_map'] = from_guesses[0], to_guesses[0]
    if from_is_ambiguous and to_is_ambiguous:
        s1 = Select(placeholder="Confirm 1st Map...", options=[discord.SelectOption(label=guess, value=guess) for guess in from_guesses])
        async def from_response(interaction: discord.Interaction):
            ctx.data['from_map'] = interaction.data['values'][0]
            await interaction.response.defer(ephemeral=True)
        s1.callback = from_response

        s2 = Select(placeholder="Confirm 2nd Map...", options=[discord.SelectOption(label=guess, value=guess) for guess in to_guesses])
        async def to_response(interaction: discord.Interaction):
            ctx.data['to_map'] = interaction.data['values'][0]
            await interaction.response.defer(ephemeral=True)
        s2.callback = to_response

        submit_button = discord.ui.Button(label="Submit", style=discord.ButtonStyle.primary, custom_id="submit")
        submit_button.callback = submit_portal

        await ctx.respond(view=View(s1, s2, submit_button), ephemeral=True)
    elif from_is_ambiguous:
        s = Select(placeholder="Confirm 1st Map...", options=[discord.SelectOption(label=guess, value=guess) for guess in from_guesses])
        async def from_response(interaction: discord.Interaction):
            ctx.data['from_map'] = interaction.data['values'][0]
            await submit_portal(interaction)
        s.callback = from_response
        await ctx.respond(content=f"2nd Map is confirmed as **{ctx.data['to_map']}**\n", view=View(s), ephemeral=True)
    elif to_is_ambiguous:
        s = Select(placeholder="Confirm 2nd Map...", options=[discord.SelectOption(label=guess, value=guess) for guess in to_guesses])
        async def to_response(interaction: discord.Interaction):
            ctx.data['to_map'] = interaction.data['values'][0]
            await submit_portal(interaction)
        s.callback = to_response
        await ctx.respond(content=f"1st Map is confirmed as **{ctx.data['from_map']}**\n", view=View(s), ephemeral=True)
    else:
        await submit_portal(ctx)

@bot.slash_command(name="route", description="Find the shortest route from one location to another")
@requires_approved
async def route(ctx: discord.ApplicationContext, start: Option(str, required=True), end: Option(str, required=True)):
    start = best_guess(start, ctx.server_data.get('homeMap', None))
    end = best_guess(end, ctx.server_data.get('homeMap', None))
    if not start or not end:
        await ctx.respond("Unable to guess exact map names. Please retry command with full map names", ephemeral=True)
        return
    route = translated_djikstra(start, end, list(PORTALS.get_all()))
    await ctx.respond(format_route(route))

@bot.slash_command(name="help", description="Learn more about the commands")
async def help(ctx: discord.ApplicationContext):
    msg = [
        "Commands: /core, /vortex, /remind, /depo, /upcoming, /delete, /roads, /route",
        "/core - Set an alarm for a core location",
        '/vortex - Set an alarm for a vortex location',
        '/remind - Set a reminder for a location',
        '/depo - Inform people to leech and set a timer to depo',
        '/upcoming - List all upcoming events',
        '/delete - Delete an existing reminder you set',
        '/roads - Add an ava portal connection',
        '/route - Find the shortest route from one location to another',
    ]
    await ctx.respond("\n".join(msg), ephemeral=True)

@bot.event
async def on_ready():
    check_mongo_updates.start()
    await bot.sync_commands()
    print(f"Bot ready!")

if __name__ == "__main__":
    bot.run(config["botToken"])
