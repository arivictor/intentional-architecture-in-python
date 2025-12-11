# Chapter 3: Domain Modeling Basics

## Introduction

Business logic is the heart of your application. It's what makes your system valuable. Yet in most codebases, business logic is scattered across functions, buried in database queries, or tangled with framework code.

Domain modeling is the practice of representing business concepts as code. Instead of thinking in terms of databases, APIs, and frameworks, you think in terms of orders, customers, products, and the rules that govern them.

This chapter teaches you to model domains with rich, behavior-focused classes instead of anemic data containers.

## The Problem

Where does business logic go? How do you represent real-world concepts in code?

**Without domain modeling:**
- Business rules scattered across functions
- Data and behavior separated
- Logic duplicated in multiple places
- Hard to understand what the system actually does
- Domain concepts hidden behind technical details

**Example of the problem:**

```python
# Anemic approach: data only, logic elsewhere
order = {
    'id': '12345',
    'items': [
        {'product_id': 'P001', 'quantity': 2, 'price': 29.99},
        {'product_id': 'P002', 'quantity': 1, 'price': 49.99}
    ],
    'status': 'pending',
    'customer_id': 'C123'
}

# Business logic lives in scattered functions
def calculate_order_total(order):
    return sum(item['price'] * item['quantity'] for item in order['items'])

def apply_discount(order, discount_percent):
    total = calculate_order_total(order)
    return total * (1 - discount_percent)

def can_cancel_order(order):
    return order['status'] in ['pending', 'confirmed']
```

**Problems:**
- Business rules are outside the data they govern
- Easy to bypass validation
- No guarantee of consistency
- Discoverability is poor (how do you find all order-related logic?)

## The Pattern

**Domain modeling** means creating classes that represent business concepts with both data and behavior. These classes:

- Encapsulate business rules
- Validate their own consistency
- Express domain language directly
- Make invalid states unrepresentable

The progression: **Anemic Models → Rich Domain Models**

### Stage 1: Anemic Model (Avoid This)

Data without behavior:

```python
class Order:
    def __init__(self):
        self.id = None
        self.items = []
        self.total = 0
        self.status = 'pending'

# Logic lives elsewhere
def process_order(order):
    order.total = sum(item.price * item.quantity for item in order.items)
    order.status = 'processing'
```

### Stage 2: Rich Domain Model (Aim For This)

Data with behavior:

```python
class Order:
    def __init__(self, order_id, customer_id):
        self.id = order_id
        self.customer_id = customer_id
        self._items = []
        self._status = OrderStatus.PENDING
    
    def add_item(self, product, quantity, price):
        """Business logic lives with the data."""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        item = OrderItem(product, quantity, price)
        self._items.append(item)
    
    def total(self):
        """Calculate total from items."""
        return sum(item.subtotal() for item in self._items)
    
    def place(self):
        """Place the order (business rule: must have items)."""
        if not self._items:
            raise ValueError("Cannot place empty order")
        
        self._status = OrderStatus.PLACED
```

## Implementation

Let's build a complete e-commerce order system with rich domain models.

### Example: E-Commerce Order System

