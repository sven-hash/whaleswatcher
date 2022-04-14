import logging
import os

import backoff
import requests

GENESIS_TS = 1231006504
FIRST_BLOCK_TS = 1636383298
ALPH_BASE = 10 ** 18

MINERS_ADDRESSES_FILE = 'address2name/miners.txt'
GENESIS_ADDRESSES_FILE = 'address2name/genesis.txt'
CLAIMED_ADDRESSES_FILE = 'address2name/known-wallets.txt'

API_BASE = "http://127.0.0.1:12973"
API_EXPLORER_BASE = "https://mainnet-backend.alephium.org"


class WhalesWatcher:

    def __init__(self, session, telegramBot, twitterBot, minAmountAlert, minAmountAlertTweet, tickerHandler):
        self.session = session
        self.minAmountAlert = minAmountAlert
        self.minAmountAlertTweet = minAmountAlertTweet
        self.telegramBot = telegramBot
        self.twitterBot = twitterBot

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
            response = self.session.get(f"{API_EXPLORER_BASE}/addresses/{addr}/transactions")
            tx = response.json()

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

    @backoff.on_exception(backoff.expo, (requests.exceptions.ConnectionError, requests.exceptions.Timeout), max_tries=5)
    def getGenesisAddresses(self):
        # GENESIS_URL = "https://raw.githubusercontent.com/alephium/alephium/master/flow/src/main/resources/mainnet_genesis.conf"
        addresses = set()

        try:
            response = self.session.get(
                f"{API_BASE}/blockflow?fromTs={GENESIS_TS * 1000}&toTs={(GENESIS_TS + 5) * 1000}")

            for inner_blocks in response.json()['blocks']:
                for block in inner_blocks:
                    for tx in block['transactions']:
                        for txUnsigned in tx['unsigned']['fixedOutputs']:
                            addresses.add(txUnsigned['address'])

        except requests.exceptions.ConnectionError as e:
            print(e)
            return False

        sourceFile = open(f'{GENESIS_ADDRESSES_FILE}', 'w')
        print(*addresses, sep="", file=sourceFile)

        return True

    @backoff.on_exception(backoff.expo, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
    def getBlockTsTransactions(self, start, end):
        txs = []
        response = self.session.get(f"{API_BASE}/blockflow?fromTs={start * 1000}&toTs={end * 1000}")

        allBlocks = response.json()
        # pprint(allBlocks)
        for inBlock in allBlocks['blocks']:
            for block in inBlock:
                for transaction in block['transactions']:
                    if len(transaction['unsigned']['inputs']) > 0:
                        txs.append(transaction['unsigned']['txId'])

        return txs

    @backoff.on_exception(backoff.expo, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
    def getUnconfirmedTransactions(self):
        response = self.session.get(f"{API_BASE}/transactions/unconfirmed")
        unconfirmedTxs = response.json()
        unconfirmedTxsId = set()

        for unconfirmed in unconfirmedTxs:
            for tx in unconfirmed['unconfirmedTransactions']:
                unconfirmedTxsId.add(tx['unsigned']['txId'])

        return unconfirmedTxsId

    @backoff.on_exception(backoff.expo, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
    def getBlockTransaction(self, transaction):
        response = self.session.get(f"{API_EXPLORER_BASE}/transactions/{transaction}")
        print(f"\nTransaction id: https://explorer.alephium.org/#/transactions/{transaction}")

        tx = response.json()
        txStatus = tx.get('type')
        print(f"Tx status: {txStatus}")
        try:
            alphPrice = self.ticker.gatePrice()['ALPH_USDT']
        except Exception as e:
            print(e)
            alphPrice = 0

        if txStatus == 'confirmed':

            for input in tx['inputs']:
                addressIn = input['address']

            for output in tx['outputs']:
                amount = float(output['amount']) / ALPH_BASE
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
        elif txStatus == 'unconfirmed' or txStatus is None:
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
            text += "#miner"

        if not isTwitter:
            text += "#blockchain"
            text += f"\n\n[TX link](https://explorer.alephium.org/#/transactions/{transactionId})"

        return text
