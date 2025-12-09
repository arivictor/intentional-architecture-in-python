# Appendix A: Factory Pattern for Complex Creation

## The Problem: Creating Domain Objects Is Complex

In Chapter 5, we built rich domain models. Entities like `Member` and `FitnessClass` enforce their own invariants. Value objects like `EmailAddress` and `TimeSlot` make invalid states impossible. But we left an important question unanswered: how do you actually create these objects?

Consider creating a new premium member:

```python
# Somewhere in your application code
email = EmailAddress("sarah@example.com")
premium_membership = MembershipType.PREMIUM
member = Member("M001", "Sarah", email, premium_membership)
```

This works for simple cases. But real creation is rarely this simple. What if:

- Email addresses need to be validated against a blacklist or verified via an external service
- Member IDs need to be generated using a specific algorithm or fetched from a sequence
- Premium members get different initial credits than basic members
- New members get a welcome bonus that imported legacy members don't
- Creation needs to trigger side effects like sending welcome emails or logging events
- Different creation contexts have different validation rules (signup vs admin creation vs data import)

If you scatter this logic across your codebase—some in controllers, some in use cases, some in the domain—you end up with inconsistent creation. Different parts of the system create members differently. Business rules get duplicated. The domain's invariants aren't consistently enforced.

**This is the problem that factory patterns solve.** They centralize complex object creation, ensuring consistency and keeping the creation logic organized.

## What Is a Factory?

A factory is an object that knows how to create other objects. Instead of calling constructors directly, you delegate to a factory that handles the complexity.

Factories exist in two main forms:

1. **Static factory methods** - Class methods that create instances
2. **Factory classes** - Dedicated objects whose job is to create other objects

Both solve the same problem: separating the complexity of creation from the object being created. They give you a single place to handle validation, default values, ID generation, and coordination across multiple objects.

## Static Factory Methods

The simplest factory is a static method on the class itself. Python uses `@classmethod` for this:

```python
from datetime import datetime, timedelta
from typing import Optional


class Member:
    def __init__(self, member_id: str, name: str, email: EmailAddress, 
                 membership_type: MembershipType):
        if not member_id:
            raise ValueError("Member ID is required")
        if not name or not name.strip():
            raise ValueError("Member name cannot be empty")
        
        self._id = member_id
        self._name = name
        self._email = email
        self._membership_type = membership_type
        self._credits = membership_type.credits_per_month
        self._credits_expiry: Optional[datetime] = None
        self._joined_at = datetime.now()
    
    @classmethod
    def create_premium(cls, member_id: str, name: str, email_str: str):
        """Factory method for creating premium members with bonus credits."""
        email = EmailAddress(email_str)
        membership = MembershipType.PREMIUM
        member = cls(member_id, name, email, membership)
        
        # Premium members get a 5-credit welcome bonus
        member.add_credits(5, expiry_days=30)
        
        return member
    
    @classmethod
    def create_basic(cls, member_id: str, name: str, email_str: str):
        """Factory method for creating basic members."""
        email = EmailAddress(email_str)
        membership = MembershipType.BASIC
        return cls(member_id, name, email, membership)
    
    @classmethod
    def from_legacy_data(cls, legacy_id: str, legacy_record: dict):
        """Factory method for importing members from legacy system."""
        # Legacy system used different field names
        email = EmailAddress(legacy_record["email_address"])
        
        # Map legacy membership tier to new types
        tier = legacy_record.get("tier", "BASIC")
        if tier == "GOLD":
            membership = MembershipType.PREMIUM
        else:
            membership = MembershipType.BASIC
        
        member = cls(
            member_id=f"LEGACY-{legacy_id}",
            name=legacy_record["full_name"],
            email=email,
            membership_type=membership
        )
        
        # Imported members don't get welcome bonuses
        # Set join date from legacy data if available
        if "join_date" in legacy_record:
            member._joined_at = legacy_record["join_date"]
        
        return member
    
    # ... rest of Member implementation
```

Notice what happened. The constructor (`__init__`) stayed simple. It just validates and assigns fields. The factory methods handle the complexity:

