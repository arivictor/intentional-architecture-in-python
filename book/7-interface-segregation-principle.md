# Chapter 7: Interface Segregation Principle

## Introduction

The Interface Segregation Principle (ISP) states: **No client should be forced to depend on methods it does not use.** Large, "fat" interfaces that try to do everything force clients to implement methods they don't need. ISP says: keep interfaces small, focused, and relevant to each client.

When an interface has too many methods, classes that implement it are forced to provide empty or throw-not-implemented methods. This creates coupling to unused functionality.

## The Problem

Interfaces that are too broad force implementers to deal with methods they don't care about.

**Symptoms:**
- Classes implementing methods they don't use
- Empty method bodies or `raise NotImplementedError`
- Changes to one feature break unrelated clients
- Difficult to understand what a class actually does

**Example of the problem:**

```python
# devices.py - Fat interface that violates ISP

from abc import ABC, abstractmethod

class MultiFunctionDevice(ABC):
    """
    A fat interface trying to represent all possible device features.
    
    Problem: Not all devices can do all of these things!
    """
    
    @abstractmethod
    def print_document(self, document):
        """Print a document."""
        pass
    
    @abstractmethod
    def scan_document(self):
        """Scan a document."""
        pass
    
    @abstractmethod
    def fax_document(self, document, number):
        """Fax a document."""
        pass
    
    @abstractmethod
    def photocopy_document(self, document):
        """Photocopy a document."""
        pass


class ModernPrinter(MultiFunctionDevice):
    """A modern all-in-one device - this works fine."""
    
    def print_document(self, document):
        print(f"Printing: {document}")
    
    def scan_document(self):
        print("Scanning document...")
        return "scanned_data"
    
    def fax_document(self, document, number):
        print(f"Faxing {document} to {number}")
    
    def photocopy_document(self, document):
        print(f"Photocopying: {document}")


class SimplePrinter(MultiFunctionDevice):
    """
    A simple printer that ONLY prints.
    
    Problem: Forced to implement methods it doesn't support!
    """
    
    def print_document(self, document):
        print(f"Printing: {document}")
    
    def scan_document(self):
        # Forced to implement - violation!
        raise NotImplementedError("This printer cannot scan")
    
    def fax_document(self, document, number):
        # Forced to implement - violation!
        raise NotImplementedError("This printer cannot fax")
    
    def photocopy_document(self, document):
        # Forced to implement - violation!
        raise NotImplementedError("This printer cannot photocopy")


# Client code breaks unexpectedly
def make_copies(device: MultiFunctionDevice, document):
    """Make copies using any device."""
    device.photocopy_document(document)

# This works
all_in_one = ModernPrinter()
make_copies(all_in_one, "report.pdf")

# This FAILS at runtime!
simple = SimplePrinter()
make_copies(simple, "report.pdf")  # NotImplementedError!
```

**Problems:**
- `SimplePrinter` forced to implement methods it doesn't support
- Runtime errors instead of compile-time safety
- Interface doesn't match actual capabilities
- Clients can't trust the interface

## The Pattern

**Interface Segregation Principle:** Many client-specific interfaces are better than one general-purpose interface.

**How to achieve ISP:**
1. **Split fat interfaces into smaller, focused interfaces**
2. **Group methods by client needs, not by object type**
3. **Classes implement only the interfaces they need**
4. **Clients depend only on methods they use**

## Implementation

Let's refactor the device system with segregated interfaces.

### Example: Office Devices with Segregated Interfaces

