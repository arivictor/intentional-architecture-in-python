# Chapter 10: Aggregates & Boundaries

## Introduction

An **Aggregate** is a cluster of related entities and value objects treated as a single unit for data changes. The aggregate enforces consistency rules (invariants) and has a clearly defined boundary with one entity designated as the **Aggregate Root**.

All external access to the aggregate goes through the root. This ensures that business rules are never violated, even in complex multi-object scenarios. Instead of scattered validation across your codebase, the aggregate centralizes consistency enforcement.

## The Problem

Without clear boundaries, business rules get scattered and objects can be put into invalid states.

**Symptoms:**
- Business rules violated because objects modified independently
- Unclear what objects can be changed together
- Cascade of validations spread across codebase
- Race conditions in concurrent modifications
- Database transactions too large or too small
- Unclear what constitutes a "consistent" state

**Example of the problem:**

```python
class Cart:
    """Shopping cart without aggregate boundaries."""
    
    def __init__(self, cart_id):
        self.cart_id = cart_id
        self.items = []
    
    def add_item(self, item):
        """Add item - but no validation."""
        self.items.append(item)


class CartItem:
    """Cart item that can be modified independently."""
    
    def __init__(self, product_id, name, price, quantity):
        self.product_id = product_id
        self.name = name
        self.price = price
        self.quantity = quantity  # Can be changed anywhere
    
    def change_quantity(self, new_quantity):
        """No validation - can set negative quantities!"""
        self.quantity = new_quantity


# Usage shows the problems
cart = Cart("cart-123")
item = CartItem("prod-1", "Widget", 19.99, 2)
cart.add_item(item)

# Problem 1: Can modify item directly, bypassing cart validation
item.quantity = -5  # Invalid state! Negative quantity
item.price = -100  # Invalid state! Negative price

# Problem 2: Can add unlimited items without checking constraints
for i in range(1000):
    cart.add_item(CartItem(f"prod-{i}", "Item", 1.0, 999999))
# No max items check, no inventory check

# Problem 3: Inconsistent state - total items vs cart state
print(f"Items in cart: {len(cart.items)}")  # Says 1001
item_count = sum(item.quantity for item in cart.items)  # But negative quantities?

# Problem 4: External code has to know business rules
def apply_discount(cart):
    """External code enforcing business rules - scattered logic."""
    if len(cart.items) < 5:
        raise ValueError("Discount requires 5+ items")  # Rule outside cart
    
    for item in cart.items:
        if item.quantity <= 0:
            raise ValueError("Invalid quantity")  # Validation outside cart
        item.price *= 0.9  # Modifying internals directly


# Problem 5: Can't ensure consistency
class Order:
    def create_from_cart(self, cart):
        # How do we know cart is in valid state?
        # No way to enforce cart invariants before creating order
        for item in cart.items:
            if item.quantity <= 0:  # Duplicate validation everywhere
                raise ValueError("Invalid cart state")
        # ... create order
```

**Problems:**
- Cart items can be modified to invalid states (negative quantities, prices)
- Business rules scattered across multiple functions
- No enforcement of invariants (e.g., max items, min order value)
- Anyone can reach into cart and modify items
- Can't guarantee cart is in valid state
- No clear transaction boundary

## The Pattern

**Aggregate:** A cluster of domain objects (entities and value objects) that should be treated as a single unit.

**Aggregate Root:** The single entity through which all external access to the aggregate must go.

**Key Principles:**

1. **Single Root:** One entity is the aggregate root. All external references go through it.
2. **Internal Consistency:** The root enforces all invariants within the aggregate boundary.
3. **Boundary:** Objects outside the aggregate can only hold references to the root.
4. **Transaction Boundary:** Each aggregate is loaded and saved as a unit.
5. **Small Aggregates:** Keep aggregates as small as possible for performance and concurrency.

### Aggregate Structure

```
ShoppingCart (Aggregate Root)
├── CartItem (Entity within aggregate)
├── CartItem (Entity within aggregate)
└── CartItem (Entity within aggregate)

External code can only:
- Get ShoppingCart by ID
- Call methods on ShoppingCart
- ShoppingCart modifies CartItems internally
```

## Implementation

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from datetime import datetime


@dataclass(frozen=True)
class Money:
    """Value object for monetary amounts."""
    amount: Decimal
    currency: str
    
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
    
    def add(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)
    
    def multiply(self, factor: Decimal) -> 'Money':
        return Money(self.amount * factor, self.currency)
    
    def __str__(self):
        return f"{self.currency} {self.amount:.2f}"


