from telegram.ext import CommandHandler, run_async
from bot.helper.mirror_utils.upload_utils.gdriveToolz import GoogleDriveHelper
from bot import LOGGER, dispatcher
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, editMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands

@run_async
def list_drive(update,context):
    try:
        search = update.message.text.split(' ',maxsplit=1)[1]
        
        
        reply = sendMessage('Wait a minute to searching the file you are looking for.\n\nSearching...', context.bot, update)
        
        LOGGER.info(f"⌛ Searching : {search} 🔎")
        gdrive = GoogleDriveHelper(None)
        msg, button = gdrive.drive_list(search)

        if button:
            editMessage(msg, reply, button)
        else:
            editMessage('No result found.', reply, button)

    except IndexError:
        sendMessage('Send a search key along with command 🤔', context.bot, update)
        return


list_handler = CommandHandler(BotCommands.ListCommand, list_drive,filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
dispatcher.add_handler(list_handler)
