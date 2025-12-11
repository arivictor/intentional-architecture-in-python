# Chapter 5: Open/Closed Principle

## Introduction

The Open/Closed Principle (OCP) states: **Software entities should be open for extension, closed for modification.** This sounds paradoxical—how can something be both open and closed? The key is understanding that you extend behavior through new code, not by changing existing code.

When requirements change (and they will), you should be able to add functionality without modifying working code. OCP makes systems flexible while keeping them stable.

## The Problem

Every time you add a new feature, you have to modify existing code. This creates risk—changes can introduce bugs, break existing functionality, and require retesting everything.

**Symptoms:**
- Adding a feature requires modifying multiple existing functions
- Long if-else or switch statements that grow with each requirement
- Fear of adding features because "it might break something"
- Extensive retesting needed after small changes

**Example of the problem:**

```python
# payment_processor.py - A class that violates OCP

class PaymentProcessor:
    """Processes payments - but requires modification for each new payment type."""
    
    def process_payment(self, payment_type: str, amount: float, details: dict):
        """Process a payment based on type."""
        
        if payment_type == "credit_card":
            # Credit card processing
            card_number = details["card_number"]
            cvv = details["cvv"]
            expiry = details["expiry"]
            
            # Validate card
            if not self._validate_credit_card(card_number, cvv, expiry):
                raise ValueError("Invalid credit card")
            
            # Charge card
            print(f"Charging ${amount} to credit card {card_number[-4:]}")
            return {"status": "success", "transaction_id": "CC123"}
        
        elif payment_type == "paypal":
            # PayPal processing
            email = details["email"]
            password = details["password"]
            
            # Authenticate
            if not self._authenticate_paypal(email, password):
                raise ValueError("PayPal authentication failed")
            
            # Transfer funds
            print(f"Transferring ${amount} via PayPal to {email}")
            return {"status": "success", "transaction_id": "PP456"}
        
        elif payment_type == "bank_transfer":
            # Bank transfer processing
            account_number = details["account_number"]
            routing_number = details["routing_number"]
            
            # Validate account
            if not self._validate_bank_account(account_number, routing_number):
                raise ValueError("Invalid bank account")
            
            # Initiate transfer
            print(f"Transferring ${amount} to account {account_number}")
            return {"status": "success", "transaction_id": "BT789"}
        
        else:
            raise ValueError(f"Unsupported payment type: {payment_type}")
    
    def _validate_credit_card(self, number, cvv, expiry):
        return len(number) == 16 and len(cvv) == 3
    
    def _authenticate_paypal(self, email, password):
        return "@" in email and len(password) > 6
    
    def _validate_bank_account(self, account, routing):
        return len(account) > 0 and len(routing) > 0
```

**Problems:**
- **Every new payment method requires modifying `process_payment()`**
- Adding cryptocurrency? Modify the function. Adding Apple Pay? Modify again.
- The function grows endlessly with if-elif chains
- Can't test payment methods in isolation
- High risk—changing one payment type might break another

**What happens when we add cryptocurrency:**

```python
elif payment_type == "cryptocurrency":
    # NOW we have to modify this working function
    wallet_address = details["wallet_address"]
    crypto_type = details["crypto_type"]
    
    if not self._validate_wallet(wallet_address):
        raise ValueError("Invalid wallet")
    
    print(f"Transferring ${amount} in {crypto_type} to {wallet_address}")
    return {"status": "success", "transaction_id": "CR999"}
```

This violates OCP—we're modifying existing code instead of extending it.

## The Pattern

**Open/Closed Principle:** Classes should be open for extension but closed for modification.

- **Open for extension:** You can add new behavior
- **Closed for modification:** Existing code doesn't change

**How to achieve this:**
1. **Abstraction:** Define an interface for the behavior
2. **Polymorphism:** Implement different behaviors in different classes
3. **Dependency Inversion:** Depend on the abstraction, not concrete classes

The **Strategy Pattern** is the classic implementation of OCP.

## Implementation

Let's refactor the payment processor to follow OCP using the Strategy pattern.

### Example: Payment Processing System

