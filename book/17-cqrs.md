# Chapter 17: CQRS (Command Query Responsibility Segregation)

## Introduction

**CQRS** (Command Query Responsibility Segregation) separates read and write operations into different models. Commands modify state, queries read state. This separation allows you to optimize each path independently and simplify complex domains.

Instead of one model serving both reads and writes, CQRS uses separate models: a write model optimized for consistency and business rules, and a read model optimized for queries and display.

## The Problem

Using a single model for both reads and writes creates conflicts between different needs.

**Symptoms:**
- Complex queries slow down writes  
- Write optimizations hurt read performance
- Domain entities bloated with display logic
- Difficult to scale reads and writes independently
- Complex object graphs for simple queries
- Performance trade-offs hurt both sides

**Example of the problem:**

```python
# Single model for reads and writes

class Product:
    """Product entity handling both writes and reads."""
    
    def __init__(self, id, name, price, stock):
        self.id = id
        self.name = name
        self.price = price
        self.stock = stock
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    # Write operations
    def update_stock(self, quantity):
        if self.stock + quantity < 0:
            raise ValueError("Insufficient stock")
        self.stock += quantity
        self.updated_at = datetime.now()
    
    def update_price(self, new_price):
        if new_price < 0:
            raise ValueError("Invalid price")
        self.price = new_price
        self.updated_at = datetime.now()
    
    # Read operation - returns entire object
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'stock': self.stock,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class ProductService:
    """Service using single model for everything."""
    
    def __init__(self, repository):
        self.repository = repository
    
    # Write operation
    def add_product(self, name, price, stock):
        product = Product(generate_id(), name, price, stock)
        self.repository.save(product)  # Saves entire entity
        return product
    
    # Read operation - loads entire entity just to display list
    def list_products(self):
        """
        Problem: Loads full entities even though we only need
        name and price for the list view.
        """
        products = self.repository.find_all()
        return [p.to_dict() for p in products]  # Returns everything
    
    # Read operation - complex joins needed
    def get_product_with_category_and_reviews(self, product_id):
        """
        Problem: Need to load related entities, creating N+1 queries
        or complex eager loading.
        """
        product = self.repository.find_by_id(product_id)
        # Load category
        # Load reviews
        # Load ratings
        # Build complex object graph
        return product  # Returns entire graph
```

**Problems:**
- List view loads entire entities (wasteful)
- Complex queries require loading full object graphs
- Write model constrained by read requirements
- Can't optimize reads without affecting writes
- Scaling reads and writes requires scaling everything
- Business logic mixed with query optimization

## The Pattern

**CQRS:** Use separate models for commands (writes) and queries (reads).

### Key Concepts

**Command Model (Write)**:
- Handles business logic and validation
- Optimized for consistency
- Domain entities and aggregates
- Processes commands

**Query Model (Read)**:
- Optimized for specific queries
- Denormalized data
- No business logic
- Serves read requests

**Synchronization**:
- Commands publish events
- Read model subscribes to events
- Eventually consistent

### Flow

```
Command → Command Handler → Write Model → Event → Read Model Updater → Query Model
Query → Query Handler → Read Model → Response
```

## Implementation

