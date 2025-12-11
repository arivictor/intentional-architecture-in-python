# Chapter 9: Entities vs Value Objects

## Introduction

In domain modeling, understanding the difference between Entities and Value Objects is fundamental. **Entities have identity** — they're the "same" even when their attributes change. **Value Objects have no identity** — they're defined purely by their attributes.

A Person is an entity: even if they change their name or address, they're still the same person. An Address is a value object: two addresses with the same street, city, and postal code are identical and interchangeable.

This distinction shapes how we design classes, implement equality, and manage state changes.

## The Problem

Treating everything as an entity or everything as primitive values leads to confused models and bugs.

**Symptoms:**
- Every class has an ID field "just in case"
- Comparison bugs where identical values aren't equal
- Mutating shared values unexpectedly affects multiple objects
- Unclear whether two objects are "the same" or just "equal"
- Excessive defensive copying

**Example of the problem:**

```python
class Customer:
    """Customer modeled without understanding entity vs value object."""
    
    def __init__(self, customer_id, name, email, address):
        self.customer_id = customer_id
        self.name = name
        self.email = email
        # Address is just primitive values - no structure
        self.street = address['street']
        self.city = address['city']
        self.postal_code = address['postal_code']
        self.country = address['country']


class Order:
    """Order with address as primitives."""
    
    def __init__(self, order_id, customer_id, items, shipping_address):
        self.order_id = order_id
        self.customer_id = customer_id
        self.items = items
        # Same address data duplicated as primitives
        self.shipping_street = shipping_address['street']
        self.shipping_city = shipping_address['city']
        self.shipping_postal_code = shipping_address['postal_code']
        self.shipping_country = shipping_address['country']


# Usage
customer_address = {
    'street': '123 Main St',
    'city': 'Springfield',
    'postal_code': '12345',
    'country': 'USA'
}

customer = Customer('C001', 'John Doe', 'john@example.com', customer_address)
order = Order('O001', 'C001', ['item1'], customer_address)

# Problem 1: Can't easily compare addresses
# Are these the same address?
same_address = (
    customer.street == order.shipping_street and
    customer.city == order.shipping_city and
    customer.postal_code == order.shipping_postal_code and
    customer.country == order.shipping_country
)  # Tedious and error-prone

# Problem 2: Modifying the dict affects both (if shared reference)
customer_address['street'] = '456 Oak Ave'  # Bug: might affect order

# Problem 3: No validation - garbage data allowed
invalid_customer = Customer(
    'C002', 
    'Jane Doe', 
    'not-an-email',  # Invalid email
    {'street': '', 'city': '', 'postal_code': '', 'country': ''}  # Empty address
)

# Problem 4: Money as primitives
class Product:
    def __init__(self, name, price_amount, price_currency):
        self.name = name
        self.price_amount = price_amount
        self.price_currency = price_currency

p1 = Product('Widget', 19.99, 'USD')
p2 = Product('Gadget', 29.99, 'EUR')

# Can't safely add prices - might mix currencies
total = p1.price_amount + p2.price_amount  # Bug: adding USD and EUR!
```

**Problems:**
- No encapsulation of value object concepts (Address, Money, Email)
- Primitive obsession leads to scattered validation
- Can't compare addresses or money amounts safely
- No protection against mixing incompatible values (currencies)
- Identity unclear: when are two addresses "the same"?

## The Pattern

**Entity:** An object defined by its identity, not its attributes. Identity persists across state changes.

**Value Object:** An object defined entirely by its attributes. No identity. Two value objects with the same attributes are identical and interchangeable.

### Key Characteristics

**Entities:**
- Have a unique identifier
- Mutable (attributes can change)
- Identity-based equality (same ID = same entity)
- Long-lived
- Examples: Customer, Order, User, Product, Account

**Value Objects:**
- No unique identifier
- Immutable (create new instance for changes)
- Value-based equality (same attributes = identical)
- Can be shared and replaced
- Examples: Money, Address, Email, DateRange, Coordinate

### Equality Comparison

```
Entity:
customer1.id == customer2.id  → Same customer
customer1.name != customer2.name  → Still same customer (name changed)

Value Object:
address1.attributes == address2.attributes  → Identical, interchangeable
```

