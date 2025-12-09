# Appendix A: Validation Strategies Across Layers

You've built a layered architecture. Domain, application, infrastructure, and interface—each with clear responsibilities. The structure is solid. But then you encounter validation, and the boundaries blur.

A user submits a form. The email field contains "not-an-email". Where do you catch this?

A use case tries to book a class. The member doesn't exist in the database. Where do you validate this?

A domain entity is about to violate a business rule. Credits are about to go negative. Where do you enforce the constraint?

**Validation happens everywhere.** But that doesn't mean it should happen the same way everywhere, or that all validation belongs in the same place. Different types of validation serve different purposes, belong in different layers, and fail in different ways.

Getting this wrong is one of the most common architectural mistakes. Validation scattered across layers. Business rules in the API layer. Input sanitization in domain models. Precondition checks duplicated in three places. The code works, but it's fragile and hard to maintain.

This appendix teaches you how to think about validation architecturally. Where each type of validation belongs. How they coordinate without duplicating logic. How to handle validation failures appropriately at each layer.

## The Problem: Validation Is Everywhere

Consider a simple operation: booking a member into a fitness class. Here's what needs to be validated:

**Input validation:**
- The `member_id` is a valid UUID format
- The `class_id` is a valid UUID format
- The request body contains required fields
- Date/time values are properly formatted

**Application validation:**
- The member exists in the system
- The fitness class exists in the system
- The class hasn't already started
- The member isn't already booked in this class

**Domain validation:**
- The member has sufficient credits
- The class hasn't exceeded capacity
- The booking doesn't create a time slot conflict
- Credits won't go below zero after deduction

All of these are "validation." But they're fundamentally different concerns:

- **Input validation** protects against malformed data
- **Application validation** checks preconditions for the use case
- **Domain validation** enforces business invariants

Treating them the same leads to problems. Put business rules in the API layer, and they can't be reused by other interfaces. Put input sanitization in the domain, and domain tests become coupled to HTTP concerns. Put precondition checks in multiple places, and you duplicate logic.

**The solution:** Recognize that these are three distinct types of validation, each belonging in a specific layer, each handling failures differently.

## Three Types of Validation

### 1. Domain Validation: Protecting Invariants

**What it is:** Enforcing business rules that must always be true. These are the fundamental constraints of your domain model—the rules that define what valid means in your business context.

**Where it belongs:** In the domain layer, within entities, value objects, and aggregates.

**Examples:**
- "A member's credit balance can never be negative"
- "A class capacity must be between 1 and 50"
- "An email address must be valid"
- "A time slot can't end before it starts"

**Why it's here:** Domain objects must protect their own invariants. They can't rely on callers to maintain consistency. If a `Member` can have negative credits, you have an invalid state—and invalid states lead to bugs.

Domain validation is about **making invalid states impossible**, not just catching them after they happen.

Here's domain validation in practice:

```python
# domain/value_objects.py
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class EmailAddress:
    """
    Value object that guarantees email validity.
    
    Using frozen=True makes the object immutable after creation.
    __post_init__ runs after __init__ to validate the data before
    the object becomes frozen.
    """
    value: str
    
    def __post_init__(self):
        if not self._is_valid(self.value):
            raise ValueError(f"Invalid email address: {self.value}")
    
    @staticmethod
    def _is_valid(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

@dataclass(frozen=True)
class Credits:
    """
    Value object that prevents negative credits.
    
    Immutable by design - you can't modify credits directly.
    Instead, methods return new Credits instances.
    """
    amount: int
    
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError(f"Credits cannot be negative: {self.amount}")
    
    def deduct(self, amount: int) -> 'Credits':
        new_amount = self.amount - amount
        if new_amount < 0:
            raise InsufficientCreditsError(
                f"Cannot deduct {amount} credits. Only {self.amount} available."
            )
        return Credits(new_amount)
    
    def add(self, amount: int) -> 'Credits':
        if amount < 0:
            raise ValueError("Cannot add negative credits")
        return Credits(self.amount + amount)
```

Notice what's happening: **You can't create an invalid `EmailAddress` or `Credits` object.** The validation happens in `__post_init__`, before the object is fully constructed. If the data is invalid, construction fails. Once the object exists, you know it's valid.

This is fundamentally different from checking validity after the fact:

```python
# Bad: Anemic validation
class Member:
    def __init__(self, email: str, credits: int):
        self.email = email
        self.credits = credits
    
    def is_valid(self) -> bool:
        return self.credits >= 0 and '@' in self.email

# You can create invalid members!
member = Member("not-an-email", -10)
# member exists, but member.is_valid() returns False
```

With anemic validation, invalid objects can exist. You have to remember to call `is_valid()` everywhere. You can't trust that a `Member` instance is actually valid.