```python
# domain.py
from enum import Enum
from typing import List
from decimal import Decimal


class OrderStatus(Enum):
    """Order lifecycle states."""
    DRAFT = "draft"
    PLACED = "placed"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Product:
    """
    Represents a product in the catalog.
    
    Products have a unique SKU, name, and price.
    """
    
    def __init__(self, sku: str, name: str, price: Decimal):
        if not sku:
            raise ValueError("SKU cannot be empty")
        if not name:
            raise ValueError("Product name cannot be empty")
        if price < 0:
            raise ValueError("Price cannot be negative")
        
        self.sku = sku
        self.name = name
        self.price = price
    
    def __repr__(self):
        return f"Product({self.sku}, {self.name}, ${self.price})"


class OrderItem:
    """
    Represents a line item in an order.
    
    An item knows its product, quantity, and price at time of order.
    We store the price because it might change later in the catalog.
    """
    
    def __init__(self, product: Product, quantity: int):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        self.product = product
        self.quantity = quantity
        self.unit_price = product.price  # Capture price at order time
    
    def subtotal(self) -> Decimal:
        """Calculate line item subtotal."""
        return self.unit_price * self.quantity
    
    def __repr__(self):
        return f"OrderItem({self.product.sku} x{self.quantity} @ ${self.unit_price})"


class Order:
    """
    Represents a customer order.
    
    An order aggregates multiple items, tracks status, and enforces
    business rules about when operations are valid.
    """
    
    def __init__(self, order_id: str, customer_id: str):
        if not order_id:
            raise ValueError("Order ID cannot be empty")
        if not customer_id:
            raise ValueError("Customer ID cannot be empty")
        
        self.id = order_id
        self.customer_id = customer_id
        self._items: List[OrderItem] = []
        self._status = OrderStatus.DRAFT
    
    def add_item(self, product: Product, quantity: int) -> None:
        """
        Add a product to the order.
        
        Business rule: Can only add items to draft orders.
        """
        if self._status != OrderStatus.DRAFT:
            raise ValueError(f"Cannot add items to {self._status.value} order")
        
        # Check if product already in order - update quantity instead
        for item in self._items:
            if item.product.sku == product.sku:
                item.quantity += quantity
                return
        
        # New product - add new item
        item = OrderItem(product, quantity)
        self._items.append(item)
    
    def remove_item(self, sku: str) -> None:
        """
        Remove a product from the order.
        
        Business rule: Can only remove items from draft orders.
        """
        if self._status != OrderStatus.DRAFT:
            raise ValueError(f"Cannot remove items from {self._status.value} order")
        
        self._items = [item for item in self._items if item.product.sku != sku]
    
    def update_quantity(self, sku: str, new_quantity: int) -> None:
        """Update quantity for a specific product."""
        if self._status != OrderStatus.DRAFT:
            raise ValueError(f"Cannot update {self._status.value} order")
        
        if new_quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        for item in self._items:
            if item.product.sku == sku:
                item.quantity = new_quantity
                return
        
        raise ValueError(f"Product {sku} not found in order")
    
    @property
    def items(self) -> List[OrderItem]:
        """Return read-only copy of items."""
        return self._items.copy()
    
    @property
    def status(self) -> OrderStatus:
        """Return current order status."""
        return self._status
    
    def total(self) -> Decimal:
        """Calculate order total from all items."""
        return sum(item.subtotal() for item in self._items)
    
    def item_count(self) -> int:
        """Return total number of items (sum of quantities)."""
        return sum(item.quantity for item in self._items)
    
    def place(self) -> None:
        """
        Place the order.
        
        Business rule: Order must have items and be in DRAFT status.
        """
        if self._status != OrderStatus.DRAFT:
            raise ValueError(f"Cannot place {self._status.value} order")
        
        if not self._items:
            raise ValueError("Cannot place empty order")
        
        self._status = OrderStatus.PLACED
    
    def mark_paid(self) -> None:
        """
        Mark order as paid.
        
        Business rule: Can only pay for placed orders.
        """
        if self._status != OrderStatus.PLACED:
            raise ValueError(f"Cannot mark {self._status.value} order as paid")
        
        self._status = OrderStatus.PAID
    
    def ship(self) -> None:
        """
        Ship the order.
        
        Business rule: Can only ship paid orders.
        """
        if self._status != OrderStatus.PAID:
            raise ValueError(f"Cannot ship {self._status.value} order")
        
        self._status = OrderStatus.SHIPPED
    
    def cancel(self) -> None:
        """
        Cancel the order.
        
        Business rule: Can only cancel draft or placed orders.
        """
        if self._status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED]:
            raise ValueError(f"Cannot cancel {self._status.value} order")
        
        self._status = OrderStatus.CANCELLED
    
    def __repr__(self):
        return f"Order({self.id}, {len(self._items)} items, {self._status.value})"


class Discount:
    """
    Represents a discount that can be applied to an order.
    
    This is a simple percentage-based discount, but could be extended
    for different discount types (fixed amount, buy-one-get-one, etc.).
    """
    
    def __init__(self, code: str, percentage: Decimal):
        if not code:
            raise ValueError("Discount code cannot be empty")
        if not (0 < percentage <= 100):
            raise ValueError("Discount percentage must be between 0 and 100")
        
        self.code = code
        self.percentage = percentage
    
    def apply_to(self, order: Order) -> Decimal:
        """
        Calculate discount amount for an order.
        
        Returns the discount amount (not the final price).
        """
        order_total = order.total()
        discount_amount = order_total * (self.percentage / 100)
        return discount_amount
    
    def __repr__(self):
        return f"Discount({self.code}, {self.percentage}%)"
```

