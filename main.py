import discord
from discord.commands import Option
from discord.ext import tasks
from discord.ui import View, Select
from pymongo import MongoClient
from pydantic_mongo import PydanticObjectId
import datetime as dt
import json

from models import *
from utils import best_guess, est_traveling_time_seconds, translated_djikstra

CONFIG_FILE_PATH = 'config.json'
with open(CONFIG_FILE_PATH, 'r') as f:
    config = json.load(f)

# Discord does not allow >25 choices
COLOUR_CHOICES = ["Green", "Blue", "Purple", "Gold"]

bot= discord.Bot()

# MongoDB setup
db = MongoClient(f"mongodb://{config['mongoDbHostname']}:{config['mongoDbPort']}/")["cortex"]
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
            f"{reminder.roleMention} {reminder.objective} in {reminder.location} {make_dc_time(reminder.time_unlocked)}",
            f"- Submitted by {reminder.submitter} at {reminder.time_submitted.strftime('%H:%M UTC (%d/%m/%Y)')}"
        ]
        await bot.get_channel(reminder.pingChannelId).send('\n'.join(msg))
        REMINDERS.delete(reminder)

@bot.slash_command(name="core", description="Set a ping timer for a core")
async def set_core_reminder(
    ctx: discord.ApplicationContext,
    color: Option(str, choices=COLOUR_CHOICES, required=True),
    location: Option(str, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    server_data = config['approvedServers'].get(str(ctx.guild_id), {})
    if not server_data:
        await ctx.respond("This server is not approved to use this command.")
        return
    location = best_guess(location)
    if not location:
        await ctx.respond("Unable to guess exact map name. Please retry command", ephemeral=True)
        return
    lead_time = int(est_traveling_time_seconds(location)) + config['reminderLeadTimeSeconds']
    reminder = Reminder(
        objective=f"{color} Core",
        location=location,
        time_unlocked=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now(),
        pingChannelId=server_data['pingChannelId'],
        roleMention=server_data['roleMention'],
        time_to_ping=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds-lead_time),
    )
    await submit_reminder(ctx, reminder)

@bot.slash_command(name="vortex", description="Set a ping timer for a vortex")
async def set_vortex_reminder(
    ctx: discord.ApplicationContext,
    color: Option(str, choices=COLOUR_CHOICES, required=True),
    location: Option(str, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    server_data = config['approvedServers'].get(str(ctx.guild_id), {})
    if not server_data:
        await ctx.respond("This server is not approved to use this command.")
        return
    location = best_guess(location)
    if not location:
        await ctx.respond("Unable to guess exact map name. Please retry command", ephemeral=True)
        return
    lead_time = int(est_traveling_time_seconds(location)) + config['reminderLeadTimeSeconds']
    reminder = Reminder(
        objective=f"{color} Vortex",
        location=location,
        time_unlocked=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now(),
        pingChannelId=server_data['pingChannelId'],
        roleMention=server_data['roleMention'],
        time_to_ping=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds-lead_time),
    )
    await submit_reminder(ctx, reminder)

@bot.slash_command(name="remind", description="Set a ping timer")
async def set_free_reminder(
    ctx: discord.ApplicationContext,
    reminder_text: Option(str, required=True),
    location: Option(str, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    server_data = config['approvedServers'].get(str(ctx.guild_id), {})
    if not server_data:
        await ctx.respond("This server is not approved to use this command.")
        return
    guess = best_guess(location)
    lead_time = config['reminderLeadTimeSeconds']
    if guess:
        location = guess
        lead_time += int(est_traveling_time_seconds(location))
    reminder = Reminder(
        objective=reminder_text,
        location=location,
        time_unlocked=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now(),
        pingChannelId=server_data['pingChannelId'],
        roleMention=server_data['roleMention'],
        time_to_ping=utc_now() + dt.timedelta(hours=hours, minutes=minutes, seconds=seconds-lead_time),
    )
    await submit_reminder(ctx, reminder)

async def submit_reminder(ctx: discord.ApplicationContext, reminder: Reminder):
    existing_reminders = list(REMINDERS.find_by({"objective": reminder.objective, "location": reminder.location}))
    # How far apart are the reminders before being considered duplicates
    exist_msg = ""
    if existing_reminders:
        exist_msg = "Reminder already exists, updated reminder!\n"
        [REMINDERS.delete(r) for r in existing_reminders]
    REMINDERS.save(reminder)
    await ctx.respond(f"{exist_msg}New reminder set: {reminder.objective} at {reminder.location} {make_dc_time(reminder.time_unlocked)}", ephemeral=True)

@bot.slash_command(name="upcoming", description="List upcoming reminders")
async def upcoming(ctx: discord.ApplicationContext):
    # sorted by time_to_ping
    pending_reminders = list(REMINDERS.find_by({}, sort=[("time_to_ping", 1)]))
    if not pending_reminders:
        await ctx.respond("No upcoming reminders", ephemeral=True)
        return
    msg = [
        f"{reminder.objective} in {reminder.location} {make_dc_time(reminder.time_unlocked)}"
    for reminder in pending_reminders]
    await ctx.respond("\n".join(msg))

@bot.slash_command(name="depo", description="Set a timer for leechers on depo time, sends immediately")
async def depo(
    ctx: discord.ApplicationContext,
    color: Option(str, choices=COLOUR_CHOICES, required=True),
    type: Option(str, choices=("Core", "Vortex"), required=True),
    location: Option(str, required=True),
    minutes: Option(int, required=True, min_value=0, max_value=59),
):
    server_data = config['approvedServers'].get(str(ctx.guild_id), {})
    if not server_data:
        await ctx.respond("This server is not approved to use this command.")
        return
    location = best_guess(location) or location
    msg = [
        f"{server_data['roleMention']} Come leech {color} {type} in {location}", 
        f"Depo {make_dc_time(utc_now() + dt.timedelta(minutes=minutes))}  -- {ctx.author.mention}",
    ]
    await bot.get_channel(int(server_data['pingChannelId'])).send("\n".join(msg))

@bot.slash_command(name="delete", description="Delete a reminder")
async def delete(ctx: discord.ApplicationContext):
    if ctx.author.id == 279919612299182080:
        user_reminders = list(REMINDERS.find_by({}))
    else:
        user_reminders = list(REMINDERS.find_by({"submitter": ctx.author.mention}))
    if not user_reminders:
        await ctx.respond("No reminders available to you...", ephemeral=True)
        return
    view = View()
    select = Select(
        placeholder="Choose reminder to delete...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label=f"{reminder.objective} in {reminder.location}", value=str(reminder.id)) 
        for reminder in user_reminders],
    )
    async def callback(interaction: discord.Interaction):
        reminder = REMINDERS.find_one_by_id(PydanticObjectId(interaction.data['values'][0]))
        REMINDERS.delete(reminder)
        await interaction.response.edit_message(content=f"Deleted Reminder: {reminder.objective} in {reminder.location}", view=None)
    select.callback = callback

    view.add_item(select)
    await ctx.respond(view=view,ephemeral=True)

@bot.slash_command(name="roads", description="Add a an ava portal connection")
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
async def route(ctx: discord.ApplicationContext, start: Option(str, required=True), end: Option(str, required=True)):
    start = best_guess(start)
    end = best_guess(end)
    if not start or not end:
        await ctx.respond("Unable to guess exact map names. Please retry command with full map names", ephemeral=True)
        return
    portals: list[Portal] = list(PORTALS.find_by({}))
    roads = [(portal.from_map_id, portal.to_map_id) for portal in portals]
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
        "User /core, /vortex, or /remind",
        "**/core <color> <location> <hours> <minutes> <seconds>**",
        "**/vortex <color> <location> <hours> <minutes> <seconds>**",
        "**/remind <reminder text> <location> <hours> <minutes> <seconds>**",
    ]
    await ctx.respond("\n".join(msg), ephemeral=True)

@bot.event
async def on_ready():
    check_mongo_updates.start()
    await bot.sync_commands()
    print(f"Bot ready!")

if __name__ == "__main__":
    bot.run(config["botToken"])