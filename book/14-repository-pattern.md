# Chapter 14: Repository Pattern

## Introduction

The **Repository Pattern** mediates between the domain and data mapping layers, acting like an in-memory collection of domain objects. It provides a clean separation between domain logic and data access code, making your application more testable and maintainable.

Instead of scattering database queries throughout your codebase, repositories centralize data access behind a well-defined interface. This allows you to swap database implementations, test with in-memory collections, and keep your domain logic independent of persistence concerns.

## The Problem

Direct database access mixed with business logic creates tight coupling and testing difficulties.

**Symptoms:**
- SQL queries scattered throughout business logic
- Can't test without a database
- Changing database requires modifying business code
- Duplicate query logic across the application
- Domain objects coupled to ORM frameworks
- Hard to maintain consistency in data access

**Example of the problem:**

```python
import sqlite3
from typing import List, Optional


class ProductService:
    """Business logic tightly coupled to SQLite."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def create_product(self, name: str, price: float, category: str):
        """Create product - mixed with SQL."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Business validation mixed with database code
        if price < 0:
            raise ValueError("Price cannot be negative")
        
        cursor.execute(
            'INSERT INTO products (name, price, category) VALUES (?, ?, ?)',
            (name, price, category)
        )
        product_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return product_id
    
    def get_product(self, product_id: int):
        """Get product - SQL in business layer."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {'id': row[0], 'name': row[1], 'price': row[2], 'category': row[3]}
        return None
    
    def find_by_category(self, category: str):
        """Query logic duplicated."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products WHERE category = ?', (category,))
        rows = cursor.fetchall()
        conn.close()
        
        return [{'id': r[0], 'name': r[1], 'price': r[2], 'category': r[3]} for r in rows]
    
    def apply_discount(self, product_id: int, discount_percent: float):
        """Business logic mixed with data access."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get product
        cursor.execute('SELECT price FROM products WHERE id = ?', (product_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            raise ValueError("Product not found")
        
        # Calculate new price (business logic)
        current_price = row[0]
        new_price = current_price * (1 - discount_percent / 100)
        
        # Update database
        cursor.execute('UPDATE products SET price = ? WHERE id = ?', (new_price, product_id))
        conn.commit()
        conn.close()
```

**Problems:**
- Can't test business logic without SQLite database
- Database connection code repeated everywhere
- Switching from SQLite to PostgreSQL requires changing all methods
- Business logic (validation, discount calculation) mixed with SQL
- No abstraction - directly coupled to sqlite3 module
- Hard to test edge cases (connection failures, etc.)

## The Pattern

**Repository Pattern:** Create an interface that provides collection-like access to domain objects, hiding all data access details.

### Key Concepts

**Repository Interface:** Abstract definition of data access operations
- `save(entity)` - Add or update
- `find_by_id(id)` - Retrieve by identifier
- `find_all()` - Retrieve all
- `delete(entity)` - Remove

**Repository Implementation:** Concrete data access code
- In-memory implementation for testing
- SQLite implementation for development
- PostgreSQL implementation for production

**Domain Objects:** Pure business entities, no database knowledge

### Structure

```
Domain Layer:
    Product (entity)
    ProductRepository (interface)

Infrastructure Layer:
    InMemoryProductRepository (implementation)
    SQLiteProductRepository (implementation)
    PostgreSQLProductRepository (implementation)
```

## Implementation

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from decimal import Decimal


# =============================================================================
# DOMAIN LAYER - Entities and Repository Interface
# =============================================================================

@dataclass
class Product:
    """
    Domain entity - pure business logic, no database knowledge.
    """
    id: Optional[str]
    name: str
    price: Decimal
    category: str
    in_stock: bool = True
    
    def __post_init__(self):
        # Business validation
        if self.price < 0:
            raise ValueError("Price cannot be negative")
        if not self.name.strip():
            raise ValueError("Name cannot be empty")
    
    def apply_discount(self, percent: Decimal) -> None:
        """Business logic: apply discount."""
        if percent < 0 or percent > 100:
            raise ValueError("Discount must be between 0 and 100")
        self.price = self.price * (1 - percent / 100)
    
    def mark_out_of_stock(self) -> None:
        """Business logic: mark as out of stock."""
        self.in_stock = False
    
    def __repr__(self):
        return f"Product(id={self.id}, name={self.name}, price={self.price})"