### Explanation

**Key design decisions:**

1. **Business rules in the domain:**
   - `add_item()` enforces "can only modify draft orders"
   - `place()` enforces "must have items to place"
   - `ship()` enforces "must be paid before shipping"

2. **Encapsulation:**
   - `_items` is private; access through methods or property
   - `_status` is private; state changes through behavior methods
   - Can't create invalid orders because constructors validate

3. **Rich behavior:**
   - `total()` calculates from items (not stored separately)
   - `add_item()` handles duplicate products intelligently
   - State transitions are explicit methods, not just setting a field

4. **Domain language:**
   - Methods named after business actions: `place()`, `ship()`, `cancel()`
   - Classes named after business concepts: `Order`, `Product`, `Discount`
   - Status is an enum, not magic strings

5. **Price immutability:**
   - `OrderItem` stores `unit_price` from product at order time
   - Even if product price changes later, order stays consistent

### Using the Domain Model

```python
from decimal import Decimal

# Create products
laptop = Product("LAPTOP-001", "MacBook Pro", Decimal("2499.00"))
mouse = Product("MOUSE-001", "Magic Mouse", Decimal("79.00"))
keyboard = Product("KB-001", "Magic Keyboard", Decimal("149.00"))

# Create an order
order = Order("ORD-12345", "CUST-789")

# Add items
order.add_item(laptop, 1)
order.add_item(mouse, 2)
order.add_item(keyboard, 1)

print(f"Order total: ${order.total()}")  # $2,885.00
print(f"Item count: {order.item_count()}")  # 4 items

# Apply discount
discount = Discount("WELCOME10", Decimal("10"))
discount_amount = discount.apply_to(order)
final_price = order.total() - discount_amount

print(f"Discount: ${discount_amount}")  # $288.50
print(f"Final price: ${final_price}")  # $2,596.50

# Process the order
order.place()  # Status: DRAFT → PLACED
order.mark_paid()  # Status: PLACED → PAID
order.ship()  # Status: PAID → SHIPPED

# Can't add items after placing
try:
    order.add_item(mouse, 1)
except ValueError as e:
    print(f"Error: {e}")  # Cannot add items to shipped order
```

## Benefits

### Business Logic Is Discoverable

All order-related logic is in the `Order` class. No hunting through scattered functions.

### Invalid States Are Prevented

Can't create an order without an ID. Can't place an empty order. Can't ship before paying. The code enforces business rules.

### Tests Are Focused

```python
def test_cannot_place_empty_order():
    order = Order("ORD-1", "CUST-1")
    
    with pytest.raises(ValueError, match="empty order"):
        order.place()

def test_adding_same_product_updates_quantity():
    order = Order("ORD-1", "CUST-1")
    product = Product("SKU-1", "Widget", Decimal("10.00"))
    
    order.add_item(product, 2)
    order.add_item(product, 3)
    
    assert len(order.items) == 1
    assert order.items[0].quantity == 5
```

### Refactoring Is Safe

Want to change how totals are calculated? Change `Order.total()`. Tests will verify nothing breaks.

### Communication Is Clear

Code reads like the domain:

```python
order.place()
order.mark_paid()
order.ship()
```

vs.

```python
order.status = 'placed'
order.status = 'paid'
order.status = 'shipped'
```

The first is clear intent. The second is just data manipulation.

## Trade-offs

### More Code Upfront

Domain models require more setup than simple dictionaries:

```python
# Simple approach: 3 lines
order = {'id': '1', 'items': [], 'status': 'draft'}

# Rich model: 100+ lines
class Order:
    # ... full implementation
```

**When it's worth it:** Business logic is complex, system will evolve, multiple developers

**When it's not:** One-time scripts, simple CRUD, throwaway prototypes

### Learning Curve

Developers need to understand:
- Where to put business rules
- How to design rich models
- When to add behavior vs. when to keep it simple

### Can Be Over-Engineered

Easy to add unnecessary abstraction:

```python
# Overkill for simple cases
class OrderItemQuantityValidator:
    def validate(self, quantity):
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

# vs. just validate inline
if quantity <= 0:
    raise ValueError("Quantity must be positive")
```