class CartItem:
    """
    Entity within the ShoppingCart aggregate.
    
    Cannot be accessed directly from outside the aggregate.
    Not a root - no independent existence.
    """
    
    def __init__(self, product_id: str, name: str, price: Money, quantity: int):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if not product_id:
            raise ValueError("Product ID required")
        if not name.strip():
            raise ValueError("Product name required")
        
        self.product_id = product_id
        self.name = name
        self.price = price
        self._quantity = quantity
    
    @property
    def quantity(self) -> int:
        """Quantity is read-only from outside - only cart can modify."""
        return self._quantity
    
    def _set_quantity(self, new_quantity: int) -> None:
        """Private method - only aggregate root should call this."""
        if new_quantity <= 0:
            raise ValueError("Quantity must be positive")
        self._quantity = new_quantity
    
    def line_total(self) -> Money:
        """Calculate total for this line item."""
        return self.price.multiply(Decimal(self._quantity))
    
    def __eq__(self, other):
        if not isinstance(other, CartItem):
            return False
        return self.product_id == other.product_id
    
    def __repr__(self):
        return f"CartItem({self.product_id}, qty={self._quantity})"


class ShoppingCart:
    """
    Aggregate root for shopping cart.
    
    Enforces all business rules and invariants:
    - No negative quantities
    - No duplicate products
    - Maximum 20 items per cart
    - Minimum order value $10
    
    All modifications go through this root.
    """
    
    MAX_ITEMS = 20
    MIN_ORDER_VALUE = Money(Decimal("10.00"), "USD")
    
    def __init__(self, cart_id: str):
        if not cart_id:
            raise ValueError("Cart ID required")
        
        self._cart_id = cart_id
        self._items: List[CartItem] = []
        self._created_at = datetime.now()
    
    @property
    def cart_id(self) -> str:
        """Cart identity."""
        return self._cart_id
    
    @property
    def items(self) -> List[CartItem]:
        """
        Return copy of items to prevent external modification.
        
        Clients can read items but cannot modify them directly.
        """
        return list(self._items)
    
    @property
    def item_count(self) -> int:
        """Total number of items in cart."""
        return sum(item.quantity for item in self._items)
    
    def add_item(self, product_id: str, name: str, price: Money, quantity: int = 1) -> None:
        """
        Add item to cart, enforcing business rules.
        
        Args:
            product_id: Product identifier
            name: Product name
            price: Product price
            quantity: Quantity to add
            
        Raises:
            ValueError: If business rules violated
        """
        # Invariant: cannot exceed max items
        if self.item_count + quantity > self.MAX_ITEMS:
            raise ValueError(
                f"Cannot add {quantity} items. "
                f"Cart limit is {self.MAX_ITEMS} items, "
                f"current count is {self.item_count}"
            )
        
        # Check if product already in cart
        existing_item = self._find_item(product_id)
        
        if existing_item:
            # Update quantity of existing item
            new_quantity = existing_item.quantity + quantity
            if self.item_count - existing_item.quantity + new_quantity > self.MAX_ITEMS:
                raise ValueError(f"Cannot exceed {self.MAX_ITEMS} items")
            existing_item._set_quantity(new_quantity)
        else:
            # Add new item
            new_item = CartItem(product_id, name, price, quantity)
            self._items.append(new_item)
    
    def remove_item(self, product_id: str) -> None:
        """
        Remove item from cart.
        
        Args:
            product_id: Product to remove
            
        Raises:
            ValueError: If product not in cart
        """
        item = self._find_item(product_id)
        if not item:
            raise ValueError(f"Product {product_id} not in cart")
        
        self._items.remove(item)
    
    def update_quantity(self, product_id: str, new_quantity: int) -> None:
        """
        Update quantity for a product in cart.
        
        Args:
            product_id: Product to update
            new_quantity: New quantity
            
        Raises:
            ValueError: If product not in cart or new quantity invalid
        """
        if new_quantity <= 0:
            raise ValueError("Quantity must be positive. Use remove_item() to remove.")
        
        item = self._find_item(product_id)
        if not item:
            raise ValueError(f"Product {product_id} not in cart")
        
        # Check if update would exceed limit
        new_total = self.item_count - item.quantity + new_quantity
        if new_total > self.MAX_ITEMS:
            raise ValueError(
                f"Cannot set quantity to {new_quantity}. "
                f"Would exceed {self.MAX_ITEMS} item limit"
            )
        
        item._set_quantity(new_quantity)
    
    def clear(self) -> None:
        """Remove all items from cart."""
        self._items.clear()
    
    def total(self) -> Money:
        """
        Calculate total value of cart.
        
        Returns:
            Total money amount
        """
        if not self._items:
            return Money(Decimal("0.00"), "USD")
        
        total = self._items[0].line_total()
        for item in self._items[1:]:
            total = total.add(item.line_total())
        
        return total
    
    def can_checkout(self) -> bool:
        """
        Check if cart meets minimum requirements for checkout.
        
        Returns:
            True if cart can be checked out
        """
        if not self._items:
            return False
        
        total = self.total()
        return total.amount >= self.MIN_ORDER_VALUE.amount
    
    def _find_item(self, product_id: str) -> Optional[CartItem]:
        """Find item by product ID."""
        for item in self._items:
            if item.product_id == product_id:
                return item
        return None
    
    def __eq__(self, other):
        """Identity-based equality."""
        if not isinstance(other, ShoppingCart):
            return False
        return self.cart_id == other.cart_id
    
    def __repr__(self):
        return f"ShoppingCart(id={self.cart_id}, items={len(self._items)}, total={self.total()})"