## Implementation

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
import re


@dataclass(frozen=True)
class Email:
    """
    Value object for email addresses.
    
    Immutable, validated, value-based equality.
    """
    address: str
    
    def __post_init__(self):
        """Validate email format."""
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', self.address):
            raise ValueError(f"Invalid email address: {self.address}")
    
    def __str__(self):
        return self.address


@dataclass(frozen=True)
class Address:
    """
    Value object for physical addresses.
    
    Two addresses with same values are identical and interchangeable.
    Immutable - create new instance to change.
    """
    street: str
    city: str
    postal_code: str
    country: str
    
    def __post_init__(self):
        """Validate address components."""
        if not self.street.strip():
            raise ValueError("Street is required")
        if not self.city.strip():
            raise ValueError("City is required")
        if not self.postal_code.strip():
            raise ValueError("Postal code is required")
        if not self.country.strip():
            raise ValueError("Country is required")
    
    def __str__(self):
        return f"{self.street}, {self.city} {self.postal_code}, {self.country}"


@dataclass(frozen=True)
class Money:
    """
    Value object for monetary amounts.
    
    Ensures currency safety and prevents mixing different currencies.
    """
    amount: Decimal
    currency: str
    
    def __post_init__(self):
        """Validate money properties."""
        if not isinstance(self.amount, Decimal):
            # Convert to Decimal if needed
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        if self.currency not in ('USD', 'EUR', 'GBP', 'JPY'):
            raise ValueError(f"Unsupported currency: {self.currency}")
    
    def add(self, other: 'Money') -> 'Money':
        """
        Add money amounts, ensuring same currency.
        
        Args:
            other: Money to add
            
        Returns:
            New Money instance with sum
            
        Raises:
            ValueError: If currencies don't match
        """
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot add {self.currency} and {other.currency}"
            )
        return Money(self.amount + other.amount, self.currency)
    
    def multiply(self, factor: Decimal) -> 'Money':
        """Multiply amount by a factor."""
        return Money(self.amount * factor, self.currency)
    
    def __str__(self):
        return f"{self.currency} {self.amount:.2f}"


class Customer:
    """
    Entity with identity.
    
    A customer is the same customer even if they change name, email, or address.
    Identity defined by customer_id.
    """
    
    def __init__(self, customer_id: str, name: str, email: Email, address: Address):
        if not customer_id:
            raise ValueError("Customer ID is required")
        if not name.strip():
            raise ValueError("Name is required")
        
        self._customer_id = customer_id  # Identity - immutable
        self.name = name  # Attributes - mutable
        self.email = email
        self.address = address
    
    @property
    def customer_id(self) -> str:
        """Customer identity - cannot be changed."""
        return self._customer_id
    
    def update_email(self, new_email: Email) -> None:
        """Update customer email."""
        self.email = new_email
    
    def relocate(self, new_address: Address) -> None:
        """Update customer address."""
        self.address = new_address
    
    def __eq__(self, other) -> bool:
        """Identity-based equality - same ID means same customer."""
        if not isinstance(other, Customer):
            return False
        return self.customer_id == other.customer_id
    
    def __hash__(self):
        """Hash based on identity."""
        return hash(self.customer_id)
    
    def __repr__(self):
        return f"Customer(id={self.customer_id}, name={self.name})"


class Order:
    """
    Entity representing a customer order.
    
    Identity defined by order_id.
    Uses value objects for address and money amounts.
    """
    
    def __init__(
        self, 
        order_id: str, 
        customer: Customer, 
        shipping_address: Address,
        total: Money
    ):
        if not order_id:
            raise ValueError("Order ID is required")
        
        self._order_id = order_id
        self.customer = customer
        self.shipping_address = shipping_address
        self.total = total
    
    @property
    def order_id(self) -> str:
        """Order identity."""
        return self._order_id
    
    def change_shipping_address(self, new_address: Address) -> None:
        """Update shipping address (creates new Address, doesn't modify old one)."""
        self.shipping_address = new_address
    
    def __eq__(self, other) -> bool:
        """Identity-based equality."""
        if not isinstance(other, Order):
            return False
        return self.order_id == other.order_id
    
    def __hash__(self):
        return hash(self.order_id)
    
    def __repr__(self):
        return f"Order(id={self.order_id}, customer={self.customer.customer_id}, total={self.total})"


