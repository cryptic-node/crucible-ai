from __future__ import annotations

"""
Finance and Bitcoin/Lightning placeholder schemas.
TODO: Replace stubs with real RPC/gRPC implementations when live integration is needed.
No live signing or payment execution occurs here.
"""

from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NodeStatus(str, Enum):
    online = "online"
    offline = "offline"
    syncing = "syncing"
    unknown = "unknown"


class BitcoinNodeHealth(BaseModel):
    """TODO: Implement via Bitcoin RPC. Currently stub."""
    status: NodeStatus = NodeStatus.unknown
    block_height: Optional[int] = None
    connected_peers: Optional[int] = None
    network: str = "mainnet"
    rpc_url: str = ""
    note: str = "STUB: No live RPC connection. Read-only status schema."


class WalletBalanceInspection(BaseModel):
    """
    TODO: Implement via Bitcoin RPC `getbalance`.
    No private keys or signing in this module.
    """
    workspace: str
    confirmed_btc: Optional[Decimal] = None
    unconfirmed_btc: Optional[Decimal] = None
    wallet_label: str = ""
    note: str = "STUB: Balance inspection contract. No signing capability."


class LightningNodeStatus(BaseModel):
    """TODO: Implement via LND REST API. Currently stub."""
    status: NodeStatus = NodeStatus.unknown
    alias: str = ""
    pubkey: str = ""
    num_channels: Optional[int] = None
    total_capacity_sat: Optional[int] = None
    rest_url: str = ""
    note: str = "STUB: LND status schema. No live connection."


class LightningInvoice(BaseModel):
    """TODO: Parse via lnd/bolt11. Currently stub."""
    payment_request: str
    amount_msat: Optional[int] = None
    description: Optional[str] = None
    expiry_seconds: Optional[int] = None
    destination: Optional[str] = None
    is_expired: Optional[bool] = None
    note: str = "STUB: Invoice parsing contract. No payment capability."


class PaymentProposal(BaseModel):
    """
    Payment proposal object. Requires HIGH trust + explicit approval before any execution.
    TODO: Wire to LND `sendpayment` only after policy approval chain is complete.
    """
    workspace: str
    payment_request: str
    max_amount_sat: int = Field(..., ge=1)
    description: str = ""
    requires_approval: bool = True
    dry_run: bool = True
    note: str = (
        "STUB: Payment proposals are never executed without policy engine approval "
        "AND explicit user confirmation. dry_run=True by default."
    )

    def validate_not_live(self) -> None:
        if not self.dry_run:
            raise ValueError(
                "Live payment execution is disabled in this stub. "
                "Set dry_run=True or implement full approval chain."
            )
