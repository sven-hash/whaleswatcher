import json
import logging
import os

import backoff
import requests
from utils import Utils

GENESIS_TS = 1231006504
FIRST_BLOCK_TS = 1636383298
ALPH_BASE = 10 ** 18

MINERS_ADDRESSES_FILE = 'address2name/miners.txt'
GENESIS_ADDRESSES_FILE = 'address2name/genesis.txt'
CLAIMED_ADDRESSES_FILE = 'address2name/known-wallets.txt'

API_BASE = Utils.apiBase
API_EXPLORER_BASE = Utils.apiExplorerBase

TIMEOUT_REQ = 120


class WhalesWatcher:

    def __init__(self, session, telegramBot, twitterBot, minAmountAlert, minAmountAlertTweet, tickerHandler,
                 debug=False, fullnode_api_key=""):
        self.session = session
        self.minAmountAlert = minAmountAlert
        self.minAmountAlertTweet = minAmountAlertTweet
        self.telegramBot = telegramBot
        self.twitterBot = twitterBot
        self.debug = debug
        self.headers = {}

        if fullnode_api_key != "":
            self.headers = {'X-API-KEY': fullnode_api_key}

        self.ticker = tickerHandler

        logging.getLogger('backoff').addHandler(logging.StreamHandler())
        logging.getLogger('backoff').setLevel(logging.INFO)

    def isGenesisAddress(self, addr):
        # GENESIS_URL "https://raw.githubusercontent.com/alephium/alephium/master/flow/src/main/resources
        # /mainnet_genesis.conf"

        exist, name, exchange = WhalesWatcher.isIn(addr, GENESIS_ADDRESSES_FILE)

        return exist

    def isMinerAddress(self, addr):

        exist, name, exchange = WhalesWatcher.isIn(addr, MINERS_ADDRESSES_FILE)

        if exist:  # schedule.every().second.do(stats, twitterBot, telegramBot, logPooler)
            return True

        try:
            response = self.session.get(f"{API_EXPLORER_BASE}/addresses/{addr}/transactions", timeout=Utils.TIMEOUT_REQ)
            try:
                tx = json.loads(response.text)
            except Exception as e:
                print(response.content)
                print(e)

            for transaction in tx:
                if transaction.get('type') == 'confirmed' and len(transaction.get('inputs')) <= 0:
                    # add miner address in file with timestamp
                    with open(f"{MINERS_ADDRESSES_FILE}", "a") as f:
                        f.write(f'{addr}\n')
                    return True

            return False

        except requests.exceptions.ConnectionError as e:
            print(e)
            return False

    def isClaimed(self, addr):
        return WhalesWatcher.isIn(addr, CLAIMED_ADDRESSES_FILE)

    def formatAddress(self, addr):
        exist, name, exchange = self.isClaimed(addr)
        maxChar = 72

        formattedAddr = ""
        if exist and name != "":
            if len(name) >= maxChar:
                name = f"{(name[:maxChar]).strip()}..."
            formattedAddr += name
        else:
            formattedAddr += f"{addr[:5]}...{addr[-5:]}"

        return formattedAddr, exchange

    @backoff.on_exception(Utils.BACKOFF_ALGO, (requests.exceptions.ConnectionError, requests.exceptions.Timeout), max_tries=Utils.BACKOFF_MAX_TRIES)
    def getGenesisAddresses(self):
        # GENESIS_URL = "https://raw.githubusercontent.com/alephium/alephium/master/flow/src/main/resources/mainnet_genesis.conf"
        addresses = set()

        try:
            response = self.session.get(
                f"{API_BASE}/blockflow/blocks?fromTs={GENESIS_TS * 1000}&toTs={(GENESIS_TS + 5) * 1000}", headers=self.headers,
                timeout=Utils.TIMEOUT_REQ)

            for inner_blocks in response.json()['blocks']:
                for block in inner_blocks:
                    for tx in block['transactions']:
                        for txUnsigned in tx['unsigned']['fixedOutputs']:
                            addresses.add(txUnsigned['address'])

        except Exception as e:
            print(e)
            return False

        sourceFile = open(f'{GENESIS_ADDRESSES_FILE}', 'w')
        print(*addresses, sep="", file=sourceFile)

        return True

    @backoff.on_exception(Utils.BACKOFF_ALGO, (requests.exceptions.ConnectionError, requests.exceptions.Timeout),max_tries=Utils.BACKOFF_MAX_TRIES)
    def getBlockTsTransactions(self, start, end):
        txs = []
        try:
            response = self.session.get(f"{API_BASE}/blockflow/blocks?fromTs={start * 1000}&toTs={end * 1000}",
                                    headers=self.headers, timeout=Utils.TIMEOUT_REQ)
            allBlocks = response.json()
        except Exception as e:
            print(e)
            return txs


        try:
            for inBlock in allBlocks['blocks']:
                for block in inBlock:
                    for transaction in block['transactions']:
                        if len(transaction['unsigned']['inputs']) > 0:
                            txs.append(transaction['unsigned']['txId'])

            return txs
        except KeyError as e:
            print(e)
            return txs

    @backoff.on_exception(Utils.BACKOFF_ALGO, (requests.exceptions.ConnectionError, requests.exceptions.Timeout),max_tries=Utils.BACKOFF_MAX_TRIES)
    def getUnconfirmedTransactions(self):
        unconfirmedTxsId = set()
        try:
            response = self.session.get(f"{API_BASE}/transactions/unconfirmed", headers=self.headers,
                                       timeout=Utils.TIMEOUT_REQ)
            unconfirmedTxs = response.json()
        except Exception as e:
            print(e)
            return unconfirmedTxsId

        for unconfirmed in unconfirmedTxs:
            for tx in unconfirmed['unconfirmedTransactions']:
                unconfirmedTxsId.add(tx['unsigned']['txId'])

        return unconfirmedTxsId

    @backoff.on_exception(Utils.BACKOFF_ALGO, (requests.exceptions.ConnectionError, requests.exceptions.Timeout),max_tries=Utils.BACKOFF_MAX_TRIES)
    def getBlockTransaction(self, transaction):
        try:
            response = self.session.get(f"{API_EXPLORER_BASE}/transactions/{transaction}", timeout=Utils.TIMEOUT_REQ)
            respTxStatus = self.session.get(f"{API_BASE}/transactions/status?txId={transaction}", headers=self.headers,
                                            timeout=Utils.TIMEOUT_REQ)

            if not response.ok or not respTxStatus.ok:
                return False

        except Exception as e:
            print(e)
            return False

        respTxStatus = respTxStatus.json()
        try:
            tx = json.loads(response.text)
        except Exception as e:
            print(response.content)
            print(e)
            return False

        if respTxStatus.get('type') is not None:
            txStatus = str.lower(respTxStatus.get('type'))
        else:
            txStatus = None

        if tx.get('type') is not None:
            txExplorerStatus = str.lower(tx.get('type'))
        else:
            txExplorerStatus = None

        if self.debug:
            print(
                f"\nTransaction id: https://explorer.alephium.org/#/transactions/{transaction}, Tx status: {txStatus}")

        try:
            alphPrice = self.ticker.gatePrice()['ALPH_USDT']
        except Exception as e:
            print(e)
            alphPrice = 0


        addressIn = None
        if txStatus == 'confirmed' and txExplorerStatus == 'confirmed':
            for inputTx in tx['inputs']:
                try:
                    addressIn = inputTx['address']
                except KeyError as e:
                    print(e)
                    return False
            try:
                if addressIn is not None:
                    for output in tx['outputs']:
                        amount = float(output['attoAlphAmount']) / ALPH_BASE
                        addressOut = output['address']
                        if addressIn != addressOut and amount >= self.minAmountAlert:

                            addressInTxt, exchangeIn = self.formatAddress(addressIn)
                            addressOutTxt, exchangeOut = self.formatAddress(addressOut)

                            if amount >= self.minAmountAlertTweet:
                                text = WhalesWatcher.formatMessage(amount, addressInTxt, addressOutTxt, transaction,
                                                                   self.isMinerAddress(addressIn),
                                                                   self.isGenesisAddress(addressIn), exchangeIn, exchangeOut,
                                                                   isTwitter=True, alphPrice=alphPrice)
                                self.twitterBot.sendMessage(text)

                            text = WhalesWatcher.formatMessage(amount, addressInTxt, addressOutTxt, transaction,
                                                               self.isMinerAddress(addressIn), self.isGenesisAddress(addressIn),
                                                               exchangeIn, exchangeOut, isTwitter=False, alphPrice=alphPrice)
                            self.telegramBot.sendMessage(text)

                    return True
                else:
                    return False
            except KeyError as e:
                print(f"error key: {e}")
                return False

        elif txStatus == 'unconfirmed' or txStatus is None or txStatus == 'confirmed' or txExplorerStatus == 'confirmed':
            return False

    @staticmethod
    def isIn(addr, file):

        if os.path.isfile(f"{file}"):

            with open(f'{file}', 'r') as f:
                for line in f:
                    if line.split(';')[0].replace('\n', '') == addr:
                        exchange = None
                        if len(line.split(';')) >= 2:
                            name = line.split(';')[1].replace('\n', '')
                            if len(line.split(';')) > 3:
                                exchange = line.split(';')[3].replace('\n', '')

                            return True, name, exchange
                        else:
                            return True, None, None

        return False, None, None

    @staticmethod
    def humanFormat(num, round_to=2):
        # From https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python
        magnitude = 0
        while abs(num) >= 1000:
            magnitude += 1
            num = round(num / 1000.0, round_to)
        return '{:.{}f} {}'.format(num, round_to, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])

    @staticmethod
    def formatMessage(amount, addressIn, addressOut, transactionId, isMiner=False, isGenesis=False,
                      exchangeIn=None, exchangeOut=None, isTwitter=False, alphPrice=0):
        # add exclaim proportionally of number of digit
        numExclaim = '❗' * (len(str(abs(int(amount)))) - 1)

        text = f"{numExclaim} {WhalesWatcher.humanFormat(amount)} ALPH transferred"

        if alphPrice > 0:
            text += f" ({WhalesWatcher.humanFormat(amount * alphPrice)} USDT)"

        text += f"\n{addressIn} to {addressOut}"

        if exchangeIn is None and exchangeOut is None:
            text += "\n"

        if exchangeIn is not None:
            text += f"\nFrom exchange: {exchangeIn}\n"

        if exchangeOut is not None:
            text += f"\nTo exchange: {exchangeOut}\n"

        if isTwitter:
            text += f"\n\nhttps://explorer.alephium.org/#/transactions/{transactionId}"
            text += "\n\n#alephium #blockchain "

        if isGenesis:
            text += "#genesis "
        elif isMiner:
            text += "#miner "

        if isTwitter:
            text += f"\nhttps://medium.com/@alephium/ttxoo-2-the-road-to-self-custody-cfea4ae89444"
            
        if not isTwitter:
            text += "#blockchain"
            text += f"\n\n[TX link](https://explorer.alephium.org/#/transactions/{transactionId})"
            text += f"\n[Road to self custody](https://medium.com/@alephium/ttxoo-2-the-road-to-self-custody-cfea4ae89444)"
        
        return text
