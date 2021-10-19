from latoken.client import LatokenClient
from typing import Optional


def currencyConverter(currency_ids: Optional[list] = None, currency_tags: Optional[list] = None) -> list:
    """Converts currency ids into tickers and vice versa
    
	.. code block:: python

    Input: [
        '0c3a106d-bde3-4c13-a26e-3fd2394529e5', 
        '92151d82-df98-4d88-9a4d-284fa9eca49f', 
        '620f2019-33c0-423b-8a9d-cde4d7f8ef7f', 
        '34629b4b-753c-4537-865f-4b62ff1a31d6', 
        '707ccdf1-af98-4e09-95fc-e685ed0ae4c6', 
        'd286007b-03eb-454e-936f-296c4c6e3be9'
        ]

    Output: [
        'USDT', 
        'BTC', 
        'ETH', 
        'TRX', 
        'LA', 
        'EOS'
        ]

    """

    response = LatokenClient().getCurrencies()
    
    if currency_ids:
        mapper = {i['id']: i['tag'] for i in response}
        return [mapper[i] for i in currency_ids]
    elif currency_tags:
        mapper = {i['tag']: i['id'] for i in response}
        return [mapper[i] for i in currency_tags]
    else:
        return print('No list of currency_ids or currency_tags provided')