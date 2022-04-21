import backoff
import requests


class Ticker:

    def __init__(self, session, pairs, apiTicker):
        self.session = session
        self.pairs = pairs
        self.apiTicker = apiTicker

    def gatePrice(self):
        res = dict()
        try:
            for pair in self.pairs:
                lastPrice = float(self.session.get(f"{self.apiTicker}/api/ticker").json()[pair]['last'])
                res.update({pair: lastPrice})
        except Exception as e:
            print(e)

            for pair in self.pairs:
                res.update({pair: 0})

        return res

    @backoff.on_exception(backoff.expo, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
    def getStats(self):
        try:
            return self.session.get(f"{self.apiTicker}/api/ticker").json()
        except Exception as e:
            print(e)
            return None

    def getPairs(self):
        return self.pairs
