# Chapter 4: Single Responsibility Principle

## Introduction

The Single Responsibility Principle (SRP) is the first of the SOLID principles and perhaps the most fundamental. At its core, it states: **A class should have one reason to change.**

This seems simple, but it's widely misunderstood. SRP isn't about "doing one thing." It's about having one stakeholder, one source of change, one reason to be modified.

When a class has multiple responsibilities, changes for one reason can break functionality for another. SRP prevents this by ensuring each class serves a single purpose.

## The Problem

Classes with multiple responsibilities are fragile and hard to maintain.

**Symptoms:**
- God classes that "do everything"
- Classes with many unrelated methods
- Changes in one area break another
- Difficult to test in isolation
- Hard to reuse

**Example of the problem:**

```python
class UserManager:
    """A class trying to do too much."""
    
    def __init__(self):
        self.users = {}
    
    def create_user(self, user_id, name, email, password):
        # Responsibility 1: User creation and storage
        if self.validate_email(email):
            hashed_password = self.hash_password(password)
            self.users[user_id] = {
                'name': name,
                'email': email,
                'password': hashed_password
            }
            self.save_to_database(user_id)
            self.send_welcome_email(email, name)
    
    def validate_email(self, email):
        # Responsibility 2: Email validation
        return '@' in email and '.' in email
    
    def hash_password(self, password):
        # Responsibility 3: Password hashing
        import hashlib
        return hashlib.sha256(password.encode()).hexdigest()
    
    def save_to_database(self, user_id):
        # Responsibility 4: Database persistence
        import sqlite3
        conn = sqlite3.connect('users.db')
        # ... save user
        conn.close()
    
    def send_welcome_email(self, email, name):
        # Responsibility 5: Email sending
        import smtplib
        server = smtplib.SMTP('smtp.gmail.com')
        # ... send email
        server.quit()
    
    def generate_report(self, user_id):
        # Responsibility 6: Report generation
        user = self.users[user_id]
        return f"User Report for {user['name']}: ..."
    
    def export_users_to_csv(self):
        # Responsibility 7: Data export
        import csv
        # ... export logic
```

**Problems:**
- Changing email validation affects the entire class
- Can't test user creation without database/email
- Switching from SQLite to PostgreSQL requires modifying UserManager
- Multiple reasons to change: validation rules, database schema, email provider, report format

## The Pattern

**Single Responsibility Principle:** A class should have only one reason to change.

Another way to think about it: **A class should have only one stakeholder** (or user) who might request changes to it.

### Identifying Responsibilities

Ask: "Who might ask me to change this code, and why?"

- **User model business rules:** Product owner wants to change what makes a valid user
- **Database persistence:** DBA wants to migrate from SQLite to PostgreSQL  
- **Email sending:** Marketing wants to change email provider
- **Password hashing:** Security team wants stronger encryption
- **Report generation:** Business analyst wants different report format

Each of these is a different stakeholder → different responsibility → different class.

## Implementation

Let's refactor the UserManager into focused classes, each with a single responsibility.

### Example: User Management System

