# Chapter 6: Liskov Substitution Principle

## Introduction

The Liskov Substitution Principle (LSP) states: **Objects of a subclass should be replaceable with objects of the superclass without breaking the program.** If you have a function that works with a base class, it should work correctly with any subclass—no surprises, no unexpected behavior.

LSP is about behavioral subtyping. A subclass must honor the contract established by its parent class.

## The Problem

Inheritance hierarchies that violate expectations. Subclasses that change behavior in incompatible ways break code that depends on the parent class.

**Symptoms:**
- Subclasses throw exceptions the parent doesn't throw
- Subclasses return different types than expected
- Client code checks types before using objects  
- Subclasses weaken preconditions or strengthen postconditions

**Example of the problem:**

```python
# shapes.py - Classic LSP violation

class Rectangle:
    """A rectangle with independent width and height."""
    
    def __init__(self, width: int, height: int):
        self._width = width
        self._height = height
    
    def set_width(self, width: int):
        self._width = width
    
    def set_height(self, height: int):
        self._height = height
    
    def get_width(self) -> int:
        return self._width
    
    def get_height(self) -> int:
        return self._height
    
    def area(self) -> int:
        return self._width * self._height


class Square(Rectangle):
    """
    A square is a rectangle where width equals height, right?
    
    WRONG! This violates LSP.
    """
    
    def set_width(self, width: int):
        # A square must have equal sides
        self._width = width
        self._height = width  # Side effect!
    
    def set_height(self, height: int):
        # A square must have equal sides  
        self._width = height  # Side effect!
        self._height = height


# Client code that works with Rectangle
def resize_rectangle(rect: Rectangle):
    """Resize a rectangle to 5x10."""
    rect.set_width(5)
    rect.set_height(10)
    
    # Expect area to be 50
    expected_area = 50
    actual_area = rect.area()
    
    print(f"Expected area: {expected_area}, Actual area: {actual_area}")
    assert actual_area == expected_area, "Area calculation is broken!"


# This works fine
rectangle = Rectangle(2, 3)
resize_rectangle(rectangle)  # Output: Expected 50, Actual 50

# This FAILS - violates LSP!
square = Square(5, 5)
resize_rectangle(square)  # Output: Expected 50, Actual 100 - BROKEN!
```

**The problem:**
- `Square` changes behavior of `set_width()` and `set_height()`  
- Code written for `Rectangle` breaks when given a `Square`
- The substitution principle is violated

## The Pattern

**Liskov Substitution Principle:** If S is a subtype of T, then objects of type T may be replaced with objects of type S without altering program correctness.

**Requirements for LSP:**
1. **Preconditions cannot be strengthened** - Subclass can't require more than parent
2. **Postconditions cannot be weakened** - Subclass must deliver at least what parent promises
3. **Invariants must be preserved** - Class properties that always hold must continue to hold
4. **History constraint** - Subclass shouldn't allow state changes parent doesn't allow

**How to achieve LSP:**
- Design by contract
- Favor composition over inheritance when behavior differs
- Use interfaces to define contracts
- Make behavior consistent across hierarchy

## Implementation

Let's fix the rectangle/square problem by not using inheritance.

### Example: Shape Hierarchy Done Right