```python
# devices.py
from abc import ABC, abstractmethod


# Segregated interfaces - each focused on one capability

class Printer(ABC):
    """Interface for devices that can print."""
    
    @abstractmethod
    def print_document(self, document: str) -> None:
        """Print a document."""
        pass


class Scanner(ABC):
    """Interface for devices that can scan."""
    
    @abstractmethod
    def scan_document(self) -> str:
        """Scan a document and return scanned data."""
        pass


class FaxMachine(ABC):
    """Interface for devices that can fax."""
    
    @abstractmethod
    def fax_document(self, document: str, number: str) -> None:
        """Fax a document to a number."""
        pass


class Photocopier(ABC):
    """Interface for devices that can photocopy."""
    
    @abstractmethod
    def photocopy_document(self, document: str) -> None:
        """Photocopy a document."""
        pass


# Implementations - only implement what you actually support

class SimplePrinter(Printer):
    """
    A simple printer that ONLY prints.
    
    Now it only implements Printer - no unused methods!
    """
    
    def print_document(self, document: str) -> None:
        print(f"[SimplePrinter] Printing: {document}")


class AdvancedScanner(Scanner):
    """A high-quality scanner that only scans."""
    
    def scan_document(self) -> str:
        print("[AdvancedScanner] Scanning document...")
        return "high_quality_scan_data"


class AllInOnePrinter(Printer, Scanner, Photocopier):
    """
    All-in-one device implementing multiple interfaces.
    
    Implements exactly what it supports - print, scan, photocopy.
    Does NOT implement fax because it doesn't have that capability.
    """
    
    def print_document(self, document: str) -> None:
        print(f"[AllInOne] Printing: {document}")
    
    def scan_document(self) -> str:
        print("[AllInOne] Scanning document...")
        return "scanned_data"
    
    def photocopy_document(self, document: str) -> None:
        print(f"[AllInOne] Photocopying: {document}")
        # Internally uses print and scan
        scanned = self.scan_document()
        self.print_document(f"copy_of_{document}")


class OldFaxMachine(FaxMachine):
    """An old fax machine that only faxes."""
    
    def fax_document(self, document: str, number: str) -> None:
        print(f"[FaxMachine] Faxing {document} to {number}")


class ModernAllInOne(Printer, Scanner, FaxMachine, Photocopier):
    """
    Modern device that truly does everything.
    
    Implements all interfaces because it has all capabilities.
    """
    
    def print_document(self, document: str) -> None:
        print(f"[Modern] Printing: {document}")
    
    def scan_document(self) -> str:
        print("[Modern] Scanning document...")
        return "modern_scan_data"
    
    def fax_document(self, document: str, number: str) -> None:
        print(f"[Modern] Faxing {document} to {number}")
    
    def photocopy_document(self, document: str) -> None:
        print(f"[Modern] Photocopying: {document}")


# Client code - depends only on what it needs

def print_documents(printer: Printer, documents: list):
    """
    Print documents using any printer.
    
    Only requires Printer interface - doesn't care about other capabilities.
    """
    for doc in documents:
        printer.print_document(doc)


def scan_and_email(scanner: Scanner, recipient: str):
    """
    Scan document and email it.
    
    Only requires Scanner interface.
    """
    scanned_data = scanner.scan_document()
    print(f"Emailing {scanned_data} to {recipient}")


def make_photocopies(copier: Photocopier, document: str, copies: int):
    """
    Make multiple photocopies.
    
    Only requires Photocopier interface.
    """
    for i in range(copies):
        copier.photocopy_document(document)


# Usage - each device used according to its capabilities
def main():
    # Simple printer can print
    simple = SimplePrinter()
    print_documents(simple, ["report.pdf", "memo.docx"])
    
    # All-in-one can do print, scan, photocopy
    all_in_one = AllInOnePrinter()
    print_documents(all_in_one, ["invoice.pdf"])
    scan_and_email(all_in_one, "boss@company.com")
    make_photocopies(all_in_one, "contract.pdf", 3)
    
    # Modern device can do everything
    modern = ModernAllInOne()
    print_documents(modern, ["report.pdf"])
    scan_and_email(modern, "client@example.com")
    modern.fax_document("urgent.pdf", "555-1234")
    
    # Old fax machine can only fax
    fax = OldFaxMachine()
    fax.fax_document("memo.pdf", "555-5678")
    
    # Type safety: Can't call photocopy on SimplePrinter
    # make_photocopies(simple, "doc.pdf", 1)  # Type error!


if __name__ == "__main__":
    main()
```

### Explanation

**What changed:**

1. **Split fat interface into focused interfaces:** `Printer`, `Scanner`, `FaxMachine`, `Photocopier`
2. **Each interface has one capability:** Print, scan, fax, or photocopy
3. **Classes implement only what they support:** `SimplePrinter` only implements `Printer`
4. **Clients depend on specific interfaces:** `print_documents()` only needs `Printer`

**Key design decisions:**

- One interface per capability
- Classes can implement multiple interfaces (composition)
- Clients declare specific dependencies
- No empty implementations or NotImplementedError

## Benefits

### No Unused Methods

Classes only implement what they actually do:

```python
class SimplePrinter(Printer):
    # Only one method needed!
    def print_document(self, document): pass
```