- `create_premium()` knows about welcome bonuses
- `create_basic()` uses different defaults
- `from_legacy_data()` handles data transformation and mapping

Each factory method returns a properly constructed `Member`. The caller doesn't need to know about `EmailAddress` construction, membership types, or credit allocation. The factory encapsulates that knowledge.

**When to use static factory methods:**

- Creation logic is closely tied to the class itself
- You have multiple ways to construct the same object (premium vs basic members)
- You want to give creation a meaningful name (`create_premium` is clearer than `Member(..., premium=True)`)
- The factory doesn't need external dependencies (like a database or ID generator)

Static factory methods work well for simple cases. But they have limitations. They can't have dependencies injected easily. They're tied to a single class. If creation becomes more complex—requiring coordination across multiple objects or external services—you need something more powerful.

## Factory Classes

A factory class is a standalone object whose sole purpose is creating other objects. Unlike static factory methods, factory classes can have dependencies, state, and complex logic.

Here's a `MemberFactory` that handles ID generation and email verification:

```python
from typing import Protocol
from datetime import datetime


class EmailVerifier(Protocol):
    """Port for email verification service."""
    def is_valid(self, email: str) -> bool:
        ...
    
    def is_blacklisted(self, email: str) -> bool:
        ...


class MemberIdGenerator(Protocol):
    """Port for generating unique member IDs."""
    def generate(self) -> str:
        ...


class MemberFactory:
    """Factory for creating Member aggregates with validation and ID generation."""
    
    def __init__(self, id_generator: MemberIdGenerator, 
                 email_verifier: EmailVerifier):
        self._id_generator = id_generator
        self._email_verifier = email_verifier
    
    def create_premium_member(self, name: str, email_str: str) -> Member:
        """Create a new premium member with validation."""
        # Validate email through external service
        if not self._email_verifier.is_valid(email_str):
            raise InvalidEmailException(f"Email address {email_str} is invalid")
        
        if self._email_verifier.is_blacklisted(email_str):
            raise BlacklistedEmailException(
                f"Email address {email_str} is blacklisted"
            )
        
        # Generate unique ID
        member_id = self._id_generator.generate()
        
        # Create the member using the static factory method
        member = Member.create_premium(member_id, name, email_str)
        
        return member
    
    def create_basic_member(self, name: str, email_str: str) -> Member:
        """Create a new basic member with validation."""
        if not self._email_verifier.is_valid(email_str):
            raise InvalidEmailException(f"Email address {email_str} is invalid")
        
        if self._email_verifier.is_blacklisted(email_str):
            raise BlacklistedEmailException(
                f"Email address {email_str} is blacklisted"
            )
        
        member_id = self._id_generator.generate()
        member = Member.create_basic(member_id, name, email_str)
        
        return member
    
    def import_from_legacy(self, legacy_id: str, legacy_record: dict) -> Member:
        """Import a member from the legacy system without validation."""
        # Legacy imports skip email verification since the data is historical
        # But we still generate a new ID for our system
        member = Member.from_legacy_data(legacy_id, legacy_record)
        
        return member


class InvalidEmailException(Exception):
    """Raised when email validation fails."""
    pass


class BlacklistedEmailException(Exception):
    """Raised when email is on the blacklist."""
    pass
```

The factory class has clear advantages over static factory methods:

1. **Dependencies are explicit** - The factory receives `EmailVerifier` and `MemberIdGenerator` through its constructor. These can be mocked in tests or swapped for different implementations.

2. **Separation of concerns** - The `Member` entity doesn't need to know about email verification or ID generation. The factory handles infrastructure concerns while the entity focuses on business logic.

3. **Testability** - You can test the factory with mock dependencies. You can test member creation without actually calling an email verification service.

4. **Reusability** - The same factory can be used across multiple use cases. Every part of your system that creates members uses the same logic.

**When to use factory classes:**

- Creation requires external dependencies (databases, ID generators, external services)
- Creation logic is complex enough to deserve its own object
- You need to test creation independently of the objects being created
- Multiple objects need to be created together in a coordinated way
- Creation rules change frequently and need to be isolated

