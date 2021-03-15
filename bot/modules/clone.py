from telegram.ext import CommandHandler, run_async
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.fs_utils import get_readable_file_size
from bot.decorators import is_authorised
from telegram.error import TimedOut, BadRequest
from bot.helper.telegram_helper.message_utils import *
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import new_thread
from bot.config import BOT_TOKEN, OWNER_ID, GDRIVE_FOLDER_ID
from bot.clone_status import CloneStatus
from bot.msg_utils import deleteMessage, sendMessage
from bot import dispatcher, updater, bot

import time

@new_thread
@is_authorised
def cloneNode(update,context):
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
        
        msg = sendMessage(f"🔁 Cloning: <code>{link}</code>",context.bot,update)
        status_class = CloneStatus()
        gd = GoogleDriveHelper(GFolder_ID=DESTINATION_ID)
        sendCloneStatus(update, context, status_class, msg, link)
        result, button = gd.clone(link, status_class, ignoreList=ignoreList)
        deleteMessage(context.bot,msg)
        status_class.set_status(True)
        if button == "":
            sendMessage(result,context.bot,update)
        else:
            sendMarkup(result,context.bot,update,button)
    else:
        sendMessage("⚙️ Provide G-Drive Shareable Link to Clone.",context.bot,update)

@new_thread
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

clone_handler = CommandHandler(BotCommands.CloneCommand,cloneNode,filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(clone_handler)
