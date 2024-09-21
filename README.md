## LAYERZERO Claimer


### Описание
Есть два режима:
1) **Клейм $ZRO**
   1. Чекает, элигбл ли кошелек. Если нот элигбл - скип
   2. Если баланс в ARB меньше чем нужно депнуть - выводит с указанной биржи (*BINANCE / OKX / BITGET*)
   3. Клеймит $ZRO
   4. Если в настройках указанно что нужно отправить на биржу - отправляет на указанный адрес

2) **Чекер**. После прокрута всех аккаунтов в базе данных останутся только элигбл аккаунты - сможете 
сразу запустить первый режим 

Если кошелек завершится с ошибкой, можете заново запустить софт, он поймет с какого момента нужно продолжить. 

На момент написания софта комиссии на биржах следующие:

| Exchange |     Min Withdraw     | Withdraw Fee         |
|----------|:--------------------:|----------------------|
| Binance  | 0.0012 BNB *(0.71$)* | 0.0006 BNB *(0.35$)* |
| OKX      | 0.002 BNB *(1.19$)*  | 0.002 BNB *(1.19$)*  |
| Bitget   |  0.01 BNB *(5.95$)*  | 0.0005 BNB *(0.30$)* |

---

### Настройка

1. Указать свои приватники в `privatekeys.txt`
2. Если хотите отправлять токены на биржу после клейма - укажите `recepients.txt`
3. В `settings.py` настройте софт под себя, указав нужную вам биржу для вывода ETH, прокси и тд

---

### Запуск

1. Установить необходимые либы `pip install -r requirements.txt`
2. Запустить софт `py main.py`
3. Создать базу данных (*Create Database -> New Database*)
4. Стартуем (*Run*)

---

[🍭 kAramelniy 🍭](https://t.me/kAramelniy)