```python
from dataclasses import dataclass
from typing import List, Optional, Dict
from decimal import Decimal
from datetime import datetime
from abc import ABC, abstractmethod


# =============================================================================
# COMMANDS (Write Side)
# =============================================================================

@dataclass
class AddProductCommand:
    """Command to add a new product."""
    name: str
    price: Decimal
    initial_stock: int


@dataclass
class UpdateStockCommand:
    """Command to update product stock."""
    product_id: str
    quantity_change: int


@dataclass
class UpdatePriceCommand:
    """Command to update product price."""
    product_id: str
    new_price: Decimal


# =============================================================================
# WRITE MODEL (Domain)
# =============================================================================

class Product:
    """
    Write model - focused on business logic.
    
    Optimized for consistency and invariants.
    """
    
    def __init__(self, product_id: str, name: str, price: Decimal, stock: int):
        if price < 0:
            raise ValueError("Price cannot be negative")
        if stock < 0:
            raise ValueError("Stock cannot be negative")
        
        self.id = product_id
        self.name = name
        self.price = price
        self.stock = stock
    
    def update_stock(self, quantity_change: int) -> None:
        """Update stock level."""
        new_stock = self.stock + quantity_change
        if new_stock < 0:
            raise ValueError(f"Insufficient stock: have {self.stock}, need {abs(quantity_change)}")
        self.stock = new_stock
    
    def update_price(self, new_price: Decimal) -> None:
        """Update price."""
        if new_price < 0:
            raise ValueError("Price cannot be negative")
        self.price = new_price


class ProductWriteRepository:
    """Write repository - stores write model."""
    
    def __init__(self):
        self._products: Dict[str, Product] = {}
    
    def save(self, product: Product) -> None:
        self._products[product.id] = product
    
    def find_by_id(self, product_id: str) -> Optional[Product]:
        return self._products.get(product_id)


# =============================================================================
# COMMAND HANDLERS
# =============================================================================

class CommandHandler:
    """Handles commands and updates write model."""
    
    def __init__(self, repository: ProductWriteRepository, event_publisher):
        self.repository = repository
        self.event_publisher = event_publisher
    
    def handle_add_product(self, command: AddProductCommand) -> str:
        """Handle add product command."""
        import uuid
        product_id = f"prod-{uuid.uuid4().hex[:8]}"
        
        # Create product (write model)
        product = Product(product_id, command.name, command.price, command.initial_stock)
        self.repository.save(product)
        
        # Publish event for read model
        self.event_publisher.publish({
            'type': 'ProductAdded',
            'product_id': product_id,
            'name': command.name,
            'price': float(command.price),
            'stock': command.initial_stock,
            'timestamp': datetime.now()
        })
        
        return product_id
    
    def handle_update_stock(self, command: UpdateStockCommand) -> None:
        """Handle update stock command."""
        product = self.repository.find_by_id(command.product_id)
        if not product:
            raise ValueError(f"Product {command.product_id} not found")
        
        # Update write model
        product.update_stock(command.quantity_change)
        self.repository.save(product)
        
        # Publish event for read model
        self.event_publisher.publish({
            'type': 'StockUpdated',
            'product_id': command.product_id,
            'new_stock': product.stock,
            'timestamp': datetime.now()
        })
    
    def handle_update_price(self, command: UpdatePriceCommand) -> None:
        """Handle update price command."""
        product = self.repository.find_by_id(command.product_id)
        if not product:
            raise ValueError(f"Product {command.product_id} not found")
        
        # Update write model
        product.update_price(command.new_price)
        self.repository.save(product)
        
        # Publish event for read model
        self.event_publisher.publish({
            'type': 'PriceUpdated',
            'product_id': command.product_id,
            'new_price': float(command.new_price),
            'timestamp': datetime.now()
        })


# =============================================================================
# QUERIES (Read Side)
# =============================================================================

@dataclass
class ProductListQuery:
    """Query for product list."""
    category: Optional[str] = None
    in_stock_only: bool = False


@dataclass
class ProductDetailQuery:
    """Query for product details."""
    product_id: str


# =============================================================================
# READ MODEL (Optimized for Queries)
# =============================================================================

@dataclass
class ProductListItem:
    """Read model for product list - only data needed for list view."""
    id: str
    name: str
    price: float
    in_stock: bool


@dataclass
class ProductDetail:
    """Read model for product detail - includes all display data."""
    id: str
    name: str
    price: float
    stock: int
    created_at: datetime
    last_updated: datetime


class ProductReadRepository:
    """Read repository - denormalized, query-optimized."""
    
    def __init__(self):
        self._list_items: Dict[str, ProductListItem] = {}
        self._details: Dict[str, ProductDetail] = {}
    
    def find_all_list_items(self, in_stock_only: bool = False) -> List[ProductListItem]:
        """Get list items - lightweight."""
        items = list(self._list_items.values())
        if in_stock_only:
            items = [item for item in items if item.in_stock]
        return items
    
    def find_detail(self, product_id: str) -> Optional[ProductDetail]:
        """Get product detail."""
        return self._details.get(product_id)
    
    # Methods for read model updater
    def add_product(self, product_id: str, name: str, price: float, stock: int):
        """Add to read model."""
        self._list_items[product_id] = ProductListItem(product_id, name, price, stock > 0)
        self._details[product_id] = ProductDetail(
            product_id, name, price, stock,
            datetime.now(), datetime.now()
        )
    
    def update_stock(self, product_id: str, new_stock: int):
        """Update stock in read model."""
        if product_id in self._list_items:
            self._list_items[product_id].in_stock = new_stock > 0
        if product_id in self._details:
            self._details[product_id].stock = new_stock
            self._details[product_id].last_updated = datetime.now()
    
    def update_price(self, product_id: str, new_price: float):
        """Update price in read model."""
        if product_id in self._list_items:
            self._list_items[product_id].price = new_price
        if product_id in self._details:
            self._details[product_id].price = new_price
            self._details[product_id].last_updated = datetime.now()


# =============================================================================
# QUERY HANDLERS
# =============================================================================

class QueryHandler:
    """Handles queries using read model."""
    
    def __init__(self, read_repository: ProductReadRepository):
        self.read_repository = read_repository
    
    def handle_product_list_query(self, query: ProductListQuery) -> List[ProductListItem]:
        """Handle product list query."""
        return self.read_repository.find_all_list_items(query.in_stock_only)
    
    def handle_product_detail_query(self, query: ProductDetailQuery) -> Optional[ProductDetail]:
        """Handle product detail query."""
        return self.read_repository.find_detail(query.product_id)


# =============================================================================
# EVENT PUBLISHER & READ MODEL UPDATER
# =============================================================================

class EventPublisher:
    """Simple event publisher."""
    
    def __init__(self):
        self.subscribers = []
    
    def subscribe(self, handler):
        self.subscribers.append(handler)
    
    def publish(self, event):
        for subscriber in self.subscribers:
            subscriber(event)


class ReadModelUpdater:
    """Updates read model based on events from write model."""
    
    def __init__(self, read_repository: ProductReadRepository):
        self.read_repository = read_repository
    
    def handle_event(self, event: dict):
        """Handle event and update read model."""
        if event['type'] == 'ProductAdded':
            self.read_repository.add_product(
                event['product_id'],
                event['name'],
                event['price'],
                event['stock']
            )
        elif event['type'] == 'StockUpdated':
            self.read_repository.update_stock(
                event['product_id'],
                event['new_stock']
            )
        elif event['type'] == 'PriceUpdated':
            self.read_repository.update_price(
                event['product_id'],
                event['new_price']
            )


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    print("=== CQRS Pattern Demo ===\n")
    
    # Setup
    event_publisher = EventPublisher()
    
    write_repo = ProductWriteRepository()
    read_repo = ProductReadRepository()
    
    # Wire up event handling
    read_model_updater = ReadModelUpdater(read_repo)
    event_publisher.subscribe(read_model_updater.handle_event)
    
    # Handlers
    command_handler = CommandHandler(write_repo, event_publisher)
    query_handler = QueryHandler(read_repo)
    
    # WRITE: Add products via commands
    print("Adding products via commands:")
    product_id1 = command_handler.handle_add_product(
        AddProductCommand("Laptop", Decimal("999.99"), 10)
    )
    product_id2 = command_handler.handle_add_product(
        AddProductCommand("Mouse", Decimal("29.99"), 0)  # Out of stock
    )
    print(f"Added: {product_id1}, {product_id2}\n")
    
    # READ: Query product list (optimized read model)
    print("Querying product list:")
    products = query_handler.handle_product_list_query(ProductListQuery())
    for p in products:
        print(f"  - {p.name}: ${p.price} {'(in stock)' if p.in_stock else '(out of stock)'}")
    print()
    
    # WRITE: Update stock
    print("Updating stock via command:")
    command_handler.handle_update_stock(UpdateStockCommand(product_id2, 5))
    print(f"Stock updated for {product_id2}\n")
    
    # READ: Query again
    print("Querying in-stock products only:")
    in_stock = query_handler.handle_product_list_query(ProductListQuery(in_stock_only=True))
    for p in in_stock:
        print(f"  - {p.name}: ${p.price}")
    print()
    
    # READ: Get product detail
    print("Querying product detail:")
    detail = query_handler.handle_product_detail_query(ProductDetailQuery(product_id1))
    if detail:
        print(f"  Product: {detail.name}")
        print(f"  Price: ${detail.price}")
        print(f"  Stock: {detail.stock}")
        print(f"  Last updated: {detail.last_updated}")
```