## Where Factories Live: Domain vs Application

One of the trickiest questions with factories is: where do they belong? Domain layer or application layer?

The answer depends on what the factory does.

### Domain Factories

A factory belongs in the **domain layer** when it creates domain objects using only domain concepts. No infrastructure. No external services. Just pure business logic.

The static factory methods we added to `Member` are domain factories. They live on the domain entity itself. They use domain concepts like `MembershipType` and credit allocation rules. They enforce business invariants.

A domain service factory might look like this:

```python
# domain/factories/class_factory.py

class FitnessClassFactory:
    """Domain factory for creating classes with business rules."""
    
    def create_yoga_class(self, class_id: str, time_slot: TimeSlot) -> FitnessClass:
        """Create a yoga class with standard capacity."""
        capacity = ClassCapacity(20)  # Yoga classes standard capacity
        return FitnessClass(class_id, "Yoga", capacity, time_slot)
    
    def create_spinning_class(self, class_id: str, time_slot: TimeSlot) -> FitnessClass:
        """Create a spinning class with smaller capacity."""
        capacity = ClassCapacity(15)  # Spinning classes have fewer bikes
        return FitnessClass(class_id, "Spinning", capacity, time_slot)
    
    def create_pilates_class(self, class_id: str, time_slot: TimeSlot) -> FitnessClass:
        """Create a pilates class with limited capacity."""
        capacity = ClassCapacity(12)  # Pilates needs more space per person
        return FitnessClass(class_id, "Pilates", capacity, time_slot)
```

This factory encapsulates domain knowledge: different class types have different standard capacities. It doesn't depend on infrastructure. It doesn't generate IDs. It just applies business rules to creation.

**Domain factories live in the domain layer when:**

- They only use domain concepts (entities, value objects, domain services)
- They don't depend on infrastructure (databases, external APIs, ID generators)
- They encode business rules about creation
- They could be tested with nothing but the domain layer

### Application Factories

A factory belongs in the **application layer** when it coordinates domain creation with infrastructure concerns.

The `MemberFactory` we built earlier is an application factory. It uses domain concepts (Member, EmailAddress) but also depends on infrastructure (EmailVerifier, MemberIdGenerator). It bridges the gap between domain and infrastructure.

Application factories live in the application layer because they orchestrate. They call domain factories, fetch data from repositories, invoke external services, and coordinate across aggregates.

```python
# application/factories/booking_factory.py

class BookingFactory:
    """Application factory for creating bookings with full validation."""
    
    def __init__(self, 
                 member_repository: MemberRepository,
                 class_repository: ClassRepository,
                 booking_id_generator: BookingIdGenerator):
        self._member_repo = member_repository
        self._class_repo = class_repository
        self._id_generator = booking_id_generator
    
    def create_booking(self, member_id: str, class_id: str) -> Booking:
        """
        Create a booking with full validation across aggregates.
        
        Checks:
        - Member exists and has credits
        - Class exists and has capacity
        - Member doesn't have conflicting bookings
        """
        # Load aggregates from repositories
        member = self._member_repo.get(member_id)
        if not member:
            raise MemberNotFoundException(f"Member {member_id} not found")
        
        fitness_class = self._class_repo.get(class_id)
        if not fitness_class:
            raise ClassNotFoundException(f"Class {class_id} not found")
        
        # Validate business rules
        if member.credits <= 0:
            raise InsufficientCreditsException(
                f"Member {member.name} has no credits"
            )
        
        if fitness_class.is_full():
            raise ClassFullException(f"Class {fitness_class.name} is full")
        
        # Check for time conflicts (requires loading member's other bookings)
        member_bookings = self._member_repo.get_bookings(member_id)
        for booking in member_bookings:
            other_class = self._class_repo.get(booking.class_id)
            if fitness_class.conflicts_with(other_class):
                raise TimeConflictException(
                    f"Member has conflicting booking at {other_class.time_slot}"
                )
        
        # Generate ID and create booking
        booking_id = self._id_generator.generate()
        booking = Booking(booking_id, member_id, class_id)
        
        return booking


class MemberNotFoundException(Exception):
    pass


class ClassNotFoundException(Exception):
    pass


class TimeConflictException(Exception):
    pass
```

