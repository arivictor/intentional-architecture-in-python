# Chapter 8: Dependency Inversion Principle

## Introduction

The Dependency Inversion Principle (DIP) is the final SOLID principle and one of the most powerful. It states: **High-level modules should not depend on low-level modules. Both should depend on abstractions.**

This principle inverts the typical dependency structure. Instead of your business logic depending on specific implementations (databases, APIs, email services), both depend on abstract interfaces. This makes your code flexible, testable, and resilient to change.

## The Problem

Depending directly on concrete implementations creates tight coupling and makes testing difficult.

**Symptoms:**
- Business logic tied to specific frameworks or libraries
- Cannot test without database/network/filesystem
- Changing implementation requires modifying business logic
- Hard to swap implementations
- Difficult to mock dependencies

**Example of the problem:**

```python
import smtplib
import requests
from twilio.rest import Client


class NotificationService:
    """A service tightly coupled to specific implementations."""
    
    def __init__(self, smtp_host: str, twilio_sid: str, twilio_token: str):
        self.smtp_host = smtp_host
        self.twilio_sid = twilio_sid
        self.twilio_token = twilio_token
    
    def send_notification(self, user, message, method):
        """Send notification using hardcoded implementations."""
        if method == 'email':
            # Directly coupled to SMTP
            server = smtplib.SMTP(self.smtp_host)
            server.send_message(
                from_addr='noreply@example.com',
                to_addrs=user['email'],
                msg=message
            )
            server.quit()
        
        elif method == 'sms':
            # Directly coupled to Twilio
            client = Client(self.twilio_sid, self.twilio_token)
            client.messages.create(
                to=user['phone'],
                from_='+1234567890',
                body=message
            )
        
        elif method == 'push':
            # Directly coupled to specific push notification API
            response = requests.post(
                'https://push-api.example.com/send',
                json={
                    'device_id': user['device_id'],
                    'message': message
                }
            )
            if response.status_code != 200:
                raise Exception('Push notification failed')


# Usage
service = NotificationService('smtp.gmail.com', 'TWILIO_SID', 'TWILIO_TOKEN')
user = {'email': 'user@example.com', 'phone': '+1234567890', 'device_id': 'abc123'}
service.send_notification(user, 'Hello!', 'email')
```

**Problems:**
- Cannot test without real SMTP server, Twilio account, push API
- Switching email provider requires modifying NotificationService
- Adding new notification method requires editing existing code
- Business logic mixed with infrastructure details
- High-level notification logic depends on low-level implementation details

## The Pattern

**Dependency Inversion Principle:** Depend on abstractions, not concretions.

This involves two key ideas:

1. **High-level modules should not depend on low-level modules.** Both should depend on abstractions (interfaces).
2. **Abstractions should not depend on details.** Details should depend on abstractions.

### Key Concepts

- **High-level module:** Contains business logic and policy (NotificationService)
- **Low-level module:** Handles implementation details (SMTP, Twilio, Push API)
- **Abstraction:** An interface that defines what something does, not how (NotificationChannel)

The dependency arrow is inverted: instead of business logic → implementation, we have business logic → interface ← implementation.

```
Traditional:
NotificationService → SMTPClient, TwilioClient, PushClient

Inverted:
NotificationService → NotificationChannel ← EmailChannel, SMSChannel, PushChannel
```

## Implementation

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Message:
    """Value object representing a notification message."""
    recipient: str
    subject: str
    body: str