```python
# shapes.py
from abc import ABC, abstractmethod
from typing import Protocol


class Shape(ABC):
    """
    Abstract base for all shapes.
    
    Defines the contract: shapes have area.
    """
    
    @abstractmethod
    def area(self) -> float:
        """Calculate and return the area of the shape."""
        pass
    
    @abstractmethod
    def perimeter(self) -> float:
        """Calculate and return the perimeter of the shape."""
        pass


class Rectangle(Shape):
    """
    A rectangle with independent width and height.
    
    No surprising behavior - width and height are independent.
    """
    
    def __init__(self, width: float, height: float):
        if width <= 0 or height <= 0:
            raise ValueError("Dimensions must be positive")
        
        self._width = width
        self._height = height
    
    def set_width(self, width: float):
        """Set width without affecting height."""
        if width <= 0:
            raise ValueError("Width must be positive")
        self._width = width
    
    def set_height(self, height: float):
        """Set height without affecting width."""
        if height <= 0:
            raise ValueError("Height must be positive")
        self._height = height
    
    def get_width(self) -> float:
        return self._width
    
    def get_height(self) -> float:
        return self._height
    
    def area(self) -> float:
        """Calculate rectangle area."""
        return self._width * self._height
    
    def perimeter(self) -> float:
        """Calculate rectangle perimeter."""
        return 2 * (self._width + self._height)
    
    def __repr__(self):
        return f"Rectangle(width={self._width}, height={self._height})"


class Square(Shape):
    """
    A square with equal sides.
    
    NOT a subclass of Rectangle - different invariants.
    Both are shapes, but they behave differently.
    """
    
    def __init__(self, side: float):
        if side <= 0:
            raise ValueError("Side must be positive")
        
        self._side = side
    
    def set_side(self, side: float):
        """Set the side length."""
        if side <= 0:
            raise ValueError("Side must be positive")
        self._side = side
    
    def get_side(self) -> float:
        return self._side
    
    def area(self) -> float:
        """Calculate square area."""
        return self._side ** 2
    
    def perimeter(self) -> float:
        """Calculate square perimeter."""
        return 4 * self._side
    
    def __repr__(self):
        return f"Square(side={self._side})"


class Circle(Shape):
    """A circle with a radius."""
    
    def __init__(self, radius: float):
        if radius <= 0:
            raise ValueError("Radius must be positive")
        
        self._radius = radius
    
    def set_radius(self, radius: float):
        """Set the radius."""
        if radius <= 0:
            raise ValueError("Radius must be positive")
        self._radius = radius
    
    def get_radius(self) -> float:
        return self._radius
    
    def area(self) -> float:
        """Calculate circle area."""
        import math
        return math.pi * self._radius ** 2
    
    def perimeter(self) -> float:
        """Calculate circle circumference."""
        import math
        return 2 * math.pi * self._radius
    
    def __repr__(self):
        return f"Circle(radius={self._radius})"


# Client code works with Shape interface
def print_shape_info(shape: Shape):
    """
    Print information about any shape.
    
    Works correctly for Rectangle, Square, Circle, or any other Shape.
    This demonstrates LSP - any Shape subclass works here.
    """
    print(f"Shape: {shape}")
    print(f"Area: {shape.area():.2f}")
    print(f"Perimeter: {shape.perimeter():.2f}")
    print()


# Usage - all shapes work the same way
def main():
    shapes = [
        Rectangle(5, 10),
        Square(7),
        Circle(3)
    ]
    
    for shape in shapes:
        print_shape_info(shape)
    
    # Calculate total area
    total_area = sum(shape.area() for shape in shapes)
    print(f"Total area of all shapes: {total_area:.2f}")


if __name__ == "__main__":
    main()
```

### Explanation

**What changed:**

1. **`Square` is NOT a subclass of `Rectangle`** - They share a common interface (`Shape`) but have different behaviors
2. **Each class has its own methods** - `Rectangle` has `set_width/set_height`, `Square` has `set_side`
3. **All implement `Shape`** - They share the contract of having `area()` and `perimeter()`
4. **No surprises** - Each class behaves as expected, no hidden side effects

**Key design decisions:**

- Common interface (`Shape`) instead of inheritance hierarchy
- Each shape manages its own state consistently
- Client code depends on `Shape` abstraction
- LSP is satisfied - any `Shape` works in `print_shape_info()`

## Benefits

### Code That Works with Base Class Works with Subclasses

```python
def calculate_total_area(shapes: List[Shape]) -> float:
    """Calculate total area of shapes."""
    return sum(shape.area() for shape in shapes)

# Works with ANY Shape implementation
shapes = [Rectangle(5, 10), Square(7), Circle(3)]
total = calculate_total_area(shapes)  # No surprises!
```

### No Type Checking Needed

```python
# Don't need this:
def process_shape(shape):
    if isinstance(shape, Rectangle):
        # Handle rectangle
        pass
    elif isinstance(shape, Square):
        # Handle square
        pass

# Just this:
def process_shape(shape: Shape):
    area = shape.area()  # Works for all shapes
```

### Polymorphism Actually Works

Subclasses are truly interchangeable:

```python
def get_largest_shape(shapes: List[Shape]) -> Shape:
    """Return shape with largest area."""
    return max(shapes, key=lambda s: s.area())
```

## Trade-offs

### Composition Over Inheritance

Sometimes avoiding inheritance means more code:

```python
# With inheritance (if it worked)
class Square(Rectangle):
    pass  # Simple!

# Without inheritance
class Square(Shape):
    # Have to implement everything
    def __init__(self, side):
        self._side = side
    # ... more code
```

