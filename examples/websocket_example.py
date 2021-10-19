from latoken.client import LatokenClient
from sortedcontainers import SortedDict
import json


# There are 4 simple steps: initialisation, subscribing, dealing with data, running the script.

# Firstly, we create a client object.
latoken = LatokenClient()
# OR (if you want to use private endpoints, you will need to provide apiKey and apiSecret arguments)
# latoken = LatokenClient(apiKey = apiKey, apiSecret = apiSecret)


# Secondly, we subscribe to streams we want. 
# Let's say we want an orderbook of LA/USDT pair and tickers of LA/USDT and LA/ETH pairs in this example.
# Note that you need to subscribe to different streams separately as in this example. Chaining doesn't work here.
latoken.streamBook(pairs = [
							'707ccdf1-af98-4e09-95fc-e685ed0ae4c6/0c3a106d-bde3-4c13-a26e-3fd2394529e5'
							])
latoken.streamPairTickers(pairs = [
							'707ccdf1-af98-4e09-95fc-e685ed0ae4c6/0c3a106d-bde3-4c13-a26e-3fd2394529e5',
							'707ccdf1-af98-4e09-95fc-e685ed0ae4c6/620f2019-33c0-423b-8a9d-cde4d7f8ef7f'
							])


# Thirdly, we write a function that contains what we want to do with the received data.
# This function must me async!
async def consumer(message):
	# Create orderbook template
	order_book = {"bid": SortedDict(), "ask": SortedDict()}

	# Creating a function that would construct and undate an ordered orderbook
	def updateOrderbook(order_book: dict, event: dict) -> dict:
		"""Updates orderbook with new data
		"""

		for side in ("ask", "bid"):
			for entry in event[side]:
				price = float(entry["price"])
				quantity_change = float(entry["quantityChange"])
				order_book[side].setdefault(price, 0)
				order_book[side][price] += float(quantity_change)

		return order_book

	# Insert received data into our orderbook object.
	# Each topic that we subscribe to is assigned a number in the order of subscription starting from 0.
	# 'body' part of the message returns string, so we need to load it as json
	if len(message['headers']) != 0:
		if message['headers']['subscription'] == '0':  # We subscribed to LA/USDT orderbook first, so subscription is 0.
			order_book = updateOrderbook(order_book, json.loads(message['body'])['payload'])
			print(f'LA/USDT orderbook is: {order_book}')

		# Let's imagine we want to know 24 hours change and last price of LA/USDT and LA/ETH pairs.
		if message['headers']['subscription'] == '1':
			la_usdt_24h_change = json.loads(message['body'])['payload']['change24h']
			la_usdt_last_price = json.loads(message['body'])['payload']['lastPrice']
			print(f'LA/USDT last price was: {la_usdt_last_price}')
			print(f'LA/USDT 24 hours change was: {la_usdt_24h_change}%')

		if message['headers']['subscription'] == '2':
			la_eth_24h_change = json.loads(message['body'])['payload']['change24h']
			la_eth_last_price = json.loads(message['body'])['payload']['lastPrice']
			print(f'LA/ETH last price was: {la_eth_last_price}')
			print(f'LA/ETH 24 hours change was: {la_eth_24h_change}%')


# Finally, we launch the connection and run the code.
# Don't forget to put the async function as on_message argument.
latoken.run(latoken.connect(on_message = consumer))
# OR (if you want to use private endpoints, you will need to set signed = True)
# latoken.run(latoken.connect(signed = True, on_message = consumer))