# Usage example
if __name__ == "__main__":
    # Create aggregate root
    cart = ShoppingCart("cart-123")
    
    # Add items through root (enforces invariants)
    price1 = Money(Decimal("19.99"), "USD")
    price2 = Money(Decimal("29.99"), "USD")
    
    cart.add_item("prod-1", "Widget", price1, 2)
    cart.add_item("prod-2", "Gadget", price2, 1)
    
    print(f"Cart: {cart}")
    print(f"Items: {cart.item_count}")
    print(f"Total: {cart.total()}")
    print(f"Can checkout? {cart.can_checkout()}")
    print()
    
    # Cannot modify items directly - they're protected
    items = cart.items  # Gets copy, not reference
    # items[0].quantity = -1  # AttributeError - quantity is read-only property
    
    # Must go through root to modify
    cart.update_quantity("prod-1", 3)
    print(f"After quantity update: {cart}")
    print()
    
    # Business rules enforced by root
    try:
        # Try to exceed item limit
        for i in range(25):
            cart.add_item(f"prod-{i}", f"Item {i}", price1, 1)
    except ValueError as e:
        print(f"Business rule enforced: {e}")
    print()
    
    # Try to checkout with insufficient total
    small_cart = ShoppingCart("cart-456")
    small_cart.add_item("prod-cheap", "Cheap Item", Money(Decimal("5.00"), "USD"), 1)
    print(f"Small cart total: {small_cart.total()}")
    print(f"Can checkout? {small_cart.can_checkout()}")  # False - below minimum
```

## Explanation

### Aggregate Root Controls Access

The `ShoppingCart` is the aggregate root. All operations go through it:

```python
# Good - through root
cart.add_item("prod-1", "Widget", price, 2)
cart.update_quantity("prod-1", 3)

# Not possible - items are protected
# cart.items[0]._set_quantity(3)  # Can't access internal method
```

### Invariants Enforced in One Place

All business rules are in the aggregate root:

```python
def add_item(self, ...):
    # Invariant 1: max items
    if self.item_count + quantity > self.MAX_ITEMS:
        raise ValueError(...)
    
    # Invariant 2: no duplicate handling
    existing_item = self._find_item(product_id)
    if existing_item:
        # Update existing
    else:
        # Add new
```

### Encapsulation

Cart items cannot be modified directly from outside:

```python
@property
def items(self) -> List[CartItem]:
    """Return copy to prevent external modification."""
    return list(self._items)

@property
def quantity(self) -> int:
    """Read-only from outside."""
    return self._quantity

def _set_quantity(self, new_quantity: int):
    """Private - only root can call."""
    self._quantity = new_quantity
```

### Transaction Boundary

The aggregate defines the consistency boundary. In a repository pattern, you would load and save the entire cart as one unit:

```python
# Load aggregate
cart = cart_repository.get(cart_id)

# Modify through root
cart.add_item(...)
cart.update_quantity(...)

