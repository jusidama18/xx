import os

class Config(object):
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    TELEGRAM_ID = int(os.environ.get("TELEGRAM_ID", 12345))
    TELEGRAM_HASH = os.environ.get("TELEGRAM_HASH")
    OWNER_ID = int(os.environ.get("OWNER_ID", 1303747114))
    AUTH_CHANNEL = set(int(x)
                       for x in os.environ.get("AUTH_CHANNEL", "-1001221644423").split())