# Usage example
if __name__ == "__main__":
    # Create value objects
    email = Email("john.doe@example.com")
    address = Address(
        street="123 Main St",
        city="Springfield",
        postal_code="12345",
        country="USA"
    )
    
    # Create entity
    customer = Customer(
        customer_id="C001",
        name="John Doe",
        email=email,
        address=address
    )
    
    print(f"Customer: {customer}")
    print(f"Email: {customer.email}")
    print(f"Address: {customer.address}")
    print()
    
    # Value objects: equality based on attributes
    same_address = Address("123 Main St", "Springfield", "12345", "USA")
    print(f"Addresses equal? {address == same_address}")  # True
    print(f"Addresses are same object? {address is same_address}")  # False
    print()
    
    # Entity: equality based on identity
    same_customer_data = Customer("C001", "John Doe", email, address)
    different_customer = Customer("C002", "John Doe", email, address)
    
    print(f"Same ID, same customer? {customer == same_customer_data}")  # True
    print(f"Different ID, different customer? {customer == different_customer}")  # False
    print()
    
    # Entity mutation: customer changes but remains same entity
    new_address = Address("456 Oak Ave", "Springfield", "12345", "USA")
    customer.relocate(new_address)
    print(f"After moving: {customer.address}")
    print(f"Still same customer? {customer == same_customer_data}")  # True
    print()
    
    # Value object immutability - cannot modify
    try:
        address.street = "999 Elm St"  # Error: frozen dataclass
    except AttributeError as e:
        print(f"Cannot modify value object: {e}")
    print()
    
    # Money value object: safe currency handling
    price1 = Money(Decimal("19.99"), "USD")
    price2 = Money(Decimal("29.99"), "USD")
    total_usd = price1.add(price2)
    print(f"Total: {total_usd}")
    
    # Prevents mixing currencies
    price_eur = Money(Decimal("25.00"), "EUR")
    try:
        invalid_total = price1.add(price_eur)
    except ValueError as e:
        print(f"Currency safety: {e}")
    print()
    
    # Create order entity
    order = Order(
        order_id="O001",
        customer=customer,
        shipping_address=new_address,
        total=total_usd
    )
    print(f"Order: {order}")
```

## Explanation

### Value Objects Are Immutable

The `@dataclass(frozen=True)` decorator makes value objects immutable. You can't modify attributes after creation:

```python
address = Address("123 Main St", "Springfield", "12345", "USA")
# address.street = "456 Oak Ave"  # Error!

# Instead, create a new instance
new_address = Address("456 Oak Ave", "Springfield", "12345", "USA")
```

This prevents bugs where modifying a shared address unexpectedly affects multiple objects.

### Value-Based Equality

Value objects use attribute-based equality (automatic with `@dataclass`):

```python
addr1 = Address("123 Main St", "Springfield", "12345", "USA")
addr2 = Address("123 Main St", "Springfield", "12345", "USA")
addr1 == addr2  # True - same values
```

### Identity-Based Equality

Entities use ID-based equality:

```python
customer1 = Customer("C001", "John", email, address)
customer2 = Customer("C001", "Jane", different_email, different_address)
customer1 == customer2  # True - same ID, same customer

customer1.name = "Jonathan"  # Mutate attributes
customer1 == customer2  # Still True - same identity
```

### Encapsulation and Validation

Value objects encapsulate validation logic:

```python
# Email validates format
email = Email("john.doe@example.com")  # OK
# Email("invalid")  # ValueError

# Money prevents currency mixing
money1 = Money(Decimal("10.00"), "USD")
money2 = Money(Decimal("10.00"), "EUR")
# money1.add(money2)  # ValueError - can't add different currencies
```

### Type Safety

Using value objects provides compile-time safety:

```python
def send_email(recipient: Email):  # Type hint ensures Email object
    ...

