# Chapter 16: Factory Pattern

## Introduction

The **Factory Pattern** encapsulates object creation logic, providing an interface for creating objects without specifying their exact classes. Instead of scattering `new User()` or complex construction logic throughout your code, factories centralize creation in one place.

This pattern is particularly useful when object creation involves complex logic, when you need to create different types of objects based on conditions, or when you want to hide implementation details from clients.

## The Problem

Complex object creation scattered throughout code leads to duplication and tight coupling.

**Symptoms:**
- Duplicate construction logic across codebase
- Hard to change how objects are created
- Client code knows too much about concrete classes
- Difficult to add new object types
- Validation and initialization logic repeated
- Tight coupling to specific implementations

**Example of the problem:**

```python
# User creation scattered everywhere with duplicate logic

def register_customer(name: str, email: str, password: str):
    """Register customer - creation logic here."""
    # Validation
    if not email or '@' not in email:
        raise ValueError("Invalid email")
    if len(password) < 8:
        raise ValueError("Password too short")
    
    # Hash password
    import hashlib
    hashed = hashlib.sha256(password.encode()).hexdigest()
    
    # Create user
    user = {
        'id': generate_id(),
        'name': name,
        'email': email,
        'password': hashed,
        'role': 'customer',
        'permissions': ['view_products', 'place_orders'],
        'created_at': datetime.now()
    }
    return user


def register_admin(name: str, email: str, password: str):
    """Register admin - DUPLICATE creation logic."""
    # Same validation copied
    if not email or '@' not in email:
        raise ValueError("Invalid email")
    if len(password) < 8:
        raise ValueError("Password too short")
    
    # Same hashing copied
    import hashlib
    hashed = hashlib.sha256(password.encode()).hexdigest()
    
    # Create admin - slightly different
    user = {
        'id': generate_id(),
        'name': name,
        'email': email,
        'password': hashed,
        'role': 'admin',  # Different role
        'permissions': ['view_products', 'place_orders', 'manage_users', 'view_reports'],  # Different permissions
        'created_at': datetime.now()
    }
    return user


def create_guest():
    """Create guest - more duplication."""
    user = {
        'id': generate_id(),
        'name': 'Guest',
        'email': None,
        'password': None,
        'role': 'guest',
        'permissions': ['view_products'],
        'created_at': datetime.now()
    }
    return user
```

**Problems:**
- Validation logic duplicated across functions
- Password hashing duplicated
- ID generation duplicated
- Changing how users are created requires modifying multiple places
- Adding new user type means more duplication
- Client code needs to know details about each user type

## The Pattern

**Factory Pattern:** Encapsulate object creation in a dedicated factory class or method.

### Types of Factories

**Simple Factory:** Single method that creates objects based on parameter
**Factory Method:** Subclasses decide which class to instantiate
**Abstract Factory:** Family of related objects

### Key Concepts

**Centralized Creation:** One place for object construction
**Encapsulation:** Hide creation complexity from clients
**Flexibility:** Easy to change how objects are created
**Type Safety:** Return interface/base class, hide concrete types

## Implementation

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from enum import Enum
import hashlib
import uuid


# =============================================================================
# DOMAIN - User Entities
# =============================================================================

class UserRole(Enum):
    GUEST = "guest"
    CUSTOMER = "customer"
    ADMIN = "admin"
    SUPPORT = "support"


