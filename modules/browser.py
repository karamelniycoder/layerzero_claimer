from tls_client import Session
from loguru import logger
from requests import get
from time import sleep

from settings import *
from .utils import sleeping
from .database import DataBase

from tls_client.exceptions import TLSClientExeption


class Browser:
    def __init__(self, privatekey: str, db: DataBase):
        self.privatekey = privatekey
        self.address = None
        self.db = db

        if PROXY not in ['http://log:pass@ip:port', '']:
            self.change_ip()

        self.session = self.get_new_session()
        self.session.headers.update({
            "Referer": "https://www.layerzero.foundation/eligibility",
        })


    def get_new_session(self):
        session = Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True
        )
        session.headers['user-agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        if PROXY not in ['http://log:pass@ip:port', '']:
            session.proxies.update({'http': PROXY, 'https': PROXY})

        return session


    def change_ip(self):
        if CHANGE_IP_LINK not in ['https://changeip.mobileproxy.space/?proxy_key=...&format=json', '']:
            while True:
                try:
                    r = get(CHANGE_IP_LINK)
                    if 'mobileproxy' in CHANGE_IP_LINK and r.json().get('status') == 'OK':
                        print('') # empty string before next acc
                        logger.debug(f'[+] Proxy | Successfully changed ip: {r.json()["new_ip"]}')
                        return True
                    elif not 'mobileproxy' in CHANGE_IP_LINK and r.status_code == 200:
                        print('') # empty string before next acc
                        logger.debug(f'[+] Proxy | Successfully changed ip: {r.text}')
                        return True
                    logger.error(f'[-] Proxy | Change IP error: {r.text} | {r.status_code}')
                    sleep(10)

                except TLSClientExeption as err:
                    logger.error(f'[-] Browser | {err}')

                except Exception as err:
                    logger.error(f'[-] Browser | Cannot get proxy: {err}')


    def get_eligibility(self, retry: int = 0):
        try:
            value = 0
            amount = 0
            proof = None

            r = self.session.get(f"https://www.layerzero.foundation/api/proof/{self.address.lower()}")
            is_eligible = not r.json().get("error") == "Record not found"

            if is_eligible:
                value = {"full": int(r.json()["amount"]), "second": int(r.json()["round2"])}
                amount = {"full": round(value["full"] / 1e18, 2), "second": round(value["second"] / 1e18, 2)}
                proof = r.json()["proof"].split('|')

                status = "Eligible"
                logger.success(f'[+] Browser | ELIGIBLE | {amount["second"]} $ZRO (TOTAL {amount["full"]} ZRO$)')
                self.db.append_report(privatekey=self.privatekey, text=f"Eligible for {amount['second']} $ZRO", success=True)
            else:
                status = "Not Eligible"
                logger.error(f'[+] Browser | NOT ELIGIBLE')
                self.db.append_report(privatekey=self.privatekey, text=f"Not Eligible", success=False)

            return {"status": status, "amount": amount, "value": value, "proof": proof}

        except Exception as err:
            if retry < RETRY:
                logger.error(f"[-] Browser | Coudlnt get eligibility: {err} [{retry + 1}/{RETRY}]")
                sleep(3)
                return self.get_eligibility(retry=retry + 1)
            else:
                logger.error(f"[-] Browser | Coudlnt get eligibility: {err}")
                return {"status": "Coudlnt get eligibility", "amount": 0, "value": 0, "proof": None}


    def get_relay_tx(self, value: int, from_chain_id: int, to_chain_id: int, retry=0):
        try:
            headers = {
                "Origin": "https://relay.link",
                "Referer": "https://relay.link/"
            }
            payload = {
                "user": self.address,
                "originChainId": from_chain_id,
                "destinationChainId": to_chain_id,
                "currency": "eth",
                "recipient": self.address,
                "amount": str(int(value / 2)),
                "usePermit": False,
                "source": "relay.link",
                "useExternalLiquidity": False,
            }

            for i in range(2):
                r = self.session.post('https://api.relay.link/execute/bridge/v2', json=payload, headers=headers)

                if i == 0:
                    fee = int(r.json()["fees"]["relayer"]["amount"])
                    gas = int(r.json()["fees"]["gas"]["amount"])
                    payload["amount"] = str(int(value - (fee * 2 + gas * 3)))
                elif i == 1:
                    return r.json()['steps'][0]['items'][0]['data']

        except Exception as err:
            if retry < RETRY:
                logger.error(f"[-] Browser | Coudlnt get relay quoutes {i+1}: {err} [{retry + 1}/{RETRY}]")
                sleeping(10)
                return self.get_relay_tx(value=value, from_chain_id=from_chain_id, to_chain_id=to_chain_id, retry=retry+1)
            else:
                raise Exception(f"Coudlnt get relay quoutes {i+1}")