send_email(Email("user@example.com"))  # OK
# send_email("user@example.com")  # Type error (with strict checking)
```

## Benefits

**1. Clear Domain Model**

The distinction between entities and value objects makes the domain model clearer. You immediately know what has identity and what doesn't.

**2. Immutability Benefits**

Value objects are immutable, which means:
- Thread-safe by default
- Can be safely shared
- No defensive copying needed
- Easier to reason about

**3. Validation in One Place**

Value objects validate themselves on construction. You can't have an invalid Email or Money object:

```python
email = Email("john@example.com")  # Validated
# No need to validate email format anywhere else
```

**4. Type Safety**

Using specific types (Email, Money, Address) instead of strings/dicts prevents errors:

```python
def calculate_total(price: Money, quantity: int) -> Money:
    return price.multiply(Decimal(quantity))

# calculate_total(19.99, 2)  # Type error - needs Money, not float
```

**5. Expressive Code**

`customer.email` is more expressive than `customer['email']` or `customer.email_string`.

## Trade-offs

**When NOT to use value objects:**

**1. Simple Data Transfer**

For simple DTOs or data structures, primitives might be fine:

```python
# OK for simple JSON response
response = {"status": "success", "code": 200}

# Overkill
@dataclass(frozen=True)
class Response:
    status: str
    code: int
```

**2. Performance-Critical Code**

Value objects add overhead:
- Object creation cost
- Garbage collection pressure
- More memory usage

For tight loops or performance-critical sections, primitives might be faster.

**3. Prototyping**

When exploring a domain, start simple. Add value objects when patterns emerge:

```python
# Start with this
user = {"name": "John", "email": "john@example.com"}

# Refactor to this when you need validation/behavior
user = User(name="John", email=Email("john@example.com"))
```

**4. External API Integration**

Sometimes you need primitives for serialization:

```python
# Value object for domain
money = Money(Decimal("19.99"), "USD")

# Convert to primitives for JSON API
api_data = {"amount": float(money.amount), "currency": money.currency}
```

## Testing

```python
import pytest
from decimal import Decimal


def test_email_validation():
    """Test that Email validates format."""
    valid_email = Email("user@example.com")
    assert valid_email.address == "user@example.com"
    
    with pytest.raises(ValueError, match="Invalid email"):
        Email("not-an-email")
    
    with pytest.raises(ValueError, match="Invalid email"):
        Email("missing-at-sign.com")


def test_address_equality():
    """Test value-based equality for Address."""
    addr1 = Address("123 Main St", "Springfield", "12345", "USA")
    addr2 = Address("123 Main St", "Springfield", "12345", "USA")
    addr3 = Address("456 Oak Ave", "Springfield", "12345", "USA")
    
    assert addr1 == addr2  # Same values
    assert addr1 != addr3  # Different values
    assert addr1 is not addr2  # Different objects


def test_address_immutability():
    """Test that Address cannot be modified."""
    addr = Address("123 Main St", "Springfield", "12345", "USA")
    
    with pytest.raises(AttributeError):
        addr.street = "456 Oak Ave"


def test_money_currency_safety():
    """Test that Money prevents mixing currencies."""
    usd = Money(Decimal("10.00"), "USD")
    eur = Money(Decimal("10.00"), "EUR")
    
    with pytest.raises(ValueError, match="Cannot add USD and EUR"):
        usd.add(eur)


def test_money_arithmetic():
    """Test Money arithmetic operations."""
    price = Money(Decimal("19.99"), "USD")
    quantity_price = price.multiply(Decimal("3"))
    
    assert quantity_price.amount == Decimal("59.97")
    assert quantity_price.currency == "USD"
    
    price2 = Money(Decimal("10.00"), "USD")
    total = price.add(price2)
    assert total.amount == Decimal("29.99")


def test_customer_identity_equality():
    """Test that Customer uses identity-based equality."""
    email = Email("john@example.com")
    address = Address("123 Main St", "Springfield", "12345", "USA")
    
    customer1 = Customer("C001", "John Doe", email, address)
    customer2 = Customer("C001", "Jane Smith", email, address)  # Same ID, different name
    customer3 = Customer("C002", "John Doe", email, address)  # Different ID
    
    assert customer1 == customer2  # Same ID
    assert customer1 != customer3  # Different ID