@dataclass
class User:
    """Base user entity."""
    id: str
    name: str
    email: Optional[str]
    password_hash: Optional[str]
    role: UserRole
    permissions: List[str]
    created_at: datetime
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a permission."""
        return permission in self.permissions
    
    def __repr__(self):
        return f"User(id={self.id}, role={self.role.value}, permissions={len(self.permissions)})"


# =============================================================================
# FACTORY PATTERN - User Factory
# =============================================================================

class UserFactory:
    """
    Factory for creating users.
    
    Centralizes all user creation logic.
    """
    
    # Permission sets for each role
    ROLE_PERMISSIONS = {
        UserRole.GUEST: ['view_products'],
        UserRole.CUSTOMER: ['view_products', 'place_orders', 'view_orders'],
        UserRole.ADMIN: ['view_products', 'place_orders', 'view_orders', 'manage_users', 'view_reports'],
        UserRole.SUPPORT: ['view_products', 'view_orders', 'manage_orders', 'view_users']
    }
    
    @staticmethod
    def _generate_id() -> str:
        """Generate unique user ID."""
        return f"user-{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password securely."""
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def _validate_email(email: str) -> None:
        """Validate email format."""
        if not email or '@' not in email or '.' not in email:
            raise ValueError(f"Invalid email: {email}")
    
    @staticmethod
    def _validate_password(password: str) -> None:
        """Validate password strength."""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain digit")
    
    @classmethod
    def create_guest(cls) -> User:
        """
        Create guest user.
        
        No authentication required.
        """
        return User(
            id=cls._generate_id(),
            name="Guest",
            email=None,
            password_hash=None,
            role=UserRole.GUEST,
            permissions=cls.ROLE_PERMISSIONS[UserRole.GUEST].copy(),
            created_at=datetime.now()
        )
    
    @classmethod
    def create_customer(cls, name: str, email: str, password: str) -> User:
        """
        Create customer user.
        
        Args:
            name: Customer name
            email: Customer email (validated)
            password: Password (validated and hashed)
            
        Returns:
            Customer user
            
        Raises:
            ValueError: If validation fails
        """
        # Validate
        cls._validate_email(email)
        cls._validate_password(password)
        
        # Create
        return User(
            id=cls._generate_id(),
            name=name,
            email=email,
            password_hash=cls._hash_password(password),
            role=UserRole.CUSTOMER,
            permissions=cls.ROLE_PERMISSIONS[UserRole.CUSTOMER].copy(),
            created_at=datetime.now()
        )
    
    @classmethod
    def create_admin(cls, name: str, email: str, password: str) -> User:
        """
        Create admin user.
        
        Admins have full permissions.
        """
        cls._validate_email(email)
        cls._validate_password(password)
        
        return User(
            id=cls._generate_id(),
            name=name,
            email=email,
            password_hash=cls._hash_password(password),
            role=UserRole.ADMIN,
            permissions=cls.ROLE_PERMISSIONS[UserRole.ADMIN].copy(),
            created_at=datetime.now()
        )
    
    @classmethod
    def create_support(cls, name: str, email: str, password: str) -> User:
        """
        Create support user.
        
        Support staff have limited admin permissions.
        """
        cls._validate_email(email)
        cls._validate_password(password)
        
        return User(
            id=cls._generate_id(),
            name=name,
            email=email,
            password_hash=cls._hash_password(password),
            role=UserRole.SUPPORT,
            permissions=cls.ROLE_PERMISSIONS[UserRole.SUPPORT].copy(),
            created_at=datetime.now()
        )
    
    @classmethod
    def create_user(cls, role: UserRole, name: str, email: Optional[str] = None, password: Optional[str] = None) -> User:
        """
        Generic factory method - creates user based on role.
        
        Delegates to specific creation methods.
        """
        if role == UserRole.GUEST:
            return cls.create_guest()
        elif role == UserRole.CUSTOMER:
            if not email or not password:
                raise ValueError("Customer requires email and password")
            return cls.create_customer(name, email, password)
        elif role == UserRole.ADMIN:
            if not email or not password:
                raise ValueError("Admin requires email and password")
            return cls.create_admin(name, email, password)
        elif role == UserRole.SUPPORT:
            if not email or not password:
                raise ValueError("Support requires email and password")
            return cls.create_support(name, email, password)
        else:
            raise ValueError(f"Unknown role: {role}")


# =============================================================================
# ADVANCED: Factory Method Pattern
# =============================================================================

class AbstractUserFactory(ABC):
    """
    Abstract factory for creating users.
    
    Subclasses define how specific user types are created.
    """
    
    @abstractmethod
    def create_user(self, name: str, **kwargs) -> User:
        """Create a user."""
        pass


class CustomerFactory(AbstractUserFactory):
    """Factory specifically for customers."""
    
    def create_user(self, name: str, **kwargs) -> User:
        """Create customer with customer-specific logic."""
        email = kwargs.get('email')
        password = kwargs.get('password')
        
        if not email or not password:
            raise ValueError("Customer requires email and password")
        
        # Could add customer-specific initialization here
        return UserFactory.create_customer(name, email, password)


