import os

class Config(object):
    AUTH_CHANNEL = set(int(x)
                       for x in os.environ.get("AUTH_CHANNEL", "").split())
