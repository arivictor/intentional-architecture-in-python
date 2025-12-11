# Chapter 13: Hexagonal Architecture (Ports & Adapters)

## Introduction

**Hexagonal Architecture**, also known as **Ports and Adapters**, organizes code around the domain logic, isolating it from external concerns. The domain sits at the center, defining **ports** (interfaces) for what it needs. **Adapters** implement these ports for specific technologies (databases, APIs, UI).

This architecture makes the business logic technology-agnostic and highly testable. You can swap databases, web frameworks, or external services without touching the core domain.

## The Problem

Tightly coupling business logic to frameworks and infrastructure makes testing difficult and changes risky.

**Symptoms:**
- Business logic mixed with framework code
- Can't test without running web server or database
- Switching database requires rewriting business logic
- Domain depends on specific libraries
- Hard to add new interfaces (CLI, API, GUI)

**Example of the problem:**

```python
from flask import Flask, request, jsonify
import smtplib
import sqlite3

app = Flask(__name__)

@app.route('/send-notification', methods=['POST'])
def send_notification():
    """Business logic tightly coupled to Flask and SMTP."""
    # Parse Flask request
    data = request.get_json()
    recipient = data['email']
    message = data['message']
    
    # Business logic mixed with infrastructure
    if not recipient or '@' not in recipient:
        return jsonify({'error': 'Invalid email'}), 400
    
    # Directly coupled to SMTP
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login('user@example.com', 'password')
        server.sendmail('sender@example.com', recipient, message)
        server.quit()
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    # Log to database - directly coupled to SQLite
    conn = sqlite3.connect('notifications.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO notifications (recipient, message, sent_at) VALUES (?, ?, datetime("now"))',
        (recipient, message)
    )
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'sent'}), 200
```

**Problems:**
- Can't test business logic without Flask, SMTP server, and SQLite
- Changing from SMTP to SendGrid requires modifying business logic
- Can't reuse logic in CLI or background job
- Business rules (email validation) mixed with infrastructure
- Domain depends on Flask, smtplib, sqlite3

## The Pattern

**Hexagonal Architecture:** Place the domain at the center. Define ports (interfaces) for what the domain needs. Implement adapters for specific technologies.

### Structure

```
          +--------------------+
          |   Primary Adapters |  (Web API, CLI, Tests)
          |  (Drive the app)   |
          +--------------------+
                    |
                    v
        +-------------------------+
        |    Application Core     |
        |    (Use Cases / Ports)  |
        |  +-------------------+  |
        |  |   Domain Logic    |  |
        |  | (Business Rules)  |  |
        |  +-------------------+  |
        +-------------------------+
                    |
                    v
          +--------------------+
          | Secondary Adapters |  (Database, Email, APIs)
          |  (Driven by app)   |
          +--------------------+
```

**Ports:** Interfaces defined by the application
- **Primary (Driving) Ports:** How the app is used (e.g., SendNotification use case)
- **Secondary (Driven) Ports:** What the app needs (e.g., NotificationSender, NotificationLogger)

**Adapters:** Implementations of ports
- **Primary Adapters:** REST API, CLI, GUI
- **Secondary Adapters:** SMTP sender, Database logger, File logger

## Implementation

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


# =============================================================================
# DOMAIN / CORE
# =============================================================================

@dataclass
class Notification:
    """Domain entity."""
    recipient: str
    message: str
    sent_at: Optional[datetime] = None
    
    def __post_init__(self):
        # Business rule
        if not self.recipient or '@' not in self.recipient:
            raise ValueError("Invalid email address")
        if not self.message:
            raise ValueError("Message cannot be empty")


# =============================================================================
# PORTS (Interfaces defined by core)
# =============================================================================

class NotificationSender(ABC):
    """
    Secondary port: sending notifications.
    
    Domain defines what it needs. Infrastructure implements it.
    """
    
    @abstractmethod
    def send(self, recipient: str, message: str) -> bool:
        """Send notification. Returns True if successful."""
        pass


class NotificationLogger(ABC):
    """Secondary port: logging notifications."""
    
    @abstractmethod
    def log(self, notification: Notification) -> None:
        """Log a notification."""
        pass
    
    @abstractmethod
    def get_recent(self, limit: int = 10) -> List[Notification]:
        """Get recent notifications."""
        pass


