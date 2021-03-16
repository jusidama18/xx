import os

class Config(object):
    OWNER_ID = int(os.environ.get("OWNER_ID", 1303747114))
    AUTH_CHANNEL = set(int(x)
                       for x in os.environ.get("AUTH_CHANNEL", "-1001221644423").split())