# Save entire aggregate
cart_repository.save(cart)  # Saves cart and all items atomically
```

## Benefits

**1. Consistency Guaranteed**

The aggregate root enforces all invariants. It's impossible to put the aggregate in an invalid state:

```python
cart.add_item(...)  # Validates before adding
cart.update_quantity(...)  # Validates before updating
```

**2. Clear Boundaries**

You know exactly what objects form a consistency unit. The aggregate boundary makes it explicit.

**3. Simplified Transactions**

The aggregate is the transaction boundary. Load it, modify it through the root, save it. No need to worry about complex cross-object transactions.

**4. Reduced Coupling**

External code only depends on the aggregate root interface, not internal structure.

**5. Better Concurrency**

Smaller aggregates mean finer-grained locking. Two users can modify different aggregates concurrently.

## Trade-offs

**When NOT to use aggregates:**

**1. Simple CRUD Applications**

For basic data entry with few business rules, aggregates add complexity:

```python
# Overkill for simple data entry
class Contact:  # Just a data holder
    def __init__(self, name, email):
        self.name = name
        self.email = email
# No complex invariants, no aggregate needed
```

**2. Large Object Graphs**

Don't make aggregates too large. Loading a huge graph is expensive:

```python
# Bad - aggregate too large
class Customer:  # Aggregate root
    orders: List[Order]  # Contains all orders
    invoices: List[Invoice]  # All invoices
    payments: List[Payment]  # All payments
# Loading customer loads everything - too expensive
```

**3. Reporting/Read Models**

Aggregates are for consistency and commands. For reports, use simpler read models:

```python
# Don't use aggregate for reporting
# Use DTO or query object instead
sales_report = database.query(
    "SELECT product, SUM(quantity) FROM orders GROUP BY product"
)
```

**4. Overhead**

Aggregates add:
- More classes and complexity
- Need to think about boundaries
- Careful design of invariants
- Repository layer for persistence

## Testing

```python
import pytest
from decimal import Decimal


def test_create_cart():
    """Test creating a new cart."""
    cart = ShoppingCart("cart-123")
    
    assert cart.cart_id == "cart-123"
    assert len(cart.items) == 0
    assert cart.item_count == 0


def test_add_item_to_cart():
    """Test adding items to cart."""
    cart = ShoppingCart("cart-123")
    price = Money(Decimal("19.99"), "USD")
    
    cart.add_item("prod-1", "Widget", price, 2)
    
    assert len(cart.items) == 1
    assert cart.item_count == 2
    assert cart.items[0].product_id == "prod-1"


def test_add_duplicate_product_updates_quantity():
    """Test that adding duplicate product updates existing item quantity."""
    cart = ShoppingCart("cart-123")
    price = Money(Decimal("19.99"), "USD")
    
    cart.add_item("prod-1", "Widget", price, 2)
    cart.add_item("prod-1", "Widget", price, 3)
    
    assert len(cart.items) == 1  # Still one item
    assert cart.items[0].quantity == 5  # Quantity increased


def test_exceeding_max_items_raises_error():
    """Test that exceeding max items raises error."""
    cart = ShoppingCart("cart-123")
    price = Money(Decimal("1.00"), "USD")
    
    with pytest.raises(ValueError, match="Cannot exceed 20 items"):
        cart.add_item("prod-1", "Item", price, 25)


def test_update_quantity():
    """Test updating item quantity."""
    cart = ShoppingCart("cart-123")
    price = Money(Decimal("19.99"), "USD")
    cart.add_item("prod-1", "Widget", price, 2)
    
    cart.update_quantity("prod-1", 5)
    
    assert cart.items[0].quantity == 5


def test_update_quantity_exceeding_limit_raises_error():
    """Test that updating quantity to exceed limit raises error."""
    cart = ShoppingCart("cart-123")
    price = Money(Decimal("1.00"), "USD")
    cart.add_item("prod-1", "Widget", price, 5)
    
    with pytest.raises(ValueError, match="Would exceed 20 item limit"):
        cart.update_quantity("prod-1", 25)


def test_remove_item():
    """Test removing item from cart."""
    cart = ShoppingCart("cart-123")
    price = Money(Decimal("19.99"), "USD")
    cart.add_item("prod-1", "Widget", price, 2)
    cart.add_item("prod-2", "Gadget", price, 1)
    
    cart.remove_item("prod-1")
    
    assert len(cart.items) == 1
    assert cart.items[0].product_id == "prod-2"


def test_remove_nonexistent_item_raises_error():
    """Test that removing nonexistent item raises error."""
    cart = ShoppingCart("cart-123")
    
    with pytest.raises(ValueError, match="not in cart"):
        cart.remove_item("prod-999")


def test_calculate_total():
    """Test calculating cart total."""
    cart = ShoppingCart("cart-123")
    cart.add_item("prod-1", "Widget", Money(Decimal("19.99"), "USD"), 2)
    cart.add_item("prod-2", "Gadget", Money(Decimal("29.99"), "USD"), 1)
    
    total = cart.total()
    
    assert total.amount == Decimal("69.97")  # 19.99*2 + 29.99