With rich domain validation, invalid objects **cannot exist**. The type system guarantees validity.

Here's domain validation in an entity:

```python
# domain/entities.py
from dataclasses import dataclass
from typing import List
from .value_objects import EmailAddress, Credits

class Member:
    """
    Domain entity with enforced invariants.
    
    Note: Unlike the immutable value objects above, entities are mutable
    but protect their state through private attributes and controlled methods.
    """
    
    def __init__(
        self,
        member_id: str,
        name: str,
        email: EmailAddress,  # Can't be invalid
        credits: Credits,      # Can't be negative
    ):
        if not name or not name.strip():
            raise ValueError("Member name cannot be empty")
        
        self._id = member_id
        self._name = name
        self._email = email
        self._credits = credits
    
    @property
    def id(self) -> str:
        return self._id
    
    @property
    def email(self) -> EmailAddress:
        return self._email
    
    @property
    def credits(self) -> Credits:
        return self._credits
    
    def deduct_credit(self) -> None:
        """Deduct one credit, enforcing the non-negative invariant."""
        self._credits = self._credits.deduct(1)
    
    def add_credits(self, amount: int) -> None:
        """Add credits, enforcing validity."""
        self._credits = self._credits.add(amount)


class FitnessClass:
    """Domain entity that protects capacity constraints."""
    
    MAX_CAPACITY = 50
    MIN_CAPACITY = 1
    
    def __init__(self, class_id: str, name: str, capacity: int):
        if not name or not name.strip():
            raise ValueError("Class name cannot be empty")
        
        if capacity < self.MIN_CAPACITY or capacity > self.MAX_CAPACITY:
            raise ValueError(
                f"Capacity must be between {self.MIN_CAPACITY} and {self.MAX_CAPACITY}"
            )
        
        self._id = class_id
        self._name = name
        self._capacity = capacity
        self._bookings: List[str] = []
    
    def add_booking(self, member_id: str) -> None:
        """Add a booking, enforcing capacity constraint."""
        if self.is_full():
            raise ClassFullError(f"Class {self._name} is at capacity")
        
        if member_id in self._bookings:
            raise DuplicateBookingError(
                f"Member {member_id} is already booked"
            )
        
        self._bookings.append(member_id)
    
    def is_full(self) -> bool:
        return len(self._bookings) >= self._capacity
```

**Key principles of domain validation:**

1. **Fail fast:** Validation happens in constructors or before state changes
2. **Use value objects:** Encapsulate validation logic in immutable types
3. **Make properties private:** Force all changes through methods that enforce invariants
4. **Domain exceptions:** Throw specific exceptions that represent business rule violations

Domain validation doesn't ask "is this valid?" It asserts "this must be valid, or we can't continue."

### 2. Application Validation: Checking Preconditions

**What it is:** Verifying that the conditions required for a use case to proceed are met. These aren't business invariants—they're contextual requirements.

**Where it belongs:** In the application layer, at the beginning of use case execution.

**Examples:**
- "The member exists in the system"
- "The fitness class exists in the system"
- "The class hasn't already started"
- "The user has permission to perform this action"
- "The requested resource is available"

**Why it's here:** Application validation checks the preconditions that must be true before domain logic executes. These aren't about protecting invariants—they're about ensuring the use case makes sense in the current state of the system.

Consider the difference:

```python
# Domain validation: Invariant
class FitnessClass:
    def add_booking(self, member_id: str):
        if self.is_full():
            raise ClassFullError("Class is at capacity")
        # This is a business rule that's always enforced

# Application validation: Precondition
class BookClassUseCase:
    def execute(self, member_id: str, class_id: str):
        member = self.member_repo.get(member_id)
        if not member:
            raise MemberNotFoundError(f"Member {member_id} not found")
        # This checks existence, not a business rule
```

The class capacity rule is a **domain invariant**—it's always true, regardless of context. The member existence check is an **application precondition**—it's specific to this use case and depends on current system state.

Here's comprehensive application validation:

```python
# application/use_cases.py
from datetime import datetime
from typing import Optional
from domain.entities import Member, FitnessClass, Booking
from domain.exceptions import ClassFullError, InsufficientCreditsError

class BookClassUseCase:
    """Use case that orchestrates class booking with precondition validation."""
    
    def __init__(self, member_repo, class_repo, booking_repo, event_bus):
        self.member_repo = member_repo
        self.class_repo = class_repo
        self.booking_repo = booking_repo
        self.event_bus = event_bus
    
    def execute(self, member_id: str, class_id: str) -> Booking:
        # Application validation: Check preconditions
        member = self._validate_member_exists(member_id)
        fitness_class = self._validate_class_exists(class_id)
        self._validate_class_not_started(fitness_class)
        self._validate_no_duplicate_booking(member_id, class_id)
        
        # Now execute domain logic (which has its own validation)
        try:
            member.deduct_credit()
            fitness_class.add_booking(member_id)
        except InsufficientCreditsError as e:
            raise ApplicationError(f"Cannot book class: {e}")
        except ClassFullError as e:
            raise ApplicationError(f"Cannot book class: {e}")
        
        # Create and persist the booking
        booking = Booking.create(member_id, class_id)
        
        self.member_repo.save(member)
        self.class_repo.save(fitness_class)
        self.booking_repo.save(booking)
        
        # Publish event
        self.event_bus.publish(BookingCreatedEvent(booking))
        
        return booking
    
    def _validate_member_exists(self, member_id: str) -> Member:
        member = self.member_repo.get(member_id)
        if not member:
            raise MemberNotFoundError(
                f"Cannot book class: Member {member_id} not found"
            )
        return member
    
    def _validate_class_exists(self, class_id: str) -> FitnessClass:
        fitness_class = self.class_repo.get(class_id)
        if not fitness_class:
            raise ClassNotFoundError(
                f"Cannot book class: Class {class_id} not found"
            )
        return fitness_class
    
    def _validate_class_not_started(self, fitness_class: FitnessClass) -> None:
        if fitness_class.has_started():
            raise ClassAlreadyStartedError(
                f"Cannot book class {fitness_class.id}: already started"
            )
    
    def _validate_no_duplicate_booking(
        self, member_id: str, class_id: str
    ) -> None:
        existing = self.booking_repo.find_by_member_and_class(
            member_id, class_id
        )
        if existing:
            raise DuplicateBookingError(
                f"Member {member_id} already booked in class {class_id}"
            )
```

**Key principles of application validation:**

1. **Validate early:** Check all preconditions before executing domain logic
2. **Be explicit:** Each validation is a separate, named method
3. **Return or raise:** Either return the validated object or raise a specific error
4. **Coordinate checks:** Application layer knows about multiple aggregates and can cross-check them
5. **Handle domain exceptions:** Catch domain-level failures and translate them for the application context

Application validation doesn't enforce business rules—it ensures the use case can proceed.

### 3. Interface Validation: Sanitizing Input

**What it is:** Checking that external input is well-formed, safe, and meets basic structural requirements before it enters the application.

**Where it belongs:** In the interface layer (API controllers, CLI handlers, GraphQL resolvers).

**Examples:**
- "The request body is valid JSON"
- "Required fields are present"
- "Field types match expected types (string, int, date)"
- "UUIDs are properly formatted"
- "Dates are in ISO-8601 format"
- "Input doesn't contain injection attacks"

**Why it's here:** The interface layer is the boundary between the external world and your application. It's responsible for translating external formats (HTTP, CLI args, events) into domain concepts. Before that translation happens, you need to ensure the input is even usable.

Interface validation is about **protecting your application from malformed data**, not enforcing business rules.

Here's interface validation with FastAPI (similar patterns apply to Flask, Django, etc.):

```python
# interface/api/schemas.py
from pydantic import BaseModel, Field, validator, UUID4
# Note: For Pydantic v2, use field_validator instead of validator
from datetime import datetime
from typing import Optional

class BookClassRequest(BaseModel):
    """Request schema with input validation."""
    
    member_id: UUID4 = Field(
        ...,
        description="UUID of the member booking the class"
    )
    class_id: UUID4 = Field(
        ...,
        description="UUID of the class to book"
    )
    
    class Config:
        # Reject extra fields
        extra = 'forbid'


class CreateMemberRequest(BaseModel):
    """Request schema with custom validation."""
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Member's full name"
    )
    email: str = Field(
        ...,
        description="Member's email address"
    )
    membership_type: str = Field(
        ...,
        description="Type of membership"
    )
    
    @validator('name')
    def name_must_not_be_whitespace(cls, v):
        """Validate that name is not just whitespace."""
        if not v.strip():
            raise ValueError('Name cannot be only whitespace')
        return v.strip()
    
    @validator('membership_type')
    def membership_type_must_be_valid(cls, v):
        """Validate that membership type is one of the allowed values."""
        valid_types = ['basic', 'premium', 'pay-per-class']
        if v not in valid_types:
            raise ValueError(
                f'Membership type must be one of {valid_types}'
            )
        return v
    
    class Config:
        extra = 'forbid'


# interface/api/controllers.py
from fastapi import APIRouter, HTTPException, status
from .schemas import BookClassRequest, CreateMemberRequest
from application.use_cases import BookClassUseCase, CreateMemberUseCase
from application.exceptions import (
    MemberNotFoundError,
    ClassNotFoundError,
    ApplicationError
)

router = APIRouter()

@router.post('/bookings', status_code=status.HTTP_201_CREATED)
async def book_class(
    request: BookClassRequest,
    use_case: BookClassUseCase
):
    """
    Book a member into a fitness class.
    
    Input validation happens automatically via Pydantic:
    - member_id and class_id are valid UUIDs
    - Required fields are present
    - No extra fields are included
    """
    try:
        booking = use_case.execute(
            member_id=str(request.member_id),
            class_id=str(request.class_id)
        )
        return {
            'booking_id': booking.id,
            'member_id': booking.member_id,
            'class_id': booking.class_id
        }
    except (MemberNotFoundError, ClassNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ApplicationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post('/members', status_code=status.HTTP_201_CREATED)
async def create_member(
    request: CreateMemberRequest,
    use_case: CreateMemberUseCase
):
    """
    Create a new member.
    
    Input validation via Pydantic ensures:
    - All required fields present
    - Name is 1-100 characters and not just whitespace
    - Membership type is valid
    - Email is a string (format validated in domain)
    """
    try:
        member = use_case.execute(
            name=request.name,
            email=request.email,
            membership_type=request.membership_type
        )
        return {
            'member_id': member.id,
            'name': member.name,
            'email': member.email.value
        }
    except ValueError as e:
        # Domain validation failed (e.g., invalid email format)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except ApplicationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
```