This factory coordinates across multiple aggregates. It loads data from repositories. It validates rules that span multiple objects. It's orchestration, not pure domain logic. So it lives in the application layer.

**Application factories live in the application layer when:**

- They depend on repositories or infrastructure services
- They coordinate creation across multiple aggregates
- They enforce application-level policies (not just domain rules)
- They need access to external systems or databases

### The Layering Principle

The dependency rule from Chapter 4 still applies. Application factories can depend on domain factories. But domain factories cannot depend on application factories.

```
Application Layer
    ↓ depends on
Domain Layer
```

This means:

- Application factories can call domain factory methods
- Application factories can instantiate domain entities
- Domain factories should know nothing about repositories or infrastructure

Keep this boundary clear. Don't let infrastructure concerns leak into domain factories. And don't duplicate domain creation logic in application factories—call domain factories when you need pure domain creation.

## Testing Factories

Factories are code, so they need tests. But testing factories is different from testing entities.

### Testing Domain Factories

Domain factories are pure domain logic. Test them like any other domain object:

```python
# tests/domain/test_member_factory.py

import pytest
from domain.entities import Member
from domain.value_objects import EmailAddress, MembershipType


class TestMemberFactoryMethods:
    """Test the static factory methods on Member."""
    
    def test_create_premium_includes_welcome_bonus(self):
        """Premium members should get 5 bonus credits."""
        member = Member.create_premium("M001", "Sarah", "sarah@example.com")
        
        assert member.id == "M001"
        assert member.name == "Sarah"
        assert member.email.value == "sarah@example.com"
        # Premium base credits (20) + welcome bonus (5) = 25
        assert member.credits == 25
        assert member.membership_type == MembershipType.PREMIUM
    
    def test_create_basic_no_bonus(self):
        """Basic members should not get a welcome bonus."""
        member = Member.create_basic("M002", "John", "john@example.com")
        
        assert member.credits == 10  # Just base credits, no bonus
        assert member.membership_type == MembershipType.BASIC
    
    def test_from_legacy_data_maps_gold_to_premium(self):
        """Legacy GOLD tier should map to Premium membership."""
        legacy_record = {
            "full_name": "Jane Doe",
            "email_address": "jane@example.com",
            "tier": "GOLD"
        }
        
        member = Member.from_legacy_data("L123", legacy_record)
        
        assert member.id == "LEGACY-L123"
        assert member.name == "Jane Doe"
        assert member.membership_type == MembershipType.PREMIUM
        # No welcome bonus for imported members
        assert member.credits == 20
    
    def test_from_legacy_data_maps_basic_to_basic(self):
        """Legacy BASIC tier should map to Basic membership."""
        legacy_record = {
            "full_name": "Bob Smith",
            "email_address": "bob@example.com",
            "tier": "BASIC"
        }
        
        member = Member.from_legacy_data("L456", legacy_record)
        
        assert member.membership_type == MembershipType.BASIC
        assert member.credits == 10
    
    def test_from_legacy_data_defaults_to_basic_when_tier_missing(self):
        """Should default to Basic when tier is not specified."""
        legacy_record = {
            "full_name": "Alice Johnson",
            "email_address": "alice@example.com"
        }
        
        member = Member.from_legacy_data("L789", legacy_record)
        
        assert member.membership_type == MembershipType.BASIC
```

No mocks needed. No infrastructure. Pure domain tests that verify creation logic.

### Testing Application Factories

Application factories have dependencies. Test them with mocks or test doubles:

