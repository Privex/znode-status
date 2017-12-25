"""
Interactions with ZCoin RPC

Crafts JSON-RPC requests using the Requests library
"""
import requests
import json


class ZCoinAdapter():
    """
    Example usage:
    >>> z = ZCoinAdapter('127.0.0.1', 8888, 'john', 'password123')
    >>> print(z.getinfo())

    """
    hostname = None
    port = None
    username = None
    password = None

    def __init__(self, hostname, port=8888, username=None, password=None):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port

    @property
    def url(self):
        if self.username is None:
            return "http://{}:{}".format(self.hostname, self.port)
        return "http://{}:{}@{}:{}".format(self.username, self.password,
                                           self.hostname, self.port)

    def call(self, method, *params):
        headers = {'content-type': 'application/json'}

        # Example echo method
        payload = {
            "method": method,
            "params": list(params),
            "jsonrpc": "2.0",
            "id": 0,
        }
        response = requests.post(
            self.url, data=json.dumps(payload), headers=headers).json()
        if response['error'] is not None:
            raise Exception(response['error'])
        return response['result']

    def getinfo(self):
        return self.call('getinfo')

    def get_block_count(self):
        info = self.getinfo()
        return info['blocks']

    def getnewaddress(self):
        return self.call('getnewaddress')

    def getreceivedbyaddress(self, address, confirmations=1):
        return self.call('getreceivedbyaddress', address, confirmations)
