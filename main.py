import argparse
import os
import random
import time
import timeit
from datetime import datetime

import requests
import schedule
from dotenv import load_dotenv

from alephium import WhalesWatcher
from bots.telegram import TelegramBot
from bots.twitter import TwitterBot
from monitor.mail import Monitor
from stats import Stats
from ticker import Ticker
from utils import Utils
from wss.gateio import GateioWss

try:
    import thread
except ImportError:
    import _thread as thread

# base code from https://github.com/capito27
API_BASE = "http://127.0.0.1:12973"
API_EXPLORER_BASE = "https://mainnet-backend.alephium.org"
API_TICKER = "http://alephium.ono.re"

GENESIS_TS = 1231006504
FIRST_BLOCK_TS = 1636383298
ALPH_BASE = 10 ** 18
MINERS_ADDRESSES_FILE = 'address2name/miners.txt'
GENESIS_ADDRESSES_FILE = 'address2name/genesis.txt'
CLAIMED_ADDRESSES_FILE = 'address2name/known-wallets.txt'
ALPH = '\u2135'

GATEIO_WSS_URL = "wss://ws.gate.io/v3/"


def stats(twitterBot, telegramBot, statHandler,telegramChannelId):
    dayOneRange = Utils.timeRangeDays(1)
    dayThreeRange = Utils.timeRangeDays(3)

    hourHashrate = statHandler.avgHashrateAPI(timeSince=datetime.timestamp(Utils.timeRangeHours(1)))
    initialHashrate = statHandler.avgHashrateAPI(timeSince=datetime.timestamp(Utils.timeRangeHours(2)),
                                                 timeUntil=datetime.timestamp(Utils.timeRangeHours(1)))
    try:
        changeHashrate = (hourHashrate - initialHashrate) / abs(initialHashrate)
    except ZeroDivisionError:
        changeHashrate = 0

    dayHashrate = statHandler.avgHashrateAPI(timeSince=datetime.timestamp(dayOneRange[0]),
                                             timeUntil=datetime.timestamp(dayOneRange[1]))
    threeDayHashrate = statHandler.avgHashrateAPI(timeSince=datetime.timestamp(dayThreeRange[0]),
                                                  timeUntil=datetime.timestamp(dayThreeRange[1]))

    # print(reward.getBlockTsTransactions(int(time.time()), int(time.time()+100), True))
    text = ""
    if hourHashrate > 0 or dayHashrate > 0 or threeDayHashrate > 0:
        text += "Global Target Hashrates (avg)"
    if hourHashrate > 0:
        hourHashrate = WhalesWatcher.humanFormat(int(hourHashrate) * 10 ** 6)
        text += f"\n1 hour: {hourHashrate}H/s ({'+' if changeHashrate > 0 else ''}{round(changeHashrate * 100, 1)}%)"

    if dayHashrate > 0:
        dayHashrate = WhalesWatcher.humanFormat(int(dayHashrate) * 10 ** 6)
        text += f"\n1 day: {dayHashrate}H/s"
    if threeDayHashrate > 0:
        threeDayHashrate = WhalesWatcher.humanFormat(int(threeDayHashrate) * 10 ** 6)
        text += f"\n3 days: {threeDayHashrate}H/s"

    circulating = statHandler.circulatingAlph()
    if circulating is not None:
        text += f"\n\nCirculating tokens: {circulating} {ALPH}"

    reward = statHandler.rewardMining()
    if reward > 0:
        text += f"\nMining rewards: {round(reward, 3)} {ALPH}"

    numTxs = statHandler.getNumberTransactions(int(datetime.timestamp(Utils.timeRangeHours(1))),
                                               int(datetime.timestamp(datetime.now())))
    if numTxs > 0:
        rangeString = "1 hour"
        text += f"\n\nNumber of transactions ({rangeString}): {numTxs}"

    text += f"\n\n#stat"

    tweet = text
    tweet += " #alephium #blockchain"
    tweet += "\n\nhttps://explorer.alephium.org"
    tweet += f"\n{hex(random.randint(1, 100000))}"

    # only for telegram
    #text += f"\nPowered by [metapool.tech](https://www.metapool.tech)"

    twitterBot.sendMessage(tweet[:280])
    telegramBot.sendMessage(text,telegramChannelId)


