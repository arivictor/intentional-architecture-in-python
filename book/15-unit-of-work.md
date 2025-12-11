# Chapter 15: Unit of Work Pattern

## Introduction

The **Unit of Work Pattern** maintains a list of objects affected by a business transaction and coordinates writing out changes. It tracks everything you change during a business transaction and handles all database updates as a single unit - ensuring either all changes succeed or all fail together.

This pattern is essential for maintaining data consistency across multiple repository operations. Instead of each repository immediately writing to the database, the Unit of Work batches all changes and commits them together in a single database transaction.

## The Problem

Managing transactions across multiple repositories leads to partial updates and inconsistent data.

**Symptoms:**
- Some changes saved, others lost when errors occur
- Inconsistent database state after failures
- Difficult to rollback related changes
- Transaction management scattered across code
- Multiple database round-trips for related changes
- No clear transaction boundaries

**Example of the problem:**

```python
class OrderService:
    """Service without Unit of Work - inconsistent transactions."""
    
    def __init__(self, order_repo, inventory_repo, customer_repo):
        self.orders = order_repo
        self.inventory = inventory_repo
        self.customers = customer_repo
    
    def place_order(self, customer_id: str, items: list):
        """
        Problem: Each repository saves immediately.
        If any step fails, previous changes are already committed!
        """
        # Step 1: Create order - SAVED TO DB
        order = Order(customer_id=customer_id, items=items)
        self.orders.save(order)  # Database write #1
        
        # Step 2: Reserve inventory - SAVED TO DB
        for item in items:
            try:
                self.inventory.reserve(item['product_id'], item['quantity'])
                self.inventory.save()  # Database write #2, #3, etc.
            except InsufficientStockError:
                # Problem: Order already saved but inventory failed!
                # Database is now inconsistent
                raise
        
        # Step 3: Update customer points - SAVED TO DB
        customer = self.customers.find_by_id(customer_id)
        customer.add_points(order.total * 0.1)
        self.customers.save(customer)  # Database write #N
        
        # If this step fails, order and inventory already committed!
        # No automatic rollback!
        
        return order


# Usage shows the problem
service = OrderService(order_repo, inventory_repo, customer_repo)

try:
    service.place_order("C123", [
        {'product_id': 'P1', 'quantity': 10},
        {'product_id': 'P2', 'quantity': 5}  # Out of stock!
    ])
except InsufficientStockError:
    # Order was created in database even though transaction failed!
    # Database is inconsistent - order exists but items not reserved
    pass
```

**Problems:**
- Order saved even when inventory reservation fails
- No way to rollback all changes together
- Partial updates leave database inconsistent
- Multiple database round-trips (inefficient)
- Transaction management scattered across service layer
- Hard to test transaction behavior

## The Pattern

**Unit of Work:** Track all changes to objects during a business transaction, then commit them all at once or rollback everything if anything fails.

### Key Concepts

**Unit of Work:** Tracks all changes in a transaction
- Registers new objects
- Tracks modified objects
- Tracks deleted objects
- Commits all or rolls back all

**Transaction Boundary:** Begin → Make Changes → Commit/Rollback

**Repository Integration:** Repositories register changes with Unit of Work instead of immediately writing to database

### Flow

```
1. Begin Unit of Work
2. Load entities through repositories
3. Modify entities (UoW tracks changes)
4. Commit UoW → All changes written atomically
   OR
   Rollback UoW → All changes discarded
```

## Implementation

