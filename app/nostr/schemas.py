from __future__ import annotations

"""
Nostr placeholder schemas and interface stubs.
TODO: Implement NIP-46 style remote signing when live relay integration is needed.
No live signing or relay connections occur here.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NostrIdentity(BaseModel):
    """
    Nostr identity abstraction.
    TODO: Derive pubkey from nsec via NIP-06. Private keys never stored in memory tables.
    """
    pubkey_hex: str = Field(..., description="Public key (hex)")
    npub: Optional[str] = None
    display_name: Optional[str] = None
    workspace: str = "personal"
    note: str = "STUB: Identity abstraction. Private key must not be passed through this schema."


class RelayAllowlist(BaseModel):
    """Approved Nostr relay URLs."""
    relays: List[str] = Field(default_factory=list)
    workspace: str = "personal"

    def is_allowed(self, url: str) -> bool:
        return url in self.relays


class NostrSigningBoundary(BaseModel):
    """
    NIP-46 style signing contract.
    TODO: Route signing requests to remote signer (nsecbunker or hardware device).
    No private key material passes through this boundary.
    """
    event_kind: int
    content: str
    tags: List[List[str]] = Field(default_factory=list)
    pubkey: str
    requires_approval: bool = True
    dry_run: bool = True
    note: str = (
        "STUB: Signing boundary contract. "
        "No event is signed without policy approval + user confirmation. "
        "Private keys handled by remote signer only."
    )

    def validate_not_live(self) -> None:
        if not self.dry_run:
            raise ValueError(
                "Live signing is disabled in this stub. "
                "Implement NIP-46 remote signer and approval chain first."
            )


class NostrReadOperation(BaseModel):
    """Contract for reading events from approved relays."""
    relay_url: str
    filter: Dict[str, Any] = Field(default_factory=dict)
    workspace: str = "personal"
    note: str = "STUB: Read-only relay operation contract."


class NostrPostOperation(BaseModel):
    """
    Contract for publishing events.
    TODO: Requires signing boundary approval before posting.
    """
    relay_url: str
    signed_event: Dict[str, Any]
    workspace: str = "personal"
    requires_approval: bool = True
    dry_run: bool = True
    note: str = "STUB: Post operation requires relay allowlist check + signing approval."


class ApprovedDMCommand(BaseModel):
    """
    Schema for approved DM-based command execution.
    Only commands from this allowlist may be triggered via Nostr DMs.
    TODO: Verify DM sender pubkey against approved senders list.
    """
    command: str
    allowed_commands: List[str] = Field(
        default_factory=lambda: ["status", "help", "ping"],
        description="Allowlist of commands that may be triggered via DM",
    )
    sender_pubkey: str
    approved_senders: List[str] = Field(default_factory=list)

    def is_allowed(self) -> bool:
        return (
            self.command in self.allowed_commands
            and self.sender_pubkey in self.approved_senders
        )