```python
# tests/application/test_member_factory.py

import pytest
from unittest.mock import Mock
from application.factories import MemberFactory, InvalidEmailException, BlacklistedEmailException


class TestMemberFactory:
    """Test the application-layer MemberFactory."""
    
    @pytest.fixture
    def email_verifier(self):
        """Mock email verifier that accepts all emails."""
        verifier = Mock()
        verifier.is_valid.return_value = True
        verifier.is_blacklisted.return_value = False
        return verifier
    
    @pytest.fixture
    def id_generator(self):
        """Mock ID generator that returns predictable IDs."""
        generator = Mock()
        generator.generate.side_effect = ["M001", "M002", "M003"]
        return generator
    
    @pytest.fixture
    def factory(self, id_generator, email_verifier):
        """Factory with mocked dependencies."""
        return MemberFactory(id_generator, email_verifier)
    
    def test_create_premium_member_generates_id(self, factory):
        """Should generate a unique ID for the member."""
        member = factory.create_premium_member("Sarah", "sarah@example.com")
        
        assert member.id == "M001"
        assert member.name == "Sarah"
    
    def test_create_premium_member_validates_email(self, factory, email_verifier):
        """Should verify email before creating member."""
        factory.create_premium_member("Sarah", "sarah@example.com")
        
        email_verifier.is_valid.assert_called_once_with("sarah@example.com")
        email_verifier.is_blacklisted.assert_called_once_with("sarah@example.com")
    
    def test_create_premium_member_rejects_invalid_email(self, factory, email_verifier):
        """Should raise exception when email is invalid."""
        email_verifier.is_valid.return_value = False
        
        with pytest.raises(InvalidEmailException) as exc_info:
            factory.create_premium_member("Sarah", "bad-email")
        
        assert "bad-email" in str(exc_info.value)
    
    def test_create_premium_member_rejects_blacklisted_email(self, factory, email_verifier):
        """Should raise exception when email is blacklisted."""
        email_verifier.is_blacklisted.return_value = True
        
        with pytest.raises(BlacklistedEmailException) as exc_info:
            factory.create_premium_member("Sarah", "spam@example.com")
        
        assert "spam@example.com" in str(exc_info.value)
    
    def test_import_from_legacy_skips_validation(self, factory, email_verifier):
        """Legacy imports should skip email verification."""
        legacy_record = {
            "full_name": "Jane Doe",
            "email_address": "jane@example.com",
            "tier": "GOLD"
        }
        
        member = factory.import_from_legacy("L123", legacy_record)
        
        # Should NOT have called the email verifier
        email_verifier.is_valid.assert_not_called()
        email_verifier.is_blacklisted.assert_not_called()
        
        assert member.id == "LEGACY-L123"
```

The tests use mocks for dependencies. They verify that the factory calls the right services with the right arguments. They check that validation happens when it should and doesn't happen when it shouldn't.

This is the beauty of dependency injection. The factory doesn't know it's talking to mocks. The tests are fast because they don't hit real email verification services or databases.

### Testing Factories End-to-End

Unit tests verify individual factory methods. But you should also test the full creation flow:

```python
# tests/integration/test_member_creation.py

import pytest
from application.factories import MemberFactory
from infrastructure.email_verifier import RealEmailVerifier
from infrastructure.id_generator import UuidMemberIdGenerator


class TestMemberCreationIntegration:
    """Integration tests for member creation with real dependencies."""
    
    @pytest.fixture
    def factory(self):
        """Factory with real implementations."""
        return MemberFactory(
            id_generator=UuidMemberIdGenerator(),
            email_verifier=RealEmailVerifier()
        )
    
    def test_create_premium_member_end_to_end(self, factory):
        """Should create a valid premium member with real dependencies."""
        member = factory.create_premium_member("Sarah", "sarah@example.com")
        
        # Should have generated a real UUID
        assert member.id.startswith("M-")
        assert len(member.id) > 10
        
        # Should have premium membership with welcome bonus
        assert member.membership_type == MembershipType.PREMIUM
        assert member.credits == 25
```

Integration tests use real implementations. They're slower but verify that the entire creation flow works correctly.

Run unit tests frequently during development. Run integration tests before committing or deploying. Both are valuable.

## Common Patterns and Variations

### Builder Pattern for Complex Construction

When an object has many optional parameters, consider the builder pattern:

