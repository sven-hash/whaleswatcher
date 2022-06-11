import time
from statistics import mean,StatisticsError

import backoff
import requests

from utils import Utils

API_BASE = Utils.apiBase
API_EXPLORER_BASE = Utils.apiExplorerBase

ALPH_BASE = 10 ** 18


class Stats:
    def __init__(self, unitName, watcherHandler):
        self.unitName = unitName
        self.watcher = watcherHandler

    @staticmethod
    @backoff.on_exception(backoff.expo, (requests.exceptions.ConnectionError, requests.exceptions.Timeout), max_tries=7)
    def avgHashrateAPI(timeSince=None, timeUntil=None):
        if timeUntil is None:
            timeUntil = time.time()

        avgHashrate = list()

        session = requests.Session()
        response = session.get(
            f"{API_BASE}/infos/history-hashrate?fromTs={int(timeSince) * 1000}&toTs={int(timeUntil) * 1000}")
        if response.json().get('hashrate'):
            hashrate = float(response.json().get('hashrate').split(' ')[0].strip())
            if hashrate > 0:
                avgHashrate.append(hashrate)
        else:
            return 0

        try:
            return mean(list(map(int, avgHashrate)))
        except StatisticsError:
            return 0

    @staticmethod
    @backoff.on_exception(backoff.expo, (requests.exceptions.ConnectionError, requests.exceptions.Timeout), max_tries=5)
    def circulatingAlph():
        try:
            s = requests.Session()
            response = s.get(f"{API_EXPLORER_BASE}/infos/supply/circulating-alph")
            return "{:,.0f}".format(float(response.text)).replace(',', ' ')
        except requests.exceptions as e:
            print(e)
            return None

    @staticmethod
    @backoff.on_exception(backoff.expo, (requests.exceptions.ConnectionError, requests.exceptions.Timeout), max_tries=5)
    def rewardMining():
        # from capito27
        s = requests.Session()
        try:
            for block in s.get(f'{API_EXPLORER_BASE}/blocks').json()['blocks']:
                transaction = s.get(f"{API_EXPLORER_BASE}/blocks/{block['hash']}/transactions").json()

                for data in transaction:
                    if len(data['inputs']) <= 0 < len(data.get('outputs')):
                        return float(data['outputs'][0]['amount']) / ALPH_BASE
        except Exception as e:
            print(e)
            return 0

    def getNumberTransactions(self, start, end):
        txs = self.watcher.getBlockTsTransactions(start, end)
        return len(txs)
