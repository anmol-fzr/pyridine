from kiteconnect import KiteConnect
from utils.envs import envs
from functools import cache
from utils.funcs import get_sha256

@cache
def get_kite():
    api_key = envs.get("KITE_API_KEY")
    return KiteConnect(api_key)


@cache
def gen_checksum(api_key: str, req_token: str, api_secret: str): 
    combine = api_key + req_token + api_secret
    checksum = get_sha256(combine)
    return checksum

def get_kite_checksum(): 
    api_key = envs.get("KITE_API_KEY")
    req_token = envs.get("KITE_REQUEST_TOKEN")
    api_secret= envs.get("KITE_API_SECRET")

    return gen_checksum(api_key, req_token, api_secret)

