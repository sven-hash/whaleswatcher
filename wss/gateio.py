import json
import random
import signal
import time

import websocket
from websocket import WebSocketConnectionClosedException, WebSocketTimeoutException

from utils import Utils

try:
    import thread
except ImportError:
    import _thread as thread

PAIR = "ALPH_USDT"
ALPH = '\u2135'


class GateioWss:

    def __init__(self, wssURL, alertAmount, twitterHandler=None, telegramHandler=None, method=None, pair=PAIR):
        self.alertAmount = alertAmount
        self.twitter = twitterHandler
        self.telegram = telegramHandler
        self.wssURL = wssURL
        self.pair = pair

        if method is None:
            self.method = "trades.subscribe"
        else:
            self.method = method

        websocket.enableTrace(False)
        self.ws = websocket.WebSocketApp(wssURL,
                                         on_message=self.on_message,
                                         on_close=self.on_close,
                                         on_ping=self.on_ping,
                                         on_pong=self.on_pong)
        self.ws.on_open = self.on_open
        while True:
            try:

                self.ws.run_forever(ping_interval=35, ping_timeout=30,
                                    ping_payload='{"id": 12994,"method":"server.ping",'
                                                 '"params": []}',
                                    skip_utf8_validation=True)
            except WebSocketConnectionClosedException as e:
                print(e)
            except WebSocketTimeoutException as e:
                print(e)

    def trades(self, data):
        timeNow = time.time()

        for trade in data['params'][1]:

            if trade['time'] >= timeNow - 10:
                if float(trade['amount']) >= self.alertAmount:

                    amount = float(trade['amount'])
                    price = float(trade['price'])

                    text = ""
                    if trade['type'] == 'buy':
                        text += "🟢 "
                    elif trade['type'] == 'sell':
                        text += "🔴 "

                    text += "Exchange: #Gateio\n\n"
                    text += f"{trade['type'].capitalize()} Volume: {Utils.humanFormat(amount)}{ALPH}" \
                            f"\nTotal: {round(amount * price, 2)} USDT (at {round(price, 4)} USDT)"

                    if self.telegram is not None:
                        telegramText = text
                        telegramText += "\n\n#exchange"
                        self.telegram.sendMessage(telegramText)
                    if self.twitter is not None:
                        twitterText = text
                        twitterText += "\n\n#alephium #exchange"
                        self.twitter.sendMessage(twitterText)

    def on_message(self, ws, message):
        jsonData = json.loads(message)

        if jsonData['method'] == "trades.update":
            self.trades(jsonData)

    def on_close(self, ws, close_status_code, close_msg):
        print(f"Connection close: {close_msg},{close_status_code}")

    def on_ping(self, ws, message):
        id = random.randint(1, 100000)
        data = {
            "id": id,
            "method": "server.ping",
            "params": []
        }
        self.ws.send(json.dumps(data))

        print("Got a ping! A pong reply has already been automatically sent.")

    def on_pong(self, ws, message):
        pass

    def on_open(self, ws):
        id = random.randint(1, 100000)
        data = {
            "id": id,
            "method": self.method,
            "params": [self.pair]
        }
        self.ws.send(json.dumps(data))
        print(f"Connected to {self.wssURL}, method: {self.method}")


def handler(signum, frame):
    exit(1)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handler)
    GateioWss("wss://ws.gate.io/v3/", 1)
