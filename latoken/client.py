import asyncio
import hashlib
import hmac
from time import time
from typing import Optional

import stomper
import websocket
import requests


class LatokenClient:

    baseWS = 'wss://api.latoken.com/stomp'
    baseAPI = 'https://api.latoken.com'

    # REST (calls)
    # Basic info
    user_info_call = '/v2/auth/user'  # PRIVATE
    time_call = '/v2/time'  # PUBLIC
    # Balances (all PRIVATE)
    account_balances_call = '/v2/auth/account'
    currency_balance_by_type_call = '/v2/auth/account/currency/{currency}/{accountType}'
    # Orders (all PRIVATE)
    order_place_call = '/v2/auth/order/place'
    order_cancel_all_call = '/v2/auth/order/cancelAll'
    order_cancel_id_call = '/v2/auth/order/cancel'
    order_cancel_pair_call = '/v2/auth/order/cancelAll/{currency}/{quote}'
    order_status_call = '/v2/auth/order/getOrder/{}'  # Get order by id
    order_pair_active_call = '/v2/auth/order/pair/{currency}/{quote}/active'
    order_pair_all_call = '/v2/auth/order/pair/{currency}/{quote}'
    order_all_call = '/v2/auth/order'  # Provides orders history (closed, cancelled, placed orders)
    # Fees
    fee_levels_call = '/v2/trade/feeLevels'  # PUBLIC
    fee_scheme_per_pair_call = '/v2/trade/fee/{currency}/{quote}'  # PUBLIC
    fee_scheme_par_pair_and_user_call = '/v2/auth/trade/fee/{currency}/{quote}'  # PRIVATE
    # Trades
    trades_user_call = '/v2/auth/trade'  # PRIVATE
    trades_user_pair_call = '/v2/auth/trade/pair/{currency}/{quote}'  # PRIVATE
    trades_all_call = '/v2/trade/history/{currency}/{quote}'  # PUBLIC
    # Books (all PUBLIC)
    orderbook_call = '/v2/book/{currency}/{quote}'
    # Tickers (all PUBLIC)
    tickers_call = '/v2/ticker'
    tickers_per_pair_call = '/v2/ticker/{currency}/{quote}'
    # Currencies and pairs (all PUBLIC)
    active_currency_call = '/v2/currency'  # Available path param not implemented as it returns the same as this endpoint
    currency_call = '/v2/currency/{currency}'
    quote_currency_call = '/v2/currency/quotes'
    active_pairs_call = '/v2/pair'  # Available path param not implemented as it returns the same as this endpoint
    # Historic prices (all PUBLIC)
    weekly_chart_call = '/v2/chart/week'
    weekly_chart_by_pair_call = '/v2/chart/week/{currency}/{quote}'
    candles_call = '/v2/tradingview/history?symbol={currency}%2F{quote}&resolution={resolution}&from={from}&to={to}'
    # Spot transfers (all Private)
    deposit_spot_call = '/v2/auth/spot/deposit'
    withdraw_spot_call = '/v2/auth/spot/withdraw'
    # Transfers (all Private)
    transfer_by_id_call = '/v2/auth/transfer/id'
    transfer_by_phone_call = '/v2/auth/transfer/phone'
    transfer_by_email_call = '/v2/auth/transfer/email'
    transfer_get_all_call = '/v2/auth/transfer'
    # Bindings data (for deposits and withdrawals)
    bindings_active_call = '/v2/transaction/bindings'  # PUBLIC
    bindings_active_currencies_call = '/v2/auth/transaction/bindings'  # PRIVATE
    bindings_currency_call = '/v2/auth/transaction/bindings/{currency}'  # PRIVATE
    # Transactions (all Private)
    deposit_address_call = '/v2/auth/transaction/depositAddress'
    withdrawal_request_call = '/v2/auth/transaction/withdraw'
    withdrawal_cancel_call = '/v2/auth/transaction/withdraw/cancel'
    withdrawal_confirmation_call = '/v2/auth/transaction/withdraw/confirm'
    withdrawal_code_resend_call = '/v2/auth/transaction/withdraw/resendCode'
    transaction_all_call = '/v2/auth/transaction'
    transaction_by_id_call = '/v2/auth/transaction/{id}'

    # WS (streams)
    # Public
    book_stream = '/v1/book/{currency}/{quote}'
    trades_stream = '/v1/trade/{currency}/{quote}'
    currencies_stream = '/v1/currency'  # All available currencies
    pairs_stream = '/v1/pair'  # All available pairs
    ticker_all_stream = '/v1/ticker'
    tickers_pair_stream = '/v1/ticker/{currency}/{quote}'  # 24h and 7d volume and change + last price for pairs
    rates_stream = '/v1/rate/{currency}/{quote}'
    rates_quote_stream = '/v1/rate/{quote}'

    # Private
    orders_stream = '/user/{user}/v1/order'
    accounts_stream = '/user/{user}/v1/account/total'  # Returns all accounts of a user including empty ones
    account_stream = '/user/{user}/v1/account'
    transactions_stream = '/user/{user}/v1/transaction'  # Returns external transactions (deposits and withdrawals)
    transfers_stream = '/user/{user}/v1/transfers'  # Returns internal transfers on the platform (inter_user, ...)

    topics = list()

    # INITIALISATION

    def __init__(self, apiKey: Optional[str] = None, apiSecret: Optional[str] = None,
                 baseAPI: str = baseAPI, baseWS: str = baseWS, topics: list = topics):
        self.apiKey = apiKey
        self.apiSecret = apiSecret
        self.baseAPI = baseAPI
        self.baseWS = baseWS
        self.topics = topics

    # CONTROLLERS

    def _inputController(self, currency: Optional[str] = None, quote: Optional[str] = None,
                         pair: Optional[str] = None, currency_name: Optional[str] = 'currency',
                         quote_name: Optional[str] = 'quote') -> dict:
        """Converting lower case currency tag into upper case as required"""

        def controller(arg):
            if len(arg) == 36:
                return arg
            else:
                return arg.upper()

        if pair:
            currency = pair.split('/')[0]
            quote = pair.split('/')[1]
            pathParams = {
                            str(currency_name): controller(currency),
                            str(quote_name): controller(quote)
                         }
            return pathParams

        elif currency and quote:
            pathParams = {
                            str(currency_name): controller(currency),
                            str(quote_name): controller(quote)
                         }
            return pathParams

        elif currency:
            pathParams = {
                            str(currency_name): controller(currency)
                            }
            return pathParams

    # SIGNATURES

    def _APIsigned(self, endpoint: str, params: dict = None, request_type: Optional[str] = 'get'):
        """Signing get and post private calls by api key and secret by HMAC-SHA512"""

        if params:
            serializeFunc = map(lambda it: it[0] + '=' + str(it[1]), params.items())
            queryParams = '&'.join(serializeFunc)
        else:
            queryParams = ''

        if request_type == 'get':
            signature = hmac.new(
                self.apiSecret,
                ('GET' + endpoint + queryParams).encode('ascii'),
                hashlib.sha512
            )

            url = self.baseAPI + endpoint + '?' + queryParams

            response = requests.get(
                url,
                headers = {
                    'X-LA-APIKEY': self.apiKey,
                    'X-LA-SIGNATURE': signature.hexdigest(),
                    'X-LA-DIGEST': 'HMAC-SHA512'
                    }
            )

        elif request_type == 'post':
            signature = hmac.new(
                self.apiSecret,
                ('POST' + endpoint + queryParams).encode('ascii'),
                hashlib.sha512
            )

            url = self.baseAPI + endpoint

            response = requests.post(
                url,
                headers = {
                    'Content-Type': 'application/json',
                    'X-LA-APIKEY': self.apiKey,
                    'X-LA-SIGNATURE': signature.hexdigest(),
                    'X-LA-DIGEST': 'HMAC-SHA512'
                    },
                json = params
            )

        return response.json()

    # EXCHANGE ENDPOINTS

    def getUserInfo(self) -> dict:
        """Returns information about the authenticated user

        :returns: dict - dict of personal data

        .. code-block:: python

            {
                'id': 'a44444aa-4444-44a4-444a-44444a444aaa',                   # User id (unique for each user)
                'status': 'ACTIVE',                                             # Account status (ACTIVE, DISABLED, FROZEN)
                'role': 'INVESTOR',                                             # Can be ignored
                'email': 'example@email.com',                                   # Email address on user account
                'phone': '',                                                    # Phone number on user account
                'authorities': [..., 'VIEW_TRANSACTIONS', 'PLACE_ORDER', ...],  # List of account priviliges
                'forceChangePassword': None,                                    # Can be ignored
                'authType': 'API_KEY',                                          # Can be ignored
                'socials': []                                                   # Can be ignored
            }

        """

        return self._APIsigned(endpoint = self.user_info_call)


    def getServerTime(self) -> dict:
        """Returns the currenct server time

        :returns: dict

        .. code-block:: python

            {
                'serverTime': 1628934753710
            }

        """

        return requests.get(self.baseAPI + self.time_call).json()


    def getAccountBalances(self,  currency: Optional[str] = None, account_type: Optional[str] = None,
                           zeros: Optional[bool] = False):
        """Returns account balances for all/specific currency and wallet type

        A request for a specific currency and wallet type has a priority over all-currencies request

        :param currency: required for one-currency request, can be currency tag or currency id
        :param account_type: required for one-currency request

        :param zeros: required for all-currencies request, default is False (doesn't return zero balances)
        :type zeros: string (method argument accepts boolean for user convenience)

        :returns: list - list of dictionaries per currency and wallet, if all-currencies request, otherwise one dict

        .. code block:: python

            [...,
                {
                    'id': 'a44444aa-4444-44a4-444a-44444a444aaa',        # Account id (unique for each account of a user)
                    'status': 'ACCOUNT_STATUS_ACTIVE',                   # Currency account status (ACTIVE, DISABLED, FROZEN)
                    'type': 'ACCOUNT_TYPE_SPOT',                         # Account type (SPOT, FUTURES, WALLET, CROWDSALE)
                    'timestamp': 1628381804961,                          # Timestamp when server returned the responce
                    'currency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',  # Currency id
                    'available': '100.830064349760000000',               # Currently available on the account (excludes blocked funds)
                    'blocked': '0.000000'                                # Currently blocked (orders placed, for example)
                },
            ...
            ]

        """

        if currency and account_type:
            pathParams = self._inputController(currency = currency)
            pathParams.update({
                        'accountType': str(account_type)
                        })
            return self._APIsigned(endpoint = self.currency_balance_by_type_call.format(**pathParams))
        else:
            queryParams = {'zeros': str(zeros).lower()}
            return self._APIsigned(endpoint = self.account_balances_call, params = queryParams)


    def getOrders(self, order_id: Optional[str] = None, pair: Optional[str] = None, active: Optional[bool] = False,
                  limit: Optional[int] = 100, timestamp: Optional[str] = None):
        """Returns user orders history

        A request for the order by id has a priority over a request for orders by pair
        that itself has a priority over a request for all orders

        :param order_id: required for a particular order request (other arguments will be ignored)

        :param pair: required for request for orders in a specific pair (should be of format ***/***)
        :param active: optional, defaults to False (returns all orders, otherwise only active are returned)
        :param limit: optional, defaults to 100
        :type limit: string (method argument accepts integer for user convenience)
        :param timestamp: optional, defaults to current (orders before this timestamp are returned)

        :returns: list - list of dictionaries for each order, otherwise dict if only 1 order exists

        .. code block:: python
            [...,
                {
                    'id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                    'status': 'ORDER_STATUS_CLOSED',
                    'side': 'ORDER_SIDE_SELL',
                    'condition': 'ORDER_CONDITION_GOOD_TILL_CANCELLED',
                    'type': 'ORDER_TYPE_LIMIT',
                    'baseCurrency': 'd286007b-03eb-454e-936f-296c4c6e3be9',
                    'quoteCurrency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                    'clientOrderId': 'my order 1',
                    'price': '3.6200',
                    'quantity': '100.000',
                    'cost': '362.0000000',
                    'filled': '100.000',
                    'trader': 'a44444aa-4444-44a4-444a-44444a444aaa',   # User id
                    'timestamp': 1624804464728
                },
            ...
            ]

        """

        if order_id:
            return self._APIsigned(endpoint = self.order_status_call.format(order_id))

        elif pair:
            queryParams = {
                            'from': str(timestamp),
                            'limit': str(limit)
                          }
            queryParams = {x: y for x, y in queryParams.items() if y != 'None'}

            pathParams = self._inputController(pair = pair)

            if active:
                return self._APIsigned(endpoint = self.order_pair_active_call.format(**pathParams), params = queryParams)
            else:
                return self._APIsigned(endpoint = self.order_pair_all_call.format(**pathParams), params = queryParams)

        else:
            queryParams = {
                            'from': str(timestamp),
                            'limit': str(limit)
                          }
            queryParams = {x: y for x, y in queryParams.items() if y != 'None'}
            return self._APIsigned(endpoint = self.order_all_call, params = queryParams)


    def placeOrder(self, pair: str, side: str, client_message: str, price: float, quantity: float,
                   timestamp: int, condition: str = 'GOOD_TILL_CANCELLED', order_type: str = 'LIMIT') -> dict:
        """Places an order

        :param pair: max 20 characters, can be any combination of currency id or currency tag (format ***/***)
        :param side: max 10 characters, can be "BUY", "BID", "SELL", "ASK"
        :param client_message: max 50 characters, write whatever you want here
        :param price: max 50 characters
        :type price: string (method argument accepts float for user convenience)
        :param quantity: max 50 characters
        :type quantity: string (method argument accepts float for user convenience)
        :param timestamp: required for correct signature
        :param condition: max 30 characters, can be "GTC", "GOOD_TILL_CANCELLED" (default),
        "IOC", "IMMEDIATE_OR_CANCEL", "FOK", "FILL_OR_KILL"
        :param order_type: max 30 characters, can be "LIMIT" (default), "MARKET"

        :returns: dict - dict with responce

        .. code block:: python

            {
                'message': 'order accepted for placing',
                'status': 'SUCCESS',
                'id': 'a44444aa-4444-44a4-444a-44444a444aaa'    # Order id
            }

        """

        requestBodyParams = self._inputController(pair = pair, currency_name = 'baseCurrency', quote_name = 'quoteCurrency')
        requestBodyParams.update({
                        'side': str(side.upper()),
                        'condition': str(condition.upper()),
                        'type': str(order_type.upper()),
                        'clientOrderId': str(client_message),
                        'price': str(price),
                        'quantity': str(quantity),
                        'timestamp': int(timestamp)
                      })
        return self._APIsigned(endpoint = self.order_place_call, params = requestBodyParams, request_type = 'post')


    def cancelOrder(self, order_id: Optional[str] = None, pair: Optional[str] = None, cancel_all: Optional[bool] = False) -> dict:
        """Cancels orders

        A request to cancel order by id has a priority over a request to cancel orders by pair
        that itself has a priority over a request to cancel all orders

        :param order_id: required for a particular order cancellation request (other arguments will be ignored)

        :param pair: required for cancel orders in a specific pair (should be of format ***/***)
        :param cancel_all: optional, defaults to False (you should explicitly set it to True to cancel all orders)

        :returns: dict - dict with responce

        .. code block:: python

           {
               'message': 'cancellation request successfully submitted',
               'status': 'SUCCESS',
               'id': 'a44444aa-4444-44a4-444a-44444a444aaa'               # Only returned if a specific order is cancelled
           }

        """

        if order_id:
            requestBodyParams = {'id': str(order_id)}
            return self._APIsigned(endpoint = self.order_cancel_id_call, params = requestBodyParams, request_type = 'post')

        elif pair:
            pathParams = self._inputController(pair = pair)
            return self._APIsigned(endpoint = self.order_cancel_pair_call.format(**pathParams), request_type = 'post')

        elif cancel_all:
            return self._APIsigned(endpoint = self.order_cancel_all_call, request_type = 'post')


    def getTrades(self, pair: Optional[str] = None, user: bool = False, limit: Optional[int] = 100, timestamp: Optional[str] = None):
        """Returns user trades history

        A request for user trades by pair has a priority over a request all user trades
        that itself has a priority over a request for all trades in the market.

        :param user: required for request of trades by user and by user in a specific pair. Defaults to False
        that means that all market trades regardless the user are returned.
        :param pair: required for request for trade of the user in a specific pair (should be of format ***/***)
        :param limit: optional, defaults to 100
        :type limit: string (method argument accepts integer for user convenience)
        :param timestamp: optional, defaults to current (orders before this timestamp are returned)

        :returns: list - list of dictionaries for each trade, otherwise dict if only 1 trade exists

        .. code block:: python
            [...,
                {
                    'id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                    'isMakerBuyer': False,
                    'direction': 'TRADE_DIRECTION_SELL',
                    'baseCurrency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                    'quoteCurrency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                    'price': '30000.00',
                    'quantity': '0.03500',
                    'cost': '1050.00',
                    'fee': '4.095000000000000000',                            # Omitted from public trades (given in quoteCurrency)
                    'order': 'a44444aa-4444-44a4-444a-44444a444aaa',          # Omitted from public trades
                    'timestamp': 1624373391929,
                    'makerBuyer': False
                },
            ...
            ]

        """

        queryParams = {
                        'from': str(timestamp),
                        'limit': str(limit)
                      }
        queryParams = {x: y for x, y in queryParams.items() if y != 'None'}

        if user and pair:  # PRIVATE
            pathParams = self._inputController(pair = pair)
            return self._APIsigned(endpoint = self.trades_user_pair_call.format(**pathParams), params = queryParams)

        elif user:  # PRIVATE
            return self._APIsigned(endpoint = self.trades_user_call, params = queryParams)

        elif pair:  # PUBLIC
            serializeFunc = map(lambda it: it[0] + '=' + str(it[1]), queryParams.items())
            queryParams = '&'.join(serializeFunc)

            pathParams = self._inputController(pair = pair)
            return requests.get(self.baseAPI + self.trades_all_call.format(**pathParams) + '?' + queryParams).json()


    def transferSpot(self, amount: float, currency_id: str, deposit: bool = True) -> dict:
        """Transfers between Spot and Wallet accounts

        :param amount: should be >= 0
        :type amount: string (method argument accepts float for user convenience)
        :param currency_id: apart from other methods, this one only accepts currency id (currency tag will return an error)
        :param deposit: defaults to True (deposit to Spot from Wallet), False means withdraw from Spot to Wallet

        :returns: dict - dict with the transfer result

        .. code block:: python

            {
                'id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                'status': 'TRANSFER_STATUS_PENDING',
                'type': 'TRANSFER_TYPE_DEPOSIT_SPOT',                  # Will be TRANSFER_TYPE_WITHDRAW_SPOT, if deposit set to False
                'fromAccount': 'a44444aa-4444-44a4-444a-44444a444aaa',
                'toAccount': 'a44444aa-4444-44a4-444a-44444a444aaa',
                'transferringFunds': '10',
                'usdValue': '0',
                'rejectReason': '',
                'timestamp': 1629537163208,
                'direction': 'INTERNAL',
                'method': 'TRANSFER_METHOD_UNKNOWN',
                'recipient': '',
                'sender': '',
                'currency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                'codeRequired': False,
                'fromUser': 'a44444aa-4444-44a4-444a-44444a444aaa',    # This is the authenticated user id
                'toUser': 'a44444aa-4444-44a4-444a-44444a444aaa',      # This is the authenticated user id (same as fromUser)
                'fee': '0'
            }

        """

        requestBodyParams = {
                                'value': str(amount),
                                'currency': str(currency_id)
                            }
        if deposit:
            return self._APIsigned(endpoint = self.deposit_spot_call, params = requestBodyParams, request_type = 'post')

        elif deposit == False:
            return self._APIsigned(endpoint = self.withdraw_spot_call, params = requestBodyParams, request_type = 'post')


    def transferAccount(self, amount: float, currency_id: str, user_id: Optional[str] = None,
                        phone: Optional[str] = None, email: Optional[str] = None) -> dict:
        """Transfers between external to the user accounts (within exchange)

        A request for transfer by user_id has a priority over the request for transfer by phone
        that itself has a priority over the request for transfer by email

        :param amount: should be >= 0
        :type amount: string (method argument accepts float for user convenience)
        :param currency_id: apart from other methods, this one only accepts currency id (currency tag will return an error)

        :param user_id: required for transfer by user_id, other arguments (phone and email) will be ignored
        :param phone: required for transfer by phone, other argument (email) will be ignored
        :param email: required for transfer by email, will only be used if other arguments are not present

        :returns: dict - dict with the transfer result

        .. code block:: python

            {
                'id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                'status': 'TRANSFER_STATUS_UNVERIFIED',
                'type': 'TRANSFER_TYPE_INTER_USER',
                'fromAccount': None,
                'toAccount': None,
                'transferringFunds': '10',
                'usdValue': '0',
                'rejectReason': None,
                'timestamp': 1629539250161,
                'direction': 'OUTCOME',
                'method': 'TRANSFER_METHOD_DIRECT',
                'recipient': 'a44444aa-4444-44a4-444a-44444a444aaa',
                'sender': 'exampleemail@email.com',
                'currency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                'codeRequired': False,
                'fromUser': 'a44444aa-4444-44a4-444a-44444a444aaa',
                'toUser': 'b44444aa-4444-44b4-444a-33333a444bbb',
                'fee': None
            }

        """

        requestBodyParams = {
                                'value': str(amount),
                                'currency': str(currency_id)
                            }
        if user_id:
            requestBodyParams.update({'recipient': str(user_id)})
            return self._APIsigned(endpoint = self.transfer_by_id_call, params = requestBodyParams, request_type = 'post')

        elif phone:
            requestBodyParams.update({'recipient': str(phone)})
            return self._APIsigned(endpoint = self.transfer_by_phone_call, params = requestBodyParams, request_type = 'post')

        elif email:
            requestBodyParams.update({'recipient': str(email)})
            return self._APIsigned(endpoint = self.transfer_by_email_call, params = requestBodyParams, request_type = 'post')

        else:
            print('No transfer method provided')


    def getTransfers(self, page: Optional[int] = 0, size: Optional[int] = 10) -> dict:
        """Returns history of user transfers without their account and to other users

        :param page: should be >= 0
        :param size: should be 1-1000 (defaults to 10), number of results returned per page

        :returns: dict - dict with transfers history (from the most recent to the least recent)

        .. code block:: python

            {
                'hasNext': True,                                                 # Means that it has the next page
                'content': [
                    {
                        'id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'status': 'TRANSFER_STATUS_UNVERIFIED',
                        'type': 'TRANSFER_TYPE_INTER_USER',
                        'fromAccount': None,
                        'toAccount': None,
                        'transferringFunds': '10',
                        'usdValue': '0',
                        'rejectReason': None,
                        'timestamp': 1629539250161,
                        'direction': 'OUTCOME',
                        'method': 'TRANSFER_METHOD_DIRECT',
                        'recipient': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'sender': 'exampleemail@email.com',
                        'currency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                        'codeRequired': False,
                        'fromUser': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'toUser': 'a44444aa-4444-44a4-444a-44444a444bbb',
                        'fee': None
                    },
                    {
                        'id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'status': 'TRANSFER_STATUS_PENDING',
                        'type': 'TRANSFER_TYPE_DEPOSIT_SPOT',
                        'fromAccount': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'toAccount': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'transferringFunds': '10',
                        'usdValue': '0',
                        'rejectReason': '',
                        'timestamp': 1629537163208,
                        'direction': 'INTERNAL',
                        'method': 'TRANSFER_METHOD_UNKNOWN',
                        'recipient': '',
                        'sender': '',
                        'currency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                        'codeRequired': False,
                        'fromUser': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'toUser': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'fee': '0'000000000000000'
                    }],
                'first': True,                                                  # Means that this is the first page and there is no page before
                'pageSize': 1,
                'hasContent': True                                              # Means that page is not empty
            }

        """

        queryParams = {
                        'page': str(page),
                        'size': str(size)
                    }
        return self._APIsigned(endpoint = self.transfer_get_all_call, params = queryParams)


    def makeWithdrawal(self, currency_binding_id: str, amount: float, address: str, memo: Optional[str] = None,
                       twoFaCode: Optional[str] = None) -> dict:
        """Makes a withdrawal from LATOKEN

        :param currency_binding_id: LATOKEN internal OUTPUT binding id (each currency has a separate INPUT and OUTPUT binding per each provider)
        :type amount: string (method argument accepts float for user convenience)

        :returns: dict - dict with the transaction result

        .. code block:: python

            {
                'withdrawalId': 'a44444aa-4444-44a4-444a-44444a444aaa',
                'codeRequired': False,
                'transaction': {
                                    'id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                                    'status': 'TRANSACTION_STATUS_PENDING',
                                    'type': 'TRANSACTION_TYPE_WITHDRAWAL',
                                    'senderAddress': None,
                                    'recipientAddress': 'TTccMcccM8ccMcMMc46KHzv6MeMeeeeeee',  # Address to send withdrawal to
                                    'amount': '20',
                                    'transactionFee': '3',                                     # Fee in sent currency
                                    'timestamp': 1629561656227,
                                    'transactionHash': None,                                   # Not present in response as status is pending
                                    'blockHeight': None,                                       # Not present in response as status is pending
                                    'currency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                                    'memo': None,
                                    'paymentProvider': None,                                   # LATOKEN payment provider id
                                    'requiresCode': False
                               }
            }

        """

        requestBodyParams = {
            'currencyBinding': str(currency_binding_id),
            'amount': str(amount),
            'recipientAddress': str(address),
            'memo': str(memo),
            'twoFaCode': str(twoFaCode)
            }
        requestBodyParams = {x: y for x, y in requestBodyParams.items() if y != 'None'}
        return self._APIsigned(endpoint = self.withdrawal_request_call, params = requestBodyParams, request_type = 'post')


    def cancelWithdrawal(self, withdrawal_id: str) -> dict:
        """Cancel UNVERIFIED withdrawal

        :returns: dict - dict with the cancellation result

        """

        requestBodyParams = {'id': str(withdrawal_id)}
        return self._APIsigned(endpoint = self.withdrawal_cancel_call, params = requestBodyParams, request_type = 'post')


    def confirmWithdrawal(self, withdrawal_id: str, code: str) -> dict:
        """Confirm UNVERIFIED withdrawal

        :returns: dict - dict with the confirmation result

        """

        requestBodyParams = {
            'id': str(withdrawal_id),
            'confirmationCode': str(code)
            }
        return self._APIsigned(endpoint = self.withdrawal_confirmation_call, params = requestBodyParams, request_type = 'post')


    def resendCode(self, withdrawal_id: str) -> dict:
        """Resends verification code for UNVERIFIED withdrawal confirmation

        :returns: dict - dict with the code result

        """

        requestBodyParams = {'id': str(withdrawal_id)}
        return self._APIsigned(endpoint = self.withdrawal_code_resend_call, params = requestBodyParams, request_type = 'post')


    def getDepositAddress(self, currency_binding_id: str) -> dict:
        """Returns a deposit address

        :param currency_binding_id: LATOKEN internal INPUT binding id

        :returns: dict - dict with the operation message and deposit address

        .. code block:: python

            {
                'message': 'address generated',
                'status': 'SUCCESS',
                'depositAccount': {
                                    'address': '0x55bb55b5b555bbb5bbb5b02555bbbb5bb5555bbb',
                                    'memo': ''
                                  }
            }

        """

        requestBodyParams = {'currencyBinding': str(currency_binding_id)}
        return self._APIsigned(endpoint = self.deposit_address_call, params = requestBodyParams, request_type = 'post')


    def getWithdrawalBindings(self) -> list:
        """Returns a list of OUTPUT bindings

        .. code block:: python

            [{
                'id': '230a4acf-e1c6-440d-a59f-607a5fb1c390',                  # Currency id
                'tag': 'ARX',
                'bindings': [{
                    'minAmount': '144.000000000000000000',                     # In transacted currency
                    'fee': '48.000000000000000000',                            # In transacted currency
                    'percentFee': '1.000000000000000000',                      # In %
                    'providerName': 'ERC20',                                   # Protocol that currency supports (once currency can have multiple providers)
                    'id': 'dbd3d401-8564-4d5d-9881-6d4b70d439b0',              # OUTPUT currency binding id
                    'currencyProvider': '35607b89-df9e-47bd-974c-d7ca378fe4e6'
                    }]
            },
            ...
            ]

        """

        return requests.get(self.baseAPI + self.bindings_active_call).json()


    def getActiveCurrencyBindings(self) -> dict:
        """Returns active currency bindings

        :returns: dict - dict with currency ids for active INPUT (deposits) and OUTPUT (withdrawals) bindings

        .. code block:: python

            {
                'inputs': [
                            'bf7cfeb8-2a8b-4356-a600-2b2f34c85fc9',
                            'ceb03f7c-2bcf-4775-9e6d-8dd95610abb7',
                            ...
                          ],
                'outputs':[
                            '2e72c082-1de2-4010-bda9-d28aac11755d',
                            '6984a559-3ec0-4f84-bd25-166fbff69a7a',
                            ...
                          ]
            }

        """

        return self._APIsigned(endpoint = self.bindings_active_currencies_call)


    def getCurrencyBindings(self, currency: str) -> list:
        """Returns all bindings of a specific currencies

        :param currency: can be either currency id or currency tag

        :returns: list - list with dict per each currency binding (both active and inactive)

        .. code block:: python

            [{
                'id': '7d28ec03-6d1a-4586-b38d-df4b334cec1c',
                'currencyProvider': '9899d208-a3e5-46bc-a594-3048b1a982bc',
                'status': 'CURRENCY_BINDING_STATUS_ACTIVE',
                'type': 'CURRENCY_BINDING_TYPE_OUTPUT',
                'currency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'minAmount': '0.001000000000000000',
                'fee': '0.000500000000000000',
                'percentFee': '1.000000000000000000',
                'warning': '',
                'feeCurrency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'title': 'BTC Wallet',
                'confirmationBlocks': 2,
                'memoSupported': False,
                'decimals': 6,
                'config': {},
                'providerName': 'BTC',
                'restrictedCountries': []
            },
            {
                'id': '3a29a9cb-3f10-46e9-a8af-52c3ca8f3cab',
                'currencyProvider': '9899d208-a3e5-46bc-a594-3048b1a982bc',
                'status': 'CURRENCY_BINDING_STATUS_ACTIVE',
                'type': 'CURRENCY_BINDING_TYPE_INPUT',
                'currency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'minAmount': '0.000500000000000000',
                'fee': '0',
                'percentFee': '0',
                'warning': '',
                'feeCurrency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'title': 'BTC Wallet ',
                'confirmationBlocks': 2,
                'memoSupported': False,
                'decimals': 6,
                'config': {},
                'providerName': 'BTC',
                'restrictedCountries': []
            },
            {
                'id': 'e225e53e-6756-4f2b-bc2c-ebc4dc60b2d9',
                'currencyProvider': 'bf169c61-26cd-49a0-a6e1-a8781d1d4058',
                'status': 'CURRENCY_BINDING_STATUS_DISABLED',
                'type': 'CURRENCY_BINDING_TYPE_INPUT',
                'currency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'minAmount': '0.000300000000000000',
                'fee': '0',
                'percentFee': '0',
                'warning': '',
                'feeCurrency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'title': 'BTCB Wallet BEP-20',
                'confirmationBlocks': 15,
                'memoSupported': False,
                'decimals': 18,
                'config': {
                    'address': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c'
                    },
                'providerName': 'BSC_TOKEN',
                'restrictedCountries': []
            },
            {
                'id': 'c65cd18f-6d9c-40f3-acca-072d4d1977fd',
                'currencyProvider': 'bf169c61-26cd-49a0-a6e1-a8781d1d4058',
                'status': 'CURRENCY_BINDING_STATUS_DISABLED',
                'type': 'CURRENCY_BINDING_TYPE_OUTPUT',
                'currency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'minAmount': '0.000300000000000000',
                'fee': '0.000300000000000000',
                'percentFee': '1.000000000000000000',
                'warning': '',
                'feeCurrency': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'title': 'BTCB Wallet BEP-20',
                'confirmationBlocks': 15,
                'memoSupported': False,
                'decimals': 18,
                'config': {
                    'address': '0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c'
                    },
                'providerName': 'BSC_TOKEN',
                'restrictedCountries': []
            }
            ]

        """

        pathParams = self._inputController(currency = currency)
        return self._APIsigned(endpoint = self.bindings_currency_call.format(**pathParams))


    def getTransactions(self, transaction_id: Optional[str] = None, page: Optional[int] = 0, size: Optional[int] = 10) -> dict:
        """Returns a history of user transactions

        A request for transaction by id pas a priority over the request for all transactions

        :param transaction_id: required, if request a specific transaction
        :param page: should be >= 0
        :param size: should be 1-1000 (defaults to 10), number of results returned per page

        ..code block:: python

            {
                'hasNext': True,
                'content': [{
                                'id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                                'status': 'TRANSACTION_STATUS_CONFIRMED',
                                'type': 'TRANSACTION_TYPE_WITHDRAWAL',
                                'senderAddress': '',
                                'recipientAddress': 'TTccMcccM8ccMcMMc46KHzv6MeMeeeeeee',
                                'amount': '20.000000000000000000',
                                'transactionFee': '3.000000000000000000',
                                'timestamp': 1629561656406,
                                'transactionHash': '900a0000000a0cc647a2aa10555a555555233aaa065a5a6369600000000000',
                                'blockHeight': 0,
                                'currency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                                'memo': None,
                                'paymentProvider': '4732c7cc-5f53-4f12-a757-96c7c6ba2e8e',
                                'requiresCode': False
                            },
                            {
                                ...
                            }],
                'first': True,
                'pageSize': 1,
                'hasContent': True
            }

        """

        if transaction_id:
            pathParams = {'id': str(transaction_id)}
            return self._APIsigned(endpoint = self.transaction_by_id_call.format(**pathParams))

        else:
            queryParams = {
                'page': str(page),
                'size': str(size)
                }
            return self._APIsigned(endpoint = self.transaction_all_call, params = queryParams)


    def getCurrencies(self, currency: Optional[str] = None, get_all: bool = True):
        """Returns currency data

        :param currency: can be either currency tag or currency id

        :returns: dict - dict with currency information (if requesting one currency), list with currencies otherwise

        .. code block:: python

            [{
                'id': '92151d82-df98-4d88-9a4d-284fa9eca49f',
                'status': 'CURRENCY_STATUS_ACTIVE',
                'type': 'CURRENCY_TYPE_CRYPTO',
                'name': 'Bitcoin',
                'tag': 'BTC',
                'description': '',
                'logo': '',
                'decimals': 8,
                'created': 1572912000000,
                'tier': 1,
                'assetClass': 'ASSET_CLASS_UNKNOWN',
                'minTransferAmount': 0
            },
            ...
            ]

        """

        if currency:
            pathParams = self._inputController(currency = currency)
            return requests.get(self.baseAPI + self.currency_call.format(**pathParams)).json()

        elif get_all:
            return requests.get(self.baseAPI + self.active_currency_call).json()


    def getQuoteCurrencies(self) -> list:
        """Returns quote currencies

        :returns: list - list of currencies used as quote on LATOKEN

        .. code block:: python

            [
                '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                '92151d82-df98-4d88-9a4d-284fa9eca49f',
                '620f2019-33c0-423b-8a9d-cde4d7f8ef7f',
                '34629b4b-753c-4537-865f-4b62ff1a31d6',
                '707ccdf1-af98-4e09-95fc-e685ed0ae4c6',
                'd286007b-03eb-454e-936f-296c4c6e3be9'
            ]

        """

        return requests.get(self.baseAPI + self.quote_currency_call).json()


    def getActivePairs(self) -> list:
        """Returns active pairs

        :returns: list - list of active pairs information

        .. code block:: python

            [...,
                {
                    'id': '752896cd-b656-4d9a-814d-b97686246350',
                    'status': 'PAIR_STATUS_ACTIVE',
                    'baseCurrency': 'c9f5bf11-92ec-461b-877c-49e32f133e13',
                    'quoteCurrency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                    'priceTick': '0.000000000010000000',
                    'priceDecimals': 11,
                    'quantityTick': '0.010000000',
                    'quantityDecimals': 2,
                    'costDisplayDecimals': 9,
                    'created': 1625153024491,
                    'minOrderQuantity': '0',
                    'maxOrderCostUsd': '999999999999999999',
                    'minOrderCostUsd': '0',
                    'externalSymbol': ''
                },
            ...]

        """

        return requests.get(self.baseAPI + self.active_pairs_call).json()


    def getOrderbook(self, pair: str, limit: Optional[int] = 1000) -> dict:
        """Returns orderbook for a specific pair

        :param pair: can be either currency tag or currency id (should of format ***/***)
        :param limit: number or price levels returned in bids and asks, defaults to 1000

        :returns: dict - dict with asks and bids that contain information for each price level

        ..code block:: python

            {
                'ask':
                    [{
                        'price': '46566.69',
                        'quantity': '0.0081',
                        'cost': '377.190189',
                        'accumulated': '377.190189'
                    }],
                'bid':
                    [{
                        'price': '46561.91',
                        'quantity': '0.0061',
                        'cost': '284.027651',
                        'accumulated': '284.027651
                    }],
                'totalAsk': '3.4354',                 # In base currency
                'totalBid': '204967.154792'           # In quote currency
            }

        """

        pathParams = self._inputController(pair = pair)
        queryParams = f'limit={limit}'
        return requests.get(self.baseAPI + self.orderbook_call.format(**pathParams) + '?' + queryParams).json()


    def getTickers(self, pair: Optional[str] = None, get_all: bool = True):
        """Returns tickers

        :param pair: can be either currency tag or currency id (should of format ***/***)
        :param get_all: defaults to True (returns tickers for all pairs)

        :returns: list - list of dicts with pairs' tickers (by default), dict with one pair ticker otherwise

        .. code block:: python

            [...,
                {
                    'symbol': 'SNX/USDT',
                    'baseCurrency': 'c4624bdb-1148-440d-803d-7b55031d481d',
                    'quoteCurrency': '0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                    'volume24h': '1177568.232859658500000000',
                    'volume7d': '1177568.232859658500000000',
                    'change24h': '0',
                    'change7d': '0',
                    'lastPrice': '12.02347082'
                },
            ...
            ]

        """

        if pair:
            pathParams = self._inputController(pair = pair)
            return requests.get(self.baseAPI + self.tickers_per_pair_call.format(**pathParams)).json()

        elif get_all:
            return requests.get(self.baseAPI + self.tickers_call).json()


    def getFeeLevels(self) -> list:
        """Returns fee levels

        :returns: list - list of dicts with maker and taker fee per each volume level (30d accumulated volume)

        .. code block:: python

            [
                {'makerFee': '0.0049', 'takerFee': '0.0049', 'volume': '0'},
                {'makerFee': '0.0039', 'takerFee': '0.0039', 'volume': '10000'},
                {'makerFee': '0.0029', 'takerFee': '0.0029', 'volume': '50000'},
                {'makerFee': '0.0012', 'takerFee': '0.0019', 'volume': '100000'},
                {'makerFee': '0.0007', 'takerFee': '0.0011', 'volume': '250000'},
                {'makerFee': '0.0006', 'takerFee': '0.0009', 'volume': '1000000'},
                {'makerFee': '0.0004', 'takerFee': '0.0007', 'volume': '2500000'},
                {'makerFee': '0.0002', 'takerFee': '0.0005', 'volume': '10000000'},
                {'makerFee': '0', 'takerFee': '0.0004', 'volume': '20000000'}
            ]

        """

        return requests.get(self.baseAPI + self.fee_levels_call).json()


    def getFeeScheme(self, pair: str, user: Optional[bool] = False) -> dict:
        """Returns fee scheme for a particular pair

        :param user: defaults to False (returns fee scheme per pair for all users, for particular user otherwise)

        .. code block:: python

            {
                'makerFee': '0.004900000000000000',       # Proportion (not %)
                'takerFee': '0.004900000000000000',       # Proportion (not %)
                'type': 'FEE_SCHEME_TYPE_PERCENT_QUOTE',
                'take': 'FEE_SCHEME_TAKE_PROPORTION'
            }

        """

        pathParams = self._inputController(pair = pair)

        if pair and user:
            return self._APIsigned(endpoint = self.fee_scheme_par_pair_and_user_call.format(**pathParams))

        elif pair:
            return requests.get(self.baseAPI + self.fee_scheme_per_pair_call.format(**pathParams)).json()


    def getChart(self, pair: Optional[str] = None):
        """Returns charts

        :param pair: can be either currency tag or currency id (should of format ***/***)

        :returns: if no arguments specified, the dict is returned with currency ids as keys
        and list of 169 weekly prices as values, otherwise a single list is retured

        ..code block:: python

            {
                '30a1032d-1e3e-4c28-8ca7-b60f3406fc3e': [..., 1.375e-05, 1.382e-05, 1.358e-05, ...],
                'd8958071-c13f-40fb-bd54-d2f64c36e15b': [..., 0.0001049, 0.000104, 0.0001045, ...],
                ...
            }

        """

        if pair:
            pathParams = self._inputController(pair = pair)
            return requests.get(self.baseAPI + self.weekly_chart_by_pair_call.format(**pathParams)).json()

        else:
            return requests.get(self.baseAPI + self.weekly_chart_call).json()


    def getCandles(self, start: str, end: str, pair: str = None, resolution: str = '1h') -> dict:
        """Returns charts

        :param pair: can be either currency tag or currency id (should of format ***/***)
        :param resolution: can be 1m, 1h (default), 4h, 6h, 12h, 1d, 7d or 1w, 30d or 1M
        :param start: timestamp in seconds (included in responce)
        :param end: timestamp in seconds (not included in responce)

        :returns: dict - the dict with open, close, low, high, time, volume as keys and list of values

        ..code block:: python

            {
                "o":["49926.320000000000000000", ..., "49853.580000000000000000"],
                "c":["50193.230000000000000000", ..., "49948.57"],
                "l":["49777.000000000000000000", ...,"49810.200000000000000000"],
                "h":["50555.000000000000000000", ...,"49997.350000000000000000"],
                "t":[1630800000, ..., 1630828800],
                "v":["2257782.696156400000000000", ..., "811505.269468400000000000"],
                "s":"ok"
            }

        """

        pathParams = self._inputController(pair = pair)
        pathParams.update({
            'resolution': str(resolution),
            'from': str(start),
            'to': str(end)
            })
        return requests.get(self.baseAPI + self.candles_call.format(**pathParams)).json()


    # WEBSOCKETS

    def _WSsigned(self) -> dict:
        timestamp = str(int(float(time()) * 1000))

        # We should sign a timestamp in milliseconds by the api secret
        signature = hmac.new(
            self.apiSecret,
            timestamp.encode('ascii'),
            hashlib.sha512
        )
        return {
                'X-LA-APIKEY': self.apiKey,
                'X-LA-SIGNATURE': signature.hexdigest(),
                'X-LA-DIGEST': 'HMAC-SHA512',
                'X-LA-SIGDATA': timestamp
                }


    async def connect(self, streams: list = topics, signed: bool = False, on_message = None):

            ws=websocket.create_connection(self.baseWS)
            msg = stomper.Frame()
            msg.cmd = "CONNECT"
            msg.headers = {
                            "accept-version": "1.1", 
                            "heart-beat": "0,0"
                            }
            
            # If the request is for a private stream, then add signature headers to headers
            if signed:
                msg.headers.update(self._WSsigned())

            ws.send(msg.pack())
            ws.recv()

            # Subscribing to streams, subscription id is assigned as an index in topics list
            for stream in streams:
                msg = stomper.subscribe(stream, streams.index(stream), ack="auto")
                ws.send(msg)

            # Telling the application to execute a business logic on each message from the server
            while True:
                message = ws.recv()
                message = stomper.unpack_frame(message.decode())
                await on_message(message)


    def run(self, connect):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(connect)


    # Websocket streams
    def streamAccounts(self) -> dict:
        """Returns all user currency balances

        :returns: dict - dict with all user balances by wallet type

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/user/a44444aa-4444-44a4-444a-44444a444aaa/v1/account',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '22090',
                        'subscription': '0'
                        },
            'body': '{
                    "payload":[
                                {
                                    "id":"a44444aa-4444-44a4-444a-44444a444aaa",
                                    "status":"ACCOUNT_STATUS_ACTIVE",
                                    "type":"ACCOUNT_TYPE_FUTURES",
                                    "timestamp":1594198124804,
                                    "currency":"ebf4eb8a-06ec-4955-bd81-85a7860764b9",
                                    "available":"31.265578482497400000",
                                    "blocked":"0",
                                    "user":"a44444aa-4444-44a4-444a-44444a444aaa"
                                },
                                ...
                               ],
                    "nonce":0,
                    "timestamp":1630172200117
                    }'
        }

        """

        user_id = self.getUserInfo()['id']
        pathParams = {'user': str(user_id)}
        accounts_topics = self.account_stream.format(**pathParams)
        return self.topics.append(accounts_topics)


    def streamTransactions(self):
        """Stream returns user transactions (to/from outside LATOKEN) history, function only returns a subscription endpoint

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/user/a44444aa-4444-44a4-444a-44444a444aaa/v1/transaction',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '13608',
                        'subscription': '0'
                        },
            'body': '{
                        "payload":[
                                    {
                                        "id":"a44444aa-4444-44a4-444a-44444a444aaa",
                                        "status":"TRANSACTION_STATUS_CONFIRMED",
                                        "type":"TRANSACTION_TYPE_WITHDRAWAL",
                                        "senderAddress":"",
                                        "recipientAddress":"TTccMcccM8ccMcMMc46KHzv6MeMeeeeeee",
                                        "transferredAmount":"20.000000000000000000",
                                        "timestamp":1629561656404,
                                        "transactionHash":"000000rrrrr000c647a27f7f7f7777ff9052338bf065000000fffffff7iiii88",
                                        "blockHeight":0,
                                        "transactionFee":"3.000000000000000000",
                                        "currency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5",
                                        "user":"a44444aa-4444-44a4-444a-44444a444aaa",
                                        "paymentProvider":"4732c7cc-5f53-4f12-a757-96c7c6ba2e8e",
                                        "requiresCode":false
                                    },
                                    ...
                                   ],
                        "nonce":0,
                        "timestamp":1630182304943
                    }'
        }

        """

        user_id = self.getUserInfo()['id']
        pathParams = {'user': str(user_id)}
        transactions_topics = self.transactions_stream.format(**pathParams)
        return self.topics.append(transactions_topics)


    def streamTransfers(self):
        """Stream returns user transfers (within LATOKEN) history, function only returns a subscription endpoint

        .. code block:: python


        """

        user_id = self.getUserInfo()['id']
        pathParams = {'user': str(user_id)}
        transfers_topics = self.transfers_stream.format(**pathParams)
        return self.topics.append(transfers_topics)


    def streamOrders(self):
        """Stream returns user orders history, function only returns a subscription endpoint

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/user/a44444aa-4444-44a4-444a-44444a444aaa/v1/order',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '27246',
                        'subscription': '0'
                        },
            'body': '{
                        "payload":[
                                    {
                                        "id":"a44444aa-4444-44a4-444a-44444a444aaa",
                                        "user":"a44444aa-4444-44a4-444a-44444a444aaa",
                                        "changeType":"ORDER_CHANGE_TYPE_UNCHANGED",
                                        "status":"ORDER_STATUS_CANCELLED",
                                        "side":"ORDER_SIDE_BUY",
                                        "condition":"ORDER_CONDITION_GOOD_TILL_CANCELLED",
                                        "type":"ORDER_TYPE_LIMIT",
                                        "baseCurrency":"92151d82-df98-4d88-9a4d-284fa9eca49f",
                                        "quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5",
                                        "clientOrderId":"test1",
                                        "price":"39000",
                                        "quantity":"0.001",
                                        "cost":"39.000000000000000000",
                                        "filled":"0.000000000000000000",
                                        "deltaFilled":"0",
                                        "timestamp":1629039302489,
                                        "rejectError":null,
                                        "rejectComment":null
                                    },
                                    ...
                                   ],
                        "nonce":0,
                        "timestamp":1630180898279
                    }'
        }

        """

        user_id = self.getUserInfo()['id']
        pathParams = {'user': str(user_id)}
        orders_topics = self.orders_stream.format(**pathParams)
        return self.topics.append(orders_topics)


    def streamCurrencies(self):
        """Stream returns currencies information, function only returns a subscription endpoint

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/v1/currency',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '265186',
                        'subscription': '0'
                        },
            'body': '{
                        "payload":[
                                    {
                                        "id":"af544ebf-630b-4bac-89c1-35ee5caca50b",
                                        "status":"CURRENCY_STATUS_ACTIVE",
                                        "type":"CURRENCY_TYPE_CRYPTO",
                                        "name":"Javvy Crypto Solution",
                                        "description":"",
                                        "decimals":18,
                                        "tag":"JVY",
                                        "logo":"",
                                        "minTransferAmount":"",
                                        "assetClass":"ASSET_CLASS_UNKNOWN"
                                    },
                                    ...
                                   ],
                        "nonce":0,
                        "timestamp":1630180614787
                    }'
        }

        """

        return self.topics.append(self.currencies_stream)


    def streamPairs(self):
        """Stream returns pairs information, function only returns a subscription endpoint

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/v1/pair',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '293954',
                        'subscription': '0'
                        },
            'body': '{
                        "payload":[
                                    {
                                        "id":"c49baa32-88f0-4f7b-adca-ab66afadc75e",
                                        "status":"PAIR_STATUS_ACTIVE",
                                        "baseCurrency":"59c87258-af77-4c15-ae12-12da8cadc545",
                                        "quoteCurrency":"620f2019-33c0-423b-8a9d-cde4d7f8ef7f",
                                        "priceTick":"0.000000010000000000",
                                        "quantityTick":"1.000000000",
                                        "costDisplayDecimals":8,
                                        "quantityDecimals":0,
                                        "priceDecimals":8,
                                        "externalSymbol":"",
                                        "minOrderQuantity":"0.000000000000000000",
                                        "maxOrderCostUsd":"999999999999999999.000000000000000000",
                                        "minOrderCostUsd":"0.000000000000000000"
                                    },
                                    ...
                                   ],
                        "nonce":0,
                        "timestamp":1630180179490
                    }'
        }

        """

        return self.topics.append(self.pairs_stream)


    def streamTickers(self):
        """Stream returns tickers for all pairs, function only returns a subscription endpoint

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/v1/ticker',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '260547',
                        'subscription': '0'
                        },
            'body': '{
                        "payload":[
                                    {
                                        "baseCurrency":"1cbcbd8f-74e6-4476-aaa1-e883a467ee3f",
                                        "quoteCurrency":"92151d82-df98-4d88-9a4d-284fa9eca49f",
                                        "volume24h":"0",
                                        "volume7d":"0",
                                        "change24h":"0",
                                        "change7d":"0",
                                        "lastPrice":"0.0000012"
                                    },
                                    ...
                                   ],
                        "nonce":1,
                        "timestamp":1630179152495
                    }'
        }

        """

        return self.topics.append(self.ticker_all_stream)


    def streamBook(self, pairs: list):
        """Stream returns orderbook of a specific pair, function only returns a subscription endpoint

        :param pairs: should consist of currency_ids only, otherwise will return nothing, pair should be of format ***/***

        :returns: dict - dict for each requested pair as a separate message

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/v1/book/620f2019-33c0-423b-8a9d-cde4d7f8ef7f/0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '184',
                        'subscription': '1'
                        },
            'body': '{
                        "payload":{
                                    "ask":[],
                                    "bid":[
                                            {
                                                "price":"3218.07",
                                                "quantityChange":"1.63351",
                                                "costChange":"5256.7495257",
                                                "quantity":"1.63351",
                                                "cost":"5256.7495257"
                                            },
                                            ...
                                           ]
                                   },
                        "nonce":1,
                        "timestamp":1630178170860
                    }'
        }

        """

        pathParams = [self._inputController(pair = pair) for pair in pairs]
        book_topics = [self.book_stream.format(**pathParam) for pathParam in pathParams]
        return [self.topics.append(book_topic) for book_topic in book_topics]


    def streamPairTickers(self, pairs: list):
        """Stream returns pairs' volume and price changes, function only returns a subscription endpoint

        :param pairs: should consist of currency_ids only, otherwise will return nothing, pair should be of format ***/***

        :returns: dict - dict for each requested pair as a separate message

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/v1/ticker/620f2019-33c0-423b-8a9d-cde4d7f8ef7f/0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                        'message-id': '0a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '277',
                        'subscription': '1'
                        },
            'body': '{
                        "payload":{
                                    "baseCurrency":"620f2019-33c0-423b-8a9d-cde4d7f8ef7f",
                                    "quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5",
                                    "volume24h":"37874830.2350945",
                                    "volume7d":"183513541.8285953",
                                    "change24h":"0.28",
                                    "change7d":"-0.71",
                                    "lastPrice":"3239"
                                   },
                        "nonce":0,
                        "timestamp":1630177120904
                    }'
        }

        """

        pathParams = [self._inputController(pair = pair) for pair in pairs]
        pair_tickers_topics = [self.tickers_pair_stream.format(**pathParam) for pathParam in pathParams]
        return [self.topics.append(pair_tickers_topic) for pair_tickers_topic in pair_tickers_topics]


    def streamTrades(self, pairs: list):
        """Stream returns market trades, function only returns a subscription endpoint

        :param pairs: should consist of currency_ids only, otherwise will return an empty message, pair should be of format ***/***

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/v1/trade/620f2019-33c0-423b-8a9d-cde4d7f8ef7f/0c3a106d-bde3-4c13-a26e-3fd2394529e5',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '30105',
                        'subscription': '1'
                        },
            'body': '{
                      "payload":[
                                {
                                "id":"a44444aa-4444-44a4-444a-44444a444aaa",
                                "timestamp":1630175902267,
                                "baseCurrency":"620f2019-33c0-423b-8a9d-cde4d7f8ef7f",
                                "quoteCurrency":"0c3a106d-bde3-4c13-a26e-3fd2394529e5",
                                "direction":null,
                                "price":"3243.14",
                                "quantity":"0.44887",
                                "cost":"1455.748251800000000000",
                                "order":null,
                                "makerBuyer":false
                                },
                                ...
                                ],
                      "nonce":0,
                      "timestamp":1630175907898
                      }'
        }

        """

        pathParams = [self._inputController(pair = pair) for pair in pairs]
        trades_topics = [self.trades_stream.format(**pathParam) for pathParam in pathParams]
        return [self.topics.append(trades_topic) for trades_topic in trades_topics]


    def streamRates(self, pairs: list):
        """Stream returns rate for specified pairs, function only returns a subscription endpoint

        :param pairs: can consist of currency_ids or currency tag, pair should be of format ***/***

        :returns: dict - dict for each requested pair as a separate message

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/v1/rate/BTC/USDT',                     # Returns the format you requested the pair in (can be mixute of currency id and quote)
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '87',
                        'subscription': '0'
                        },
            'body': '{
                        "payload":[
                                    {
                                        "symbol":"BTC/USDT",
                                        "rate":48984.99
                                    }
                                  ],
                        "nonce":0,
                        "timestamp":1630173083252
                    }'
        }

        """

        pathParams = [self._inputController(pair = pair) for pair in pairs]
        rates_topics = [self.rates_stream.format(**pathParam) for pathParam in pathParams]
        return [self.topics.append(rates_topic) for rates_topic in rates_topics]


    def streamQuoteRates(self, quotes: list):
        """Stream returns rates for all currencies quoted to specified quotes, function only returns a subscription endpoint

        :param quotes: is a list of quote currencies that can be either currency tag or currency id (should of format ***/***)

        .. code block:: python

        {
            'cmd': 'MESSAGE',
            'headers': {
                        'destination': '/v1/rate/USDT',
                        'message-id': 'a44444aa-4444-44a4-444a-44444a444aaa',
                        'content-length': '49986',
                        'subscription': '0'
                        },
            'body': '{
                    "payload":[
                              {"symbol":"USDN/USDT","rate":0.9988},
                              {"symbol":"USDJ/USDT","rate":0.98020001},
                              ...,
                              {"symbol":"VTHO/USDT","rate":0.011324}
                              ],
                    "nonce":0,
                    "timestamp":1630171197332
                    }'
        }

        """

        pathParams = [self._inputController(currency = quote, currency_name = 'quote') for quote in quotes]
        quote_rates_topics = [self.rates_quote_stream.format(**pathParam) for pathParam in pathParams]
        return [self.topics.append(quote_rates_topic) for quote_rates_topic in quote_rates_topics]