**Key principles of interface validation:**

1. **Validate structure, not business rules:** Check format, not meaning
2. **Use schema validation libraries:** Pydantic, Marshmallow, JSON Schema
3. **Fail with appropriate HTTP codes:** 400 for validation, 422 for semantic errors
4. **Sanitize input:** Strip whitespace, normalize formats
5. **Don't leak domain exceptions:** Translate them to interface-appropriate errors

Interface validation protects your application from bad input. It doesn't understand business rules.

## How Validation Flows Through Layers

Understanding how validation works at each layer is important. Understanding how they coordinate is critical.

Here's a complete flow from HTTP request to domain execution:

```
1. HTTP Request arrives
   └─> Interface Layer: Structural validation
       ├─ Valid JSON?
       ├─ Required fields present?
       ├─ UUIDs properly formatted?
       └─ Field types correct?
       
2. If valid, translate to application request
   └─> Application Layer: Precondition validation
       ├─ Member exists?
       ├─ Class exists?
       ├─ Class hasn't started?
       └─ No duplicate booking?
       
3. If preconditions met, execute domain logic
   └─> Domain Layer: Invariant enforcement
       ├─ Member has credits? (deduct)
       ├─ Class has capacity? (add booking)
       └─ No invalid state changes?
       
4. If successful, persist and respond
   └─> Interface Layer: Format response
       └─ Return 201 Created with booking data
```

At each layer, validation serves a different purpose:

- **Interface:** "Can I even parse this?"
- **Application:** "Does this make sense right now?"
- **Domain:** "Does this violate business rules?"

Let's see this in action with a complete example:

```python
# Request: POST /bookings
# Body: { "member_id": "invalid-uuid", "class_id": "123e4567-e89b-12d3-a456-426614174000" }

# Layer 1: Interface validation
# Pydantic tries to parse member_id as UUID
# Fails: "member_id: value is not a valid uuid"
# Response: 422 Unprocessable Entity
# ❌ Request stops here - never reaches application


# Request: POST /bookings  
# Body: { "member_id": "123e4567-e89b-12d3-a456-426614174000", "class_id": "123e4567-e89b-12d3-a456-426614174001" }

# Layer 1: Interface validation
# ✓ Both UUIDs valid
# ✓ Required fields present
# Passes to application layer

# Layer 2: Application validation
def execute(self, member_id: str, class_id: str):
    member = self.member_repo.get(member_id)
    # Member not found in database
    if not member:
        raise MemberNotFoundError(...)
# Response: 404 Not Found
# ❌ Request stops here - never reaches domain


# Request: POST /bookings
# Body: { "member_id": "existing-member", "class_id": "existing-class" }

# Layer 1: Interface validation
# ✓ Valid structure
# Passes to application

# Layer 2: Application validation  
# ✓ Member exists
# ✓ Class exists
# ✓ Class hasn't started
# Passes to domain

# Layer 3: Domain validation
def deduct_credit(self):
    self._credits = self._credits.deduct(1)
    # self._credits.deduct checks: amount - 1 >= 0
    # Fails: member has 0 credits
    raise InsufficientCreditsError(...)
# Response: 400 Bad Request
# ❌ Request stops here - domain invariant violated


# Request: POST /bookings
# Body: { "member_id": "member-with-credits", "class_id": "class-with-space" }

# Layer 1: ✓ Valid structure
# Layer 2: ✓ Preconditions met
# Layer 3: ✓ Invariants maintained
# Response: 201 Created
# ✓ Success
```