## Explanation

### Separate Models

Write model focuses on business logic:
```python
class Product:  # Write model
    def update_stock(self, quantity):
        if self.stock + quantity < 0:
            raise ValueError("Insufficient stock")
        self.stock += quantity
```

Read models optimized for queries:
```python
@dataclass
class ProductListItem:  # Read model - lightweight
    id: str
    name: str
    price: float
    in_stock: bool  # Computed, not actual stock number
```

### Commands vs Queries

Commands modify state:
```python
command = AddProductCommand("Laptop", Decimal("999.99"), 10)
command_handler.handle_add_product(command)
```

Queries read state:
```python
query = ProductListQuery(in_stock_only=True)
products = query_handler.handle_product_list_query(query)
```

### Event-Based Synchronization

Write side publishes events:
```python
# After updating write model
event_publisher.publish({
    'type': 'StockUpdated',
    'product_id': product_id,
    'new_stock': product.stock
})
```

Read side subscribes:
```python
def handle_event(self, event):
    if event['type'] == 'StockUpdated':
        self.read_repository.update_stock(...)
```

## Benefits

**1. Optimized Models**

Read and write models optimized independently.

**2. Scalability**

Scale reads and writes separately.

**3. Simplified Queries**

Read models denormalized for fast queries.

**4. Flexibility**