class AdminFactory(AbstractUserFactory):
    """Factory specifically for admins."""
    
    def create_user(self, name: str, **kwargs) -> User:
        """Create admin with admin-specific logic."""
        email = kwargs.get('email')
        password = kwargs.get('password')
        
        if not email or not password:
            raise ValueError("Admin requires email and password")
        
        # Could add admin-specific initialization here
        # E.g., send notification to other admins
        return UserFactory.create_admin(name, email, password)


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    print("=== Simple Factory Pattern ===\n")
    
    # Create different user types
    guest = UserFactory.create_guest()
    print(f"Guest: {guest}")
    print(f"  Permissions: {guest.permissions}\n")
    
    customer = UserFactory.create_customer("John Doe", "john@example.com", "SecurePass123")
    print(f"Customer: {customer}")
    print(f"  Can place orders? {customer.has_permission('place_orders')}")
    print(f"  Can manage users? {customer.has_permission('manage_users')}\n")
    
    admin = UserFactory.create_admin("Admin User", "admin@example.com", "AdminPass123")
    print(f"Admin: {admin}")
    print(f"  Permissions: {admin.permissions}\n")
    
    # Generic factory method
    support = UserFactory.create_user(UserRole.SUPPORT, "Support Agent", "support@example.com", "SupportPass123")
    print(f"Support: {support}")
    print(f"  Can view reports? {support.has_permission('view_reports')}")
    print(f"  Can manage orders? {support.has_permission('manage_orders')}\n")
    
    # Validation in action
    print("=== Validation ===\n")
    try:
        invalid_user = UserFactory.create_customer("Jane", "invalid-email", "weak")
    except ValueError as e:
        print(f"✗ Validation error: {e}\n")
    
    print("=== Factory Method Pattern ===\n")
    
    customer_factory = CustomerFactory()
    admin_factory = AdminFactory()
    
    customer2 = customer_factory.create_user("Jane Smith", email="jane@example.com", password="JanePass123")
    print(f"Customer from factory: {customer2}")
    
    admin2 = admin_factory.create_user("Super Admin", email="super@example.com", password="SuperPass123")
    print(f"Admin from factory: {admin2}")
```

## Explanation

### Centralized Creation

All user creation logic in one place:

```python
class UserFactory:
    @classmethod
    def create_customer(cls, name, email, password):
        # All validation here
        cls._validate_email(email)
        cls._validate_password(password)
        
        # All construction here
        return User(...)
```

### Encapsulated Complexity

Clients don't see validation, hashing, ID generation:

```python
# Client code is simple
customer = UserFactory.create_customer("John", "john@example.com", "SecurePass123")

# Factory handles:
# - Email validation
# - Password validation and hashing
# - ID generation
# - Permission assignment
# - Timestamp creation
```

### Easy to Extend

Add new user type without modifying existing code:

```python
# Add new user type
@classmethod
def create_premium_customer(cls, name, email, password):
    user = cls.create_customer(name, email, password)
    user.permissions.append('priority_support')
    user.permissions.append('early_access')
    return user
```

## Benefits

**1. Single Responsibility**

Object creation is separate from business logic.

**2. DRY Principle**

Validation and initialization logic in one place, not duplicated.

**3. Easy to Test**

Factory can be mocked or replaced with test version:

```python
class TestUserFactory:
    @classmethod
    def create_customer(cls, name, email, password):
        return User(...)  # No validation for tests
```

**4. Flexibility**

Change how objects are created without affecting clients.

**5. Encapsulation**

Hide complex creation logic from clients.

## Trade-offs

**When NOT to use factories:**

**1. Simple Objects**

For trivial construction, factories add complexity:

```python
# Overkill
ProductFactory.create_product(name, price)

# Just use constructor
Product(name, price)
```

**2. One Type**

If you only create one type, factory is unnecessary.

**3. Framework Constraints**

Some frameworks (Django, SQLAlchemy) have their own creation patterns.

**4. Overhead**

Factories add:
- Extra class to maintain
- Indirection
- More code to understand

## Testing

```python
import pytest


def test_create_guest():
    """Test guest creation."""
    guest = UserFactory.create_guest()
    
    assert guest.role == UserRole.GUEST
    assert guest.email is None
    assert guest.password_hash is None
    assert 'view_products' in guest.permissions
    assert 'place_orders' not in guest.permissions