**The validation layers act as filters.** Each layer eliminates a class of errors before passing the request deeper into the system. By the time you reach the domain, you know:
- The input was well-formed
- The preconditions were met
- Only business rule violations can occur

This is efficient and separates concerns properly.

## Validation Errors vs Domain Exceptions

Not all validation failures should be handled the same way. The type of validation that failed determines the appropriate response.

### Interface Validation Errors

**What failed:** Input structure or format

**HTTP Status:** 400 Bad Request or 422 Unprocessable Entity

**Response example:**
```json
{
  "error": "Validation failed",
  "details": {
    "member_id": ["value is not a valid uuid"],
    "name": ["field required"]
  }
}
```

**Characteristics:**
- Client error - they sent bad data
- Detailed field-level errors
- Fixable by correcting the request
- Never logged as application errors

### Application Validation Errors

**What failed:** Preconditions not met

**HTTP Status:** 404 Not Found, 409 Conflict, or 400 Bad Request

**Response example:**
```json
{
  "error": "Member not found",
  "message": "Cannot book class: Member 123e4567-e89b-12d3-a456-426614174000 not found"
}
```

**Characteristics:**
- Request was well-formed, but state doesn't allow the operation
- Single, descriptive error message
- Might be fixable (member exists now) or not (class already started)
- May be logged for metrics but not as errors

### Domain Exceptions

**What failed:** Business rule violation

**HTTP Status:** 400 Bad Request or 409 Conflict

**Response example:**
```json
{
  "error": "Insufficient credits",
  "message": "Cannot deduct 1 credit. Only 0 available."
}
```

**Characteristics:**
- Request was valid, preconditions met, but business rules prevent the action
- Represents a business constraint
- Should be logged for business analytics
- User needs to take action (buy credits) to resolve

Here's how to handle each type:

```python
# interface/api/error_handlers.py
from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from application.exceptions import (
    ApplicationError,
    MemberNotFoundError,
    ClassNotFoundError,
    DuplicateBookingError
)
from domain.exceptions import (
    InsufficientCreditsError,
    ClassFullError,
    DomainValidationError
)

async def validation_error_handler(
    request: Request,
    exc: ValidationError
):
    """Handle Pydantic validation errors (interface layer)."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation failed",
            "details": exc.errors()
        }
    )

async def not_found_handler(
    request: Request,
    exc: Union[MemberNotFoundError, ClassNotFoundError]
):
    """Handle resource not found (application layer)."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "Resource not found",
            "message": str(exc)
        }
    )

async def domain_error_handler(
    request: Request,
    exc: Union[InsufficientCreditsError, ClassFullError, DomainValidationError]
):
    """Handle domain rule violations."""
    # Log for business metrics
    logger.info(
        "Domain rule violation",
        extra={
            "error_type": type(exc).__name__,
            "message": str(exc)
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Business rule violation",
            "message": str(exc)
        }
    )

async def application_error_handler(
    request: Request,
    exc: ApplicationError
):
    """Handle application-level errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Operation failed",
            "message": str(exc)
        }
    )
```

**The pattern:** Different exception types from different layers get different HTTP status codes and different response formats. This tells the client exactly what went wrong and what they can do about it.

## Testing Validation at Each Layer

Each validation layer needs its own tests. Testing them together obscures which layer is actually being validated.

### Testing Domain Validation

Domain validation tests focus on invariant enforcement, independent of application logic or HTTP concerns.

