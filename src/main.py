import sys
import webbrowser
import kiteconnect

from modules.strategy.test_moving_average_strategy import MovingAverageStrategyTester
from utils.envs import envs
from utils.kite import get_kite
import pandas as pd

req_token = envs.get("KITE_REQUEST_TOKEN")
api_secret = envs.get("KITE_API_SECRET")
access_token = envs.get("KITE_ACCESS_TOKEN")

kite = get_kite()

try:
    if access_token:
        kite.set_access_token(access_token)

    # test authentication
    profile = kite.profile()
    #print(profile)

    data = MovingAverageStrategyTester(kite)

    print(data)

    df = pd.DataFrame(data)
    df.to_csv("MovingAverageStrategyTester_result.csv", index=False)

except kiteconnect.exceptions.TokenException:
    print("Access token invalid or expired.")

    if req_token:
        print("Generating new access token...")

        data = kite.generate_session(req_token, api_secret)
        kite.set_access_token(data["access_token"])

        print("New access token:", data["access_token"])
    else:
        print("Opening Kite login to obtain request_token...")
        webbrowser.open(kite.login_url())
        sys.exit(1)

except Exception as e:
    print("Unhandled error:", e)
    sys.exit(1)