class NotificationChannel(ABC):
    """
    Abstract notification channel interface.
    
    This is the abstraction that both high-level and low-level modules depend on.
    """
    
    @abstractmethod
    def send(self, message: Message) -> bool:
        """
        Send a notification message.
        
        Args:
            message: The message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass


class EmailChannel(NotificationChannel):
    """Email notification implementation."""
    
    def __init__(self, smtp_host: str, sender: str):
        self.smtp_host = smtp_host
        self.sender = sender
    
    def send(self, message: Message) -> bool:
        """Send email notification."""
        # In real implementation: use smtplib
        print(f"[EMAIL via {self.smtp_host}] To: {message.recipient}")
        print(f"Subject: {message.subject}")
        print(f"Body: {message.body}")
        return True


class SMSChannel(NotificationChannel):
    """SMS notification implementation."""
    
    def __init__(self, api_key: str, sender_number: str):
        self.api_key = api_key
        self.sender_number = sender_number
    
    def send(self, message: Message) -> bool:
        """Send SMS notification."""
        # In real implementation: use Twilio or similar
        print(f"[SMS from {self.sender_number}] To: {message.recipient}")
        print(f"Message: {message.subject} - {message.body}")
        return True


class PushChannel(NotificationChannel):
    """Push notification implementation."""
    
    def __init__(self, api_endpoint: str):
        self.api_endpoint = api_endpoint
    
    def send(self, message: Message) -> bool:
        """Send push notification."""
        # In real implementation: call push notification API
        print(f"[PUSH via {self.api_endpoint}] Device: {message.recipient}")
        print(f"Alert: {message.subject} - {message.body}")
        return True


class NotificationService:
    """
    High-level notification service.
    
    Depends on NotificationChannel abstraction, not concrete implementations.
    This allows for easy testing, extension, and modification.
    """
    
    def __init__(self, channels: List[NotificationChannel]):
        self.channels = channels
    
    def notify(self, recipient: str, subject: str, body: str) -> int:
        """
        Send notification through all configured channels.
        
        Args:
            recipient: Who to notify
            subject: Notification subject
            body: Notification body
            
        Returns:
            Number of successful sends
        """
        message = Message(recipient, subject, body)
        successful = 0
        
        for channel in self.channels:
            try:
                if channel.send(message):
                    successful += 1
            except Exception as e:
                print(f"Failed to send via {channel.__class__.__name__}: {e}")
        
        return successful
    
    def notify_via_specific_channel(
        self, 
        channel_type: type, 
        recipient: str, 
        subject: str, 
        body: str
    ) -> bool:
        """Send notification via a specific channel type."""
        message = Message(recipient, subject, body)
        
        for channel in self.channels:
            if isinstance(channel, channel_type):
                return channel.send(message)
        
        raise ValueError(f"No channel of type {channel_type.__name__} configured")


# Usage example
if __name__ == "__main__":
    # Configure channels
    email = EmailChannel(smtp_host="smtp.gmail.com", sender="noreply@example.com")
    sms = SMSChannel(api_key="TWILIO_KEY", sender_number="+1234567890")
    push = PushChannel(api_endpoint="https://push-api.example.com")
    
    # Inject dependencies - high-level service depends on abstractions
    service = NotificationService(channels=[email, sms, push])
    
    # Use the service
    print("Sending notification to all channels:")
    sent_count = service.notify(
        recipient="user@example.com",
        subject="Welcome!",
        body="Thanks for signing up."
    )
    print(f"\nSent via {sent_count} channels\n")
    
    # Use specific channel
    print("Sending via SMS only:")
    service.notify_via_specific_channel(
        SMSChannel,
        recipient="+1987654321",
        subject="Alert",
        body="Your order has shipped!"
    )
```

## Explanation

### Abstraction Layer

The `NotificationChannel` abstract base class is the key abstraction. It defines **what** a notification channel can do (send messages) without specifying **how**.

Both the high-level `NotificationService` and low-level implementations (`EmailChannel`, `SMSChannel`, `PushChannel`) depend on this abstraction.

### Dependency Injection

The `NotificationService` doesn't create its own channels. They're injected through the constructor:

```python
service = NotificationService(channels=[email, sms, push])
```

This is **Dependency Injection**, a technique that implements DIP. The service receives its dependencies from the outside rather than creating them internally.

### Benefits of Inversion

**Before (tight coupling):**
- NotificationService creates SMTP client directly
- Cannot test without real email server
- Changing email provider requires modifying service code

**After (loose coupling):**
- NotificationService depends on interface
- Can inject mock channel for testing
- Can swap email provider without touching service code

### Extension Points

Adding a new notification method is easy:

```python
class SlackChannel(NotificationChannel):
    def send(self, message: Message) -> bool:
        # Implement Slack notification
        return True

# No changes to NotificationService needed
service = NotificationService(channels=[email, sms, SlackChannel()])
```

## Benefits

**1. Testability**

You can easily inject test doubles:

```python
class FakeChannel(NotificationChannel):
    def __init__(self):
        self.sent_messages = []
    
    def send(self, message: Message) -> bool:
        self.sent_messages.append(message)
        return True

# Test without real infrastructure
fake = FakeChannel()
service = NotificationService([fake])
service.notify("test@example.com", "Test", "Message")
assert len(fake.sent_messages) == 1
```

**2. Flexibility**

Swap implementations without changing business logic:

```python
# Development: use console logging
dev_channel = ConsoleChannel()

# Production: use real services
prod_channels = [EmailChannel(...), SMSChannel(...)]
```

**3. Maintainability**

Changes to low-level details don't affect high-level policy. Upgrading from one email provider to another only affects the `EmailChannel` implementation.

**4. Parallel Development**

Teams can work independently. One team builds the service using the interface, another builds the implementations.

**5. Reusability**

The `NotificationService` can be reused with any `NotificationChannel` implementation, not just the original ones.

## Trade-offs

**When NOT to use DIP:**

**1. Simple Scripts or Prototypes**

For one-off scripts or quick prototypes, abstractions add unnecessary complexity:

```python
# Overkill for a simple script
import smtplib
smtplib.SMTP('localhost').send_message(...)  # Just do it directly
```

**2. Stable Dependencies**

If you're never going to swap the implementation, abstraction might be overkill:

```python
# Python's built-in json module is stable - no need to abstract
import json
data = json.loads(response)  # No need for IJsonParser interface
```

**3. Overhead**

DIP adds:
- More files/classes to maintain
- Indirection that can make code harder to trace
- Setup complexity (dependency injection)

**4. Over-abstraction**

Don't create interfaces for everything "just in case." Wait until you have a real need:

```python
# Probably unnecessary
class IStringConcatenator(ABC):
    @abstractmethod
    def concatenate(self, a: str, b: str) -> str:
        pass
```

## Testing

```python
import pytest
from typing import List


class FakeNotificationChannel(NotificationChannel):
    """Test double for testing NotificationService."""
    
    def __init__(self, should_succeed: bool = True):
        self.should_succeed = should_succeed
        self.sent_messages: List[Message] = []
    
    def send(self, message: Message) -> bool:
        self.sent_messages.append(message)
        return self.should_succeed


class FailingChannel(NotificationChannel):
    """Channel that always fails."""
    
    def send(self, message: Message) -> bool:
        raise Exception("Network error")


def test_notify_sends_to_all_channels():
    """Test that notification is sent to all configured channels."""
    fake1 = FakeNotificationChannel()
    fake2 = FakeNotificationChannel()
    service = NotificationService([fake1, fake2])
    
    sent = service.notify("user@test.com", "Hello", "Test message")
    
    assert sent == 2
    assert len(fake1.sent_messages) == 1
    assert len(fake2.sent_messages) == 1
    assert fake1.sent_messages[0].recipient == "user@test.com"


def test_notify_handles_channel_failures():
    """Test that service continues if one channel fails."""
    good_channel = FakeNotificationChannel()
    bad_channel = FailingChannel()
    service = NotificationService([good_channel, bad_channel])
    
    sent = service.notify("user@test.com", "Hello", "Test")
    
    assert sent == 1  # Only the good channel succeeded
    assert len(good_channel.sent_messages) == 1


def test_notify_via_specific_channel():
    """Test sending via a specific channel type."""
    email = EmailChannel("smtp.test.com", "test@sender.com")
    sms = SMSChannel("API_KEY", "+1234567890")
    service = NotificationService([email, sms])
    
    result = service.notify_via_specific_channel(
        SMSChannel, "+1999999999", "Alert", "Test"
    )
    
    assert result is True


def test_notify_via_nonexistent_channel_raises_error():
    """Test that requesting nonexistent channel raises error."""
    email = EmailChannel("smtp.test.com", "test@sender.com")
    service = NotificationService([email])
    
    with pytest.raises(ValueError, match="No channel of type SMSChannel"):
        service.notify_via_specific_channel(
            SMSChannel, "+1999999999", "Alert", "Test"
        )


def test_message_creation():
    """Test that Message value object is created correctly."""
    msg = Message("recipient@test.com", "Subject", "Body text")
    
    assert msg.recipient == "recipient@test.com"
    assert msg.subject == "Subject"
    assert msg.body == "Body text"
```

## Common Mistakes

**1. Creating Abstractions Too Early**

Don't create interfaces until you need them. Wait for a second implementation or a testing need before abstracting:

```python
# Premature abstraction - you don't have a second implementation yet
class IUserRepository(ABC):
    @abstractmethod
    def save(self, user): pass

# Just write the concrete class first
class UserRepository:
    def save(self, user):
        # implementation
        pass
```

**2. Leaky Abstractions**

Abstractions shouldn't expose implementation details:

```python
# Bad - abstraction leaks SMTP details
class NotificationChannel(ABC):
    @abstractmethod
    def send(self, smtp_host: str, message: Message):
        pass

# Good - abstraction is generic
class NotificationChannel(ABC):
    @abstractmethod
    def send(self, message: Message):
        pass
```

**3. Depending on Concrete Classes**

Even with abstractions defined, you might still depend on concretions:

```python
# Bad - still coupled to EmailChannel
class NotificationService:
    def __init__(self):
        self.channel = EmailChannel(...)  # Creates concrete class

# Good - depend on abstraction
class NotificationService:
    def __init__(self, channel: NotificationChannel):
        self.channel = channel  # Injected abstraction
```

**4. Abstract Everything**

Not every class needs an interface. Only create abstractions when:
- You need to swap implementations
- You need to test with mocks
- Multiple implementations will exist
- You're designing a plugin system

```python
# Probably unnecessary - datetime.now() is stable
class ITimeProvider(ABC):
    @abstractmethod
    def now(self): pass

# Just use datetime directly for simple cases
from datetime import datetime
now = datetime.now()
```

## Related Patterns

- **Chapter 2 (Test-Driven Development):** DIP makes TDD easier by allowing dependency injection
- **Chapter 4 (Single Responsibility):** Each class should have one responsibility; DIP helps separate concerns
- **Chapter 5 (Open/Closed):** DIP supports OCP by making code open for extension (new channels)
- **Chapter 13 (Hexagonal Architecture):** DIP is fundamental to ports and adapters architecture
- **Chapter 14 (Repository Pattern):** Repositories are a classic example of DIP (abstract data access)
- **Chapter 16 (Factory Pattern):** Factories help create and inject dependencies

## Summary

The Dependency Inversion Principle inverts the traditional dependency structure by having both high-level business logic and low-level implementation details depend on abstractions. This makes code testable, flexible, and maintainable.

Use DIP when you need to swap implementations, test with mocks, or keep business logic independent of infrastructure details. Skip it for simple scripts, stable dependencies, or when you're certain the implementation will never change.

Combined with dependency injection, DIP enables clean architecture where business rules are independent of frameworks, databases, and external services.

## Further Reading

- Martin, Robert C. "The Dependency Inversion Principle." *C++ Report*, 1996.
- Seemann, Mark. *Dependency Injection in .NET*. Manning Publications, 2011.
- Martin, Robert C. *Clean Architecture*. Prentice Hall, 2017. (Chapter 11: DIP)
- Freeman, Steve, and Nat Pryce. *Growing Object-Oriented Software, Guided by Tests*. Addison-Wesley, 2009.
- Fowler, Martin. "Inversion of Control Containers and the Dependency Injection pattern." martinfowler.com, 2004.
