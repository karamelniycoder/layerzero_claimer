from web3.middleware import geth_poa_middleware
from eth_account.messages import encode_defunct
from random import uniform, randint, choice
from typing import Union
from ccxt import bitget, binance
from time import sleep
from web3 import Web3
import requests
import base64
import hmac

from modules.utils import logger, sleeping
from modules.database import DataBase
from modules.browser import Browser
import modules.config as config
import settings


class Wallet:
    def __init__(self, privatekey: str, db: DataBase, browser: Browser, recipient: str | None = None):
        self.privatekey = privatekey
        self.recipient = Web3().to_checksum_address(recipient) if recipient else None
        self.account = Web3().eth.account.from_key(privatekey)
        self.address = self.account.address
        self.db = db
        self.browser = browser


    def get_web3(self, chain_name: str):
        web3 = Web3(Web3.HTTPProvider(settings.RPCS[chain_name]))
        web3.middleware_onion.inject(geth_poa_middleware, layer=0)
        return web3


    def wait_for_gwei(self):
        for chain_data in [
            {'chain_name': 'ethereum', 'max_gwei': settings.MAX_ETH_GWEI},
        ]:
            first_check = True
            while True:
                try:
                    new_gwei = round(self.get_web3(chain_name=chain_data['chain_name']).eth.gas_price / 10 ** 9, 2)
                    if new_gwei < chain_data["max_gwei"]:
                        if not first_check: logger.debug(f'[•] Web3 | New {chain_data["chain_name"].title()} GWEI is {new_gwei}')
                        break
                    sleep(5)
                    if first_check:
                        first_check = False
                        logger.debug(f'[•] Web3 | Waiting for GWEI in {chain_data["chain_name"].title()} at least {chain_data["max_gwei"]}. Now it is {new_gwei}')
                except Exception as err:
                    logger.warning(f'[•] Web3 | {chain_data["chain_name"].title()} gwei waiting error: {err}')
                    sleeping(10)

    def get_gas(self, chain_name, increasing_gwei=0):
        max_priority = int(self.get_web3(chain_name=chain_name).eth.max_priority_fee * (settings.GWEI_MULTIPLIER + increasing_gwei))
        last_block = self.get_web3(chain_name=chain_name).eth.get_block('latest')
        base_fee = last_block['baseFeePerGas']
        if max_priority == 0: max_priority = base_fee

        block_filled = last_block['gasUsed'] / last_block['gasLimit'] * 100
        if block_filled > 50: base_fee *= 1.127
        max_fee = int(base_fee + max_priority)

        return {'maxPriorityFeePerGas': max_priority, 'maxFeePerGas': max_fee}


    def approve(self, chain_name: str, token_name: str, spender: str, amount=None, value=None, retry=0):
        try:
            web3 = self.get_web3(chain_name=chain_name)
            spender = web3.to_checksum_address(spender)
            token_contract = web3.eth.contract(address=web3.to_checksum_address(config.TOKEN_ADDRESSES[token_name]),
                                         abi='[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]')

            decimals = token_contract.functions.decimals().call()
            if amount:
                value = int(amount * 10 ** decimals)
                new_amount = round(amount * randint(10, 40), 5)
                new_value = int(new_amount * 10 ** decimals)
            else:
                new_value = int(value * randint(10, 40))
                new_amount = round(new_value / 10 ** decimals, 5)
            module_str = f'approve {new_amount} {token_name} to {spender}'

            allowance = token_contract.functions.allowance(self.address, spender).call()
            if allowance < value:
                tx = token_contract.functions.approve(spender, new_value)
                tx_hash = self.sent_tx(chain_name=chain_name, tx=tx, tx_label=module_str)
                sleeping(settings.SLEEP_AFTER_TX)
                return tx_hash
        except Exception as error:
            if retry < settings.RETRY:
                logger.error(f'[-] Web3 | {module_str} | {error}')
                sleeping(10)
                self.approve(chain_name=chain_name, token_name=token_name, spender=spender, amount=amount, value=value, retry=retry+1)
            else:
                self.db.append_report(privatekey=self.privatekey, text=module_str, success=False)
                raise ValueError(f'{module_str}: {error}')


    def sent_tx(self, chain_name: str, tx, tx_label, tx_raw=False, value=0, increasing_gwei=0, gas_multiplier=1.1):
        try:
            web3 = self.get_web3(chain_name=chain_name)
            if not tx_raw:
                tx_completed = tx.build_transaction({
                    'from': self.address,
                    'chainId': web3.eth.chain_id,
                    'nonce': web3.eth.get_transaction_count(self.address),
                    'value': value,
                    **self.get_gas(chain_name=chain_name, increasing_gwei=increasing_gwei),
                })
                tx_completed['gas'] = int(int(tx_completed['gas']) * gas_multiplier)
            else:
                tx_completed = tx

            signed_tx = web3.eth.account.sign_transaction(tx_completed, self.privatekey)
            raw_tx_hash = web3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash = web3.to_hex(raw_tx_hash)
            tx_link = f'{config.CHAINS_DATA[chain_name]["explorer"]}{tx_hash}'
            logger.debug(f'[•] Web3 | {tx_label} tx sent: {tx_link}')

            status = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=int(settings.TO_WAIT_TX * 60)).status

            if status == 1:
                logger.info(f'[+] Web3 | {tx_label} tx confirmed\n')
                self.db.append_report(privatekey=self.privatekey, text=tx_label, success=True)
                return tx_hash
            else:
                self.db.append_report(privatekey=self.privatekey, text=f'{tx_label} | tx is failed | <a href="{tx_link}">link 👈</a>', success=False)
                raise ValueError(f'{tx_label} tx failed: {tx_link}')

        except Exception as err:
            if "replacement transaction underpriced" in str(err) or "not in the chain after" in str(err) or "max fee per gas less" in str(err):
                logger.warning(f'[-] Web3 | {tx_label} | couldnt send tx, increasing gwei')
                return self.sent_tx(chain_name=chain_name, tx=tx, tx_label=tx_label, tx_raw=tx_raw, value=value, increasing_gwei=increasing_gwei + 0.05)
            elif tx_raw: value = tx_completed.get('value')

            try: encoded_tx = f'\n{tx_completed._encode_transaction_data()}'
            except: encoded_tx = ''
            raise ValueError(f'failed: "{err}", value: {value};{encoded_tx}')


    def get_balance(self, chain_name: str, token_name=False, token_address=False, human=False):
        web3 = self.get_web3(chain_name=chain_name)
        if token_name: token_address = config.TOKEN_ADDRESSES[token_name]
        if token_address: contract = web3.eth.contract(address=web3.to_checksum_address(token_address),
                                                       abi='[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]')

        while True:
            try:
                if token_address: balance = contract.functions.balanceOf(self.address).call()
                else: balance = web3.eth.get_balance(self.address)

                if not human: return balance

                decimals = contract.functions.decimals().call() if token_address else 18
                return balance / 10 ** decimals

            except Exception as err:
                logger.warning(f'[•] Web3 | Get balance error: {err}')
                sleep(5)


    def wait_balance(self, chain_name: str, needed_balance: Union[int, float], only_more: bool = False):
        " needed_balance: human digit "
        if only_more: logger.debug(f'[•] Web3 | Waiting for balance more than {round(needed_balance, 6)} ETH in {chain_name.upper()}')
        else: logger.debug(f'[•] Web3 | Waiting for {round(needed_balance, 6)} ETH balance in {chain_name.upper()}')
        while True:
            try:
                new_balance = self.get_balance(chain_name=chain_name, human=True)
                if only_more: status = new_balance > needed_balance
                else: status = new_balance >= needed_balance
                if status:
                    logger.debug(f'[•] Web3 | New balance: {round(new_balance, 6)} ETH\n')
                    return new_balance
                sleep(5)
            except Exception as err:
                logger.warning(f'[•] Web3 | Wait balance error: {err}')
                sleep(10)


    def get_token_decimals(self, chain_name: str, token_name: str):
        if token_name == 'ETH': return 18

        web3 = self.get_web3(chain_name=chain_name)
        token_contract = web3.eth.contract(address=web3.to_checksum_address(config.TOKEN_ADDRESSES[token_name]),
                                           abi='[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"spender","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"approve","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"address","name":"spender","type":"address"}],"name":"allowance","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"}]')
        return token_contract.functions.decimals().call()


    def get_human_token_amount(self, chain_name: str, token_name: str, value: Union[int, float], human=True):
        decimals = self.get_token_decimals(chain_name=chain_name, token_name=token_name)

        if human: return round(value / 10 ** decimals, 7)
        else: return int(value * 10 ** decimals)


    def okx_withdraw(self, chain: str, amount: float = None, multiplier=0.6, retry=0):

        def okx_data(api_key, secret_key, passphras, request_path="/api/v5/account/balance?ccy=ETH", body='', meth="GET"):
            try:
                import datetime
                def signature(timestamp: str, method: str, request_path: str, secret_key: str, body: str = "") -> str:
                    if not body: body = ""

                    message = timestamp + method.upper() + request_path + body
                    mac = hmac.new(
                        bytes(secret_key, encoding="utf-8"),
                        bytes(message, encoding="utf-8"),
                        digestmod="sha256",
                    )
                    d = mac.digest()
                    return base64.b64encode(d).decode("utf-8")

                dt_now = datetime.datetime.utcnow()
                ms = str(dt_now.microsecond).zfill(6)[:3]
                timestamp = f"{dt_now:%Y-%m-%dT%H:%M:%S}.{ms}Z"

                base_url = "https://www.okex.com"
                headers = {
                    "Content-Type": "application/json",
                    "OK-ACCESS-KEY": api_key,
                    "OK-ACCESS-SIGN": signature(timestamp, meth, request_path, secret_key, body),
                    "OK-ACCESS-TIMESTAMP": timestamp,
                    "OK-ACCESS-PASSPHRASE": passphras,
                    'x-simulated-trading': '0'
                }
            except Exception as ex:
                logger.error(ex)
            return base_url, request_path, headers

        SYMBOL = 'ETH'
        CHAIN = config.OKX_CHAINS[chain]["chain_name"]

        if amount:
            amount_from = amount
            amount_to = amount
        else:
            amount_from = settings.WITHDRAW_VALUES[0]
            amount_to = settings.WITHDRAW_VALUES[1]
        wallet = self.address
        SUB_ACC = True

        old_balance = self.get_balance(chain_name=chain, human=True)

        api_key = settings.OKX_API_KEY
        secret_key = settings.OKX_API_SECRET
        passphras = settings.OKX_API_PASSWORD

        # take FEE for withdraw
        _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/currencies?ccy={SYMBOL}", meth="GET")
        response = requests.get(f"https://www.okx.cab/api/v5/asset/currencies?ccy={SYMBOL}", timeout=10, headers=headers)

        if not response.json().get('data'): raise Exception(f'Bad OKX API keys: {response.json()}')
        for lst in response.json()['data']:
            if lst['chain'] == f'{SYMBOL}-{CHAIN}':
                raw_fee = float(lst['minFee'])

        try:
            while True:
                if SUB_ACC == True:
                    _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/users/subaccount/list", meth="GET")
                    list_sub = requests.get("https://www.okx.cab/api/v5/users/subaccount/list", timeout=10, headers=headers)
                    list_sub = list_sub.json()

                    for sub_data in list_sub['data']:
                        while True:
                            name_sub = sub_data['subAcct']

                            _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/subaccount/balances?subAcct={name_sub}&ccy={SYMBOL}", meth="GET")
                            sub_balance = requests.get(f"https://www.okx.cab/api/v5/asset/subaccount/balances?subAcct={name_sub}&ccy={SYMBOL}", timeout=10, headers=headers)
                            sub_balance = sub_balance.json()
                            if sub_balance.get('msg') == f'Sub-account {name_sub} doesn\'t exist':
                                logger.warning(f'[-] OKX | Error: {sub_balance["msg"]}')
                                continue
                            sub_balance = sub_balance['data'][0]['bal']

                            logger.info(f'[•] OKX | {name_sub} | {sub_balance} {SYMBOL}')

                            if float(sub_balance) > 0:
                                body = {"ccy": f"{SYMBOL}", "amt": str(sub_balance), "from": 6, "to": 6, "type": "2", "subAcct": name_sub}
                                _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/transfer", body=str(body), meth="POST")
                                a = requests.post("https://www.okx.cab/api/v5/asset/transfer", data=str(body), timeout=10, headers=headers)
                            break

                try:
                    _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/account/balance?ccy={SYMBOL}")
                    balance = requests.get(f'https://www.okx.cab/api/v5/account/balance?ccy={SYMBOL}', timeout=10, headers=headers)
                    balance = balance.json()
                    balance = balance["data"][0]["details"][0]["cashBal"]

                    if balance != 0:
                        body = {"ccy": f"{SYMBOL}", "amt": float(balance), "from": 18, "to": 6, "type": "0", "subAcct": "", "clientId": "", "loanTrans": "", "omitPosRisk": ""}
                        _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/transfer", body=str(body), meth="POST")
                        a = requests.post("https://www.okx.cab/api/v5/asset/transfer", data=str(body), timeout=10, headers=headers)
                except Exception as ex:
                    pass

                # CHECK MAIN BALANCE
                _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/balances?ccy={SYMBOL}", meth="GET")
                main_balance = requests.get(f'https://www.okx.cab/api/v5/asset/balances?ccy={SYMBOL}', timeout=10, headers=headers)
                main_balance = main_balance.json()
                main_balance = float(main_balance["data"][0]['availBal'])
                logger.info(f'[•] OKX | Total balance: {main_balance} {SYMBOL}')

                if amount_from > main_balance:
                    logger.warning(f'[•] OKX | Not enough balance ({main_balance} < {amount_from}), waiting 10 secs...')
                    sleep(10)
                    continue

                if amount_to > main_balance:
                    logger.warning(f'[•] OKX | You want to withdraw MAX {amount_to} but have only {round(main_balance, 7)}')
                    amount_to = round(main_balance, 7)

                AMOUNT = round(uniform(amount_from, amount_to), 4)
                break

            while True:
                body = {"ccy": SYMBOL, "amt": AMOUNT, "fee": round(raw_fee * multiplier, 6), "dest": "4", "chain": f"{SYMBOL}-{CHAIN}", "toAddr": wallet}
                _, _, headers = okx_data(api_key, secret_key, passphras, request_path=f"/api/v5/asset/withdrawal", meth="POST", body=str(body))
                a = requests.post("https://www.okx.cab/api/v5/asset/withdrawal", data=str(body), timeout=10, headers=headers)
                result = a.json()

                if result['code'] == '0':
                    logger.success(f"[+] OKX | Success withdraw {AMOUNT} {SYMBOL} in {CHAIN}")
                    self.db.append_report(privatekey=self.privatekey, text=f"OKX withdraw {AMOUNT} {SYMBOL} in {CHAIN}", success=True)
                    new_balance = self.wait_balance(chain_name=chain, needed_balance=old_balance, only_more=True)
                    return chain, new_balance-old_balance
                else:
                    if 'Withdrawal fee is lower than the lower limit' in result['msg'] and multiplier < 1:
                        # logger.warning(f"[-] OKX | Withdraw failed to {wallet} | error : {result['msg']} | New fee multiplier {round((multiplier + 0.05) * 100)}%")
                        multiplier += 0.05
                    else:
                        raise ValueError(result['msg'])

        except Exception as error:
            if retry < settings.RETRY:
                if 'Insufficient balance' in str(error):
                    logger.warning(f"[-] OKX | Withdraw failed to {chain} | error : {error}")
                    sleep(10)
                    return self.okx_withdraw(chain=chain, amount=amount, multiplier=multiplier, retry=retry)
                else:
                    logger.error(f"[-] OKX | Withdraw failed to {chain} | error : {error}")
                    sleep(10)
                    return self.okx_withdraw(chain=chain, amount=amount, multiplier=multiplier, retry=retry + 1)

            else:
                self.db.append_report(privatekey=self.privatekey, text=f'OKX withdraw error: {error}', success=False)
                raise Exception(f'OKX withdraw error: {error}')


    def bitget_withdraw(self, chain: str, amount: float = None, lowercase: bool = False, retry: int = 0):
        if amount:
            AMOUNT = amount
        else:
            AMOUNT = round(uniform(settings.WITHDRAW_VALUES[0], settings.WITHDRAW_VALUES[1]), 4)

        SYMBOL = 'ETH'
        NETWORK = config.BITGET_CHAINS[chain]["chain_name"]

        old_balance = self.get_balance(chain_name=chain, human=True)

        account_bitget = bitget({
            'apiKey': settings.BITGET_KEY,
            'secret': settings.BITGET_SECRET,
            'password': settings.BITGET_PASSWORD,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })

        if lowercase: address = self.address.lower()
        else: address = self.address

        try:
            account_bitget.withdraw(
                code=SYMBOL,
                amount=AMOUNT,
                address=address,
                params={"chain": NETWORK}
            )
            logger.success(f"[+] Bitget | Success withdraw {AMOUNT} {SYMBOL} in {chain.title()}")
            self.db.append_report(privatekey=self.privatekey, text=f'Bitget Withdraw {AMOUNT} {SYMBOL} in {chain.title()}', success=True)
            new_balance = self.wait_balance(chain_name=chain, needed_balance=old_balance, only_more=True)
            return chain, new_balance-old_balance

        except Exception as error:
            if retry < settings.RETRY:
                if 'Withdraw address is not in addressBook' in str(error): return self.bitget_withdraw(chain=chain, amount=amount, lowercase=True, retry=retry+1)

                logger.error(f'[-] Bitget | Withdraw to {chain.title()} error: {error}')
                sleeping(10)
                if 'Insufficient balance' in str(error): return self.bitget_withdraw(chain=chain, amount=amount, lowercase=lowercase, retry=retry)
                else: return self.bitget_withdraw(chain=chain, amount=amount, lowercase=lowercase, retry=retry+1)

            else:
                self.db.append_report(privatekey=self.privatekey, text=f'Bitget Withdraw {AMOUNT} {SYMBOL}: {error}', success=False)
                raise ValueError(f'Bitget withdraw error: {error}')



    def binance_withdraw(self, chain: str, amount: float = None, retry=0):
        old_balance = self.get_balance(chain_name=chain, human=True)

        if amount:
            AMOUNT = amount
        else:
            AMOUNT = round(uniform(settings.WITHDRAW_VALUES[0], settings.WITHDRAW_VALUES[1]), 4)
        SYMBOL = "ETH"
        NETWORK = config.BINANCE_CHAINS[chain]["chain_name"]

        account_binance = binance({
            'apiKey': settings.BINANCE_KEY,
            'secret': settings.BINANCE_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot'
            }
        })

        try:
            account_binance.withdraw(
                code=SYMBOL,
                amount=AMOUNT,
                address=self.address,
                tag=None,
                params={
                    "network": NETWORK
                }
            )
            logger.success(f"[+] Binance | Success withdraw {AMOUNT} {SYMBOL} in {chain.title()}")
            self.db.append_report(privatekey=self.privatekey, text=f'Binance Withdraw {AMOUNT} {SYMBOL} in {chain.title()}', success=True)
            new_balance = self.wait_balance(chain_name=chain, needed_balance=old_balance, only_more=True)
            return chain, new_balance-old_balance

        except Exception as error:
            if retry < settings.RETRY:
                logger.error(f'[-] Binance | Withdraw to {chain.title()} error: {error}')
                sleeping(10)
                return self.binance_withdraw(chain=chain, amount=amount, retry=retry + 1)

            else:
                self.db.append_report(privatekey=self.privatekey, text=f'Binance Withdraw {AMOUNT} {SYMBOL}: {error}', success=False)
                raise ValueError(f'Binance withdraw error: {error}')


    def call_withdraw(self, chain: str = None, amount: float = None):
        if not chain:
            available_chains = settings.AVAILABLE_CHAINS
            if "arbitrum" in available_chains: available_chains.remove("arbitrum")
            chain = choice(available_chains)

        if settings.EXCHANGE_TYPE.lower() == "bitget":
            return self.bitget_withdraw(chain=chain, amount=amount)
        elif settings.EXCHANGE_TYPE.lower() == "okx":
            return self.okx_withdraw(chain=chain, amount=amount)
        elif settings.EXCHANGE_TYPE.lower() == "binance":
            return self.binance_withdraw(chain=chain, amount=amount)


    def sign_message(self, text: str):
        message = encode_defunct(text=text)
        signed_message = self.account.sign_message(message)
        return signed_message.signature.hex()


    def send_to_exchange(self, chain: str, retry=0):
        module_str = f'sent ZRO'
        try:
            self.wait_for_gwei()

            web3 = self.get_web3(chain_name=chain)
            zro_contract = web3.eth.contract(
                address=web3.to_checksum_address(config.TOKEN_ADDRESSES["ZRO"]),
                abi='[{"inputs":[{"internalType":"address","name":"to","type":"address"},{"internalType":"uint256","name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"nonpayable","type":"function"}]'
            )

            value = self.get_balance(chain_name=chain, token_name="ZRO")
            amount = round(value / 1e18, 2)
            module_str = f'sent {amount} ZRO to {self.recipient}'

            if amount == 0:
                return "Already claimed"

            contract_tx = zro_contract.functions.transfer(
                self.recipient,
                value
            )

            self.sent_tx(chain_name=chain, tx=contract_tx, tx_label=module_str)
            return "Transferred"

        except Exception as error:
            logger.error(f'[-] Web3 | {module_str} | {error}')
            if "gas required exceeds allowance" in str(error):
                self.call_withdraw(chain=chain)
                return self.send_to_exchange(chain=chain, retry=retry)
            elif retry < settings.RETRY:
                sleeping(10)
                return self.send_to_exchange(chain=chain, retry=retry + 1)
            else:
                if 'tx failed' not in str(error):
                    self.db.append_report(privatekey=self.privatekey, text=f"{module_str}: {error}", success=False)


    def send_native_to_exchange(self, chain: str, retry=0):
        module_str = f'sent ETH in {chain} to {self.recipient}'
        try:
            web3 = self.get_web3(chain_name=chain)

            keep_values_ = settings.TRANSFER_ETH["keep_balance"]
            keep_value = round(uniform(keep_values_[0], keep_values_[1]), 5) * 1e18
            balance = self.get_balance(chain_name=chain)
            value_ = int(balance - keep_value)

            gaslimit = int(web3.eth.estimate_gas({'from': self.address, 'to': self.address}) * 1.1)
            value = int((value_ - gaslimit * web3.eth.gas_price) // 10 ** 12 * 10 ** 12)  # round value
            amount = value / 1e18

            module_str = f'sent {amount} ETH to {self.recipient}'

            tx = {
                'from': self.address,
                'to': self.recipient,
                'chainId': web3.eth.chain_id,
                'nonce': web3.eth.get_transaction_count(self.address),
                'value': value,
                'gas': gaslimit,
                **self.get_gas(chain_name=chain),
            }
            self.sent_tx(chain, tx, module_str, tx_raw=True)

        except Exception as error:
            logger.error(f'[-] Web3 | {module_str} | {error}')
            if retry < settings.RETRY:
                sleeping(10)
                return self.send_to_exchange(chain=chain, retry=retry + 1)
            else:
                self.db.append_report(privatekey=self.privatekey, text=f"{module_str}: {error}", success=False)
