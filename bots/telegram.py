import telegram
from telegram import ParseMode
import time

class TelegramBot:

    def __init__(self, token, chatId, botEnabled=True, monitor=None):
        self.token = token
        self.chatId = chatId
        self.bot = telegram.Bot(token=self.token)
        self.botEnabled = botEnabled
        self.monitor = monitor

    def getChatId(self):
        return self.chatId

    def sendMessage(self, text,chatId=None):
        print(f"----\nBot Telegram (chat id: {chatId})\n{text}")
        if self.botEnabled:
            for __ in range(10):
                try:
                    self.bot.send_message(chat_id=self.getChatId() if chatId is None else chatId, text=text,
                                          parse_mode=ParseMode.MARKDOWN,disable_web_page_preview=True)
                except telegram.error.RetryAfter as ra:
                    if self.monitor is not None:
                        self.monitor.sendMessage("Telegram", ra, text)

                    if int(ra.retry_after) > 60:
                        print("Flood control exceeded. Retry in 60 seconds")
                        time.sleep(60)
                    else:
                        print(ra)
                        time.sleep(int(ra.retry_after))
                    continue
                except Exception as e:
                    if self.monitor is not None:
                        self.monitor.sendMessage("Telegram", e, text)
                else:
                    break