def test_can_checkout_with_sufficient_total():
    """Test that cart with sufficient total can checkout."""
    cart = ShoppingCart("cart-123")
    cart.add_item("prod-1", "Widget", Money(Decimal("19.99"), "USD"), 1)
    
    assert cart.can_checkout() is True


def test_cannot_checkout_below_minimum():
    """Test that cart below minimum cannot checkout."""
    cart = ShoppingCart("cart-123")
    cart.add_item("prod-1", "Cheap", Money(Decimal("5.00"), "USD"), 1)
    
    assert cart.can_checkout() is False


def test_cannot_modify_items_directly():
    """Test that cart items cannot be modified externally."""
    cart = ShoppingCart("cart-123")
    cart.add_item("prod-1", "Widget", Money(Decimal("19.99"), "USD"), 2)
    
    # Get items returns a copy
    items = cart.items
    items.append(CartItem("prod-2", "Hack", Money(Decimal("1.00"), "USD"), 1))
    
    # Original cart unchanged
    assert len(cart.items) == 1


def test_cart_equality_based_on_id():
    """Test that cart equality is based on cart ID."""
    cart1 = ShoppingCart("cart-123")
    cart2 = ShoppingCart("cart-123")
    cart3 = ShoppingCart("cart-456")
    
    assert cart1 == cart2  # Same ID
    assert cart1 != cart3  # Different ID
```

## Common Mistakes

**1. Aggregate Too Large**

Don't include everything related to an entity:

```python
# Bad - aggregate too large
class Customer:  # Root
    def __init__(self):
        self.orders = []  # All historical orders
        self.payments = []  # All payments
        self.support_tickets = []  # All tickets
# Loading customer loads entire history - expensive!

# Good - separate aggregates
class Customer:  # One aggregate
    pass

class Order:  # Another aggregate
    customer_id: str  # Reference by ID, not object
```

**2. Aggregate Too Small**

Don't split things that need to maintain consistency:

```python
# Bad - split what should be together
class Order:  # Root
    order_id: str

class OrderItem:  # Also a root - wrong!
    order_item_id: str
    order_id: str  # Reference to order

# Problem: Can create OrderItem without valid Order
# Cannot enforce Order invariants

# Good - OrderItem inside Order aggregate
class Order:  # Root
    def __init__(self):
        self._items: List[OrderItem] = []
    
    def add_item(self, ...):
        # Enforce invariants here
```

**3. Modifying Objects Outside Root**

Don't bypass the aggregate root:

```python
# Bad - modifying internals directly
cart = get_cart(cart_id)
cart._items[0]._quantity = 5  # Bypasses validation!

# Good - through root
cart.update_quantity("prod-1", 5)  # Enforces rules
```

**4. References Between Aggregates**

Don't hold object references between aggregates, use IDs:

```python
# Bad - object reference across aggregates
class Order:
    def __init__(self, customer: Customer):  # Object reference
        self.customer = customer

# Good - ID reference
class Order:
    def __init__(self, customer_id: str):  # ID reference
        self.customer_id = customer_id
```

## Related Patterns

- **Chapter 9 (Entities vs Value Objects):** Aggregates contain entities and value objects
- **Chapter 11 (Domain Events):** Aggregates publish events when state changes
- **Chapter 14 (Repository):** Repositories load/save entire aggregates
- **Chapter 15 (Unit of Work):** Manages transactions across aggregate boundaries
- **Chapter 17 (CQRS):** Commands target single aggregates

## Summary

Aggregates are clusters of related objects with a single root entity that enforces all consistency rules. The root is the only entry point for modifications, ensuring invariants are never violated. Aggregates define both consistency boundaries and transaction boundaries.

Use aggregates when you have complex business rules involving multiple objects that must remain consistent. Keep aggregates as small as possible, referencing other aggregates by ID rather than object references. The aggregate pattern is fundamental to maintaining consistency in domain-driven design.

## Further Reading

- Evans, Eric. *Domain-Driven Design*. Addison-Wesley, 2003. (Chapter 6: The Life Cycle of a Domain Object)
- Vernon, Vaughn. *Implementing Domain-Driven Design*. Addison-Wesley, 2013. (Chapter 10: Aggregates)
- Vernon, Vaughn. "Effective Aggregate Design" (three-part series). dddcommunity.org.
- Fowler, Martin. "DDD Aggregate." martinfowler.com.
- Nilsson, Jimmy. *Applying Domain-Driven Design and Patterns*. Addison-Wesley, 2006.
