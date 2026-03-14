import os 

from frozendict import frozendict as freezed
from dotenv_vault import load_dotenv
load_dotenv()

envs = freezed({
    "KITE_BASE_URL": os.getenv("KITE_BASE_URL"),
    "KITE_USER_ID": os.getenv("KITE_USER_ID"),
    "KITE_API_KEY": os.getenv("KITE_API_KEY"),
    "KITE_API_SECRET": os.getenv("KITE_API_SECRET"),
    "KITE_REQUEST_TOKEN": os.getenv("KITE_REQUEST_TOKEN"),
    "KITE_ACCESS_TOKEN": os.getenv("KITE_ACCESS_TOKEN"),
    "KITE_PUBLIC_TOKEN": os.getenv("KITE_PUBLIC_TOKEN"),
})