```python
class MemberBuilder:
    """Builder for constructing Member objects step by step."""
    
    def __init__(self, member_id: str):
        self._id = member_id
        self._name = None
        self._email = None
        self._membership_type = None
        self._initial_credits = None
    
    def with_name(self, name: str):
        self._name = name
        return self
    
    def with_email(self, email_str: str):
        self._email = EmailAddress(email_str)
        return self
    
    def with_premium_membership(self):
        self._membership_type = MembershipType.PREMIUM
        return self
    
    def with_basic_membership(self):
        self._membership_type = MembershipType.BASIC
        return self
    
    def with_initial_credits(self, credits: int):
        self._initial_credits = credits
        return self
    
    def build(self) -> Member:
        if not all([self._name, self._email, self._membership_type]):
            raise ValueError("Name, email, and membership type are required")
        
        member = Member(self._id, self._name, self._email, self._membership_type)
        
        if self._initial_credits is not None:
            member.add_credits(self._initial_credits)
        
        return member


# Usage
member = (MemberBuilder("M001")
    .with_name("Sarah")
    .with_email("sarah@example.com")
    .with_premium_membership()
    .with_initial_credits(10)
    .build())
```

Builders work well when you have many optional parameters or when construction needs to happen in steps.

### Abstract Factory for Families of Objects

When you need to create families of related objects, use an abstract factory:

```python
from abc import ABC, abstractmethod


class MembershipFactory(ABC):
    """Abstract factory for creating membership-related objects."""
    
    @abstractmethod
    def create_member(self, member_id: str, name: str, email: str) -> Member:
        pass
    
    @abstractmethod
    def create_membership_type(self) -> MembershipType:
        pass


class PremiumMembershipFactory(MembershipFactory):
    """Factory for premium membership objects."""
    
    def create_member(self, member_id: str, name: str, email: str) -> Member:
        return Member.create_premium(member_id, name, email)
    
    def create_membership_type(self) -> MembershipType:
        return MembershipType.PREMIUM


class BasicMembershipFactory(MembershipFactory):
    """Factory for basic membership objects."""
    
    def create_member(self, member_id: str, name: str, email: str) -> Member:
        return Member.create_basic(member_id, name, email)
    
    def create_membership_type(self) -> MembershipType:
        return MembershipType.BASIC
```

This ensures that related objects (members and their membership types) are created consistently together.

## When to Use Factories

Don't use factories everywhere. They add indirection. They're another thing to maintain. Use them when creation deserves its own abstraction.

**Use factories when:**

- Object creation is complex (multiple steps, validation, default values)
- You have multiple ways to create the same object (different configurations or contexts)
- Creation requires external dependencies (ID generators, repositories, external services)
- Creation logic is duplicated across the codebase
- You need to test creation separately from the objects themselves
- Creation coordinates multiple objects or aggregates

**Don't use factories when:**

- Construction is simple and straightforward
- Objects can be created with a single constructor call
- There's only one way to create the object
- Adding a factory would be premature abstraction

The constructor is a factory method. If it does the job, use it.

## Summary

Factories solve the problem of complex object creation. They centralize creation logic, enforce consistency, and keep your domain objects focused on behavior rather than construction.

**Static factory methods** live on the class itself. Use them when creation logic is tied to the class and doesn't need external dependencies. They give meaningful names to construction (`create_premium` instead of `Member(..., premium=True)`).

**Factory classes** are standalone objects that create other objects. Use them when creation requires dependencies like repositories, ID generators, or external services. They enable testing with mocks and separate creation concerns from the objects being created.

**Domain factories** belong in the domain layer when they only use domain concepts and encode business rules. They don't depend on infrastructure.

**Application factories** belong in the application layer when they coordinate domain creation with infrastructure concerns. They orchestrate repositories, external services, and cross-aggregate validation.

**Testing factories** means testing at multiple levels. Unit test domain factories with pure domain tests. Unit test application factories with mocked dependencies. Integration test the full creation flow with real implementations.

Factories aren't mandatory. They're a tool. Use them when creation is complex enough to deserve its own abstraction. Trust your judgment. If a simple constructor works, use it. If creation becomes painful, scattered, or inconsistent—that's when you reach for a factory.

The goal isn't to have factories everywhere. The goal is to have complex creation logic in a predictable, testable place. Factories give you that place.
