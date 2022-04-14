# whaleswatcher

# How to start
```
1. pip install pipenv
2. pipenv install
3. pipenv run python main.py
```

## Example


Basic: `python3 main.py --no-bot --debug  -t 1000 -tt 1000 -gt 10000`
No message send on twitter or telegram (for debug purpose): `python3 main.py --no-bot --debug  -t 1000 -tt 1000 -gt 10000  -i 1`

# Parameters

| Parameter | Short | Default | Description |
|----------|---------|---------|-------------|
| `bot` | _none_ |`true` | Messages are send to Twitter and Telegram |
| `debug` | _none_ | `false` | Send message every second to Twitter and Telegram (for debug purpose) |
| `stats` | _none_ | `true` | Enable periodic insight messages |
| `threshold` | `t` | 10000  | threshold amount to send a message to Telegram |
| `tweetthreshold` | `tt` | 10000 | threshold amount to send a message to Twitter  | 
| `gatethreshold` | `gt` | 5000 | threshold amount detected on gate to send a message to Twitter and Telegram |
| `interval` | `i` | 120 | Interval between requests |

Note: for parameters `bot`, `debug` and `stats`, negative parameters `no-bot`, `no-debug` and `no-stats` are available
