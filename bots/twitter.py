import tweepy
import time

from tweepy import TweepyException


class TwitterBot:
    def __init__(self, consumerKey, consumerSecret, bearer, accessToken, accessSecret, botEnabled=True, monitor=None):
        self.consumerKey = consumerKey
        self.consumerSecret = consumerSecret
        self.accessToken = accessToken
        self.accessSecret = accessSecret
        self.bearer = bearer
        self.botEnabled = botEnabled
        self.monitor = monitor

        self.bot = tweepy.Client(bearer_token=self.bearer,
                                 consumer_key=self.consumerKey,
                                 consumer_secret=self.consumerSecret, access_token=self.accessToken,
                                 access_token_secret=self.accessSecret)

    def sendMessage(self, text):
        print(f"----\nBot Twitter\n{text}")
        if self.botEnabled:
            for __ in range(10):
                try:
                    self.bot.create_tweet(text=text, reply_settings="following")
                except TweepyException as e:
                    if self.monitor is not None:
                        self.monitor.sendMessage("Twitter", e, text)
                    print(e)
                    time.sleep(2)
                    continue
                else:
                    break