```python
from abc import ABC, abstractmethod
from typing import Dict, Set, Optional, List
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


# =============================================================================
# DOMAIN ENTITIES
# =============================================================================

class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """Order entity."""
    id: Optional[str]
    customer_id: str
    items: List[dict]
    total: Decimal
    status: OrderStatus = OrderStatus.PENDING
    
    def confirm(self):
        """Business logic: confirm order."""
        if self.status != OrderStatus.PENDING:
            raise ValueError("Can only confirm pending orders")
        self.status = OrderStatus.CONFIRMED
    
    def cancel(self):
        """Business logic: cancel order."""
        if self.status == OrderStatus.CANCELLED:
            raise ValueError("Order already cancelled")
        self.status = OrderStatus.CANCELLED


@dataclass
class InventoryItem:
    """Inventory entity."""
    product_id: str
    quantity_available: int
    quantity_reserved: int = 0
    
    def reserve(self, quantity: int):
        """Reserve inventory."""
        if quantity > self.quantity_available:
            raise ValueError(f"Insufficient stock: need {quantity}, have {self.quantity_available}")
        self.quantity_available -= quantity
        self.quantity_reserved += quantity
    
    def release(self, quantity: int):
        """Release reserved inventory."""
        self.quantity_available += quantity
        self.quantity_reserved -= quantity


@dataclass
class Customer:
    """Customer entity."""
    id: str
    name: str
    loyalty_points: int = 0
    
    def add_points(self, points: int):
        """Add loyalty points."""
        self.loyalty_points += points


# =============================================================================
# UNIT OF WORK PATTERN
# =============================================================================

class UnitOfWork(ABC):
    """
    Abstract Unit of Work.
    
    Tracks all changes and commits them atomically.
    """
    
    def __init__(self):
        self._new_objects: Set[object] = set()
        self._dirty_objects: Set[object] = set()
        self._removed_objects: Set[object] = set()
    
    def register_new(self, obj: object) -> None:
        """Register a new object to be inserted."""
        self._new_objects.add(obj)
    
    def register_dirty(self, obj: object) -> None:
        """Register a modified object to be updated."""
        self._dirty_objects.add(obj)
    
    def register_removed(self, obj: object) -> None:
        """Register an object to be deleted."""
        self._removed_objects.add(obj)
    
    @abstractmethod
    def commit(self) -> None:
        """Commit all changes atomically."""
        pass
    
    @abstractmethod
    def rollback(self) -> None:
        """Rollback all changes."""
        pass
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - commit or rollback."""
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


class InMemoryUnitOfWork(UnitOfWork):
    """
    In-memory Unit of Work for testing.
    
    Simulates transaction behavior without a database.
    """
    
    def __init__(self):
        super().__init__()
        # Simulated storage
        self.orders: Dict[str, Order] = {}
        self.inventory: Dict[str, InventoryItem] = {}
        self.customers: Dict[str, Customer] = {}
        self._committed = False
    
    def commit(self) -> None:
        """Commit all changes to in-memory storage."""
        # Insert new objects
        for obj in self._new_objects:
            if isinstance(obj, Order):
                self.orders[obj.id] = obj
            elif isinstance(obj, InventoryItem):
                self.inventory[obj.product_id] = obj
            elif isinstance(obj, Customer):
                self.customers[obj.id] = obj
        
        # Updates handled automatically (objects already modified)
        # Deletes
        for obj in self._removed_objects:
            if isinstance(obj, Order) and obj.id in self.orders:
                del self.orders[obj.id]
            elif isinstance(obj, InventoryItem) and obj.product_id in self.inventory:
                del self.inventory[obj.product_id]
            elif isinstance(obj, Customer) and obj.id in self.customers:
                del self.customers[obj.id]
        
        self._committed = True
        self._clear_tracking()
    
    def rollback(self) -> None:
        """Discard all changes."""
        self._clear_tracking()
    
    def _clear_tracking(self):
        """Clear tracking sets."""
        self._new_objects.clear()
        self._dirty_objects.clear()
        self._removed_objects.clear()


import sqlite3


class SQLiteUnitOfWork(UnitOfWork):
    """
    SQLite Unit of Work.
    
    Uses database transactions for atomicity.
    """
    
    def __init__(self, db_path: str):
        super().__init__()
        self.db_path = db_path
        self.connection = None
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    total REAL,
                    status TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    product_id TEXT PRIMARY KEY,
                    quantity_available INTEGER,
                    quantity_reserved INTEGER
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    loyalty_points INTEGER
                )
            ''')
            conn.commit()
    
    def __enter__(self):
        """Start transaction."""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.execute('BEGIN')
        return self
    
    def commit(self) -> None:
        """Commit all changes to database."""
        if not self.connection:
            raise RuntimeError("No active transaction")
        
        try:
            # Insert new objects
            for obj in self._new_objects:
                if isinstance(obj, Order):
                    self.connection.execute(
                        'INSERT INTO orders (id, customer_id, total, status) VALUES (?, ?, ?, ?)',
                        (obj.id, obj.customer_id, float(obj.total), obj.status.value)
                    )
                elif isinstance(obj, InventoryItem):
                    self.connection.execute(
                        'INSERT INTO inventory (product_id, quantity_available, quantity_reserved) VALUES (?, ?, ?)',
                        (obj.product_id, obj.quantity_available, obj.quantity_reserved)
                    )
                elif isinstance(obj, Customer):
                    self.connection.execute(
                        'INSERT INTO customers (id, name, loyalty_points) VALUES (?, ?, ?)',
                        (obj.id, obj.name, obj.loyalty_points)
                    )
            
            # Update dirty objects
            for obj in self._dirty_objects:
                if isinstance(obj, Order):
                    self.connection.execute(
                        'UPDATE orders SET customer_id=?, total=?, status=? WHERE id=?',
                        (obj.customer_id, float(obj.total), obj.status.value, obj.id)
                    )
                elif isinstance(obj, InventoryItem):
                    self.connection.execute(
                        'UPDATE inventory SET quantity_available=?, quantity_reserved=? WHERE product_id=?',
                        (obj.quantity_available, obj.quantity_reserved, obj.product_id)
                    )
                elif isinstance(obj, Customer):
                    self.connection.execute(
                        'UPDATE customers SET name=?, loyalty_points=? WHERE id=?',
                        (obj.name, obj.loyalty_points, obj.id)
                    )
            
            # Delete removed objects
            for obj in self._removed_objects:
                if isinstance(obj, Order):
                    self.connection.execute('DELETE FROM orders WHERE id=?', (obj.id,))
                elif isinstance(obj, InventoryItem):
                    self.connection.execute('DELETE FROM inventory WHERE product_id=?', (obj.product_id,))
                elif isinstance(obj, Customer):
                    self.connection.execute('DELETE FROM customers WHERE id=?', (obj.id,))
            
            # Commit transaction
            self.connection.commit()
            self._clear_tracking()
            
        except Exception as e:
            self.rollback()
            raise
    
    def rollback(self) -> None:
        """Rollback transaction."""
        if self.connection:
            self.connection.rollback()
        self._clear_tracking()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up connection."""
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None


# =============================================================================
# REPOSITORIES WITH UNIT OF WORK
# =============================================================================

class OrderRepository:
    """Order repository that works with Unit of Work."""
    
    def __init__(self, unit_of_work: UnitOfWork):
        self.uow = unit_of_work
    
    def add(self, order: Order) -> None:
        """Add new order."""
        self.uow.register_new(order)
    
    def save(self, order: Order) -> None:
        """Save modified order."""
        self.uow.register_dirty(order)


class InventoryRepository:
    """Inventory repository."""
    
    def __init__(self, unit_of_work: UnitOfWork):
        self.uow = unit_of_work
    
    def save(self, item: InventoryItem) -> None:
        """Save inventory item."""
        self.uow.register_dirty(item)


class CustomerRepository:
    """Customer repository."""
    
    def __init__(self, unit_of_work: UnitOfWork):
        self.uow = unit_of_work
    
    def save(self, customer: Customer) -> None:
        """Save customer."""
        self.uow.register_dirty(customer)


# =============================================================================
# APPLICATION SERVICE
# =============================================================================

class OrderService:
    """
    Order service using Unit of Work.
    
    All changes committed atomically.
    """
    
    def place_order_atomic(
        self,
        order_id: str,
        customer_id: str,
        items: List[dict],
        total: Decimal,
        unit_of_work: UnitOfWork,
        inventory_items: Dict[str, InventoryItem],
        customer: Customer
    ) -> Order:
        """
        Place order with atomic transaction.
        
        Either all changes succeed or all fail.
        """
        # Create repositories within UoW
        order_repo = OrderRepository(unit_of_work)
        inventory_repo = InventoryRepository(unit_of_work)
        customer_repo = CustomerRepository(unit_of_work)
        
        # Create order
        order = Order(order_id, customer_id, items, total)
        order_repo.add(order)
        
        # Reserve inventory
        for item in items:
            inventory_item = inventory_items[item['product_id']]
            inventory_item.reserve(item['quantity'])
            inventory_repo.save(inventory_item)
        
        # Award loyalty points
        points = int(total * Decimal('0.1'))
        customer.add_points(points)
        customer_repo.save(customer)
        
        # Confirm order
        order.confirm()
        order_repo.save(order)
        
        # All changes tracked, will be committed together
        return order


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    print("=== Unit of Work - Atomic Transactions ===\n")
    
    # Setup test data
    inventory_items = {
        'P1': InventoryItem('P1', quantity_available=100),
        'P2': InventoryItem('P2', quantity_available=50)
    }
    customer = Customer('C123', 'John Doe', loyalty_points=0)
    
    # Successful transaction
    print("Scenario 1: Successful order\n")
    uow = InMemoryUnitOfWork()
    service = OrderService()
    
    with uow:  # Context manager handles commit/rollback
        order = service.place_order_atomic(
            'O001',
            'C123',
            [{'product_id': 'P1', 'quantity': 10}],
            Decimal('100.00'),
            uow,
            inventory_items,
            customer
        )
        print(f"Order created: {order.id}")
        print(f"Inventory reserved: P1 has {inventory_items['P1'].quantity_available} available")
        print(f"Customer points: {customer.loyalty_points}")
    
    print(f"\n✓ Transaction committed successfully")
    print(f"Order status: {order.status}")
    print()
    
    # Failed transaction - rollback
    print("Scenario 2: Failed order (insufficient inventory)\n")
    
    inventory_items_2 = {
        'P1': InventoryItem('P1', quantity_available=5),  # Only 5 available
        'P2': InventoryItem('P2', quantity_available=50)
    }
    customer_2 = Customer('C456', 'Jane Smith', loyalty_points=0)
    
    uow2 = InMemoryUnitOfWork()
    
    try:
        with uow2:
            order2 = service.place_order_atomic(
                'O002',
                'C456',
                [{'product_id': 'P1', 'quantity': 10}],  # Need 10, only have 5
                Decimal('100.00'),
                uow2,
                inventory_items_2,
                customer_2
            )
    except ValueError as e:
        print(f"✗ Transaction failed: {e}")
        print(f"Inventory unchanged: P1 has {inventory_items_2['P1'].quantity_available} available")
        print(f"Customer points unchanged: {customer_2.loyalty_points}")
        print("\n✓ All changes rolled back automatically")
```