```python
# payment_strategies.py
from abc import ABC, abstractmethod
from typing import Dict, Any


class PaymentStrategy(ABC):
    """
    Abstract base class for payment strategies.
    
    This is the abstraction that makes OCP possible.
    New payment methods extend this without modifying existing code.
    """
    
    @abstractmethod
    def validate(self, details: Dict[str, Any]) -> bool:
        """Validate payment details before processing."""
        pass
    
    @abstractmethod
    def process(self, amount: float, details: Dict[str, Any]) -> Dict[str, str]:
        """Process the payment and return transaction result."""
        pass
    
    @abstractmethod
    def get_payment_type(self) -> str:
        """Return human-readable payment type name."""
        pass


class CreditCardPayment(PaymentStrategy):
    """Credit card payment strategy."""
    
    def validate(self, details: Dict[str, Any]) -> bool:
        """Validate credit card details."""
        required_fields = ["card_number", "cvv", "expiry"]
        
        if not all(field in details for field in required_fields):
            return False
        
        card_number = details["card_number"]
        cvv = details["cvv"]
        
        # Simple validation
        return len(card_number) == 16 and len(cvv) == 3
    
    def process(self, amount: float, details: Dict[str, Any]) -> Dict[str, str]:
        """Process credit card payment."""
        if not self.validate(details):
            raise ValueError("Invalid credit card details")
        
        card_number = details["card_number"]
        masked_card = f"****{card_number[-4:]}"
        
        # Simulate card processing
        print(f"Charging ${amount:.2f} to credit card {masked_card}")
        
        return {
            "status": "success",
            "transaction_id": f"CC{hash(card_number) % 10000}",
            "method": "credit_card"
        }
    
    def get_payment_type(self) -> str:
        return "Credit Card"


class PayPalPayment(PaymentStrategy):
    """PayPal payment strategy."""
    
    def validate(self, details: Dict[str, Any]) -> bool:
        """Validate PayPal credentials."""
        required_fields = ["email", "password"]
        
        if not all(field in details for field in required_fields):
            return False
        
        email = details["email"]
        password = details["password"]
        
        return "@" in email and len(password) >= 6
    
    def process(self, amount: float, details: Dict[str, Any]) -> Dict[str, str]:
        """Process PayPal payment."""
        if not self.validate(details):
            raise ValueError("Invalid PayPal credentials")
        
        email = details["email"]
        
        # Simulate PayPal processing
        print(f"Transferring ${amount:.2f} via PayPal to {email}")
        
        return {
            "status": "success",
            "transaction_id": f"PP{hash(email) % 10000}",
            "method": "paypal"
        }
    
    def get_payment_type(self) -> str:
        return "PayPal"


class BankTransferPayment(PaymentStrategy):
    """Bank transfer payment strategy."""
    
    def validate(self, details: Dict[str, Any]) -> bool:
        """Validate bank account details."""
        required_fields = ["account_number", "routing_number"]
        
        if not all(field in details for field in required_fields):
            return False
        
        account = details["account_number"]
        routing = details["routing_number"]
        
        return len(account) > 0 and len(routing) > 0
    
    def process(self, amount: float, details: Dict[str, Any]) -> Dict[str, str]:
        """Process bank transfer."""
        if not self.validate(details):
            raise ValueError("Invalid bank account details")
        
        account = details["account_number"]
        
        # Simulate bank transfer
        print(f"Transferring ${amount:.2f} to account ****{account[-4:]}")
        
        return {
            "status": "success",
            "transaction_id": f"BT{hash(account) % 10000}",
            "method": "bank_transfer"
        }
    
    def get_payment_type(self) -> str:
        return "Bank Transfer"


# NEW: Adding cryptocurrency support WITHOUT modifying existing code
class CryptocurrencyPayment(PaymentStrategy):
    """Cryptocurrency payment strategy - EXTENSION, not modification."""
    
    def validate(self, details: Dict[str, Any]) -> bool:
        """Validate cryptocurrency wallet details."""
        required_fields = ["wallet_address", "crypto_type"]
        
        if not all(field in details for field in required_fields):
            return False
        
        wallet = details["wallet_address"]
        crypto_type = details["crypto_type"]
        
        # Simple validation
        return len(wallet) > 20 and crypto_type in ["BTC", "ETH", "USDT"]
    
    def process(self, amount: float, details: Dict[str, Any]) -> Dict[str, str]:
        """Process cryptocurrency payment."""
        if not self.validate(details):
            raise ValueError("Invalid cryptocurrency details")
        
        wallet = details["wallet_address"]
        crypto_type = details["crypto_type"]
        
        # Simulate crypto transfer
        print(f"Transferring ${amount:.2f} in {crypto_type} to {wallet[:10]}...")
        
        return {
            "status": "success",
            "transaction_id": f"CR{hash(wallet) % 10000}",
            "method": "cryptocurrency"
        }
    
    def get_payment_type(self) -> str:
        return "Cryptocurrency"


# payment_processor.py
class PaymentProcessor:
    """
    Payment processor that follows OCP.
    
    This class is CLOSED for modification but OPEN for extension.
    We can add new payment methods without changing this code.
    """
    
    def __init__(self, strategy: PaymentStrategy):
        """Initialize with a payment strategy."""
        self.strategy = strategy
    
    def process_payment(self, amount: float, details: Dict[str, Any]) -> Dict[str, str]:
        """
        Process payment using the configured strategy.
        
        This method never changes, regardless of how many payment types we add.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        print(f"Processing {self.strategy.get_payment_type()} payment...")
        result = self.strategy.process(amount, details)
        print(f"Payment processed successfully: {result['transaction_id']}")
        
        return result
    
    def set_strategy(self, strategy: PaymentStrategy):
        """Change payment strategy at runtime."""
        self.strategy = strategy


# Usage example
def main():
    # Process credit card payment
    credit_card = CreditCardPayment()
    processor = PaymentProcessor(credit_card)
    
    result = processor.process_payment(99.99, {
        "card_number": "1234567890123456",
        "cvv": "123",
        "expiry": "12/25"
    })
    print(f"Result: {result}\n")
    
    # Process PayPal payment
    paypal = PayPalPayment()
    processor.set_strategy(paypal)
    
    result = processor.process_payment(49.99, {
        "email": "user@example.com",
        "password": "securepass"
    })
    print(f"Result: {result}\n")
    
    # Process cryptocurrency payment (NEW - no modification to existing code!)
    crypto = CryptocurrencyPayment()
    processor.set_strategy(crypto)
    
    result = processor.process_payment(199.99, {
        "wallet_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "crypto_type": "BTC"
    })
    print(f"Result: {result}\n")


if __name__ == "__main__":
    main()
```

