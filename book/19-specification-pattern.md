# Chapter 19: Specification Pattern

## Introduction

The **Specification Pattern** encapsulates business rules into reusable, composable objects. Instead of scattering conditional logic throughout your code, specifications make business rules explicit, testable, and combinable using AND, OR, and NOT operations.

A specification represents a single business rule that can be evaluated against an object. Specifications can be combined to create complex filtering logic while keeping each rule simple and maintainable.

## The Problem

Business rules scattered as conditional logic are hard to reuse and maintain.

**Symptoms:**
- Duplicate filtering logic across codebase
- Complex nested if statements
- Hard to test business rules in isolation
- Can't reuse rules in different contexts
- Difficult to combine rules dynamically
- Business logic mixed with query code

**Example of the problem:**

```python
def find_products(products, min_price=None, max_price=None, 
                  category=None, in_stock=None, featured=None):
    """Filter products - complex nested logic."""
    results = []
    
    for product in products:
        # Complex nested conditions
        if min_price and product.price < min_price:
            continue
        if max_price and product.price > max_price:
            continue
        if category and product.category != category:
            continue
        if in_stock is not None and product.in_stock != in_stock:
            continue
        if featured is not None and product.featured != featured:
            continue
        
        results.append(product)
    
    return results
```

**Problems:**
- Can't reuse individual rules
- Hard to test price range logic separately
- Can't combine rules dynamically
- Adding new criteria requires modifying function
- Business rules not explicit

## The Pattern

**Specification:** Encapsulate business rules in objects that can be composed using AND, OR, NOT.

### Key Concepts

**Specification:** Interface with `is_satisfied_by(item)` method
**Composite Specifications:** AND, OR, NOT combinations
**Reusable Rules:** Single responsibility per specification
**Type Safety:** Specifications work with specific types

## Implementation

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from dataclasses import dataclass
from decimal import Decimal


T = TypeVar('T')


class Specification(ABC, Generic[T]):
    """
    Base specification interface.
    
    Specifications can be combined using and_, or_, not_.
    """
    
    @abstractmethod
    def is_satisfied_by(self, item: T) -> bool:
        """Check if item satisfies this specification."""
        pass
    
    def and_(self, other: 'Specification[T]') -> 'Specification[T]':
        """Combine with AND logic."""
        return AndSpecification(self, other)
    
    def or_(self, other: 'Specification[T]') -> 'Specification[T]':
        """Combine with OR logic."""
        return OrSpecification(self, other)
    
    def not_(self) -> 'Specification[T]':
        """Negate this specification."""
        return NotSpecification(self)


class AndSpecification(Specification[T]):
    """Combines two specifications with AND."""
    
    def __init__(self, left: Specification[T], right: Specification[T]):
        self.left = left
        self.right = right
    
    def is_satisfied_by(self, item: T) -> bool:
        return self.left.is_satisfied_by(item) and self.right.is_satisfied_by(item)


class OrSpecification(Specification[T]):
    """Combines two specifications with OR."""
    
    def __init__(self, left: Specification[T], right: Specification[T]):
        self.left = left
        self.right = right
    
    def is_satisfied_by(self, item: T) -> bool:
        return self.left.is_satisfied_by(item) or self.right.is_satisfied_by(item)


class NotSpecification(Specification[T]):
    """Negates a specification."""
    
    def __init__(self, spec: Specification[T]):
        self.spec = spec
    
    def is_satisfied_by(self, item: T) -> bool:
        return not self.spec.is_satisfied_by(item)


# Domain Model
@dataclass
class Product:
    id: str
    name: str
    price: Decimal
    category: str
    in_stock: bool
    featured: bool


# Concrete Specifications
class PriceRangeSpecification(Specification[Product]):
    """Product price within range."""
    
    def __init__(self, min_price: Decimal, max_price: Decimal):
        self.min_price = min_price
        self.max_price = max_price
    
    def is_satisfied_by(self, product: Product) -> bool:
        return self.min_price <= product.price <= self.max_price


class CategorySpecification(Specification[Product]):
    """Product in specific category."""
    
    def __init__(self, category: str):
        self.category = category
    
    def is_satisfied_by(self, product: Product) -> bool:
        return product.category == self.category


class InStockSpecification(Specification[Product]):
    """Product is in stock."""
    
    def is_satisfied_by(self, product: Product) -> bool:
        return product.in_stock


class FeaturedSpecification(Specification[Product]):
    """Product is featured."""
    
    def is_satisfied_by(self, product: Product) -> bool:
        return product.featured


class ProductRepository:
    """Repository with specification-based filtering."""
    
    def __init__(self, products: list[Product]):
        self._products = products
    
    def find(self, spec: Specification[Product]) -> list[Product]:
        """Find products matching specification."""
        return [p for p in self._products if spec.is_satisfied_by(p)]


# Usage Example
if __name__ == "__main__":
    print("=== Specification Pattern Demo ===\n")
    
    # Sample products
    products = [
        Product("1", "Laptop", Decimal("999"), "Electronics", True, True),
        Product("2", "Mouse", Decimal("29"), "Electronics", True, False),
        Product("3", "Desk", Decimal("299"), "Furniture", False, False),
        Product("4", "Chair", Decimal("199"), "Furniture", True, True),
    ]
    
    repo = ProductRepository(products)
    
    # Simple specification
    print("1. In-stock products:")
    in_stock = InStockSpecification()
    results = repo.find(in_stock)
    for p in results:
        print(f"   {p.name} - ${p.price}")
    print()
    
    # Composed specification (AND)
    print("2. Featured Electronics:")
    spec = CategorySpecification("Electronics").and_(FeaturedSpecification())
    results = repo.find(spec)
    for p in results:
        print(f"   {p.name}")
    print()
    
    # Complex specification
    print("3. Affordable in-stock items ($0-$200):")
    spec = (PriceRangeSpecification(Decimal("0"), Decimal("200"))
            .and_(InStockSpecification()))
    results = repo.find(spec)
    for p in results:
        print(f"   {p.name} - ${p.price}")
    print()
    
    # Using NOT
    print("4. Non-featured items:")
    spec = FeaturedSpecification().not_()
    results = repo.find(spec)
    for p in results:
        print(f"   {p.name}")