## Explanation

### Transaction Boundary

The Unit of Work defines the transaction boundary:

```python
with uow:  # Begin transaction
    # Make changes
    order_repo.add(order)
    inventory_repo.save(item)
    customer_repo.save(customer)
    # End of context - commit if no exceptions, rollback if exception
```

### Change Tracking

The UoW tracks what changed:

```python
class UnitOfWork:
    def __init__(self):
        self._new_objects = set()     # To insert
        self._dirty_objects = set()   # To update
        self._removed_objects = set() # To delete
```

### Repositories Register Changes

Repositories don't write immediately - they register with UoW:

```python
class OrderRepository:
    def add(self, order):
        self.uow.register_new(order)  # Track, don't save yet
    
    def save(self, order):
        self.uow.register_dirty(order)  # Track update
```

### Atomic Commit

All changes written together:

```python
def commit(self):
    # Insert all new objects
    # Update all dirty objects
    # Delete all removed objects
    # Database transaction commits - all or nothing
```

## Benefits

**1. Data Consistency**

All changes succeed or all fail - no partial updates:

```python
with uow:
    # Create order
    # Reserve inventory
    # Update customer
    # If ANY step fails, EVERYTHING rolls back
```

**2. Performance**

One database round-trip instead of many:

```python
# Without UoW: 3 separate database calls
order_repo.save(order)      # DB call 1
inventory_repo.save(item)   # DB call 2
customer_repo.save(customer) # DB call 3

# With UoW: 1 database call at commit
```