def test_customer_mutation():
    """Test that entity attributes can be mutated without changing identity."""
    email1 = Email("john@example.com")
    email2 = Email("john.doe@example.com")
    address = Address("123 Main St", "Springfield", "12345", "USA")
    
    customer = Customer("C001", "John Doe", email1, address)
    original_id = customer.customer_id
    
    customer.update_email(email2)
    
    assert customer.email == email2
    assert customer.customer_id == original_id  # Identity unchanged


def test_customer_can_be_used_in_set():
    """Test that Customer can be used in sets (hashable)."""
    email = Email("john@example.com")
    address = Address("123 Main St", "Springfield", "12345", "USA")
    
    customer1 = Customer("C001", "John", email, address)
    customer2 = Customer("C001", "John", email, address)
    customer3 = Customer("C002", "Jane", email, address)
    
    customer_set = {customer1, customer2, customer3}
    
    assert len(customer_set) == 2  # customer1 and customer2 are same (same ID)


def test_order_uses_value_objects():
    """Test that Order correctly uses value objects."""
    email = Email("john@example.com")
    address = Address("123 Main St", "Springfield", "12345", "USA")
    customer = Customer("C001", "John", email, address)
    total = Money(Decimal("99.99"), "USD")
    
    order = Order("O001", customer, address, total)
    
    assert order.order_id == "O001"
    assert order.customer == customer
    assert order.shipping_address == address
    assert order.total == total
```

## Common Mistakes

**1. Making Value Objects Mutable**

Value objects should be immutable to be safely shared:

```python
# Bad - mutable value object
class Money:
    def __init__(self, amount, currency):
        self.amount = amount  # Can be changed!
        self.currency = currency

# Good - immutable value object
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str
```

**2. Giving Value Objects Identity**

Don't give value objects an ID field:

```python
# Bad - value object with ID
@dataclass(frozen=True)
class Address:
    id: str  # Why does an address have an ID?
    street: str
    city: str

# Good - no identity
@dataclass(frozen=True)
class Address:
    street: str
    city: str
```

**3. Using Identity Equality for Value Objects**

Don't implement identity-based `__eq__` for value objects:

```python
# Bad - identity equality for value object
class Money:
    def __eq__(self, other):
        return id(self) == id(other)  # Wrong!

# Good - value equality (automatic with @dataclass)
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str
    # __eq__ compares attributes automatically
```

**4. Primitive Obsession**

Don't use primitives when a value object would be clearer:

```python
# Bad - primitives everywhere
def send_money(amount: float, currency: str, to_email: str):
    if currency not in ['USD', 'EUR']:  # Validation scattered
        raise ValueError("Invalid currency")
    if '@' not in to_email:  # Validation scattered
        raise ValueError("Invalid email")
    ...

# Good - value objects encapsulate validation
def send_money(amount: Money, to_email: Email):
    # Money and Email are already validated
    ...
```

## Related Patterns

- **Chapter 3 (Domain Modeling):** Entities and value objects are core domain modeling concepts
- **Chapter 10 (Aggregates):** Aggregates are clusters of entities and value objects
- **Chapter 11 (Domain Events):** Events often carry value objects as data
- **Chapter 19 (Specification):** Specifications work with entities and value objects

## Summary

Entities have identity that persists across attribute changes; value objects are defined purely by their attributes and have no identity. Entities use identity-based equality and are mutable. Value objects use value-based equality and should be immutable.

Use entities for objects that have a lifecycle and unique identity (Customer, Order, Account). Use value objects for descriptive attributes (Money, Address, Email, Date Range). The distinction makes your domain model clearer and prevents common bugs.

## Further Reading

- Evans, Eric. *Domain-Driven Design: Tackling Complexity in the Heart of Software*. Addison-Wesley, 2003. (Chapter 5: A Model Expressed in Software)
- Vernon, Vaughn. *Implementing Domain-Driven Design*. Addison-Wesley, 2013. (Chapter 6: Value Objects)
- Fowler, Martin. "Value Object." martinfowler.com.
- Nilsson, Jimmy. *Applying Domain-Driven Design and Patterns*. Addison-Wesley, 2006.
- Wlaschin, Scott. "Domain Modeling Made Functional." Pragmatic Bookshelf, 2018.