**Trade-off:** More code for correct behavior.

### Less Code Reuse Through Inheritance

Can't reuse Rectangle's `area()` implementation in Square.

**Solution:** Extract common code to helper functions/composition.

## Testing

```python
# test_shapes.py
import pytest
import math


def test_rectangle_area():
    rect = Rectangle(5, 10)
    assert rect.area() == 50


def test_rectangle_perimeter():
    rect = Rectangle(3, 4)
    assert rect.perimeter() == 14


def test_square_area():
    square = Square(5)
    assert square.area() == 25


def test_square_perimeter():
    square = Square(5)
    assert square.perimeter() == 20


def test_circle_area():
    circle = Circle(3)
    expected = math.pi * 9
    assert abs(circle.area() - expected) < 0.01


def test_all_shapes_have_area():
    """LSP test: all shapes can calculate area."""
    shapes = [
        Rectangle(5, 10),
        Square(7),
        Circle(3)
    ]
    
    for shape in shapes:
        area = shape.area()
        assert area > 0
        assert isinstance(area, (int, float))


def test_all_shapes_have_perimeter():
    """LSP test: all shapes can calculate perimeter."""
    shapes = [
        Rectangle(5, 10),
        Square(7),
        Circle(3)
    ]
    
    for shape in shapes:
        perimeter = shape.perimeter()
        assert perimeter > 0
        assert isinstance(perimeter, (int, float))


def test_shapes_work_in_collections():
    """LSP test: can treat all shapes uniformly."""
    shapes = [Rectangle(5, 10), Square(7), Circle(3)]
    
    # Should be able to process all shapes the same way
    total_area = sum(s.area() for s in shapes)
    assert total_area > 0
```

## Common Mistakes

### Using Inheritance When Composition Is Better

```python
# Bad: Inheritance just for code reuse
class Stack(list):
    """Use list as a stack."""
    def push(self, item):
        self.append(item)

# Problem: Stack inherits all list methods (pop, insert, etc.)
# Violates LSP - a Stack shouldn't allow inserting at arbitrary positions

# Good: Composition
class Stack:
    def __init__(self):
        self._items = []  # Use list internally
    
    def push(self, item):
        self._items.append(item)
    
    def pop(self):
        return self._items.pop()
```

### Strengthening Preconditions in Subclass

```python
# Bad: Subclass is more restrictive
class BankAccount:
    def withdraw(self, amount):
        # Parent accepts any positive amount
        if amount > 0:
            self.balance -= amount

class SavingsAccount(BankAccount):
    def withdraw(self, amount):
        # Subclass adds restriction (strengthens precondition)
        if amount > 1000:  # Violates LSP!
            raise ValueError("Savings: max withdrawal $1000")
        super().withdraw(amount)

# Code expecting BankAccount behavior breaks
def withdraw_money(account: BankAccount, amount):
    account.withdraw(amount)  # Expects to work for any amount

withdraw_money(SavingsAccount(), 2000)  # Fails! LSP violated
```

### Throwing New Exceptions in Subclass

```python
# Bad: Subclass throws exceptions parent doesn't
class FileReader:
    def read(self, filename):
        return open(filename).read()

class SecureFileReader(FileReader):
    def read(self, filename):
        if not self.is_authorized():
            raise SecurityError()  # New exception! LSP violated
        return super().read(filename)

# Fix: Parent should define all possible exceptions
class FileReader:
    def read(self, filename):
        """Read file. May raise SecurityError."""
        pass
```

## Related Patterns

- **Chapter 5: Open/Closed Principle** - LSP enables OCP through polymorphism
- **Chapter 8: Dependency Inversion** - Depend on abstractions that follow LSP
- **Chapter 3: Domain Modeling** - Model hierarchies correctly

## Summary

The Liskov Substitution Principle ensures that subclasses can replace their parent classes without breaking code. This requires subclasses to honor the contract established by the parent—same behavior, same expectations, no surprises. When inheritance doesn't fit LSP, use composition or separate hierarchies instead.

## Further Reading

- **Barbara Liskov** - *"Data Abstraction and Hierarchy"* (1987) - Original LSP paper
- **Robert C. Martin** - *Agile Software Development* - LSP chapter
- **Bertrand Meyer** - *Object-Oriented Software Construction* - Design by Contract
- **Joshua Bloch** - *Effective Java* - Item 18: "Favor composition over inheritance"
