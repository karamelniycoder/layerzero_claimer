from random import choice

from .relay import Relay
from .wallet import Wallet
from .utils import sleeping
from .orbiter import Orbiter
from settings import AVAILABLE_BRIDGES, SLEEP_AFTER_TX


def call_bridge(wallet: Wallet, from_chain: str, amount: float):
    bridge_type = choice(AVAILABLE_BRIDGES).lower()
    match bridge_type:
        case "orbiter":
            bridge = Orbiter(wallet=wallet, from_chain=from_chain, amount=amount)
        case "relay":
            bridge = Relay(wallet=wallet, from_chain=from_chain, amount=amount)

    sleeping(SLEEP_AFTER_TX)
    return bridge.to_chain
