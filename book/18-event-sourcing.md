# Chapter 18: Event Sourcing

## Introduction

**Event Sourcing** stores the state of an application as a sequence of events rather than just the current state. Every state change is captured as an immutable event, providing a complete audit trail and enabling powerful capabilities like time travel and event replay.

Instead of storing "Account balance: $100", event sourcing stores "Account opened with $0", "Deposited $50", "Deposited $75", "Withdrew $25". The current state is derived by replaying all events.

## The Problem

Traditional state storage loses history and makes auditing difficult.

**Symptoms:**
- No audit trail of changes
- Can't answer "how did we get here?"
- Lost data when updates overwrite
- Difficult to debug state issues
- Can't replay or reconstruct past states
- Compliance and audit requirements hard to meet

**Example of the problem:**

```python
class BankAccount:
    """Traditional state storage - loses history."""
    
    def __init__(self, account_id, balance=0):
        self.account_id = account_id
        self.balance = balance  # Only current state
    
    def deposit(self, amount):
        self.balance += amount  # Overwrites state, loses history
    
    def withdraw(self, amount):
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount  # Overwrites state
```

**Problems:**
- Can't see deposit/withdrawal history
- Can't answer "when was this deposit made?"
- Can't audit who made changes
- Can't reconstruct account state at specific time
- Lost data if update fails partway through

## The Pattern

**Event Sourcing:** Store all changes as a sequence of immutable events. Current state is derived by replaying events.

### Key Concepts

**Event:** Immutable record of something that happened
**Event Store:** Append-only storage for events
**Event Stream:** Sequence of events for an entity
**Projection:** Current state derived from events
**Snapshot:** Cached state for performance

## Implementation

```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from abc import ABC


@dataclass(frozen=True)
class Event(ABC):
    """Base event class."""
    aggregate_id: str
    timestamp: datetime
    version: int


@dataclass(frozen=True)
class AccountOpenedEvent(Event):
    """Account was opened."""
    initial_balance: Decimal


@dataclass(frozen=True)
class MoneyDepositedEvent(Event):
    """Money was deposited."""
    amount: Decimal


@dataclass(frozen=True)
class MoneyWithdrawnEvent(Event):
    """Money was withdrawn."""
    amount: Decimal


class BankAccount:
    """
    Event-sourced bank account.
    
    State is derived from events, not stored directly.
    """
    
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.balance = Decimal('0')
        self.version = 0
        self._changes: List[Event] = []
    
    # Event Handlers (apply events to state)
    
    def _apply_account_opened(self, event: AccountOpenedEvent):
        self.balance = event.initial_balance
        self.version = event.version
    
    def _apply_money_deposited(self, event: MoneyDepositedEvent):
        self.balance += event.amount
        self.version = event.version
    
    def _apply_money_withdrawn(self, event: MoneyWithdrawnEvent):
        self.balance -= event.amount
        self.version = event.version
    
    def apply_event(self, event: Event):
        """Apply event to update state."""
        if isinstance(event, AccountOpenedEvent):
            self._apply_account_opened(event)
        elif isinstance(event, MoneyDepositedEvent):
            self._apply_money_deposited(event)
        elif isinstance(event, MoneyWithdrawnEvent):
            self._apply_money_withdrawn(event)
    
    # Commands (create new events)
    
    def open_account(self, initial_balance: Decimal):
        """Open account with initial balance."""
        if self.version > 0:
            raise ValueError("Account already opened")
        
        event = AccountOpenedEvent(
            aggregate_id=self.account_id,
            timestamp=datetime.now(),
            version=1,
            initial_balance=initial_balance
        )
        
        self.apply_event(event)
        self._changes.append(event)
    
    def deposit(self, amount: Decimal):
        """Deposit money."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        
        event = MoneyDepositedEvent(
            aggregate_id=self.account_id,
            timestamp=datetime.now(),
            version=self.version + 1,
            amount=amount
        )
        
        self.apply_event(event)
        self._changes.append(event)
    
    def withdraw(self, amount: Decimal):
        """Withdraw money."""
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValueError(f"Insufficient funds: have {self.balance}, need {amount}")
        
        event = MoneyWithdrawnEvent(
            aggregate_id=self.account_id,
            timestamp=datetime.now(),
            version=self.version + 1,
            amount=amount
        )
        
        self.apply_event(event)
        self._changes.append(event)
    
    def get_uncommitted_changes(self) -> List[Event]:
        """Get events that haven't been saved yet."""
        return list(self._changes)
    
    def mark_changes_as_committed(self):
        """Mark all changes as saved."""
        self._changes.clear()


class EventStore:
    """
    Event store - append-only storage.
    
    Stores all events for all aggregates.
    """
    
    def __init__(self):
        self._events: dict[str, List[Event]] = {}
    
    def save_events(self, aggregate_id: str, events: List[Event], expected_version: int):
        """Save events for an aggregate."""
        if aggregate_id not in self._events:
            self._events[aggregate_id] = []
        
        # Optimistic concurrency check
        current_version = len(self._events[aggregate_id])
        if current_version != expected_version:
            raise ValueError(f"Concurrency conflict: expected version {expected_version}, got {current_version}")
        
        self._events[aggregate_id].extend(events)
    
    def get_events(self, aggregate_id: str) -> List[Event]:
        """Get all events for an aggregate."""
        return self._events.get(aggregate_id, [])


class EventSourcedRepository:
    """Repository for event-sourced aggregates."""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
    
    def save(self, account: BankAccount):
        """Save account by storing its events."""
        events = account.get_uncommitted_changes()
        if events:
            expected_version = account.version - len(events)
            self.event_store.save_events(account.account_id, events, expected_version)
            account.mark_changes_as_committed()
    
    def get_by_id(self, account_id: str) -> Optional[BankAccount]:
        """Rebuild account from events."""
        events = self.event_store.get_events(account_id)
        if not events:
            return None
        
        account = BankAccount(account_id)
        for event in events:
            account.apply_event(event)
        
        return account


# Usage Example
if __name__ == "__main__":
    print("=== Event Sourcing Demo ===\n")
    
    event_store = EventStore()
    repository = EventSourcedRepository(event_store)
    
    # Create and use account
    account = BankAccount("ACC-001")
    account.open_account(Decimal("100"))
    account.deposit(Decimal("50"))
    account.withdraw(Decimal("25"))
    
    print(f"Account balance: ${account.balance}")
    print(f"Version: {account.version}\n")
    
    # Save (stores events, not state)
    repository.save(account)
    
    # Reload from events
    print("Reloading account from event store...")
    loaded_account = repository.get_by_id("ACC-001")
    
    print(f"Loaded balance: ${loaded_account.balance}")
    print(f"Loaded version: {loaded_account.version}\n")
    
    # Show event history
    print("Event history:")
    events = event_store.get_events("ACC-001")
    for event in events:
        print(f"  {event.timestamp}: {event.__class__.__name__} - v{event.version}")
    
    # Time travel - rebuild at specific version
    print("\nState at version 2:")
    account_v2 = BankAccount("ACC-001")
    for event in events[:2]:
        account_v2.apply_event(event)
    print(f"Balance at v2: ${account_v2.balance}")
