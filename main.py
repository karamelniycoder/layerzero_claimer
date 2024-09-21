from random import uniform

from modules.utils import sleeping, logger, sleep, choose_mode
from modules import *
import settings


def runner(mode: str):
    while True:
        try:
            module_data = db.get_random_module()
            if module_data == 'No more accounts left':
                logger.success(f'All accounts done.')
                return 'Ended'

            # initialize
            browser = Browser(privatekey=module_data["privatekey"], db=db)
            wallet = Wallet(privatekey=module_data["privatekey"], recipient=module_data["recipient"], browser=browser, db=db)
            browser.address = wallet.address
            logger.info(f'[•] Web3 | {wallet.address}')

            eligibility_data = browser.get_eligibility()

            if eligibility_data["status"] != "Eligible":
                module_data["module_info"]["status"] = eligibility_data["status"]
                continue

            claimed_amount = LayerZero(wallet=wallet).is_claimed()
            if claimed_amount != eligibility_data["value"]["full"]:
                if mode == "Checker only": continue
                donate_value = int(eligibility_data["value"]["second"] / (36000 - 1))
                # fund ARBITRUM
                balance = wallet.get_balance(chain_name="arbitrum")
                if balance < donate_value + (settings.ADDITIONAL_BALANCE * 1e18):
                    amount = round(uniform(*settings.WITHDRAW_VALUES) + donate_value / 1e18, 5)

                    if mode == "Run (only Arbitrum)":
                        wallet.call_withdraw(chain="arbitrum", amount=amount)
                        sleeping(settings.SLEEP_AFTER_TX)
                    else:
                        funded_chain, withdrew_amount = wallet.call_withdraw(amount=amount)
                        sleeping(settings.SLEEP_AFTER_TX)
                        call_bridge(wallet=wallet, from_chain=funded_chain, amount=withdrew_amount)

                claim_status = LayerZero(wallet=wallet).claim(eligibility_data=eligibility_data, claimed_amount=claimed_amount, donate_value=donate_value)
            else:
                claim_status = "Already claimed"
                db.append_report(privatekey=wallet.privatekey, text="Already claimed", success=True)
                logger.success(f'[+] Web3 | Already claimed')
                if mode == "Checker only": continue

            if settings.TRANSFER_TOKENS and wallet.recipient:
                if claim_status == "Claimed": sleeping(settings.SLEEP_AFTER_TX)
                module_data["module_info"]["status"] = wallet.send_to_exchange(chain="arbitrum")
            else:
                module_data["module_info"]["status"] = claim_status

            if settings.TRANSFER_ETH["transfer"]:
                sleeping(settings.SLEEP_AFTER_TX)
                wallet.send_native_to_exchange(chain="arbitrum")

        except Exception as err:
            module_data["module_info"]["status"] = str(err)
            logger.error(f'[-] Soft | {wallet.address} | Account error: {err}')
            db.append_report(privatekey=wallet.privatekey, text=str(err), success=False)

        finally:
            if type(module_data) == dict:
                db.remove_module(module_data=module_data)

                if module_data['last']:
                    reports = db.get_account_reports(privatekey=wallet.privatekey)
                    TgReport().send_log(logs=reports)

                sleeping(settings.SLEEP_AFTER_ACCOUNT)


if __name__ == '__main__':
    if settings.PROXY in ['http://log:pass@ip:port', '']: logger.error(f'You will not use proxies!')
    db = DataBase()

    while True:
        mode = choose_mode()
        match mode:
            case "New Database":
                try: db.create_modules()
                except Exception as err: logger.error(f'[-] Database: {err}\n')
            case x if "Run" in x or "Checker only":
                if runner(mode=mode) == 'Ended': break
                print('')
    sleep(0.1)
    input('\n > Exit')