### Type Safety

Can't call unsupported methods:

```python
simple_printer = SimplePrinter()
# simple_printer.scan_document()  # Type error - method doesn't exist!
```

### Clear Dependencies

Clients declare exactly what they need:

```python
def process_document(printer: Printer):  # Only needs printing
    printer.print_document("doc")

def archive_document(scanner: Scanner):  # Only needs scanning
    data = scanner.scan_document()
```

### Easier Testing

Mock only what you use:

```python
class MockPrinter(Printer):
    def print_document(self, document):
        self.printed_documents.append(document)

# Test code that only needs printing
def test_printing():
    mock = MockPrinter()
    print_documents(mock, ["test.pdf"])
```

## Trade-offs

### More Interfaces

ISP creates more interfaces:

```python
# Before: 1 interface
class MultiFunctionDevice: pass

# After: 4 interfaces
class Printer: pass
class Scanner: pass
class FaxMachine: pass
class Photocopier: pass
```

**Trade-off:** More files/classes, but clearer contracts.

### Multiple Inheritance

Devices implementing multiple interfaces:

```python
class AllInOne(Printer, Scanner, Photocopier):
    pass
```

Python handles this well, but some languages make it harder.

## Testing

```python
# test_devices.py
import pytest


def test_simple_printer_prints():
    printer = SimplePrinter()
    # Should not raise
    printer.print_document("test.pdf")


def test_all_in_one_implements_all_interfaces():
    device = AllInOnePrinter()
    
    # All these should work
    device.print_document("test.pdf")
    data = device.scan_document()
    assert data
    device.photocopy_document("test.pdf")


def test_print_documents_works_with_any_printer():
    """ISP test: any Printer works in print_documents()."""
    printers = [
        SimplePrinter(),
        AllInOnePrinter(),
        ModernAllInOne()
    ]
    
    for printer in printers:
        # Should work with all Printer implementations
        print_documents(printer, ["test.pdf"])


def test_scan_only_works_with_scanners():
    """ISP test: can't scan with a simple printer."""
    scanner = AllInOnePrinter()
    
    # This works - AllInOnePrinter implements Scanner
    scan_and_email(scanner, "test@example.com")
    
    # This would be a type error:
    # simple = SimplePrinter()
    # scan_and_email(simple, "test@example.com")  # Type error!


class MockPrinter(Printer):
    """Mock for testing print functionality."""
    
    def __init__(self):
        self.documents = []
    
    def print_document(self, document: str):
        self.documents.append(document)


def test_with_mock_printer():
    """ISP benefit: easy to mock specific interfaces."""
    mock = MockPrinter()
    print_documents(mock, ["doc1.pdf", "doc2.pdf"])
    
    assert len(mock.documents) == 2
    assert "doc1.pdf" in mock.documents
```

## Common Mistakes

### Creating Too Many Interfaces

```python
# Overkill: One interface per method
class PrintInBlackAndWhite(ABC):
    def print_bw(self): pass

class PrintInColor(ABC):
    def print_color(self): pass

class PrintDoubleSided(ABC):
    def print_duplex(self): pass

# Better: Group related methods
class Printer(ABC):
    def print_document(self, document, color=False, duplex=False): pass
```

### Not Grouping by Client Need

```python
# Bad: Grouped by implementation detail
class DatabaseMethods(ABC):
    def connect(self): pass
    def query(self): pass
    def close(self): pass

# Better: Grouped by client purpose
class ReadOnlyDatabase(ABC):
    def query(self): pass

class ReadWriteDatabase(ReadOnlyDatabase):
    def insert(self): pass
    def update(self): pass
```

## Related Patterns

- **Chapter 4: Single Responsibility** - Focused interfaces support SRP
- **Chapter 8: Dependency Inversion** - Depend on segregated interfaces
- **Chapter 2: Test-Driven Development** - ISP makes testing easier

## Summary

The Interface Segregation Principle states that no client should depend on methods it doesn't use. By creating small, focused interfaces instead of large, general ones, you make code more flexible, easier to implement, and safer to use. Apply ISP by splitting fat interfaces into client-specific ones.

## Further Reading

- **Robert C. Martin** - *Agile Software Development* - ISP chapter
- **Gang of Four** - *Design Patterns* - Interface design principles
- **Martin Fowler** - *Refactoring* - Extract interface refactoring
