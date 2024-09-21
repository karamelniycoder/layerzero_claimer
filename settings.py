
SHUFFLE_WALLETS     = True                  # True | False - перемешивать ли кошельки
RETRY               = 3                     # кол-во попыток при ошибках / фейлах

RPCS                = {
    'ethereum'  : 'https://eth.meowrpc.com',
    'arbitrum'  : 'https://arbitrum.meowrpc.com',
    'optimism'  : 'https://optimism.drpc.org',
    'zksync'    : 'https://zksync.drpc.org',
    'base'      : 'https://base.drpc.org',
}

MAX_ETH_GWEI        = 40                    # максимальный гвей в Ethereum
GWEI_MULTIPLIER     = 1.05                  # умножать текущий гвей при отправке транз на 5%
TO_WAIT_TX          = 1                     # сколько минут ожидать транзакцию. по истечению будет считатся зафейленной

SLEEP_AFTER_TX      = [10, 20]              # задержка после каждой транзакции 10-20 секунд
SLEEP_AFTER_ACCOUNT = [30, 60]              # задержка после каждого аккаунта 30-60 секунд

EXCHANGE_TYPE       = "Binance"             # выбор биржи для вывода: "OKX" | "Bitget" | "Binance"
WITHDRAW_VALUES     = [0.002, 0.004]        # вывести в ARB от 0.002 до 0.004 ETH

AVAILABLE_CHAINS    = [                     # (для второго режима) в какие сети выводить с биржи для последующего бриджа в Arbitrum
    "zksync",
    "optimism",
    "base",
]
AVAILABLE_BRIDGES   = [                     # (для второго режима) какие мосты использовать для бриджа в Arbitrum
    "Orbiter",
    "Relay",
]

# --------------------- CLAIM SETTINGS ---------------------
TRANSFER_TOKENS     = True                  # после успешного клейма $ZRO отправлять токены на указанный адрес
ADDITIONAL_BALANCE  = 0.001                 # софт перед клеймом проверяет баланс кошелька на (сколько донат в Л0 + указанный баланс в этом параметре).
                                            # выводит с `WITHDRAW_VALUES` биржи если не хватает
TRANSFER_ETH        = {
    "transfer": True,                       # выводить эфир после всех действий на биржу
    "keep_balance": [0.001, 0.002],         # сколько ETH оставлять на кошельке
}

# --------------------- PERSONAL SETTINGS --------------------

OKX_API_KEY         = ''
OKX_API_SECRET      = ''
OKX_API_PASSWORD    = ''


BITGET_KEY          = ''
BITGET_SECRET       = ''
BITGET_PASSWORD     = ''

BINANCE_KEY         = ''
BINANCE_SECRET      = ''

PROXY               = 'http://log:pass@ip:port'           # что бы не использовать прокси - оставьте как есть
CHANGE_IP_LINK      = 'https://changeip.mobileproxy.space/?proxy_key=...&format=json'

TG_BOT_TOKEN        = ''                           # токен от тг бота (`12345:Abcde`) для уведомлений. если не нужно - оставляй пустым
TG_USER_ID          = []                             # тг айди куда должны приходить уведомления. [21957123] - для отправления уведомления только себе, [21957123, 103514123] - отправлять нескольким людями