class SendNotificationUseCase:
    """
    Primary port (driving): application use case.
    
    This is how the application is used from the outside.
    """
    
    def __init__(self, sender: NotificationSender, logger: NotificationLogger):
        self.sender = sender
        self.logger = logger
    
    def execute(self, recipient: str, message: str) -> Notification:
        """
        Send a notification.
        
        Pure business logic - no framework dependencies.
        """
        # Create domain object (validates)
        notification = Notification(recipient, message)
        
        # Send via port
        success = self.sender.send(recipient, message)
        if not success:
            raise RuntimeError("Failed to send notification")
        
        # Mark as sent
        notification = Notification(recipient, message, datetime.now())
        
        # Log via port
        self.logger.log(notification)
        
        return notification


# =============================================================================
# ADAPTERS (Secondary/Driven - Infrastructure)
# =============================================================================

class EmailNotificationSender(NotificationSender):
    """Adapter: send notifications via email (SMTP)."""
    
    def __init__(self, smtp_host: str, smtp_port: int = 587):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
    
    def send(self, recipient: str, message: str) -> bool:
        """Send email notification."""
        print(f"[EmailSender] Sending to {recipient} via {self.smtp_host}")
        print(f"Message: {message}")
        # In real implementation: use smtplib
        return True


class SMSNotificationSender(NotificationSender):
    """Adapter: send notifications via SMS."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def send(self, recipient: str, message: str) -> bool:
        """Send SMS notification."""
        print(f"[SMSSender] Sending SMS to {recipient}")
        print(f"Message: {message}")
        # In real implementation: call SMS API
        return True


class InMemoryNotificationLogger(NotificationLogger):
    """Adapter: log notifications in memory."""
    
    def __init__(self):
        self._logs: List[Notification] = []
    
    def log(self, notification: Notification) -> None:
        """Log notification."""
        self._logs.append(notification)
        print(f"[InMemoryLogger] Logged notification to {notification.recipient}")
    
    def get_recent(self, limit: int = 10) -> List[Notification]:
        """Get recent notifications."""
        return self._logs[-limit:]


class FileNotificationLogger(NotificationLogger):
    """Adapter: log notifications to file."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
    
    def log(self, notification: Notification) -> None:
        """Log to file."""
        with open(self.filepath, 'a') as f:
            f.write(f"{notification.sent_at}: {notification.recipient} - {notification.message}\n")
        print(f"[FileLogger] Logged to {self.filepath}")
    
    def get_recent(self, limit: int = 10) -> List[Notification]:
        """Get recent from file."""
        try:
            with open(self.filepath, 'r') as f:
                lines = f.readlines()
                return lines[-limit:]  # Simplified
        except FileNotFoundError:
            return []


# =============================================================================
# ADAPTERS (Primary/Driving - Entry points)
# =============================================================================

class WebAPIAdapter:
    """Adapter: REST API interface."""
    
    def __init__(self, use_case: SendNotificationUseCase):
        self.use_case = use_case
    
    def handle_send_notification(self, request_data: dict) -> tuple[dict, int]:
        """Handle POST /notifications request."""
        try:
            recipient = request_data.get('email')
            message = request_data.get('message')
            
            notification = self.use_case.execute(recipient, message)
            
            return {
                'status': 'sent',
                'recipient': notification.recipient,
                'sent_at': notification.sent_at.isoformat() if notification.sent_at else None
            }, 200
            
        except ValueError as e:
            return {'error': str(e)}, 400
        except RuntimeError as e:
            return {'error': str(e)}, 500


class CLIAdapter:
    """Adapter: Command-line interface."""
    
    def __init__(self, use_case: SendNotificationUseCase):
        self.use_case = use_case
    
    def send_command(self, recipient: str, message: str) -> None:
        """CLI command to send notification."""
        try:
            notification = self.use_case.execute(recipient, message)
            print(f"✓ Notification sent to {notification.recipient}")
        except (ValueError, RuntimeError) as e:
            print(f"✗ Error: {e}")


# =============================================================================
# COMPOSITION ROOT
# =============================================================================