```python
# user.py
"""Domain model - User entity with business rules."""

class User:
    """
    Represents a user in the system.
    
    Responsibility: Model a user and enforce user business rules.
    """
    
    def __init__(self, user_id: str, name: str, email: str, password_hash: str):
        if not user_id:
            raise ValueError("User ID cannot be empty")
        if not name:
            raise ValueError("Name cannot be empty")
        if not email:
            raise ValueError("Email cannot be empty")
        
        self.id = user_id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.is_active = True
    
    def deactivate(self):
        """Deactivate this user account."""
        self.is_active = False
    
    def activate(self):
        """Activate this user account."""
        self.is_active = True
    
    def __repr__(self):
        return f"User({self.id}, {self.name}, {self.email})"


# validators.py
"""Validation logic - separate from domain model."""

import re

class EmailValidator:
    """
    Validates email addresses.
    
    Responsibility: Determine if an email is valid.
    Stakeholder: Product owner defining validation rules.
    """
    
    @staticmethod
    def is_valid(email: str) -> bool:
        """
        Check if email format is valid.
        
        Using a simple regex for demonstration. In production,
        you'd use a more robust solution.
        """
        if not email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None


class PasswordValidator:
    """
    Validates password strength.
    
    Responsibility: Determine if a password meets security requirements.
    Stakeholder: Security team defining password policy.
    """
    
    @staticmethod
    def is_strong(password: str) -> bool:
        """
        Check if password meets strength requirements.
        
        Requirements:
        - At least 8 characters
        - Contains uppercase and lowercase
        - Contains at least one digit
        """
        if len(password) < 8:
            return False
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        return has_upper and has_lower and has_digit


# password_hasher.py
"""Password hashing logic."""

import hashlib
import secrets

class PasswordHasher:
    """
    Handles password hashing and verification.
    
    Responsibility: Secure password storage.
    Stakeholder: Security team defining encryption standards.
    """
    
    @staticmethod
    def hash(password: str, salt: str = None) -> tuple[str, str]:
        """
        Hash a password with a salt.
        
        Returns:
            (hashed_password, salt) tuple
        """
        if salt is None:
            salt = secrets.token_hex(16)
        
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        
        return hashed.hex(), salt
    
    @staticmethod
    def verify(password: str, hashed: str, salt: str) -> bool:
        """Verify a password against a hash."""
        new_hash, _ = PasswordHasher.hash(password, salt)
        return new_hash == hashed


# user_repository.py
"""Data persistence."""

from typing import Optional

class UserRepository:
    """
    Handles user data persistence.
    
    Responsibility: Store and retrieve users from database.
    Stakeholder: DBA managing database infrastructure.
    """
    
    def __init__(self):
        # Using in-memory storage for demonstration
        # In production, this would be a real database
        self._users = {}
    
    def save(self, user: User) -> None:
        """Save a user to the database."""
        self._users[user.id] = user
    
    def get(self, user_id: str) -> Optional[User]:
        """Retrieve a user by ID."""
        return self._users.get(user_id)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Retrieve a user by email."""
        for user in self._users.values():
            if user.email == email:
                return user
        return None
    
    def exists(self, user_id: str) -> bool:
        """Check if a user exists."""
        return user_id in self._users
    
    def delete(self, user_id: str) -> None:
        """Delete a user."""
        if user_id in self._users:
            del self._users[user_id]


# email_service.py
"""Email sending."""

class EmailService:
    """
    Sends emails to users.
    
    Responsibility: Email delivery.
    Stakeholder: Marketing/ops team managing email provider.
    """
    
    def __init__(self, smtp_host: str = 'smtp.example.com'):
        self.smtp_host = smtp_host
    
    def send_welcome_email(self, email: str, name: str) -> None:
        """Send welcome email to new user."""
        subject = "Welcome to Our Service!"
        body = f"""
        Hello {name},
        
        Welcome to our service! We're excited to have you on board.
        
        Best regards,
        The Team
        """
        
        self._send(email, subject, body)
    
    def _send(self, to: str, subject: str, body: str) -> None:
        """
        Send an email.
        
        In production, this would use smtplib or an email service API.
        For demonstration, we just print.
        """
        print(f"[EMAIL] To: {to}")
        print(f"[EMAIL] Subject: {subject}")
        print(f"[EMAIL] Body: {body}")


# user_service.py
"""Application service - coordinates user operations."""

class UserRegistrationService:
    """
    Coordinates user registration process.
    
    Responsibility: Orchestrate user creation workflow.
    Stakeholder: Product owner defining registration flow.
    
    This class brings together multiple single-responsibility
    components to accomplish a business use case.
    """
    
    def __init__(
        self,
        user_repository: UserRepository,
        email_service: EmailService,
        email_validator: EmailValidator = None,
        password_validator: PasswordValidator = None,
        password_hasher: PasswordHasher = None
    ):
        self.user_repository = user_repository
        self.email_service = email_service
        self.email_validator = email_validator or EmailValidator()
        self.password_validator = password_validator or PasswordValidator()
        self.password_hasher = password_hasher or PasswordHasher()
    
    def register(self, user_id: str, name: str, email: str, password: str) -> User:
        """
        Register a new user.
        
        Orchestrates:
        1. Validation (delegates to validators)
        2. Password hashing (delegates to hasher)
        3. User creation (delegates to User class)
        4. Persistence (delegates to repository)
        5. Welcome email (delegates to email service)
        
        This class's responsibility is coordination, not implementation.
        """
        # Check if user already exists
        if self.user_repository.exists(user_id):
            raise ValueError(f"User {user_id} already exists")
        
        if self.user_repository.get_by_email(email):
            raise ValueError(f"Email {email} already registered")
        
        # Validate email
        if not self.email_validator.is_valid(email):
            raise ValueError(f"Invalid email address: {email}")
        
        # Validate password strength
        if not self.password_validator.is_strong(password):
            raise ValueError("Password does not meet strength requirements")
        
        # Hash password
        password_hash, salt = self.password_hasher.hash(password)
        
        # Create user
        user = User(user_id, name, email, f"{password_hash}:{salt}")
        
        # Save to database
        self.user_repository.save(user)
        
        # Send welcome email
        self.email_service.send_welcome_email(email, name)
        
        return user


# user_report_generator.py
"""Report generation."""

class UserReportGenerator:
    """
    Generates user reports.
    
    Responsibility: Format user data for reports.
    Stakeholder: Business analyst defining report requirements.
    """
    
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
    
    def generate_summary(self, user_id: str) -> str:
        """Generate a summary report for a user."""
        user = self.user_repository.get(user_id)
        
        if not user:
            return f"User {user_id} not found"
        
        status = "Active" if user.is_active else "Inactive"
        
        return f"""
        User Report
        ===========
        ID: {user.id}
        Name: {user.name}
        Email: {user.email}
        Status: {status}
        """
```