def statsTicker(twitterBot, telegramBot, tickerHandler, statHandler,telegramChannelId):
    apiPrice = tickerHandler.getStats()

    if apiPrice is not None:
        data = apiPrice.get('ALPH_USDT')
        dataOther = apiPrice.get('coingecko')['alephium']

        high24 = float(data.get('high_24h'))
        low24 = float(data.get('low_24h'))
        actualPrice = float(data.get('last'))
        alphVolume = "{:,.0f}".format(float(data.get('base_volume'))).replace(',', ' ')
        usdtVolume = "{:,.0f}".format(float(data.get('quote_volume'))).replace(',', ' ')
        roundPrice = 4

        ath = dataOther.get('ath')['usd']
        date = dataOther.get('ath_relative_date')
        changePercent = float(data.get('change_percentage'))
        marketCap = dataOther.get('market_cap')
        marketCapChange = dataOther.get('market_cap_change_24')

        circulatingAlph = int(statHandler.circulatingAlph().replace(' ', ''))

        marketCapTxt = ''
        if marketCap > 0:
            marketCapTxt = f"Market cap: {Utils.humanFormat(marketCap)} USD (change 24h {round(marketCapChange, roundPrice)}%)"
        else:
            marketCapTxt = f"Market cap: {Utils.humanFormat(round(circulatingAlph * actualPrice), 2)} USD"

        text = f"""
ALPH/USDT

Last price: {round(actualPrice, roundPrice)} USDT
Price 24h: {'+' if changePercent > 0 else ''}{round(changePercent, 1)}%
{marketCapTxt}

High all: {round(ath, roundPrice)} USDT ({date})
High 24h: {round(high24, roundPrice)} USDT
Low 24h: {round(low24, roundPrice)} USDT

Volume: {alphVolume} {ALPH} / {usdtVolume} USDT

"""
        tweet = text
        tweet += "From #gateio\n#stat #price #alephium #blockchain"
        twitterBot.sendMessage(tweet[:280])
        text += "From https://gate.io/trade/ALPH\\_USDT\n\n#stat #price"
        telegramBot.sendMessage(text,telegramChannelId)


def exchangesWatcher(alertAmount, twitterBot, telegramBot):
    try:
        GateioWss(GATEIO_WSS_URL, alertAmount, twitterBot, telegramBot)
    except Exception as e:
        print(e)


