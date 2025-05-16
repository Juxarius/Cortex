import discord
from discord.commands import Option
from discord.ext import tasks
from discord.ui import View, Select
from pymongo import MongoClient
from pydantic_mongo import PydanticObjectId
import datetime as dt

from models import *
from utils import est_traveling_time_seconds, translated_djikstra, config, ctx_info, requires_approved, best_guess
from utils import debug, info, warning, error

# Discord does not allow >25 choices
COLOUR_CHOICES = ["Green", "Blue", "Purple", "Gold"]

bot = discord.Bot()

# MongoDB setup
db = MongoClient(f"mongodb://{config['mongoDbHostname']}:{config['mongoDbPort']}/")["cortex"]
debug("Connected to MongoDB")
REMINDERS = Reminders(database=db)
PORTALS = Portals(database=db)

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
            f"- Submitted by {reminder.submitter} at {reminder.time_submitted.strftime('%H:%M UTC (%d/%m/%Y)')}"
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
    # How far apart are the reminders before being considered duplicates
    exist_msg = ""
    if existing_reminders:
        info(f'Deleting existing {len(existing_reminders)} reminders for {reminder.objective} in {reminder.location}')
        exist_msg = "Reminder already exists, updated reminder!\n"
        [REMINDERS.delete(r) for r in existing_reminders]
    REMINDERS.save(reminder)
    info(f'{ctx_info(ctx)} Saved reminder {reminder.objective} in {reminder.location}')
    await ctx.respond(f"{exist_msg}New reminder set: {reminder.objective} at {reminder.location} {make_dc_time(reminder.time_unlocked)} {reminder.time_unlocked.strftime('%H:%M UTC')}", ephemeral=True)

@bot.slash_command(name="upcoming", description="List upcoming reminders")
@requires_approved
async def upcoming(ctx: discord.ApplicationContext):
    server_name = ctx.server_data['name']
    info(f'{ctx.author.name} ({ctx.author.id}) from {server_name} sent /upcoming')
    pending_reminders = list(REMINDERS.find_by({'pingChannelId': ctx.server_data['pingChannelId']}, sort=[("time_to_ping", 1)]))
    if not pending_reminders:
        await ctx.respond("No upcoming reminders", ephemeral=True)
        return
    msg = [
        f"{reminder.objective} in {reminder.location} {make_dc_time(reminder.time_unlocked)} {reminder.time_unlocked.strftime('%H:%M UTC (%d/%m/%Y)')}"
    for reminder in pending_reminders]
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
    if ctx.author.id == config['juxId']:
        user_reminders = list(REMINDERS.find_by({}))
    else:
        user_reminders = list(REMINDERS.find_by({"submitter": ctx.author.mention}))
    info(f'{ctx.author.name} ({ctx.author.id}) sent /delete, {len(user_reminders)} reminders available')
    if not user_reminders:
        await ctx.respond("No reminders available to you...", ephemeral=True)
        return
    view = View()
    options = [
        discord.SelectOption(label=f"{reminder.objective} in {reminder.location}", value=str(reminder.id)) 
    for reminder in user_reminders]
    select = Select(
        placeholder="Choose reminder to delete...",
        min_values=1,
        max_values=1,
        options=options,
    )
    async def callback(interaction: discord.Interaction):
        reminder = REMINDERS.find_one_by_id(PydanticObjectId(interaction.data['values'][0]))
        REMINDERS.delete(reminder)
        info(f'{interaction.user.name} ({interaction.user.id}) deleted {reminder.objective} in {reminder.location}')
        await interaction.response.edit_message(content=f"Deleted Reminder: {reminder.objective} in {reminder.location}", view=None)
    select.callback = callback

    view.add_item(select)
    await ctx.respond(view=view,ephemeral=True)

@bot.slash_command(name="roads", description="Add a an ava portal connection")
@requires_approved
async def roads(
    ctx: discord.ApplicationContext,
    from_map: Option(str, required=True),
    to_map: Option(str, required=True),
    portal_type: Option(str, choices=("Gold", "Blue")),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    await ctx.respond("Not implemented yet, stay tuned...", ephemeral=True)

@bot.slash_command(name="route", description="Find the shortest route from one location to another")
@requires_approved
async def route(ctx: discord.ApplicationContext, start: Option(str, required=True), end: Option(str, required=True)):
    start = best_guess(start, ctx.server_data.get('homeMap', None))
    end = best_guess(end, ctx.server_data.get('homeMap', None))
    if not start or not end:
        await ctx.respond("Unable to guess exact map names. Please retry command with full map names", ephemeral=True)
        return
    portals: list[Portal] = list(PORTALS.find_by({}))
    roads = tuple((portal.from_map_id, portal.to_map_id) for portal in portals)
    route = translated_djikstra(start, end, roads)

    def find_portal_time(map1: str, map2: str) -> dt.datetime:
        for portal in portals:
            if portal.from_map == map1 and portal.to_map == map2:
                return portal.time_expire
        return None
    msg = [f'**{route[0]}**']
    for idx, step in enumerate(route):
        if idx == 0: continue
        time_expire = find_portal_time(route[idx-1], step)
        if time_expire:
            msg.append(f"--{make_dc_time(time_expire)}-->")
        else:
            msg.append(f"-->")
        msg.append(f'**{step}**')
    await ctx.respond('   '.join(msg))

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