```python
# tests/domain/test_value_objects.py
import pytest
from domain.value_objects import EmailAddress, Credits
from domain.exceptions import InsufficientCreditsError

class TestEmailAddress:
    """Test email validation in isolation."""
    
    def test_valid_email_accepted(self):
        email = EmailAddress("user@example.com")
        assert email.value == "user@example.com"
    
    def test_invalid_email_rejected(self):
        with pytest.raises(ValueError, match="Invalid email"):
            EmailAddress("not-an-email")
    
    def test_email_without_domain_rejected(self):
        with pytest.raises(ValueError, match="Invalid email"):
            EmailAddress("user@")
    
    def test_email_without_at_rejected(self):
        with pytest.raises(ValueError, match="Invalid email"):
            EmailAddress("userexample.com")


class TestCredits:
    """Test credit invariants in isolation."""
    
    def test_positive_credits_accepted(self):
        credits = Credits(10)
        assert credits.amount == 10
    
    def test_zero_credits_accepted(self):
        credits = Credits(0)
        assert credits.amount == 0
    
    def test_negative_credits_rejected(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            Credits(-1)
    
    def test_deduct_within_balance_succeeds(self):
        credits = Credits(10)
        new_credits = credits.deduct(5)
        assert new_credits.amount == 5
    
    def test_deduct_exact_balance_succeeds(self):
        credits = Credits(10)
        new_credits = credits.deduct(10)
        assert new_credits.amount == 0
    
    def test_deduct_more_than_balance_fails(self):
        credits = Credits(5)
        with pytest.raises(InsufficientCreditsError):
            credits.deduct(6)
    
    def test_add_positive_credits_succeeds(self):
        credits = Credits(10)
        new_credits = credits.add(5)
        assert new_credits.amount == 15
    
    def test_add_negative_credits_fails(self):
        credits = Credits(10)
        with pytest.raises(ValueError, match="Cannot add negative"):
            credits.add(-5)


# tests/domain/test_entities.py
from domain.entities import FitnessClass
from domain.exceptions import ClassFullError, DuplicateBookingError

class TestFitnessClass:
    """Test class capacity invariants."""
    
    def test_capacity_within_bounds_accepted(self):
        fitness_class = FitnessClass("id", "Yoga", 20)
        assert fitness_class.capacity == 20
    
    def test_capacity_too_low_rejected(self):
        with pytest.raises(ValueError, match="between 1 and 50"):
            FitnessClass("id", "Yoga", 0)
    
    def test_capacity_too_high_rejected(self):
        with pytest.raises(ValueError, match="between 1 and 50"):
            FitnessClass("id", "Yoga", 51)
    
    def test_add_booking_within_capacity_succeeds(self):
        fitness_class = FitnessClass("id", "Yoga", 2)
        fitness_class.add_booking("member-1")
        fitness_class.add_booking("member-2")
        assert fitness_class.is_full()
    
    def test_add_booking_when_full_fails(self):
        fitness_class = FitnessClass("id", "Yoga", 1)
        fitness_class.add_booking("member-1")
        
        with pytest.raises(ClassFullError):
            fitness_class.add_booking("member-2")
    
    def test_add_duplicate_booking_fails(self):
        fitness_class = FitnessClass("id", "Yoga", 10)
        fitness_class.add_booking("member-1")
        
        with pytest.raises(DuplicateBookingError):
            fitness_class.add_booking("member-1")
```

**Domain test characteristics:**
- No mocks or stubs (pure domain logic)
- Test edge cases and boundary conditions
- Test that invalid states cannot be created
- Test that invalid transitions are prevented
- Fast (no I/O, no database)

### Testing Application Validation

Application validation tests verify precondition checking, using test doubles for repositories.

```python
# tests/application/test_book_class_use_case.py
import pytest
from unittest.mock import Mock
from application.use_cases import BookClassUseCase
from application.exceptions import (
    MemberNotFoundError,
    ClassNotFoundError,
    ClassAlreadyStartedError
)
from domain.entities import Member, FitnessClass
from domain.value_objects import EmailAddress, Credits

class TestBookClassUseCase:
    """Test application-level precondition validation."""
    
    def setup_method(self):
        self.member_repo = Mock()
        self.class_repo = Mock()
        self.booking_repo = Mock()
        self.event_bus = Mock()
        
        self.use_case = BookClassUseCase(
            self.member_repo,
            self.class_repo,
            self.booking_repo,
            self.event_bus
        )
    
    def test_member_not_found_raises_error(self):
        """Application validation: Member must exist."""
        self.member_repo.get.return_value = None
        
        with pytest.raises(MemberNotFoundError, match="not found"):
            self.use_case.execute("member-id", "class-id")
        
        # Verify we checked for the member
        self.member_repo.get.assert_called_once_with("member-id")
        # Verify we didn't proceed further
        self.class_repo.get.assert_not_called()
    
    def test_class_not_found_raises_error(self):
        """Application validation: Class must exist."""
        self.member_repo.get.return_value = Mock(spec=Member)
        self.class_repo.get.return_value = None
        
        with pytest.raises(ClassNotFoundError, match="not found"):
            self.use_case.execute("member-id", "class-id")
    
    def test_class_already_started_raises_error(self):
        """Application validation: Class must not have started."""
        member = Mock(spec=Member)
        fitness_class = Mock(spec=FitnessClass)
        fitness_class.has_started.return_value = True
        
        self.member_repo.get.return_value = member
        self.class_repo.get.return_value = fitness_class
        
        with pytest.raises(ClassAlreadyStartedError):
            self.use_case.execute("member-id", "class-id")
    
    def test_duplicate_booking_raises_error(self):
        """Application validation: No duplicate bookings."""
        member = Mock(spec=Member)
        fitness_class = Mock(spec=FitnessClass)
        fitness_class.has_started.return_value = False
        existing_booking = Mock()
        
        self.member_repo.get.return_value = member
        self.class_repo.get.return_value = fitness_class
        self.booking_repo.find_by_member_and_class.return_value = existing_booking
        
        with pytest.raises(DuplicateBookingError):
            self.use_case.execute("member-id", "class-id")
    
    def test_successful_booking_when_preconditions_met(self):
        """When all preconditions met, domain logic executes."""
        member = Mock(spec=Member)
        fitness_class = Mock(spec=FitnessClass)
        fitness_class.has_started.return_value = False
        
        self.member_repo.get.return_value = member
        self.class_repo.get.return_value = fitness_class
        self.booking_repo.find_by_member_and_class.return_value = None
        
        booking = self.use_case.execute("member-id", "class-id")
        
        # Verify domain methods were called
        member.deduct_credit.assert_called_once()
        fitness_class.add_booking.assert_called_once_with("member-id")
        
        # Verify persistence
        self.member_repo.save.assert_called_once()
        self.class_repo.save.assert_called_once()
        self.booking_repo.save.assert_called_once()
```