def main(minAmountAlert, botEnabled, intervalReq, statsEnabled, minAmountAlertTweet, debug, minAmountAlertGate):
    load_dotenv()
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
    TELEGRAM_CHAT_ID_INSIGHT_CHANNEL = os.getenv("CHAT_ID_INSIGHT")

    TWITTER_CONSUMER_API_KEY = os.getenv("TWITTER_CONSUMER_API_KEY")
    TWITTER_CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")
    TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
    TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
    TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")

    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_RECEIVER = os.getenv("SMTP_RECEIVER")
    SMTP_FROM = os.getenv("SMTP_FROM")

    print(
        f"Start options:\n\tbot enabled: {botEnabled}\n"
        f"\tinterval request: {intervalReq}\n"
        f"\tthreshold alert: {minAmountAlert}\n"
        f"\ttweet threshold alert: {minAmountAlertTweet}\n"
        f"\tgate threshold alert: {minAmountAlertGate}\n"
        f"\tstats: {statsEnabled}"
    )

    monitor = Monitor(SMTP_SERVER, SMTP_USER, SMTP_PASSWORD, SMTP_RECEIVER, SMTP_FROM)

    telegramBot = TelegramBot(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, botEnabled, monitor)
    twitterBot = TwitterBot(TWITTER_CONSUMER_API_KEY, TWITTER_CONSUMER_SECRET,
                            TWITTER_BEARER_TOKEN, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET, botEnabled, monitor)
    thread.start_new_thread(exchangesWatcher,
                            (minAmountAlertGate, twitterBot, telegramBot))

    s = requests.Session()

    tickerHandler = Ticker(session=s, pairs=['ALPH_USDT'], apiTicker=API_TICKER)

    watcher = WhalesWatcher(s, telegramBot, twitterBot, minAmountAlert, minAmountAlertTweet, tickerHandler)

    if statsEnabled:
        logPooler = Stats('alephium', watcher)
        schedule.every().hour.at(":00").do(stats, twitterBot, telegramBot, logPooler,TELEGRAM_CHAT_ID_INSIGHT_CHANNEL)
        schedule.every().hour.at(":30").do(statsTicker, twitterBot, telegramBot, tickerHandler, logPooler,TELEGRAM_CHAT_ID_INSIGHT_CHANNEL)

        if debug:
            schedule.every().second.do(statsTicker, twitterBot, telegramBot, tickerHandler, logPooler,TELEGRAM_CHAT_ID_INSIGHT_CHANNEL)
            schedule.every().second.do(stats, twitterBot, telegramBot, logPooler,TELEGRAM_CHAT_ID_INSIGHT_CHANNEL)

    print("Retrieve genesis adresses: ")
    print(f"{watcher.getGenesisAddresses()}")

    timestampPast = int(time.time() - intervalReq)

    # store the unconfirmed transactions
    txsUnconfirmed = set()

    try:
        while True:
            timestampNow = int(time.time())
            print(datetime.fromtimestamp(timestampPast), datetime.fromtimestamp(timestampNow))

            txs = watcher.getBlockTsTransactions(timestampPast, timestampNow)
            timestampPast = int(time.time())

            # remove from sleep time the amount time used to compute transaction id
            start = timeit.default_timer()

            for transaction in txs:
                if transaction in txsUnconfirmed:
                    txsUnconfirmed.remove(transaction)
                checked = watcher.getBlockTransaction(transaction)
                if not checked:
                    txsUnconfirmed.add(transaction)

            if len(txsUnconfirmed) > 0:
                print("\nUnconfirmed txs:\n"+'\n'.join(map(str, txsUnconfirmed)))
            for transaction in list(txsUnconfirmed):
                checked = watcher.getBlockTransaction(transaction)
                if checked:
                    txsUnconfirmed.remove(transaction)

            txsUnconfirmed.update(watcher.getUnconfirmedTransactions())

            schedule.run_pending()
            stop = timeit.default_timer()
            timeElapsed = stop - start

            sleepTime = intervalReq - timeElapsed

            if sleepTime > 0:
                time.sleep(sleepTime)
    except Exception as e:
        print(e.with_traceback())
        if not debug:
            monitor.sendMessage('Watcher', 'Stop working', f'Main app had a problem or was shutdown\n{e}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot", help="Enable bot message", action='store_true')
    parser.add_argument("--no-bot", help="Disable bot message", dest="bot", action='store_false')
    parser.set_defaults(bot=True)

    parser.add_argument("--debug", help="Debug message", action='store_true')
    parser.add_argument("--no-debug", help="Disable debug message", dest="debug", action='store_false')
    parser.set_defaults(debug=False)

    parser.add_argument("--stat", help="Enable stats messages", action='store_true')
    parser.add_argument("--no-stat", help="Disable stats messages", dest="stats", action='store_false')
    parser.set_defaults(stats=True)

    parser.add_argument("-t", "--threshold", help="Threshold amount to send message", default=10000, type=float)
    parser.add_argument("-tt", "--tweetthreshold", help="Threshold amount to send message for twitter", default=10000,
                        type=float)
    parser.add_argument("-gt", "--gatethreshold", help="Threshold amount to send message for gateio", default=5000,
                        type=float)

    parser.add_argument("-i", "--interval", help="Interval request in seconds", default=120, type=int)

    args = parser.parse_args()

    main(args.threshold, args.bot, args.interval, args.stats, args.tweetthreshold, args.debug, args.gatethreshold)
