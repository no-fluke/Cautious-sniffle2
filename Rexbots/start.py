# Rexbots
# Don't Remove Credit
# Telegram Channel @RexBots_Official

import os
import asyncio
import random
import time
import shutil
import pyrogram
from pyrogram import Client, filters, enums
from pyrogram.errors import (
    FloodWait, UserIsBlocked, InputUserDeactivated, UserAlreadyParticipant,
    InviteHashExpired, UsernameNotOccupied, AuthKeyUnregistered,
    UserDeactivated, UserDeactivatedBan
)
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from config import API_ID, API_HASH, ERROR_MESSAGE, DOWNLOAD_DELAY
from database.db import db
import math
from Rexbots.strings import HELP_TXT, COMMANDS_TXT
from logger import LOGGER

logger = LOGGER(__name__)

# -------------------
# Utils
# -------------------

def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
          ((str(hours) + "h, ") if hours else "") + \
          ((str(minutes) + "m, ") if minutes else "") + \
          ((str(seconds) + "s, ") if seconds else "")
    return tmp[:-2] if tmp else "0s"

# -------------------
# Batch controller
# -------------------

class batch_temp(object):
    IS_BATCH = {}

# -------------------
# NEW HELPERS (ADDED)
# -------------------

async def anti_ban_delay(msg):
    try:
        await msg.edit(
            f"⏳ Waiting {DOWNLOAD_DELAY} seconds before download (anti-ban)"
        )
    except:
        pass
    await asyncio.sleep(DOWNLOAD_DELAY)


async def wait_for_final_file(folder, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        for f in os.listdir(folder):
            if not f.endswith(".temp") and not f.endswith(".part"):
                return os.path.join(folder, f)
        await asyncio.sleep(0.5)
    raise Exception("Download not finalized")

# -------------------
# Reactions
# -------------------

REACTIONS = [
    "🤝","😇","🤗","😍","👍","🎅","😐","🥰","🤩",
    "😱","🤣","😘","👏","😛","😈","🎉","⚡️","🫡",
    "🤓","😎","🏆","🔥","🤭","🌚","🆒","👻","😁"
]

# -------------------
# Progress UI
# -------------------

PROGRESS_BAR_DASHBOARD = """\
<blockquote>
✦ <code>{bar}</code> • <b>{percentage:.1f}%</b><br>
›› <b>Speed</b> • <code>{speed}/s</code><br>
›› <b>Size</b> • <code>{current} / {total}</code><br>
›› <b>ETA</b> • <code>{eta}</code><br>
›› <b>Elapsed</b> • <code>{elapsed}</code>
</blockquote>
"""

def progress(current, total, message, type):
    if batch_temp.IS_BATCH.get(message.from_user.id):
        raise Exception("Cancelled")

    if not hasattr(progress, "cache"):
        progress.cache = {}
    if not hasattr(progress, "start_time"):
        progress.start_time = {}

    now = time.time()
    task_id = f"{message.id}{type}"

    if task_id not in progress.start_time:
        progress.start_time[task_id] = now

    last = progress.cache.get(task_id, 0)
    if now - last < 3 and current != total:
        return

    percent = current * 100 / total
    speed = current / (now - progress.start_time[task_id])
    eta = (total - current) / speed if speed else 0
    elapsed = now - progress.start_time[task_id]

    bar = "▰" * int(percent / 10) + "▱" * (10 - int(percent / 10))

    status = PROGRESS_BAR_DASHBOARD.format(
        bar=bar,
        percentage=percent,
        current=humanbytes(current),
        total=humanbytes(total),
        speed=humanbytes(speed),
        eta=TimeFormatter(eta * 1000),
        elapsed=TimeFormatter(elapsed * 1000)
    )

    with open(f"{message.id}{type}status.txt", "w", encoding="utf-8") as f:
        f.write(status)

    progress.cache[task_id] = now

    if current == total:
        progress.cache.pop(task_id, None)
        progress.start_time.pop(task_id, None)

# -------------------
# Download / Upload status (UNCHANGED)
# -------------------

async def downstatus(client, statusfile, message, chat):
    while not os.path.exists(statusfile):
        await asyncio.sleep(3)
    while os.path.exists(statusfile):
        try:
            with open(statusfile, "r", encoding="utf-8") as f:
                txt = f.read()
            await client.edit_message_text(chat, message.id, f"📥 **Downloading...**\n\n{txt}")
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(5)


async def upstatus(client, statusfile, message, chat):
    while not os.path.exists(statusfile):
        await asyncio.sleep(3)
    while os.path.exists(statusfile):
        try:
            with open(statusfile, "r", encoding="utf-8") as f:
                txt = f.read()
            await client.edit_message_text(chat, message.id, f"📤 **Uploading...**\n\n{txt}")
            await asyncio.sleep(10)
        except:
            await asyncio.sleep(5)

# -------------------
# CANCEL
# -------------------

@Client.on_message(filters.command(["cancel"]))
async def send_cancel(client, message):
    batch_temp.IS_BATCH[message.from_user.id] = True
    await message.reply_text("❌ Batch Process Cancelled Successfully.")

# -------------------
# MAIN SAVE HANDLER
# -------------------

@Client.on_message(filters.text & filters.private & ~filters.regex("^/"))
async def save(client, message):

    if "https://t.me/" not in message.text:
        return

    if batch_temp.IS_BATCH.get(message.from_user.id) is False:
        return await message.reply_text(
            "One task already processing. Use /cancel"
        )

    datas = message.text.split("/")
    temp = datas[-1].replace("?single", "").split("-")
    fromID = int(temp[0])
    toID = int(temp[1]) if len(temp) > 1 else fromID

    batch_temp.IS_BATCH[message.from_user.id] = False

    for msgid in range(fromID, toID + 1):
        if batch_temp.IS_BATCH.get(message.from_user.id):
            break

        user_data = await db.get_session(message.from_user.id)
        if not user_data:
            await message.reply("**You must /login first**")
            batch_temp.IS_BATCH[message.from_user.id] = True
            return

        acc = Client(
            "saverestricted",
            session_string=user_data,
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True
        )
        await acc.connect()

        try:
            await handle_private(client, acc, message, datas[3], msgid)
        finally:
            await acc.disconnect()

        await asyncio.sleep(3)

    batch_temp.IS_BATCH[message.from_user.id] = True

# -------------------
# HANDLE PRIVATE CONTENT
# -------------------

async def handle_private(client, acc, message, chatid, msgid):

    msg = await acc.get_messages(chatid, msgid)
    if msg.empty:
        return

    smsg = await client.send_message(
        message.chat.id,
        "**__Downloading 🚀__**",
        reply_to_message_id=message.id
    )

    # ✅ Anti-ban delay
    await anti_ban_delay(smsg)

    temp_dir = f"downloads/{message.id}"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        asyncio.create_task(downstatus(client, f"{message.id}downstatus.txt", smsg, message.chat.id))
    except:
        pass

    file = await acc.download_media(
        msg,
        file_name=f"{temp_dir}/",
        progress=progress,
        progress_args=[message, "down"]
    )

    # ✅ FIX .temp BUG
    file = await wait_for_final_file(temp_dir)

    try:
        asyncio.create_task(upstatus(client, f"{message.id}upstatus.txt", smsg, message.chat.id))
    except:
        pass

    await client.send_document(
        message.chat.id,
        file,
        reply_to_message_id=message.id,
        progress=progress,
        progress_args=[message, "up"]
    )

    shutil.rmtree(temp_dir, ignore_errors=True)
    await client.delete_messages(message.chat.id, [smsg.id])

# -------------------
# END
# -------------------