**Application test characteristics:**
- Mock repositories and external services
- Test each precondition independently
- Verify that failures stop execution
- Verify that success leads to domain execution
- Test orchestration, not business rules

### Testing Interface Validation

Interface validation tests verify input sanitization and schema validation.

```python
# tests/interface/api/test_booking_endpoints.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
from interface.api.app import app
from application.use_cases import BookClassUseCase
from application.exceptions import MemberNotFoundError
from domain.exceptions import InsufficientCreditsError

client = TestClient(app)

class TestBookClassEndpoint:
    """Test interface-level input validation."""
    
    def test_missing_member_id_returns_422(self):
        """Interface validation: Required fields must be present."""
        response = client.post('/bookings', json={
            "class_id": "123e4567-e89b-12d3-a456-426614174000"
            # member_id missing
        })
        
        assert response.status_code == 422
        assert "member_id" in response.json()["detail"][0]["loc"]
    
    def test_invalid_uuid_format_returns_422(self):
        """Interface validation: UUIDs must be properly formatted."""
        response = client.post('/bookings', json={
            "member_id": "not-a-uuid",
            "class_id": "123e4567-e89b-12d3-a456-426614174000"
        })
        
        assert response.status_code == 422
        error_detail = response.json()["detail"][0]
        assert "member_id" in error_detail["loc"]
        assert "uuid" in error_detail["msg"].lower()
    
    def test_extra_fields_rejected(self):
        """Interface validation: No unexpected fields allowed."""
        response = client.post('/bookings', json={
            "member_id": "123e4567-e89b-12d3-a456-426614174000",
            "class_id": "123e4567-e89b-12d3-a456-426614174001",
            "extra_field": "not allowed"
        })
        
        assert response.status_code == 422
    
    def test_member_not_found_returns_404(self, mocker):
        """Application error translated to appropriate HTTP status."""
        mock_use_case = mocker.patch.object(BookClassUseCase, 'execute')
        mock_use_case.side_effect = MemberNotFoundError("Member not found")
        
        response = client.post('/bookings', json={
            "member_id": "123e4567-e89b-12d3-a456-426614174000",
            "class_id": "123e4567-e89b-12d3-a456-426614174001"
        })
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_insufficient_credits_returns_400(self, mocker):
        """Domain exception translated to appropriate HTTP status."""
        mock_use_case = mocker.patch.object(BookClassUseCase, 'execute')
        mock_use_case.side_effect = InsufficientCreditsError(
            "Cannot deduct 1 credit. Only 0 available."
        )
        
        response = client.post('/bookings', json={
            "member_id": "123e4567-e89b-12d3-a456-426614174000",
            "class_id": "123e4567-e89b-12d3-a456-426614174001"
        })
        
        assert response.status_code == 400
        assert "credit" in response.json()["detail"].lower()
    
    def test_successful_booking_returns_201(self, mocker):
        """Valid input with successful execution returns correct status."""
        mock_booking = Mock()
        mock_booking.id = "booking-123"
        mock_booking.member_id = "member-123"
        mock_booking.class_id = "class-123"
        
        mock_use_case = mocker.patch.object(BookClassUseCase, 'execute')
        mock_use_case.return_value = mock_booking
        
        response = client.post('/bookings', json={
            "member_id": "123e4567-e89b-12d3-a456-426614174000",
            "class_id": "123e4567-e89b-12d3-a456-426614174001"
        })
        
        assert response.status_code == 201
        assert response.json()["booking_id"] == "booking-123"
```

**Interface test characteristics:**
- Test HTTP-level concerns
- Use test client (no real HTTP server)
- Test schema validation
- Test error response formatting
- Test status code mapping
- Don't test business logic (use mocks)

## Common Validation Mistakes

