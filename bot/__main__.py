import shutil, psutil
import signal
import pickle
from bot import app
from os import execl, path, remove
from sys import executable
import time
from pyrogram import idle
from telegram.ext import CommandHandler, run_async
from bot import dispatcher, updater, botStartTime
from bot.gDrive import GoogleDriveHelper
from bot.fs_utils import get_readable_file_size
from bot import LOGGER, dispatcher, updater, bot
from bot.config import BOT_TOKEN, OWNER_ID, GDRIVE_FOLDER_ID
from bot.decorators import is_authorised, is_owner
from telegram.error import TimedOut, BadRequest
from bot.clone_status import CloneStatus
from bot.msg_utils import deleteMessage, sendMessage
from bot.helper.ext_utils import fs_utils
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import *
from .helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time
from .helper.telegram_helper.filters import CustomFilters
from .modules import authorize, list, cancel_mirror, mirror_status, mirror, clone, watch, shell, eval, anime, stickers, search, delete, speedtest, usage

REPO_LINK = "https://t.me/jusidama"
# Soon to be used for direct updates from within the bot.

@run_async
def stats(update, context):
    currentTime = get_readable_time((time.time() - botStartTime))
    total, used, free = shutil.disk_usage('.')
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    cpuUsage = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    stats = f'<b>🤖 The Robot Stats Monitor 🤖</b>\n\n<b>⏱️ Bot Uptime:</b> {currentTime}\n' \
            f'<b>Total disk space🗄️:</b> {total}\n' \
            f'<b>Used 🗃️:</b> {used}  ' \
            f'<b>Free 🗃️:</b> {free}\n\n' \
            f'📇Data Usage📇\n<b>Uploaded :</b> {sent}\n' \
            f'<b>Downloaded:</b> {recv}\n\n' \
            f'<b>CPU 🖥️:</b> {cpuUsage}% ' \
            f'<b>RAM ⛏️:</b> {memory}% ' \
            f'<b>Disk 🗄️:</b> {disk}%'
    sendMessage(stats, context.bot, update)


@run_async
def start(update, context):
    LOGGER.info('UID: {} - UN: {} - MSG: {}'.format(update.message.chat.id,update.message.chat.username,update.message.text))
    if update.message.chat.type == "private" :
        sendMessage(f"Hey <b>{update.message.chat.first_name}</b>. Welcome to <b>@Jusidama18,\n\n🤖 This is a bot which can mirror all your links to Google drive!</b>", context.bot, update)
    else :
        sendMessage("I'm alive :)", context.bot, update)


@run_async
def restart(update, context):
    restart_message = sendMessage("🛠 Bot Restarting, Please wait !", context.bot, update)
    # Save restart message object in order to reply to it after restarting
    fs_utils.clean_all()
    with open('restart.pickle', 'wb') as status:
        pickle.dump(restart_message, status)
    execl(executable, executable, "-m", "bot")


@run_async
def ping(update, context):
    start_time = int(round(time.time() * 1000))
    reply = sendMessage("🏓 Starting Ping", context.bot, update)
    end_time = int(round(time.time() * 1000))
    editMessage(f'🏓 Pong {end_time - start_time} ms', reply)


@run_async
def log(update, context):
    sendLogFile(context.bot, update)


@run_async
def bot_help(update, context):
    help_string = f'''
/{BotCommands.HelpCommand} 📣 : To get this message

/{BotCommands.MirrorCommand} 📣 [download_url][magnet_link]: Start mirroring the link to google drive

/{BotCommands.UnzipMirrorCommand} 📣  [download_url][magnet_link] : starts mirroring and if downloaded file is any archive , extracts it to google drive

/{BotCommands.TarMirrorCommand} 📣  [download_url][magnet_link]: start mirroring and upload the archived (.tar) version of the download

/{BotCommands.WatchCommand} 📣  [youtube-dl supported link]: Mirror through youtube-dl. Click /{BotCommands.WatchCommand} for more help.

/{BotCommands.TarWatchCommand} 📣 [youtube-dl supported link]: Mirror through youtube-dl and tar before uploading

/{BotCommands.CancelMirror} 📣  : Reply to the message by which the download was initiated and that download will be cancelled

/{BotCommands.StatusCommand} 📣 : Shows a status of all the downloads

/{BotCommands.ListCommand} 📣  [search term]: Searches the search term in the Google drive, if found replies with the link

/{BotCommands.StatsCommand} 📣:  Show Stats of the machine the bot is hosted on

/{BotCommands.AuthorizeCommand} 📣 : Authorize a chat or a user to use the bot (Can only be invoked by owner of the bot)

/{BotCommands.LogCommand} 📣 : Get a log file of the bot. Handy for getting crash reports

/{BotCommands.SpeedCommand} : Doing check on speedtest

/{BotCommands.CloneCommand} : Clone GDrive link to Google Drive

/{BotCommands.UsageCommand} : Displays the remaining usage dyno for this month

/helptorrent 📣 : Show command to search torrent or magnet.

/weeb 📣 : Show command to search Anime and Manga .

/helpsticker 📣 : Show command to create sticker.
'''
    sendMessage(help_string, context.bot, update)

