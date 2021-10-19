from latoken.client import LatokenClient


# There are 2 simple steps: initialisation, getting data.

# Firstly, we create a client object.
latoken = LatokenClient()
# OR (if you want to use private endpoints, you will need to provide apiKey and apiSecret arguments)
# latoken = LatokenClient(apiKey = apiKey, apiSecret = apiSecret)


# Secondly, we get information from LATOKEN.
# Checking server time
time = latoken.getServerTime()
print(time)

# Get all currencies and create a dictionary with tag: id pairs. 
# A lot of requests would require you submitting a currency id instead of the ticker (tag).
currencies = latoken.getCurrencies()

currencies_dict = dict()

for i in range(len(currencies)):
	if currencies[i]['status'] == 'CURRENCY_STATUS_ACTIVE':
		currencies_dict[currencies[i]['tag']] = currencies[i]['id']

print(currencies_dict['BTC'])


# You can combine websockets and rest api. They are implemented as one class.