class ProductRepository(ABC):
    """
    Repository interface - defines what operations are available.
    
    Domain defines what it needs, infrastructure implements it.
    """
    
    @abstractmethod
    def save(self, product: Product) -> None:
        """Save a product (insert or update)."""
        pass
    
    @abstractmethod
    def find_by_id(self, product_id: str) -> Optional[Product]:
        """Find product by ID."""
        pass
    
    @abstractmethod
    def find_by_category(self, category: str) -> List[Product]:
        """Find all products in a category."""
        pass
    
    @abstractmethod
    def find_all(self) -> List[Product]:
        """Get all products."""
        pass
    
    @abstractmethod
    def delete(self, product: Product) -> None:
        """Delete a product."""
        pass
    
    @abstractmethod
    def find_in_stock(self) -> List[Product]:
        """Find all products in stock."""
        pass


# =============================================================================
# INFRASTRUCTURE LAYER - Repository Implementations
# =============================================================================

class InMemoryProductRepository(ProductRepository):
    """
    In-memory implementation for testing.
    
    No database required - perfect for tests.
    """
    
    def __init__(self):
        self._products: dict[str, Product] = {}
        self._next_id = 1
    
    def save(self, product: Product) -> None:
        """Save product to memory."""
        if product.id is None:
            product.id = str(self._next_id)
            self._next_id += 1
        self._products[product.id] = product
    
    def find_by_id(self, product_id: str) -> Optional[Product]:
        """Find by ID."""
        return self._products.get(product_id)
    
    def find_by_category(self, category: str) -> List[Product]:
        """Find by category."""
        return [p for p in self._products.values() if p.category == category]
    
    def find_all(self) -> List[Product]:
        """Get all products."""
        return list(self._products.values())
    
    def delete(self, product: Product) -> None:
        """Delete product."""
        if product.id and product.id in self._products:
            del self._products[product.id]
    
    def find_in_stock(self) -> List[Product]:
        """Find in-stock products."""
        return [p for p in self._products.values() if p.in_stock]


import sqlite3
from pathlib import Path