Use judgment. Don't create classes for everything.

## Common Mistakes

### Anemic Domain Models

Classes with only getters/setters, no behavior:

```python
# Bad: Just a data container
class Order:
    def __init__(self):
        self.items = []
        self.total = 0
    
    def set_total(self, total):
        self.total = total
    
    def get_total(self):
        return self.total

# Logic lives elsewhere
def calculate_total(order):
    order.set_total(sum(i.price for i in order.items))
```

**Fix:** Put behavior in the class:

```python
class Order:
    def total(self):
        return sum(item.subtotal() for item in self._items)
```

### Exposing Internal State

```python
# Bad: Allows external code to break invariants
class Order:
    def __init__(self):
        self.items = []  # Public, mutable

order = Order()
order.items.append(invalid_item)  # Bypasses validation!
```

**Fix:** Encapsulate:

```python
class Order:
    def __init__(self):
        self._items = []  # Private
    
    def add_item(self, product, quantity):
        # Validation happens here
        item = OrderItem(product, quantity)
        self._items.append(item)
    
    @property
    def items(self):
        return self._items.copy()  # Read-only copy
```

### Business Logic in Getters/Setters

```python
# Bad: Hidden side effects
class Order:
    def set_status(self, status):
        self._status = status
        if status == 'placed':
            self.send_confirmation_email()  # Surprise!
```

**Fix:** Make operations explicit:

```python
class Order:
    def place(self):
        self._status = OrderStatus.PLACED
        self._send_confirmation()  # Clear that something happens
```

## Testing

```python
# test_order.py
from decimal import Decimal
import pytest


def test_create_order():
    order = Order("ORD-1", "CUST-1")
    
    assert order.id == "ORD-1"
    assert order.customer_id == "CUST-1"
    assert order.status == OrderStatus.DRAFT
    assert len(order.items) == 0


def test_add_item_to_order():
    order = Order("ORD-1", "CUST-1")
    product = Product("SKU-1", "Widget", Decimal("10.00"))
    
    order.add_item(product, 2)
    
    assert len(order.items) == 1
    assert order.items[0].quantity == 2
    assert order.total() == Decimal("20.00")


def test_cannot_add_items_to_placed_order():
    order = Order("ORD-1", "CUST-1")
    product = Product("SKU-1", "Widget", Decimal("10.00"))
    
    order.add_item(product, 1)
    order.place()
    
    with pytest.raises(ValueError, match="Cannot add items"):
        order.add_item(product, 1)


def test_order_lifecycle():
    order = Order("ORD-1", "CUST-1")
    product = Product("SKU-1", "Widget", Decimal("10.00"))
    
    order.add_item(product, 1)
    
    # Draft → Placed
    order.place()
    assert order.status == OrderStatus.PLACED
    
    # Placed → Paid
    order.mark_paid()
    assert order.status == OrderStatus.PAID
    
    # Paid → Shipped
    order.ship()
    assert order.status == OrderStatus.SHIPPED


def test_discount_calculation():
    order = Order("ORD-1", "CUST-1")
    product = Product("SKU-1", "Widget", Decimal("100.00"))
    order.add_item(product, 1)
    
    discount = Discount("SAVE10", Decimal("10"))
    discount_amount = discount.apply_to(order)
    
    assert discount_amount == Decimal("10.00")
    assert order.total() - discount_amount == Decimal("90.00")
```

## Related Patterns

- **Chapter 9: Entities vs Value Objects** - Deep dive into identity vs value equality
- **Chapter 10: Aggregates & Boundaries** - How to group related domain models
- **Chapter 11: Domain Events** - Making domain models publish events

## Summary

Domain modeling is about representing business concepts as rich classes with behavior, not just data. By putting business logic inside domain classes, you create code that's more maintainable, testable, and expressive.

The key is moving from anemic models (data containers) to rich models (data + behavior), while keeping interfaces clean and invalid states impossible.

## Further Reading

- **Eric Evans** - *Domain-Driven Design* - The definitive guide to domain modeling
- **Vaughn Vernon** - *Implementing Domain-Driven Design* - Practical DDD patterns
- **Martin Fowler** - *Patterns of Enterprise Application Architecture* - Domain Model pattern
