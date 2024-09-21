from random import choice, shuffle, randint
from os import path, mkdir
import json

from modules.utils import logger, get_address, WindowName
from settings import SHUFFLE_WALLETS, TRANSFER_TOKENS


class DataBase:
    def __init__(self):
        self.modules_db_name = 'databases/modules.json'
        self.report_db_name = 'databases/report.json'
        self.window_name = None

        # create db's if not exists
        if not path.isdir(self.modules_db_name.split('/')[0]):
            mkdir(self.modules_db_name.split('/')[0])

        if not path.isfile(self.modules_db_name):
            with open(self.modules_db_name, 'w') as f: f.write('[]')
        if not path.isfile(self.report_db_name):
            with open(self.report_db_name, 'w') as f: f.write('{}')

        amounts = self.get_amounts()
        logger.info(f'Loaded {amounts["accs_amount"]} accounts\n')


    def create_modules(self):
        with open('privatekeys.txt') as f: private_keys = f.read().splitlines()
        if TRANSFER_TOKENS:
            with open('recipients.txt') as f: recipients = f.read().splitlines()
            if len(private_keys) != len(recipients):
                raise Exception(f'Amount of privatekeys ({len(private_keys)}) must be same as recipients amount ({len(recipients)})')
        else:
            recipients = [None for _ in range(len(private_keys))]

        with open(self.report_db_name, 'w') as f: f.write('{}')  # clear report db

        new_modules = {pk: {"modules": [{"module_name": "claim", "status": "to_run"}], "recipient": recip} for pk, recip in zip(private_keys, recipients)}

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(new_modules, f)

        amounts = self.get_amounts()
        logger.success(f'Created database for {amounts["accs_amount"]} accounts!\n')


    def get_wallets_count(self):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        return len(modules_db)


    def get_amounts(self):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)
        modules_len = sum([len(modules_db[acc]["modules"]) for acc in modules_db])

        for acc in modules_db:
            for index, module in enumerate(modules_db[acc]["modules"]):
                if module["status"] == "failed": modules_db[acc]["modules"][index]["status"] = "to_run"

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)

        if self.window_name == None: self.window_name = WindowName(accs_amount=len(modules_db))
        else: self.window_name.accs_amount = len(modules_db)
        self.window_name.set_modules(modules_amount=modules_len)

        return {'accs_amount': len(modules_db), 'modules_amount': modules_len}


    def get_random_module(self):
        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        if (
                not modules_db or
                [module["status"] for acc in modules_db for module in modules_db[acc]["modules"]].count('to_run') == 0
        ):
            return 'No more accounts left'

        while True:
            if SHUFFLE_WALLETS: privatekey = choice(list(modules_db.keys()))
            else: privatekey = list(modules_db.keys())[0]
            modules_list = [module for module in modules_db[privatekey]["modules"] if module["status"] == "to_run"]
            if not modules_list:
                del modules_db[privatekey]
                continue

            module_info = choice(modules_list)

            # simulate db
            for module in modules_db[privatekey]["modules"]:
                if module["module_name"] == module_info["module_name"] and module["status"] == module_info["status"]:
                    modules_db[privatekey]["modules"].remove(module)
                    break

            return {
                'privatekey': privatekey,
                'recipient': modules_db[privatekey].get("recipient"),
                'module_info': module_info,
                'last': [module["status"] for module in modules_db[privatekey]["modules"]].count('to_run') == 0,
            }


    def remove_module(self, module_data: dict):
        self.window_name.add_module()

        with open(self.modules_db_name, encoding="utf-8") as f: modules_db = json.load(f)

        for index, module in enumerate(modules_db[module_data["privatekey"]]["modules"]):
            if module["module_name"] == module_data["module_info"]["module_name"] and module["status"] == "to_run":

                if module_data["module_info"]["status"] in [True, "Not Eligible", "Claimed", "Already claimed", "Transferred"]:
                    modules_db[module_data["privatekey"]]["modules"].remove(module)
                else:
                    modules_db[module_data["privatekey"]]["modules"][index]["status"] = "failed"
                break

        if [module["status"] for module in modules_db[module_data["privatekey"]]["modules"]].count('to_run') == 0:
            self.window_name.add_acc()

            if not modules_db[module_data["privatekey"]]["modules"]:
                del modules_db[module_data["privatekey"]]

        with open(self.modules_db_name, 'w', encoding="utf-8") as f: json.dump(modules_db, f)


    def append_report(self, privatekey: str, text: str, success: bool = None):
        status_smiles = {True: '✅ ', False: "❌ ", None: ""}

        with open(self.report_db_name, encoding="utf-8") as f: report_db = json.load(f)

        if not report_db.get(privatekey): report_db[privatekey] = {'texts': [], 'success_rate': [0, 0]}

        report_db[privatekey]["texts"].append(status_smiles[success] + text.replace('#', '%23'))
        if success != None:
            report_db[privatekey]["success_rate"][1] += 1
            if success == True: report_db[privatekey]["success_rate"][0] += 1

        with open(self.report_db_name, 'w') as f: json.dump(report_db, f)


    def get_account_reports(self, privatekey: str, get_rate: bool = False):
        with open(self.report_db_name, encoding="utf-8") as f: report_db = json.load(f)

        if report_db.get(privatekey):
            account_reports = report_db[privatekey]
            if get_rate: return f'{account_reports["success_rate"][0]}/{account_reports["success_rate"][1]}'
            del report_db[privatekey]

            with open(self.report_db_name, 'w', encoding="utf-8") as f: json.dump(report_db, f)

            logs_text = '\n'.join(account_reports['texts'])
            tg_text = f'[{self.window_name.accs_done}/{self.window_name.accs_amount}] {get_address(pk=privatekey)}\n\n' \
                      f'{logs_text}'

            return tg_text

        else:
            return f'[{self.window_name.accs_done}/{self.window_name.accs_amount}] {get_address(pk=privatekey)}\n\n' \
                     f'No actions'
