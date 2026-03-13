from utils.kite import get_kite

kite = get_kite()

instruments = kite.instruments()
print(instruments)

# data = kite.historical_data(
#     instrument_token,
#     from_date,
#     to_date,
#     "5minute"
# )