### Explanation

**What changed:**

1. **Created `PaymentStrategy` abstract base class:** This is the interface that all payment methods must implement
2. **Each payment type is its own class:** `CreditCardPayment`, `PayPalPayment`, `BankTransferPayment`, `CryptocurrencyPayment`
3. **`PaymentProcessor` depends on abstraction:** It takes a `PaymentStrategy`, not a concrete type
4. **Adding new payment methods requires NO changes to existing code:** Just create a new class that implements `PaymentStrategy`

**Key design decisions:**

- `PaymentStrategy` defines the contract: `validate()`, `process()`, `get_payment_type()`
- Each concrete strategy encapsulates its own logic
- `PaymentProcessor` is closed—it never needs modification
- New payment types are extensions, not modifications

## Benefits

### Easy to Extend

Adding a new payment method is simple—create a new class:

```python
class ApplePayPayment(PaymentStrategy):
    def validate(self, details):
        # Apple Pay validation
        pass
    
    def process(self, amount, details):
        # Apple Pay processing
        pass
    
    def get_payment_type(self):
        return "Apple Pay"
```

No existing code changes. No risk of breaking credit card payments.

### Easy to Test

Test each payment strategy in isolation:

```python
def test_credit_card_payment():
    strategy = CreditCardPayment()
    result = strategy.process(100.0, {
        "card_number": "1234567890123456",
        "cvv": "123",
        "expiry": "12/25"
    })
    assert result["status"] == "success"
```

No need to test the entire processor for each payment type.

### Follows Single Responsibility

Each class has one reason to change:
- `CreditCardPayment` changes only when credit card logic changes
- `PayPalPayment` changes only when PayPal logic changes
- `PaymentProcessor` changes only when payment processing flow changes

### Runtime Flexibility

Can switch strategies at runtime:

```python
processor = PaymentProcessor(CreditCardPayment())
# Later...
processor.set_strategy(PayPalPayment())
```

## Trade-offs

### More Classes

Following OCP creates more classes. One `PaymentProcessor` becomes multiple strategy classes.

**Is this bad?**
- For 2-3 payment types, might be overkill
- For 10+ payment types, absolutely worth it
- Balance: How often do requirements change?

### Indirection

Instead of one function with if-statements, you have abstract classes and polymorphism.

**Trade-off:** More setup for better extensibility.

### Not Always Applicable

Some changes genuinely require modifying existing code:
- Changing core algorithms
- Fixing bugs
- Refactoring internal implementations

**OCP doesn't mean "never modify code."** It means "design so extensions don't require modifications."

## Variations

### Factory Pattern with OCP

Combine with Factory to select strategies:

```python
class PaymentStrategyFactory:
    @staticmethod
    def create(payment_type: str) -> PaymentStrategy:
        strategies = {
            "credit_card": CreditCardPayment,
            "paypal": PayPalPayment,
            "bank_transfer": BankTransferPayment,
            "crypto": CryptocurrencyPayment
        }
        
        strategy_class = strategies.get(payment_type)
        if not strategy_class:
            raise ValueError(f"Unknown payment type: {payment_type}")
        
        return strategy_class()

# Usage
strategy = PaymentStrategyFactory.create("paypal")
processor = PaymentProcessor(strategy)
```

### Plugin Architecture

Load payment strategies dynamically:

```python
# Discover all PaymentStrategy subclasses
import inspect

def get_available_strategies():
    strategies = {}
    for name, obj in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(obj) and issubclass(obj, PaymentStrategy):
            if obj != PaymentStrategy:
                strategies[name] = obj
    return strategies
```

## Testing

```python
# test_payment_strategies.py
import pytest


def test_credit_card_validation():
    strategy = CreditCardPayment()
    
    # Valid details
    assert strategy.validate({
        "card_number": "1234567890123456",
        "cvv": "123",
        "expiry": "12/25"
    })
    
    # Invalid - missing field
    assert not strategy.validate({
        "card_number": "1234567890123456"
    })
    
    # Invalid - wrong length
    assert not strategy.validate({
        "card_number": "123",
        "cvv": "123",
        "expiry": "12/25"
    })


def test_credit_card_processing():
    strategy = CreditCardPayment()
    
    result = strategy.process(100.0, {
        "card_number": "1234567890123456",
        "cvv": "123",
        "expiry": "12/25"
    })
    
    assert result["status"] == "success"
    assert result["method"] == "credit_card"
    assert "transaction_id" in result


def test_payment_processor_with_different_strategies():
    # Test with credit card
    processor = PaymentProcessor(CreditCardPayment())
    result = processor.process_payment(50.0, {
        "card_number": "1234567890123456",
        "cvv": "123",
        "expiry": "12/25"
    })
    assert result["status"] == "success"
    
    # Test with PayPal
    processor.set_strategy(PayPalPayment())
    result = processor.process_payment(50.0, {
        "email": "user@example.com",
        "password": "password123"
    })
    assert result["status"] == "success"


def test_invalid_payment_amount():
    processor = PaymentProcessor(CreditCardPayment())
    
    with pytest.raises(ValueError, match="Amount must be positive"):
        processor.process_payment(-10.0, {})


def test_cryptocurrency_payment():
    strategy = CryptocurrencyPayment()
    
    result = strategy.process(100.0, {
        "wallet_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "crypto_type": "BTC"
    })
    
    assert result["status"] == "success"
    assert result["method"] == "cryptocurrency"
```

## Common Mistakes

### Using Type Checking Instead of Polymorphism

```python
# Bad: Still checking types
class PaymentProcessor:
    def process(self, strategy: PaymentStrategy, amount, details):
        if isinstance(strategy, CreditCardPayment):
            # Special handling for credit cards
            pass
        elif isinstance(strategy, PayPalPayment):
            # Special handling for PayPal
            pass
```

**Fix:** Trust polymorphism. If you need type checks, your abstraction is wrong.

### Overapplying OCP

```python
# Overkill: Making everything extensible
class StringFormatter:
    """Do we really need strategies for string formatting?"""
    def __init__(self, strategy: FormattingStrategy):
        self.strategy = strategy
```

**Fix:** Apply OCP where change is likely, not everywhere.

### Premature Abstraction

Creating strategies before you know what varies:

```python
# Premature: We only have one payment type
class PaymentStrategy(ABC):  # Why?
    pass

class OnlyPaymentType(PaymentStrategy):
    pass
```

**Fix:** Wait until you have 2-3 concrete cases before abstracting.

## Related Patterns

- **Chapter 4: Single Responsibility Principle** - Each strategy has one job
- **Chapter 8: Dependency Inversion Principle** - Depend on `PaymentStrategy` abstraction
- **Chapter 16: Factory Pattern** - Create strategies without knowing concrete types

## Summary

The Open/Closed Principle states that software should be open for extension but closed for modification. By depending on abstractions and using polymorphism, you can add new features without changing existing code. This reduces risk, improves testability, and makes systems more maintainable. Apply OCP where change is frequent, but don't over-engineer stable code.

## Further Reading

- **Bertrand Meyer** - *Object-Oriented Software Construction* - Original OCP formulation
- **Robert C. Martin** - *Agile Software Development, Principles, Patterns, and Practices* - OCP chapter
- **Gang of Four** - *Design Patterns* - Strategy pattern
- **Martin Fowler** - *Refactoring* - Replace Conditional with Polymorphism