**3. Clear Transaction Boundaries**

The `with` statement makes transaction scope explicit.

**4. Automatic Rollback**

Exceptions automatically trigger rollback.

**5. Testability**

Use in-memory UoW for testing without database.

## Trade-offs

**When NOT to use Unit of Work:**

**1. Simple Single-Object Operations**

For operations on one entity, UoW adds complexity:

```python
# Overkill for single save
with uow:
    customer_repo.save(customer)

# Just save directly
customer_repo.save(customer)
```

**2. Read-Only Operations**

No changes = no need for UoW:

```python
# Don't need UoW for queries
products = product_repo.find_all()
```

**3. Long-Running Processes**

UoW holds database connection/transaction. Don't use for long operations.

**4. Overhead**

UoW adds:
- Complexity in tracking changes
- Need to manage transaction scope
- Memory overhead for change tracking

## Testing

```python
import pytest


def test_successful_transaction_commits_all_changes():
    """Test that successful transaction commits all changes."""
    uow = InMemoryUnitOfWork()
    
    order = Order('O1', 'C1', [], Decimal('100'), OrderStatus.PENDING)
    
    with uow:
        uow.register_new(order)
    
    assert 'O1' in uow.orders
    assert uow.orders['O1'].id == 'O1'


def test_failed_transaction_rolls_back():
    """Test that exception triggers rollback."""
    uow = InMemoryUnitOfWork()
    
    order = Order('O1', 'C1', [], Decimal('100'))
    
    try:
        with uow:
            uow.register_new(order)
            raise ValueError("Simulated error")
    except ValueError:
        pass
    
    # Order not saved due to rollback
    assert 'O1' not in uow.orders


def test_atomic_order_placement():
    """Test complete order placement is atomic."""
    inventory = {'P1': InventoryItem('P1', 100)}
    customer = Customer('C1', 'Test', 0)
    
    uow = InMemoryUnitOfWork()
    service = OrderService()
    
    with uow:
        order = service.place_order_atomic(
            'O1', 'C1',
            [{'product_id': 'P1', 'quantity': 10}],
            Decimal('100'),
            uow, inventory, customer
        )
    
    # All changes committed
    assert 'O1' in uow.orders
    assert inventory['P1'].quantity_available == 90
    assert customer.loyalty_points == 10


def test_insufficient_inventory_rolls_back_all():
    """Test that inventory failure rolls back order and customer changes."""
    inventory = {'P1': InventoryItem('P1', 5)}  # Only 5 available
    customer = Customer('C1', 'Test', 0)
    
    uow = InMemoryUnitOfWork()
    service = OrderService()
    
    with pytest.raises(ValueError, match="Insufficient stock"):
        with uow:
            service.place_order_atomic(
                'O1', 'C1',
                [{'product_id': 'P1', 'quantity': 10}],  # Need 10
                Decimal('100'),
                uow, inventory, customer
            )
    
    # Nothing committed - all rolled back
    assert 'O1' not in uow.orders
    assert inventory['P1'].quantity_available == 5  # Unchanged
    assert customer.loyalty_points == 0  # Unchanged
```