### Mistake 1: Validation in the Wrong Layer

**Problem:** Putting business rules in the API layer:

```python
# ❌ Bad: Business logic in the interface layer
@router.post('/bookings')
async def book_class(request: BookClassRequest):
    member = get_member(request.member_id)
    
    # This is a business rule, not input validation!
    if member.credits < 1:
        raise HTTPException(400, "Insufficient credits")
    
    # Now what if we add a CLI interface?
    # We have to duplicate this logic!
```

**Solution:** Business rules belong in the domain:

```python
# ✓ Good: Business logic in the domain
class Member:
    def deduct_credit(self):
        self._credits = self._credits.deduct(1)
        # Raises InsufficientCreditsError if balance too low

# Interface just handles the error
@router.post('/bookings')
async def book_class(request: BookClassRequest):
    try:
        booking = use_case.execute(request.member_id, request.class_id)
    except InsufficientCreditsError as e:
        raise HTTPException(400, str(e))
```

### Mistake 2: Duplicate Validation

**Problem:** Checking the same thing in multiple layers:

```python
# ❌ Bad: Email validation duplicated
@router.post('/members')
async def create_member(request: CreateMemberRequest):
    # Validation 1: In the API
    if '@' not in request.email:
        raise HTTPException(400, "Invalid email")
    
    # Validation 2: In the use case
    use_case.execute(request.email)  # Checks email again
    
    # Validation 3: In the domain
    EmailAddress(request.email)  # Checks email again
```

**Solution:** Each layer validates its concern:

```python
# ✓ Good: Each layer validates once
# Interface: Checks email is a string
class CreateMemberRequest(BaseModel):
    email: str  # Just type checking

# Domain: Checks email format
class EmailAddress:
    def __post_init__(self):
        if not self._is_valid(self.value):
            raise ValueError("Invalid email")
```

### Mistake 3: Leaking Domain Exceptions to the Interface

**Problem:** Letting domain exceptions reach the API layer unchanged:

```python
# ❌ Bad: Domain exception becomes HTTP response
@router.post('/bookings')
async def book_class(request: BookClassRequest):
    # If this raises InsufficientCreditsError, what HTTP status?
    # The client gets a 500 because we didn't handle it
    booking = use_case.execute(request.member_id, request.class_id)
    return booking
```

**Solution:** Translate domain exceptions appropriately:

```python
# ✓ Good: Domain exceptions handled
@router.post('/bookings')
async def book_class(request: BookClassRequest):
    try:
        booking = use_case.execute(request.member_id, request.class_id)
        return booking
    except InsufficientCreditsError as e:
        raise HTTPException(400, str(e))
    except ClassFullError as e:
        raise HTTPException(409, str(e))
```

### Mistake 4: Validating in Application That Should Be in Domain

**Problem:** Checking business rules in the use case:

```python
# ❌ Bad: Use case checks domain invariants
class BookClassUseCase:
    def execute(self, member_id, class_id):
        member = self.member_repo.get(member_id)
        fitness_class = self.class_repo.get(class_id)
        
        # This is a domain rule, not a use case concern!
        if member.credits < 1:
            raise ApplicationError("Insufficient credits")
        
        member.credits -= 1  # Direct manipulation breaks encapsulation
```

**Solution:** Let the domain enforce its rules:

```python
# ✓ Good: Domain enforces its own rules
class BookClassUseCase:
    def execute(self, member_id, class_id):
        member = self.member_repo.get(member_id)
        fitness_class = self.class_repo.get(class_id)
        
        # Domain method handles the rule
        member.deduct_credit()  # Raises InsufficientCreditsError if needed
```

## Summary: Where Does Validation Go?

| Validation Type | Layer | Purpose | Examples | Error Type |
|----------------|-------|---------|----------|------------|
| **Input Validation** | Interface | Protect from malformed data | UUID format, required fields, data types | 422 Unprocessable Entity |
| **Precondition Validation** | Application | Verify use case can proceed | Resource exists, not duplicate, hasn't started | 404 Not Found, 409 Conflict |
| **Invariant Enforcement** | Domain | Maintain business rules | Credits non-negative, capacity limits | Domain exceptions → 400 Bad Request |

**The key insight:** Validation is not one thing. It's three different concerns that happen in three different places for three different reasons. Mixing them creates fragile, duplicated, hard-to-test code.

When you encounter validation logic, ask:
- **"What is being validated?"** Format? Existence? Business rule?
- **"Why is it being validated?"** Safety? Precondition? Invariant?
- **"Where should it be validated?"** Interface? Application? Domain?

Get these right, and your validation will be clear, testable, and maintainable. Get them wrong, and validation will be scattered, duplicated, and impossible to change.

Validation is everywhere. Now you know where it should be.
