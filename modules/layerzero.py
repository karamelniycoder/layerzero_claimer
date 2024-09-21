from modules.utils import sleeping, logger
from modules.wallet import Wallet
import settings


class LayerZero(Wallet):
    def __init__(self, wallet: Wallet):
        super().__init__(privatekey=wallet.privatekey, recipient=wallet.recipient, db=wallet.db, browser=wallet.browser)

        self.from_chain = 'arbitrum'
        self.web3 = self.get_web3(chain_name=self.from_chain)

        self.zro_contract = self.web3.eth.contract(
            address="0xB09F16F625B363875e39ADa56C03682088471523",
            abi='[{"inputs":[{"internalType":"enumCurrency","name":"currency","type":"uint8"},{"internalType":"uint256","name":"amountToDonate","type":"uint256"},{"internalType":"uint256","name":"_zroAmount","type":"uint256"},{"internalType":"bytes32[]","name":"_proof","type":"bytes32[]"},{"internalType":"address","name":"_to","type":"address"},{"internalType":"bytes","name":"_extraBytes","type":"bytes"}],"name":"donateAndClaim","outputs":[{"components":[{"internalType":"bytes32","name":"guid","type":"bytes32"},{"internalType":"uint64","name":"nonce","type":"uint64"},{"components":[{"internalType":"uint256","name":"nativeFee","type":"uint256"},{"internalType":"uint256","name":"lzTokenFee","type":"uint256"}],"internalType":"structMessagingFee","name":"fee","type":"tuple"}],"internalType":"structMessagingReceipt","name":"receipt","type":"tuple"}],"stateMutability":"payable","type":"function"}]'
        )
        self.claimer_contract = self.web3.eth.contract(
            address="0xd6b6a6701303B5Ea36fa0eDf7389b562d8F894DB",
            abi='[{"inputs":[{"internalType":"address","name":"user","type":"address"}],"name":"zroClaimed","outputs":[{"internalType":"uint256","name":"amount","type":"uint256"}],"stateMutability":"view","type":"function"}]'
        )


    def is_claimed(self):
        return self.claimer_contract.functions.zroClaimed(self.address).call()


    def claim(self, eligibility_data: dict, claimed_amount: int, donate_value: int, retry=0):
        donate_amount = round(donate_value / 1e18, 5)

        real_claim_amount = round(eligibility_data["amount"]["full"] - claimed_amount / 1e18, 2)
        module_str = f'claim {real_claim_amount} $ZRO with {donate_amount} ETH'

        try:
            contract_txn = self.zro_contract.functions.donateAndClaim(
                2,
                donate_value,
                eligibility_data["value"]["full"],
                eligibility_data["proof"],
                self.address,
                "0x"
            )

            self.wait_for_gwei()

            self.sent_tx(chain_name=self.from_chain, tx=contract_txn, tx_label=module_str, value=donate_value)
            return "Claimed"

        except Exception as error:
            if retry < settings.RETRY:
                logger.error(f'[-] Web3 | {module_str} | {error} [{retry + 1}/{settings.RETRY}]')
                sleeping(10)
                return self.claim(eligibility_data=eligibility_data, claimed_amount=claimed_amount, donate_value=donate_value, retry=retry+1)
            else:
                if 'tx failed' not in str(error):
                    self.db.append_report(privatekey=self.privatekey, text=f'{module_str}: {error}', success=False)
                raise ValueError(f'{module_str}: {error}')
