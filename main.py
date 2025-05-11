import discord
from discord.commands import Option
from discord.ext import tasks
from pymongo import MongoClient
import datetime as dt
import json

from models import *

CONFIG_FILE_PATH = 'config.json'
with open(CONFIG_FILE_PATH, 'r') as f:
    config = json.load(f)

CHOICES_FILE_PATH = 'choices.json'
with open(CHOICES_FILE_PATH, 'r') as f:
    choices = json.load(f)

COLOUR_CHOICES = choices['colours']
LOCATION_CHOICES = choices['locations']
OPEN_WORLD_OBJECTIVES = choices['objectives']
RESOURCES = choices['resources']

bot= discord.Bot()

# MongoDB setup
db = MongoClient(f"mongodb://{config['mongoDbHostname']}:{config['mongoDbPort']}/")["cortex"]
REMINDERS = Reminders(database=db)

def utc_now():
    return dt.datetime.now(dt.timezone.utc)

def time_left_to_str(t: datetime) -> str:
    min, s = divmod((t.replace(tzinfo=dt.timezone.utc) - utc_now()).total_seconds(), 60)
    return f"{int(min)}min {int(s)}s"

@tasks.loop(seconds=config['dbPollingIntervalSeconds'])
async def check_mongo_updates():
    query = {"time_unlocked": {"$lt": utc_now() + timedelta(minutes=config['pingBeforeMinutes'])}}
    pending_reminders = sorted(list(REMINDERS.find_by(query)), key=lambda x: x.time_unlocked)
    for reminder in pending_reminders:
        msg = [
            f"<@&{config['cutThroatRoleId']}> {reminder.objective} in {reminder.location} in {time_left_to_str(reminder.time_unlocked)}",
            f"- Submitted by {reminder.submitter} at {reminder.time_submitted.strftime('%H:%M UTC (%d/%m/%Y)')}"
        ]
        await bot.get_channel(1287246163086671905).send('\n'.join(msg))
        REMINDERS.delete(reminder)

@bot.slash_command(name="core", description="Set a ping timer for a core")
async def set_core_reminder(
    ctx: discord.ApplicationContext,
    color: Option(str, choices=COLOUR_CHOICES, required=True),
    location: Option(str, choices=LOCATION_CHOICES, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    reminder = Reminder(
        objective=f"{color} Core",
        location=location,
        time_unlocked=utc_now() + timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now()
    )
    REMINDERS.save(reminder)
    await ctx.respond(f"New reminder set: {reminder.objective} at {location} at {reminder.time_unlocked.strftime('%H:%M UTC (%d/%m/%Y)')} ({hours}h {minutes}m {seconds}s)")

@bot.slash_command(name="vortex", description="Set a ping timer for a vortex")
async def set_vortex_reminder(
    ctx: discord.ApplicationContext,
    color: Option(str, choices=COLOUR_CHOICES, required=True),
    location: Option(str, choices=LOCATION_CHOICES, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    reminder = Reminder(
        objective=f"{color} Vortex",
        location=location,
        time_unlocked=utc_now() + timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now()
    )
    REMINDERS.save(reminder)
    await ctx.respond(f"New reminder set: {reminder.objective} at {location} at {reminder.time_unlocked.strftime('%H:%M UTC (%d/%m/%Y)')} ({hours}h {minutes}m {seconds}s)")

@bot.slash_command(name="chest", description="Set a ping timer for a chest")
async def set_chest_reminder(
    ctx: discord.ApplicationContext,
    size: Option(str, choices=OPEN_WORLD_OBJECTIVES, required=True),
    location: Option(str, choices=LOCATION_CHOICES, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    reminder = Reminder(
        objective=f"{size} Chest",
        location=location,
        time_unlocked=utc_now() + timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now()
    )
    REMINDERS.save(reminder)
    await ctx.respond(f"New reminder set: {reminder.objective} at {location} at {reminder.time_unlocked.strftime('%H:%M UTC (%d/%m/%Y)')} ({hours}h {minutes}m {seconds}s)")

@bot.slash_command(name="remind", description="Set a ping timer")
async def set_free_reminder(
    ctx: discord.ApplicationContext,
    reminder_text: Option(str, required=True),
    location: Option(str, choices=LOCATION_CHOICES, required=True),
    hours: Option(int, required=True, min_value=0, max_value=24),
    minutes: Option(int, required=True, min_value=0, max_value=59),
    seconds: Option(int, default=0, min_value=0, max_value=59),
):
    reminder = Reminder(
        objective=reminder_text,
        location=location,
        time_unlocked=utc_now() + timedelta(hours=hours, minutes=minutes, seconds=seconds),
        submitter=ctx.author.mention,
        time_submitted=utc_now()
    )
    REMINDERS.save(reminder)
    await ctx.respond(f"New reminder set: {reminder.objective} at {location} at {reminder.time_unlocked.strftime('%H:%M UTC (%d/%m/%Y)')} ({hours}h {minutes}m {seconds}s)")

@bot.event
async def on_ready():
    check_mongo_updates.start()
    await bot.sync_commands()
    print(f"Bot ready!")

if __name__ == "__main__":
    bot.run(config["botToken"])