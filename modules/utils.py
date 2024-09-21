from datetime import datetime
from random import randint
from requests import post
from loguru import logger
from time import sleep
from tqdm import tqdm
from web3 import Web3
import sys
import ctypes
import os

sys.__stdout__ = sys.stdout # error with `import inquirer` without this string in some system
from inquirer import prompt, List

from inspect import getsourcefile
from settings import TG_BOT_TOKEN, TG_USER_ID, AVAILABLE_CHAINS


logger.remove()
logger.add(sys.stderr, format="<white>{time:HH:mm:ss}</white> | <level>{message}</level>")
windll = ctypes.windll if os.name == 'nt' else None # for Mac users


class WindowName:
    def __init__(self, accs_amount):
        try: self.path = os.path.abspath(getsourcefile(lambda: 0)).split("\\")[-3]
        except: self.path = os.path.abspath(getsourcefile(lambda: 0)).split("/")[-3]

        self.accs_amount = accs_amount
        self.accs_done = 0
        self.modules_amount = 0
        self.modules_done = 0

        self.update_name()

    def update_name(self):
        if os.name == 'nt':
            windll.kernel32.SetConsoleTitleW(f'LayerZero Claimer [{self.accs_done}/{self.accs_amount}] | {self.path}')

    def add_acc(self):
        self.accs_done += 1
        self.update_name()

    def add_module(self, modules_done=1):
        self.modules_done += modules_done
        self.update_name()

    def set_modules(self, modules_amount: int):
        self.modules_amount = modules_amount
        self.update_name()


class TgReport:
    def __init__(self):
        self.logs = ''


    def update_logs(self, text: str):
        self.logs += f'{text}\n'


    def send_log(self, logs: str = None):
        notification_text = logs or self.logs

        texts = []
        while len(notification_text) > 0:
            texts.append(notification_text[:1900])
            notification_text = notification_text[1900:]

        if TG_BOT_TOKEN:
            for tg_id in TG_USER_ID:
                for text in texts:
                    try:
                        r = post(f'https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage?parse_mode=html&chat_id={tg_id}&text={text}')
                        if r.json().get("ok") != True: raise Exception(r.json())
                    except Exception as err:
                        logger.error(f'[-] TG | Send Telegram message error to {tg_id}: {err}\n{text}')


def sleeping(*timing):
    if type(timing[0]) == list: timing = timing[0]
    if len(timing) == 2: x = randint(timing[0], timing[1])
    else: x = timing[0]
    desc = datetime.now().strftime('%H:%M:%S')
    for _ in tqdm(range(x), desc=desc, bar_format='{desc} | [•] Sleeping {n_fmt}/{total_fmt}'):
        sleep(1)


def make_text_border(text: str):
    new_text = ''
    space = ' ' * 12
    max_len = max([len(string) for string in text.split('\n')])

    new_text += f'{space}+' + '—' * (max_len + 12) + f'+\n{space}│{" " * (max_len + 12)}│\n'
    for string in text.split('\n'): new_text += f'{space}│      {string}{" " * (max_len + 6 - len(string))}│\n'
    new_text += f'{space}│{" " * (max_len + 12)}│\n{space}+' + '—' * (max_len + 12) + '+\n'

    return new_text


def get_address(pk: str):
    return Web3().eth.account.from_key(pk).address


def choose_mode():
    questions = [
        List('prefered_path', message="Choose action",
             choices=[
                '(Re)Create Database',
                'Run (only Arbitrum)',
                f'Run ({"/".join([chain.upper() for chain in AVAILABLE_CHAINS])} to Arbitrum)',
                'Checker only',
             ])]
    answer = prompt(questions)['prefered_path']

    if answer == '(Re)Create Database':
        questions = [
            List('db_type', message="Which type of database you want to create?",
                 choices=[
                     'Exit',
                     'New Database',
                 ])]
        answer = prompt(questions)['db_type']

    return answer