@run_async
def helper(update, context):
    sendMessage('''Here are the available commands of the bot\n\n*Usage:* `/clonebot1 <link> [DESTINATION_ID]`
            \n*Example:* \n1. `/clonebot1 https://drive.google.com/drive/u/1/folders/0AO-ISIXXXXXXXXXXXX`\n2. `/clonebot1 0AO-ISIXXXXXXXXXXXX`"
            \n*DESTIONATION_ID* is optional. It can be either link or ID to where you wish to store a particular clone.1 \
            \n\nYou can also *ignore folders* from clone process by doing the following:\n \
                `/clonebot1 <FOLDER_ID> [DESTINATION] [id1,id2,id3]`\n 
                In this example: id1, id2 and id3 would get ignored from cloning\nDo not use <> or [] in actual message. \
                    *Make sure to not put any space between commas (,).*\n" \
                        f"Any Problem? Just ask at our [Channel]({REPO_LINK})", context.bot, update, "Markdown" ''')

# TODO Cancel Clones with /cancel command.
@run_async
@is_authorised
def cloneNode(update, context):
    args = update.message.text.split(" ")
    if len(args) > 1:
        link = args[1]
        try:
            ignoreList = args[-1].split(',')
        except IndexError:
            ignoreList = []

        DESTINATION_ID = GDRIVE_FOLDER_ID
        try:
            DESTINATION_ID = args[2]
            print(DESTINATION_ID)
        except IndexError:
            pass
            # Usage: /clone <FolderToClone> <Destination> <IDtoIgnoreFromClone>,<IDtoIgnoreFromClone>

        msg = sendMessage(f"<b>Cloning:</b> <code>{link}</code>", context.bot, update)
        status_class = CloneStatus()
        gd = GoogleDriveHelper(GFolder_ID=DESTINATION_ID)
        sendCloneStatus(update, context, status_class, msg, link)
        result = gd.clone(link, status_class, ignoreList=ignoreList)
        deleteMessage(context.bot, msg)
        status_class.set_status(True)
        sendMessage(result, context.bot, update)
    else:
        sendMessage("Please Provide a Google Drive Shared Link to Clone.", bot, update)
@run_async
def sendCloneStatus(update, context, status, msg, link):
    old_text = ''
    while not status.done():
        sleeper(3)
        try:
            text=f'🔗 *Cloning:* [{status.MainFolderName}]({status.MainFolderLink})\n━━━━━━━━━━━━━━\n🗃️ *Current File:* `{status.get_name()}`\n⬆️ *Transferred*: `{status.get_size()}`\n📁 *Destination:* [{status.DestinationFolderName}]({status.DestinationFolderLink})'
            if status.checkFileStatus():
                text += f"\n🕒 *Checking Existing Files:* `{str(status.checkFileStatus())}`"
            if not text == old_text:
                msg.edit_text(text=text, parse_mode="Markdown", timeout=200)
                old_text = text
        except Exception as e:
            LOGGER.error(e)
            if str(e) == "Message to edit not found":
                break
            sleeper(2)
            continue
    return

def sleeper(value, enabled=True):
    time.sleep(int(value))
    return

def main():
    fs_utils.start_cleanup()
    # Check if the bot is restarting
    if path.exists('restart.pickle'):
        with open('restart.pickle', 'rb') as status:
            restart_message = pickle.load(status)
        restart_message.edit_text("Restarted Successfully!")
        remove('restart.pickle')
    
    start_handler = CommandHandler(BotCommands.StartCommand, start,
                                   filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    ping_handler = CommandHandler(BotCommands.PingCommand, ping,
                                  filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    restart_handler = CommandHandler(BotCommands.RestartCommand, restart,
                                     filters=CustomFilters.owner_filter| CustomFilters.authorized_user)
    help_handler = CommandHandler(BotCommands.HelpCommand,
                                  bot_help, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    stats_handler = CommandHandler(BotCommands.StatsCommand,
                                   stats, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
    log_handler = CommandHandler(BotCommands.LogCommand, log, filters=CustomFilters.owner_filter)
    clone_handler = CommandHandler(BotCommands.clnCommand, cloneNode)
    helps_handler = CommandHandler(BotCommands.hclnCommand, helper)
    
    dispatcher.add_handler(clone_handler)
    dispatcher.add_handler(helps_handler)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(ping_handler)
    dispatcher.add_handler(restart_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(stats_handler)
    dispatcher.add_handler(log_handler)
    updater.start_polling()
    LOGGER.info("Bot Started!")
    signal.signal(signal.SIGINT, fs_utils.exit_clean_up)
    updater.start_polling()
    LOGGER.info("Yeah I'm Running!")
    updater.idle()
    
main()
