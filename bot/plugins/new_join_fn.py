#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler

import logging

import pyrogram

app = Client("MirrorBot")

# the logging things
AUTH_CHANNEL = [-1001221644423]

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)


async def new_join_f(client, message):
    chat_type = message.chat.type
    if chat_type != "private":
        await message.reply_text(f"Current CHAT ID: <code>{message.chat.id}</code>")
        # leave chat
        await client.leave_chat(
            chat_id=message.chat.id,
            delete=True
        )
    # delete all other messages, except for AUTH_CHANNEL
    await message.delete(revoke=True)


async def help_message_f(client, message):
    # await message.reply_text("no one gonna help you 🤣🤣🤣🤣", quote=True)
    #channel_id = str(AUTH_CHANNEL)[4:]
    #message_id = 99
    # display the /help

    await message.reply_text("""Follow Our Channel @Jusidama\n\n And also don't forget to Join Our Group, Link In Our <a href="https://t.me/Jusidama">Channel</a>""", disable_web_page_preview=False)
    
    new_join_handler = MessageHandler(
        new_join_f,
        filters=~filters.chat(chats=AUTH_CHANNEL)
    )
    
    group_new_join_handler = MessageHandler(
        help_message_f,
        filters=filters.chat(chats=AUTH_CHANNEL) & filters.new_chat_members
    )

# async def rename_message_f(client, message):
#     inline_keyboard = []
#     inline_keyboard.append([
#         pyrogram.InlineKeyboardButton(
#             text="read this?",
#             url="https://t.me/keralagram/698909"
#         )
#     ])
#     reply_markup = pyrogram.InlineKeyboardMarkup(inline_keyboard)
#     await message.reply_text(
#         "please use @renamebot",
#         quote=True,
#         reply_markup=reply_markup
#     )
    app.add_handler(new_join_handler)
    app.add_handler(group_new_join_handler)