### Usage

```python
# Create dependencies
repository = UserRepository()
email_service = EmailService()

# Create registration service
registration = UserRegistrationService(repository, email_service)

# Register a user
try:
    user = registration.register(
        user_id="U001",
        name="Alice Smith",
        email="alice@example.com",
        password="SecurePass123"
    )
    print(f"✓ Registered: {user}")
except ValueError as e:
    print(f"✗ Error: {e}")

# Generate report
report_gen = UserReportGenerator(repository)
report = report_gen.generate_summary("U001")
print(report)
```

### Explanation

**What changed:**

Before: One `UserManager` class with 7 responsibilities
After: 7 focused classes, each with 1 responsibility

**Each class has a single reason to change:**

1. **User** - Business rules change ("users need a status field")
2. **EmailValidator** - Validation rules change ("allow plus addressing")
3. **PasswordValidator** - Security requirements change ("require special characters")
4. **PasswordHasher** - Encryption standards change ("use bcrypt instead of PBKDF2")
5. **UserRepository** - Database changes ("migrate to PostgreSQL")
6. **EmailService** - Email provider changes ("switch to SendGrid")
7. **UserReportGenerator** - Report format changes ("add more fields")

**The coordinator:**

`UserRegistrationService` doesn't have its own logic—it coordinates other components. This is its single responsibility: orchestration.

## Benefits

### Easier to Understand

Each class is small and focused. You can understand `EmailValidator` in 10 seconds:

```python
class EmailValidator:
    @staticmethod
    def is_valid(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
```

Compare that to understanding a 500-line god class.

### Easier to Test

Test each responsibility in isolation:

```python
def test_email_validation():
    assert EmailValidator.is_valid("user@example.com")
    assert not EmailValidator.is_valid("invalid-email")
    assert not EmailValidator.is_valid("")

def test_password_strength():
    assert PasswordValidator.is_strong("SecurePass123")
    assert not PasswordValidator.is_strong("weak")
    assert not PasswordValidator.is_strong("NoDigits")
```

No need to set up database, email server, etc. just to test validation.

### Easier to Change

Need to change password hashing? Modify `PasswordHasher` only:

```python
class PasswordHasher:
    @staticmethod
    def hash(password: str, salt: str = None) -> tuple[str, str]:
        # Changed from PBKDF2 to bcrypt
        import bcrypt
        if salt is None:
            salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode(), salt)
        return hashed.decode(), salt.decode()
```

Nothing else needs to change.

### Easier to Reuse

Want to use email validation elsewhere? Just import `EmailValidator`:

```python
from validators import EmailValidator

# Use in different context
if EmailValidator.is_valid(contact_email):
    # ...
```

Can't easily extract validation from a god class.

## Trade-offs

### More Classes

Single responsibility creates more classes. One large class becomes many small ones.

**Is this bad?**
- If you have good tooling (IDE navigation), no problem
- If classes are well-named, easier to find things
- But for very simple cases, might be overkill

### More Indirection

To register a user, you now coordinate multiple classes:

```python
# More verbose than god class
registration = UserRegistrationService(repository, email_service)
user = registration.register(...)

# vs.
manager = UserManager()
manager.create_user(...)
```

**Trade-off:** More setup for better separation.

### Risk of Over-Splitting

Can go too far:

```python
# Too granular?
class EmailAtSymbolValidator:
    def validate(self, email):
        return '@' in email

class EmailDotValidator:
    def validate(self, email):
        return '.' in email
```

**Balance:** Split when responsibilities diverge, not just to make smaller classes.

## Common Mistakes

### Splitting by Layer Instead of Responsibility

```python
# Bad: Split by technical concern, not business responsibility
class UserData:
    def __init__(self, id, name, email):
        self.id = id
        self.name = name
        self.email = email

class UserLogic:
    def create_user(self, data):
        # validation logic
        pass

class UserPersistence:
    def save_user(self, user):
        # database logic
        pass
```

This isn't SRP—it's just arbitrary splitting. Each class doesn't have a clear purpose.

**Better:** Split by actual stakeholder concerns (validation, hashing, storage).

### Utility Classes with Many Static Methods

```python
# Bad: Utility classes often hide multiple responsibilities
class Utils:
    @staticmethod
    def validate_email(email): ...
    
    @staticmethod
    def hash_password(password): ...
    
    @staticmethod
    def send_email(to, subject, body): ...
    
    @staticmethod
    def format_date(date): ...
```

This is just a god class disguised as a utility class.

**Better:** Separate classes for email validation, password hashing, etc.

### Confusing "One Responsibility" with "One Method"

```python
# Not necessary - these are the same responsibility
class UserNameGetter:
    def get(self, user):
        return user.name

class UserEmailGetter:
    def get(self, user):
        return user.email
```

SRP doesn't mean one method per class. It means one reason to change.

## Testing

```python
# test_validators.py
def test_email_validator_accepts_valid_emails():
    assert EmailValidator.is_valid("user@example.com")
    assert EmailValidator.is_valid("test.user@company.co.uk")

def test_email_validator_rejects_invalid_emails():
    assert not EmailValidator.is_valid("not-an-email")
    assert not EmailValidator.is_valid("@example.com")
    assert not EmailValidator.is_valid("user@")

def test_password_validator_strong_password():
    assert PasswordValidator.is_strong("SecurePass123")

def test_password_validator_weak_password():
    assert not PasswordValidator.is_strong("weak")
    assert not PasswordValidator.is_strong("NOCAPS123")
    assert not PasswordValidator.is_strong("nodigits")


# test_user_service.py
def test_register_valid_user():
    repo = UserRepository()
    email = EmailService()
    service = UserRegistrationService(repo, email)
    
    user = service.register("U001", "Alice", "alice@example.com", "SecurePass123")
    
    assert user.name == "Alice"
    assert repo.exists("U001")

def test_register_duplicate_user_raises_error():
    repo = UserRepository()
    email = EmailService()
    service = UserRegistrationService(repo, email)
    
    service.register("U001", "Alice", "alice@example.com", "SecurePass123")
    
    with pytest.raises(ValueError, match="already exists"):
        service.register("U001", "Bob", "bob@example.com", "SecurePass123")

def test_register_invalid_email_raises_error():
    repo = UserRepository()
    email = EmailService()
    service = UserRegistrationService(repo, email)
    
    with pytest.raises(ValueError, match="Invalid email"):
        service.register("U001", "Alice", "not-an-email", "SecurePass123")
```

## Related Patterns

- **Chapter 5: Open/Closed Principle** - Often achieved through SRP
- **Chapter 8: Dependency Inversion** - Makes SRP classes easy to swap
- **Chapter 13: Hexagonal Architecture** - SRP at the architectural level

## Summary

The Single Responsibility Principle states that a class should have only one reason to change. This isn't about "doing one thing"—it's about serving one stakeholder, one purpose.

By separating concerns into focused classes, you create code that's easier to understand, test, and modify. The key is identifying true responsibilities (reasons to change) rather than arbitrarily splitting code.

## Further Reading

- **Robert C. Martin** - *Clean Code* - Chapter on classes and SRP
- **Robert C. Martin** - *Agile Software Development, Principles, Patterns, and Practices* - Original SRP formulation
- **Steve Freeman & Nat Pryce** - *Growing Object-Oriented Software, Guided by Tests* - SRP through testing