if __name__ == "__main__":
    print("=== Configuration 1: Email + InMemory ===\n")
    
    # Wire up adapters
    email_sender = EmailNotificationSender("smtp.gmail.com")
    memory_logger = InMemoryNotificationLogger()
    
    # Create use case with adapters
    use_case = SendNotificationUseCase(email_sender, memory_logger)
    
    # Use via Web API adapter
    api = WebAPIAdapter(use_case)
    response, status = api.handle_send_notification({
        'email': 'user@example.com',
        'message': 'Hello from Web API!'
    })
    print(f"API Response ({status}): {response}\n")
    
    # Use via CLI adapter
    cli = CLIAdapter(use_case)
    cli.send_command('admin@example.com', 'Hello from CLI!')
    
    print("\n=== Configuration 2: SMS + File (NO CODE CHANGES!) ===\n")
    
    # Swap adapters - core unchanged
    sms_sender = SMSNotificationSender("SMS_API_KEY")
    file_logger = FileNotificationLogger("/tmp/notifications.log")
    
    use_case2 = SendNotificationUseCase(sms_sender, file_logger)
    api2 = WebAPIAdapter(use_case2)
    
    response, status = api2.handle_send_notification({
        'email': '+1234567890',
        'message': 'Hello via SMS!'
    })
    print(f"API Response ({status}): {response}")
```

## Explanation

### Domain at the Center

The `Notification` class and `SendNotificationUseCase` have no dependencies on frameworks or infrastructure:

```python
class SendNotificationUseCase:
    def __init__(self, sender: NotificationSender, logger: NotificationLogger):
        # Depends on interfaces, not concrete implementations
        self.sender = sender
        self.logger = logger
```

### Ports Define Needs

The core defines what it needs through interfaces:

```python
class NotificationSender(ABC):
    @abstractmethod
    def send(self, recipient: str, message: str) -> bool:
        pass
```

### Adapters Implement Ports

Infrastructure implements the ports:

```python
class EmailNotificationSender(NotificationSender):
    def send(self, recipient: str, message: str) -> bool:
        # SMTP implementation
        pass

class SMSNotificationSender(NotificationSender):
    def send(self, recipient: str, message: str) -> bool:
        # SMS API implementation
        pass
```

### Swappable Infrastructure

Change infrastructure without touching core:

```python
# Configuration 1
use_case = SendNotificationUseCase(
    EmailNotificationSender("smtp.gmail.com"),
    InMemoryNotificationLogger()
)

# Configuration 2 - different adapters, same core
use_case = SendNotificationUseCase(
    SMSNotificationSender("API_KEY"),
    FileNotificationLogger("/tmp/log.txt")
)
```

## Benefits

**1. Technology Independence**

Business logic doesn't depend on any specific technology. Swap databases, frameworks, or external services without touching the core.

**2. Testability**

Test core logic with fake adapters:

```python
fake_sender = FakeNotificationSender()
fake_logger = FakeNotificationLogger()
use_case = SendNotificationUseCase(fake_sender, fake_logger)
# Test without real email or database
```

**3. Multiple Interfaces**

Same core logic, different entry points:

```python
# Same use case
web_api = WebAPIAdapter(use_case)
cli = CLIAdapter(use_case)
gui = GUIAdapter(use_case)
```

**4. Delayed Decisions**

Decide infrastructure details later. Start with in-memory implementations, swap for real ones when ready.

**5. Clear Boundaries**

Ports create explicit boundaries. Clear what the core provides and what it needs.

## Trade-offs

**When NOT to use hexagonal architecture:**

**1. Simple CRUD Apps**

For basic data entry, the extra abstraction is overkill.

**2. Prototypes**

When exploring, start simple. Add hexagonal structure when you understand the domain.

**3. Overhead**

Hexagonal architecture adds:
- More interfaces and classes
- Indirection
- Need to understand ports/adapters concept
- Configuration complexity

**4. Small Scripts**

One-off scripts don't need this level of abstraction.

## Testing

```python
import pytest


class FakeNotificationSender(NotificationSender):
    def __init__(self):
        self.sent_notifications = []
    
    def send(self, recipient: str, message: str) -> bool:
        self.sent_notifications.append((recipient, message))
        return True