class SQLiteProductRepository(ProductRepository):
    """
    SQLite implementation for development/production.
    
    Encapsulates all SQL queries.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Create products table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price REAL NOT NULL,
                    category TEXT NOT NULL,
                    in_stock INTEGER NOT NULL
                )
            ''')
            conn.commit()
    
    def save(self, product: Product) -> None:
        """Save product to database."""
        with sqlite3.connect(self.db_path) as conn:
            if product.id is None:
                # Insert
                cursor = conn.execute(
                    'INSERT INTO products (name, price, category, in_stock) VALUES (?, ?, ?, ?)',
                    (product.name, float(product.price), product.category, int(product.in_stock))
                )
                product.id = str(cursor.lastrowid)
            else:
                # Update
                conn.execute(
                    'UPDATE products SET name=?, price=?, category=?, in_stock=? WHERE id=?',
                    (product.name, float(product.price), product.category, int(product.in_stock), product.id)
                )
            conn.commit()
    
    def find_by_id(self, product_id: str) -> Optional[Product]:
        """Find product by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT id, name, price, category, in_stock FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            
            if row:
                return Product(
                    id=str(row[0]),
                    name=row[1],
                    price=Decimal(str(row[2])),
                    category=row[3],
                    in_stock=bool(row[4])
                )
            return None
    
    def find_by_category(self, category: str) -> List[Product]:
        """Find products by category."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT id, name, price, category, in_stock FROM products WHERE category = ?', (category,))
            rows = cursor.fetchall()
            
            return [
                Product(str(r[0]), r[1], Decimal(str(r[2])), r[3], bool(r[4]))
                for r in rows
            ]
    
    def find_all(self) -> List[Product]:
        """Get all products."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT id, name, price, category, in_stock FROM products')
            rows = cursor.fetchall()
            
            return [
                Product(str(r[0]), r[1], Decimal(str(r[2])), r[3], bool(r[4]))
                for r in rows
            ]
    
    def delete(self, product: Product) -> None:
        """Delete product."""
        if product.id:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('DELETE FROM products WHERE id = ?', (product.id,))
                conn.commit()
    
    def find_in_stock(self) -> List[Product]:
        """Find in-stock products."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT id, name, price, category, in_stock FROM products WHERE in_stock = 1')
            rows = cursor.fetchall()
            
            return [
                Product(str(r[0]), r[1], Decimal(str(r[2])), r[3], bool(r[4]))
                for r in rows
            ]


# =============================================================================
# APPLICATION LAYER - Use Cases
# =============================================================================

class ProductCatalogService:
    """
    Application service using repository.
    
    Pure business logic - no database knowledge.
    """
    
    def __init__(self, product_repository: ProductRepository):
        self.products = product_repository
    
    def add_product(self, name: str, price: Decimal, category: str) -> Product:
        """Add new product to catalog."""
        product = Product(
            id=None,
            name=name,
            price=price,
            category=category
        )
        self.products.save(product)
        return product
    
    def apply_seasonal_discount(self, category: str, discount: Decimal) -> int:
        """Apply discount to all products in a category."""
        products = self.products.find_by_category(category)
        
        for product in products:
            product.apply_discount(discount)
            self.products.save(product)
        
        return len(products)
    
    def get_available_products(self) -> List[Product]:
        """Get all in-stock products."""
        return self.products.find_in_stock()
    
    def discontinue_product(self, product_id: str) -> None:
        """Mark product as out of stock."""
        product = self.products.find_by_id(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        product.mark_out_of_stock()
        self.products.save(product)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    print("=== Using In-Memory Repository (for testing) ===\n")
    
    # In-memory for tests
    repo = InMemoryProductRepository()
    catalog = ProductCatalogService(repo)
    
    # Add products
    product1 = catalog.add_product("Laptop", Decimal("999.99"), "Electronics")
    product2 = catalog.add_product("Mouse", Decimal("29.99"), "Electronics")
    product3 = catalog.add_product("Desk", Decimal("299.99"), "Furniture")
    
    print(f"Added: {product1}")
    print(f"Added: {product2}")
    print(f"Added: {product3}\n")
    
    # Apply discount
    discounted = catalog.apply_seasonal_discount("Electronics", Decimal("10"))
    print(f"Applied 10% discount to {discounted} products\n")
    
    # Get available products
    available = catalog.get_available_products()
    print(f"Available products: {len(available)}")
    for p in available:
        print(f"  - {p.name}: ${p.price}")
    
    print("\n=== Using SQLite Repository (for production) ===\n")
    
    # SQLite for production
    sqlite_repo = SQLiteProductRepository("/tmp/products.db")
    catalog2 = ProductCatalogService(sqlite_repo)
    
    # Add product
    product4 = catalog2.add_product("Chair", Decimal("149.99"), "Furniture")
    print(f"Saved to database: {product4}")
    
    # Retrieve from database
    retrieved = sqlite_repo.find_by_id(product4.id)
    print(f"Retrieved from database: {retrieved}")
    
    # Find by category
    furniture = sqlite_repo.find_by_category("Furniture")
    print(f"\nFurniture items in database: {len(furniture)}")
    for item in furniture:
        print(f"  - {item.name}: ${item.price}")
```

## Explanation

### Repository Interface

The `ProductRepository` interface defines what operations are available:

```python
class ProductRepository(ABC):
    @abstractmethod
    def save(self, product: Product) -> None:
        pass
    
    @abstractmethod
    def find_by_id(self, product_id: str) -> Optional[Product]:
        pass
```

This is the contract. Domain and application layers depend on this interface, not concrete implementations.

### Multiple Implementations

Same interface, different storage:

```python
# Testing: In-memory
repo = InMemoryProductRepository()

# Development: SQLite
repo = SQLiteProductRepository("/tmp/products.db")

# Production: PostgreSQL (could be implemented)
repo = PostgreSQLProductRepository("postgresql://...")
```

Business logic works with all of them.

### Domain Independence

The `Product` entity has no database knowledge:

```python
@dataclass
class Product:
    id: Optional[str]
    name: str
    price: Decimal
    
    def apply_discount(self, percent: Decimal):
        # Pure business logic
        self.price = self.price * (1 - percent / 100)
```

No SQLAlchemy decorators, no database fields - just business logic.

### Application Layer Simplicity

The service works with repositories, not databases:

```python
class ProductCatalogService:
    def __init__(self, product_repository: ProductRepository):
        self.products = product_repository  # Interface, not implementation
    
    def apply_seasonal_discount(self, category: str, discount: Decimal):
        products = self.products.find_by_category(category)
        for product in products:
            product.apply_discount(discount)
            self.products.save(product)
```

No SQL, no connection management - just business operations.

## Benefits

**1. Testability**

Test business logic without a database:

```python
def test_apply_discount():
    repo = InMemoryProductRepository()  # No database needed
    service = ProductCatalogService(repo)
    
    service.add_product("Item", Decimal("100"), "Test")
    service.apply_seasonal_discount("Test", Decimal("10"))
    
    products = repo.find_by_category("Test")
    assert products[0].price == Decimal("90")
```

**2. Flexibility**

Swap implementations without changing business logic:

```python
# Development
dev_repo = InMemoryProductRepository()

# Production
prod_repo = PostgreSQLProductRepository(...)

# Same service works with both
service = ProductCatalogService(dev_repo)  # or prod_repo
```

**3. Centralized Data Access**

All SQL in one place. Need to optimize a query? Change one method in one class.

**4. Domain Purity**

Domain entities don't know about persistence. Clean separation of concerns.

**5. Maintainability**

Clear boundaries make code easier to understand and modify.

## Trade-offs

**When NOT to use the repository pattern:**

**1. Simple CRUD Applications**

For basic data entry with no business logic, repositories add unnecessary complexity:

```python
# Overkill for simple CRUD
# Just use the ORM directly
product = Product.objects.get(id=product_id)
```

**2. Reporting/Analytics**

Complex queries with joins, aggregations are awkward with repositories:

```python
# Bad fit for repository
SELECT category, COUNT(*), AVG(price) 
FROM products 
GROUP BY category
HAVING COUNT(*) > 10

# Better to use direct SQL or query builder
```

**3. Performance-Critical Paths**

Repositories add abstraction overhead. For tight loops or performance-critical code, direct database access might be faster.

**4. Overhead**

Repositories add:
- More classes and interfaces
- Indirection
- Need to think about abstraction boundaries

## Testing

```python
import pytest
from decimal import Decimal


def test_save_and_find_product():
    """Test saving and retrieving products."""
    repo = InMemoryProductRepository()
    
    product = Product(None, "Test Product", Decimal("99.99"), "Test")
    repo.save(product)
    
    assert product.id is not None
    
    found = repo.find_by_id(product.id)
    assert found is not None
    assert found.name == "Test Product"
    assert found.price == Decimal("99.99")


def test_find_by_category():
    """Test finding products by category."""
    repo = InMemoryProductRepository()
    
    repo.save(Product(None, "Item 1", Decimal("10"), "Electronics"))
    repo.save(Product(None, "Item 2", Decimal("20"), "Electronics"))
    repo.save(Product(None, "Item 3", Decimal("30"), "Furniture"))
    
    electronics = repo.find_by_category("Electronics")
    
    assert len(electronics) == 2
    assert all(p.category == "Electronics" for p in electronics)


def test_update_product():
    """Test updating existing product."""
    repo = InMemoryProductRepository()
    
    product = Product(None, "Original", Decimal("100"), "Test")
    repo.save(product)
    
    # Modify and save again
    product.name = "Updated"
    product.price = Decimal("150")
    repo.save(product)
    
    # Verify update
    found = repo.find_by_id(product.id)
    assert found.name == "Updated"
    assert found.price == Decimal("150")


def test_delete_product():
    """Test deleting products."""
    repo = InMemoryProductRepository()
    
    product = Product(None, "To Delete", Decimal("50"), "Test")
    repo.save(product)
    
    product_id = product.id
    repo.delete(product)
    
    assert repo.find_by_id(product_id) is None


def test_find_in_stock():
    """Test finding in-stock products."""
    repo = InMemoryProductRepository()
    
    product1 = Product(None, "In Stock", Decimal("100"), "Test", in_stock=True)
    product2 = Product(None, "Out of Stock", Decimal("100"), "Test", in_stock=False)
    
    repo.save(product1)
    repo.save(product2)
    
    in_stock = repo.find_in_stock()
    
    assert len(in_stock) == 1
    assert in_stock[0].name == "In Stock"


def test_catalog_service_apply_discount():
    """Test applying discount through service."""
    repo = InMemoryProductRepository()
    service = ProductCatalogService(repo)
    
    service.add_product("Item 1", Decimal("100"), "Electronics")
    service.add_product("Item 2", Decimal("200"), "Electronics")
    service.add_product("Item 3", Decimal("300"), "Furniture")
    
    count = service.apply_seasonal_discount("Electronics", Decimal("10"))
    
    assert count == 2
    
    electronics = repo.find_by_category("Electronics")
    assert electronics[0].price == Decimal("90")
    assert electronics[1].price == Decimal("180")


def test_discontinue_product():
    """Test marking product as out of stock."""
    repo = InMemoryProductRepository()
    service = ProductCatalogService(repo)
    
    product = service.add_product("Item", Decimal("100"), "Test")
    
    service.discontinue_product(product.id)
    
    updated = repo.find_by_id(product.id)
    assert updated.in_stock is False
```

## Common Mistakes

**1. Repositories That Return DTOs**

Repositories should return domain entities, not data transfer objects:

```python
# Bad - returns dictionary
def find_by_id(self, id: str) -> dict:
    return {'id': id, 'name': 'Product'}

# Good - returns domain entity
def find_by_id(self, id: str) -> Optional[Product]:
    return Product(id, 'Product', Decimal('10'), 'Category')
```

**2. Business Logic in Repository**

Keep business logic in domain entities, not repositories:

```python
# Bad - business logic in repository
class ProductRepository:
    def apply_discount(self, product_id, percent):
        product = self.find_by_id(product_id)
        product.price *= (1 - percent/100)  # Business logic!
        self.save(product)

# Good - repository just handles persistence
class Product:
    def apply_discount(self, percent):  # Business logic in entity
        self.price *= (1 - percent/100)

# Service orchestrates
service.get_product(id).apply_discount(10)
repo.save(product)
```

**3. Generic Repository**

Don't create one repository for all entities:

```python
# Bad - generic repository
class GenericRepository:
    def save(self, entity): pass
    def find(self, id): pass

# Good - specific repositories
class ProductRepository:
    def find_by_category(self, category): pass  # Product-specific

class CustomerRepository:
    def find_by_email(self, email): pass  # Customer-specific
```

**4. Leaking Infrastructure**

Don't let repository interface leak database details:

```python
# Bad - SQL in interface
class ProductRepository(ABC):
    @abstractmethod
    def execute_query(self, sql: str, params: tuple):
        pass

# Good - domain concepts in interface
class ProductRepository(ABC):
    @abstractmethod
    def find_by_category(self, category: str):
        pass
```

## Related Patterns

- **Chapter 8 (Dependency Inversion):** Repositories implement DIP
- **Chapter 13 (Hexagonal Architecture):** Repositories are secondary adapters
- **Chapter 15 (Unit of Work):** Often used together with repositories
- **Chapter 17 (CQRS):** Separate repositories for reads and writes

## Summary

The Repository Pattern provides a collection-like interface for accessing domain objects, hiding all persistence details. It separates domain logic from data access code, making applications more testable and maintainable.

Use repositories when you have significant business logic that needs to be independent of database details, when you need to support multiple storage backends, or when testability is important. Skip repositories for simple CRUD apps, complex reporting queries, or when the abstraction overhead outweighs the benefits.

## Further Reading

- Fowler, Martin. *Patterns of Enterprise Application Architecture*. Addison-Wesley, 2002. (Repository pattern)
- Evans, Eric. *Domain-Driven Design*. Addison-Wesley, 2003. (Chapter 6: Repositories)
- Vernon, Vaughn. *Implementing Domain-Driven Design*. Addison-Wesley, 2013.
- Microsoft. "The Repository Pattern." docs.microsoft.com.
- Nilsson, Jimmy. *Applying Domain-Driven Design and Patterns*. Addison-Wesley, 2006.