## Common Mistakes

**1. Not Using Transaction Scope**

Always use context manager or explicit begin/commit:

```python
# Bad - no transaction scope
uow = UnitOfWork()
order_repo.add(order)  # When does this commit?

# Good - clear transaction scope
with uow:
    order_repo.add(order)  # Commits at end of block
```

**2. Long Transactions**

Keep transactions short:

```python
# Bad - long-running transaction
with uow:
    for i in range(10000):
        process_item(i)  # Holds transaction too long

# Good - batch smaller transactions
for batch in batches:
    with uow:
        for item in batch:
            process_item(item)
```

**3. Mixing Direct Saves with UoW**

Don't bypass the Unit of Work:

```python
# Bad - inconsistent
with uow:
    order_repo.add(order)  # Goes through UoW
    db.execute("INSERT...")  # Bypasses UoW - might commit before rollback!

# Good - everything through UoW
with uow:
    order_repo.add(order)
    inventory_repo.save(item)
```

## Related Patterns

- **Chapter 14 (Repository):** Repositories often used with Unit of Work
- **Chapter 10 (Aggregates):** UoW transaction boundaries often align with aggregates
- **Chapter 17 (CQRS):** Commands use UoW for write operations

## Summary

The Unit of Work Pattern tracks all changes during a business transaction and coordinates writing them out as a single atomic operation. It ensures data consistency by making sure all changes succeed together or all fail together.

Use Unit of Work when you need to coordinate changes across multiple repositories, when data consistency is critical, or when you want to batch database operations for performance. Skip it for simple single-entity operations or read-only queries.

## Further Reading

- Fowler, Martin. *Patterns of Enterprise Application Architecture*. Addison-Wesley, 2002. (Unit of Work pattern)
- Vernon, Vaughn. *Implementing Domain-Driven Design*. Addison-Wesley, 2013.
- Evans, Eric. *Domain-Driven Design*. Addison-Wesley, 2003.
- Microsoft. "Implement the infrastructure persistence layer with Entity Framework Core." docs.microsoft.com.
- Nilsson, Jimmy. *Applying Domain-Driven Design and Patterns*. Addison-Wesley, 2006.