class FakeNotificationLogger(NotificationLogger):
    def __init__(self):
        self.logged_notifications = []
    
    def log(self, notification: Notification) -> None:
        self.logged_notifications.append(notification)
    
    def get_recent(self, limit: int = 10) -> List[Notification]:
        return self.logged_notifications[-limit:]


def test_send_notification_use_case():
    """Test use case with fake adapters."""
    sender = FakeNotificationSender()
    logger = FakeNotificationLogger()
    use_case = SendNotificationUseCase(sender, logger)
    
    notification = use_case.execute('test@example.com', 'Test message')
    
    assert notification.recipient == 'test@example.com'
    assert len(sender.sent_notifications) == 1
    assert len(logger.logged_notifications) == 1


def test_invalid_email_raises_error():
    """Test that invalid email raises ValueError."""
    sender = FakeNotificationSender()
    logger = FakeNotificationLogger()
    use_case = SendNotificationUseCase(sender, logger)
    
    with pytest.raises(ValueError, match="Invalid email"):
        use_case.execute('invalid-email', 'Test')


def test_web_api_adapter():
    """Test Web API adapter."""
    sender = FakeNotificationSender()
    logger = FakeNotificationLogger()
    use_case = SendNotificationUseCase(sender, logger)
    api = WebAPIAdapter(use_case)
    
    response, status = api.handle_send_notification({
        'email': 'test@example.com',
        'message': 'Hello'
    })
    
    assert status == 200
    assert response['status'] == 'sent'


def test_cli_adapter():
    """Test CLI adapter."""
    sender = FakeNotificationSender()
    logger = FakeNotificationLogger()
    use_case = SendNotificationUseCase(sender, logger)
    cli = CLIAdapter(use_case)
    
    cli.send_command('test@example.com', 'Hello')
    
    assert len(sender.sent_notifications) == 1
```

## Common Mistakes

**1. Putting Logic in Adapters**

Adapters should be thin. Don't put business logic in them:

```python
# Bad - business logic in adapter
class EmailSender(NotificationSender):
    def send(self, recipient, message):
        if len(message) < 10:  # Business rule!
            raise ValueError("Too short")
        # send email

# Good - business logic in core
class Notification:
    def __post_init__(self):
        if len(self.message) < 10:  # Business rule in domain
            raise ValueError("Too short")
```

**2. Core Depending on Adapters**

Core should only depend on ports, never adapters:

```python
# Bad - core imports concrete adapter
from adapters import EmailSender

class UseCase:
    def __init__(self):
        self.sender = EmailSender()  # Wrong!

# Good - core depends on port
class UseCase:
    def __init__(self, sender: NotificationSender):  # Interface
        self.sender = sender
```

**3. Too Many Ports**

Don't create a port for everything. Only create ports for external dependencies you want to swap:

```python
# Probably overkill
class TimeProvider(ABC):
    @abstractmethod
    def now(self): pass

# Just use datetime directly unless you really need to mock time
```

## Related Patterns

- **Chapter 8 (Dependency Inversion):** Hexagonal architecture implements DIP
- **Chapter 12 (Layered Architecture):** Alternative architectural pattern
- **Chapter 14 (Repository):** Repositories are secondary adapters
- **Chapter 16 (Factory):** Factories can create adapters

## Summary

Hexagonal Architecture places the domain at the center, isolating it from external concerns. The domain defines ports (interfaces) for what it needs. Adapters implement these ports for specific technologies. This makes the core testable, technology-independent, and flexible.

Use hexagonal architecture when you have significant business logic that needs to be independent of frameworks and infrastructure. Skip it for simple CRUD apps, prototypes, or when the overhead outweighs the benefits. Hexagonal architecture is ideal for long-lived systems where technology choices may change over time.

## Further Reading

- Cockburn, Alistair. "Hexagonal Architecture." alistair.cockburn.us, 2005.
- Freeman, Steve, and Nat Pryce. *Growing Object-Oriented Software, Guided by Tests*. Addison-Wesley, 2009.
- Martin, Robert C. *Clean Architecture*. Prentice Hall, 2017.
- Fowler, Martin. "Ports and Adapters." martinfowler.com.
- Palermo, Jeffrey. "The Onion Architecture." jeffreypalermo.com, 2008.