Multiple read models for different needs.

**5. Performance**

Optimize each side without compromising the other.

## Trade-offs

**When NOT to use CQRS:**

**1. Simple CRUD**

For basic applications, CQRS adds complexity.

**2. Strong Consistency Required**

CQRS often uses eventual consistency.

**3. Small Applications**

Overhead not justified for small systems.

**4. Complexity**

CQRS adds:
- Two models to maintain
- Synchronization logic
- Event infrastructure

## Testing

```python
import pytest


def test_add_product_command():
    """Test adding product via command."""
    event_publisher = EventPublisher()
    write_repo = ProductWriteRepository()
    handler = CommandHandler(write_repo, event_publisher)
    
    product_id = handler.handle_add_product(
        AddProductCommand("Test", Decimal("10.00"), 5)
    )
    
    assert product_id is not None
    product = write_repo.find_by_id(product_id)
    assert product.name == "Test"


def test_read_model_updated_on_add():
    """Test that read model is updated when product added."""
    event_publisher = EventPublisher()
    write_repo = ProductWriteRepository()
    read_repo = ProductReadRepository()
    
    updater = ReadModelUpdater(read_repo)
    event_publisher.subscribe(updater.handle_event)
    
    handler = CommandHandler(write_repo, event_publisher)
    product_id = handler.handle_add_product(
        AddProductCommand("Test", Decimal("10.00"), 5)
    )
    
    # Check read model
    items = read_repo.find_all_list_items()
    assert len(items) == 1
    assert items[0].name == "Test"


def test_query_in_stock_only():
    """Test filtering by stock status."""
    read_repo = ProductReadRepository()
    read_repo.add_product("1", "In Stock", 10.0, 5)
    read_repo.add_product("2", "Out of Stock", 20.0, 0)
    
    query_handler = QueryHandler(read_repo)
    results = query_handler.handle_product_list_query(
        ProductListQuery(in_stock_only=True)
    )
    
    assert len(results) == 1
    assert results[0].name == "In Stock"
```

## Common Mistakes

**1. Synchronous Updates**

Don't update read model synchronously in command handler:
```python
# Bad
def handle_command(self, cmd):
    self.write_repo.save(...)
    self.read_repo.update(...)  # Tight coupling!

# Good
def handle_command(self, cmd):
    self.write_repo.save(...)
    self.event_publisher.publish(...)  # Async update
```

**2. Shared Database**

Read and write models can share database, but should have separate schemas.

**3. Over-Engineering**

Don't use CQRS for simple applications.

## Related Patterns

- **Chapter 11 (Domain Events):** CQRS uses events for synchronization
- **Chapter 18 (Event Sourcing):** Often combined with CQRS
- **Chapter 14 (Repository):** Separate repositories for read/write

## Summary

CQRS separates read and write operations into different models, allowing independent optimization of each. Commands modify state through a write model, queries read from an optimized read model, and events synchronize the two.

Use CQRS for complex domains where read and write requirements differ significantly, when you need to scale reads and writes independently, or when you want to optimize each path separately. Skip CQRS for simple CRUD applications or when strong consistency is required.

## Further Reading

- Young, Greg. "CQRS Documents." cqrs.files.wordpress.com.
- Fowler, Martin. "CQRS." martinfowler.com.
- Vernon, Vaughn. *Implementing Domain-Driven Design*. Addison-Wesley, 2013.
- Richardson, Chris. *Microservices Patterns*. Manning, 2018.
- Microsoft. "CQRS pattern." docs.microsoft.com.