def test_create_customer():
    """Test customer creation."""
    customer = UserFactory.create_customer("John", "john@example.com", "SecurePass123")
    
    assert customer.role == UserRole.CUSTOMER
    assert customer.name == "John"
    assert customer.email == "john@example.com"
    assert customer.password_hash is not None
    assert 'place_orders' in customer.permissions


def test_email_validation():
    """Test email validation."""
    with pytest.raises(ValueError, match="Invalid email"):
        UserFactory.create_customer("John", "invalid-email", "SecurePass123")


def test_password_validation():
    """Test password validation."""
    with pytest.raises(ValueError, match="at least 8 characters"):
        UserFactory.create_customer("John", "john@example.com", "weak")
    
    with pytest.raises(ValueError, match="uppercase letter"):
        UserFactory.create_customer("John", "john@example.com", "lowercase123")
    
    with pytest.raises(ValueError, match="digit"):
        UserFactory.create_customer("John", "john@example.com", "NoDigits")


def test_create_admin():
    """Test admin creation."""
    admin = UserFactory.create_admin("Admin", "admin@example.com", "AdminPass123")
    
    assert admin.role == UserRole.ADMIN
    assert 'manage_users' in admin.permissions
    assert 'view_reports' in admin.permissions


def test_generic_create_user():
    """Test generic factory method."""
    guest = UserFactory.create_user(UserRole.GUEST, "Guest")
    assert guest.role == UserRole.GUEST
    
    customer = UserFactory.create_user(UserRole.CUSTOMER, "John", "john@example.com", "SecurePass123")
    assert customer.role == UserRole.CUSTOMER


def test_password_hashing():
    """Test that passwords are hashed."""
    customer = UserFactory.create_customer("John", "john@example.com", "SecurePass123")
    
    assert customer.password_hash != "SecurePass123"
    assert len(customer.password_hash) == 64  # SHA256 hex length
```

## Common Mistakes

**1. Factory Doing Too Much**

Keep factories focused on creation:

```python
# Bad - factory doing business logic
class UserFactory:
    @classmethod
    def create_and_send_welcome_email(cls, name, email, password):
        user = cls.create_customer(name, email, password)
        send_email(user.email, "Welcome!")  # Not factory's job
        return user

# Good - factory just creates
class UserFactory:
    @classmethod
    def create_customer(cls, name, email, password):
        return User(...)

# Service handles business logic
user = UserFactory.create_customer(...)
email_service.send_welcome(user)
```

**2. Stateful Factories**

Factories should be stateless:

```python
# Bad - stateful factory
class UserFactory:
    def __init__(self):
        self.user_count = 0  # State!
    
    def create_user(self):
        self.user_count += 1
        return User(id=self.user_count)

# Good - stateless factory
class UserFactory:
    @staticmethod
    def create_user():
        return User(id=generate_id())
```

**3. Too Many Factory Methods**

If factory has 20 creation methods, consider multiple factories:

```python
# Bad - one factory for everything
class UserFactory:
    def create_customer(self): pass
    def create_premium_customer(self): pass
    def create_admin(self): pass
    def create_super_admin(self): pass
    # ... 20 more methods

# Good - separate factories
class CustomerFactory: pass
class AdminFactory: pass
```

## Related Patterns

- **Chapter 4 (Single Responsibility):** Factories separate creation from business logic
- **Chapter 8 (Dependency Inversion):** Factories can create objects implementing interfaces
- **Chapter 13 (Hexagonal Architecture):** Factories can create adapters
- **Chapter 14 (Repository):** Factories can work with repositories for persistence

## Summary

The Factory Pattern encapsulates object creation logic, providing a clean interface for creating objects without exposing construction details. It centralizes validation, initialization, and complex construction logic in one place.

Use factories when object creation involves complex logic, when you need different types of objects based on conditions, or when you want to hide implementation details. Skip factories for simple objects with trivial construction.

## Further Reading

- Gamma, Erich, et al. *Design Patterns: Elements of Reusable Object-Oriented Software*. Addison-Wesley, 1994. (Factory Method and Abstract Factory)
- Freeman, Eric, and Elisabeth Robson. *Head First Design Patterns*. O'Reilly, 2004.
- Martin, Robert C. *Clean Code*. Prentice Hall, 2008. (Chapter 9: Unit Tests)
- Fowler, Martin. "Constructor." refactoring.com.
- Bloch, Joshua. *Effective Java*. Addison-Wesley, 2018. (Item 1: Consider static factory methods)
