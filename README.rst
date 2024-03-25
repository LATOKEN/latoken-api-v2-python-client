=======================================
Welcome to latoken-api-v2-python-client
=======================================

If you find any bugs or want to contribute, feel free to submit your improvements.

Source code
  https://github.com/LATOKEN/latoken-api-v2-python-client

REST API Documentation
  https://api.latoken.com/doc/v2/

STOMP Websockets Documentation
  https://api.latoken.com/doc/ws/

PyPI location
  https://pypi.org/project/latoken-api-v2-python-client/

This library covers
-------------------

- Authentication of private requests for both REST API and STOMP Websockets
- Asyncio websockets with the option to subscribe to multiple streams simultaneously
- General market data such as historic and current prices, orderbooks, active currencies and pairs
- User account balances access
- Deposit address generation
- Withdrawals
- Transfers within the account
- Transfers between accounts (to other users)
- Crypto Spot Trading

This library doesn't cover
--------------------------

- Futures Trading
- Stocks Trading
- IEO Purchases
- Responce exceptions are exchange generated and are not handled by the library
- Logging is not implemented

Quick Start
-----------

Register an account on `LATOKEN <https://latoken.com>`_.

Generate an API key `in your account <https://latoken.com/account/apikeys>`_ with relevant permissions.

There are 4 levels of API key permissions at LATOKEN:

- Read only (you can view market and account data)
- Trade on Spot (in addition: place and cancel orders)
- Trade and Transfer (in addition: transfer within your account)
- Full access (in addition: transfer to other users, deposit and withdraw)

Install latoken-api-v2-python-client library:

.. code-block:: bash

  pip install latoken-api-v2-python-client
  

Examples of code usage:
-----------------------

- `REST API <https://github.com/LATOKEN/latoken-api-v2-python-client/blob/main/examples/rest_example.py>`_
- `Websockets <https://github.com/LATOKEN/latoken-api-v2-python-client/blob/main/examples/websocket_example.py>`_
