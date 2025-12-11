# Chapter 2: Test-Driven Development

## Introduction

Test-Driven Development (TDD) is a design practice disguised as a testing practice. You write tests first, then write code to make them pass. This seems backwards until you realize: tests that come first shape better code. They force you to think about interfaces before implementation, about behavior before mechanics.

TDD isn't about testing. It's about thinking clearly before coding.

## The Problem

How do you ensure your code works? How do you refactor safely? How do you design clean interfaces?

**Without TDD:**
- Write code, hope it works
- Test manually through the UI or console
- Break things without knowing
- Fear refactoring because you might break something
- Design emerges from implementation details

**Symptoms:**
- "It worked yesterday, I don't know what broke it"
- "I can't refactor this, it might break something"
- "Testing this requires running the whole application"
- Functions with unclear interfaces because you never thought about usage first

## The Pattern

Test-Driven Development follows a simple cycle:

**Red → Green → Refactor**

1. **Red:** Write a failing test for the next small piece of functionality
2. **Green:** Write the minimum code to make the test pass
3. **Refactor:** Improve the code without changing behavior

Repeat until the feature is complete.

### Key Principles

- **Test behavior, not implementation:** Tests should describe what code does, not how
- **One test at a time:** Focus on one small piece of functionality
- **Minimal code:** Write just enough to make the test pass
- **Refactor fearlessly:** Tests catch breaks

## Implementation

Let's build a simple task management system using TDD. We'll implement core functionality: adding tasks, completing them, and listing them.

### Example: Task Manager

```python
# test_tasks.py
import pytest
from datetime import datetime

# We don't have these classes yet - that's the point of TDD
from tasks import Task, TaskManager, TaskStatus


class TestTask:
    """Test Task entity behavior."""
    
    def test_create_task_with_title(self):
        """A task should be created with a title."""
        task = Task(title="Buy groceries")
        
        assert task.title == "Buy groceries"
        assert task.status == TaskStatus.PENDING
        assert isinstance(task.created_at, datetime)
    
    def test_task_starts_pending(self):
        """New tasks should start in PENDING status."""
        task = Task(title="Call dentist")
        
        assert task.status == TaskStatus.PENDING
        assert task.is_pending()
        assert not task.is_completed()
    
    def test_complete_task(self):
        """Marking a task complete should update status."""
        task = Task(title="Write tests")
        
        task.complete()
        
        assert task.status == TaskStatus.COMPLETED
        assert task.is_completed()
        assert task.completed_at is not None
    
    def test_cannot_complete_already_completed_task(self):
        """Completing an already completed task should raise an error."""
        task = Task(title="Finish report")
        task.complete()
        
        with pytest.raises(ValueError, match="already completed"):
            task.complete()


class TestTaskManager:
    """Test TaskManager behavior."""
    
    def test_create_empty_task_manager(self):
        """A new task manager should have no tasks."""
        manager = TaskManager()
        
        assert manager.task_count() == 0
        assert manager.list_tasks() == []
    
    def test_add_task(self):
        """Adding a task should increase count."""
        manager = TaskManager()
        
        task = manager.add_task("Buy milk")
        
        assert manager.task_count() == 1
        assert task.title == "Buy milk"
        assert task in manager.list_tasks()
    
    def test_add_multiple_tasks(self):
        """Can add multiple tasks."""
        manager = TaskManager()
        
        task1 = manager.add_task("Task 1")
        task2 = manager.add_task("Task 2")
        task3 = manager.add_task("Task 3")
        
        assert manager.task_count() == 3
        tasks = manager.list_tasks()
        assert task1 in tasks
        assert task2 in tasks
        assert task3 in tasks
    
    def test_list_pending_tasks_only(self):
        """Can filter to show only pending tasks."""
        manager = TaskManager()
        
        task1 = manager.add_task("Pending task 1")
        task2 = manager.add_task("Will complete this")
        task3 = manager.add_task("Pending task 2")
        
        task2.complete()
        
        pending = manager.list_pending_tasks()
        
        assert len(pending) == 2
        assert task1 in pending
        assert task3 in pending
        assert task2 not in pending
    
    def test_list_completed_tasks_only(self):
        """Can filter to show only completed tasks."""
        manager = TaskManager()
        
        task1 = manager.add_task("Complete this")
        task2 = manager.add_task("And this")
        task3 = manager.add_task("Leave pending")
        
        task1.complete()
        task2.complete()
        
        completed = manager.list_completed_tasks()
        
        assert len(completed) == 2
        assert task1 in completed
        assert task2 in completed
        assert task3 not in completed
    
    def test_clear_completed_tasks(self):
        """Can remove all completed tasks."""
        manager = TaskManager()
        
        task1 = manager.add_task("Keep this")
        task2 = manager.add_task("Remove this")
        task3 = manager.add_task("Remove this too")
        
        task2.complete()
        task3.complete()
        
        removed_count = manager.clear_completed()
        
        assert removed_count == 2
        assert manager.task_count() == 1
        assert task1 in manager.list_tasks()
        assert task2 not in manager.list_tasks()
```

Now let's implement the code to make these tests pass:

```python
# tasks.py
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"


class Task:
    """
    Represents a single task.
    
    A task has a title, status, and timestamps for creation and completion.
    Tasks start in PENDING status and can be marked as COMPLETED.
    """
    
    def __init__(self, title: str):
        if not title or not title.strip():
            raise ValueError("Task title cannot be empty")
        
        self.title = title
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
    
    def complete(self) -> None:
        """Mark task as completed."""
        if self.status == TaskStatus.COMPLETED:
            raise ValueError("Task is already completed")
        
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
    
    def is_pending(self) -> bool:
        """Check if task is pending."""
        return self.status == TaskStatus.PENDING
    
    def is_completed(self) -> bool:
        """Check if task is completed."""
        return self.status == TaskStatus.COMPLETED
    
    def __repr__(self):
        return f"Task('{self.title}', {self.status.value})"


class TaskManager:
    """
    Manages a collection of tasks.
    
    Provides operations to add, list, and filter tasks.
    """
    
    def __init__(self):
        self._tasks: List[Task] = []
    
    def add_task(self, title: str) -> Task:
        """
        Add a new task.
        
        Args:
            title: The task title
            
        Returns:
            The created Task instance
        """
        task = Task(title)
        self._tasks.append(task)
        return task
    
    def task_count(self) -> int:
        """Return total number of tasks."""
        return len(self._tasks)
    
    def list_tasks(self) -> List[Task]:
        """Return all tasks."""
        return self._tasks.copy()
    
    def list_pending_tasks(self) -> List[Task]:
        """Return only pending tasks."""
        return [task for task in self._tasks if task.is_pending()]
    
    def list_completed_tasks(self) -> List[Task]:
        """Return only completed tasks."""
        return [task for task in self._tasks if task.is_completed()]
    
    def clear_completed(self) -> int:
        """
        Remove all completed tasks.
        
        Returns:
            Number of tasks removed
        """
        before_count = len(self._tasks)
        self._tasks = [task for task in self._tasks if task.is_pending()]
        after_count = len(self._tasks)
        return before_count - after_count
```

### Running the Tests

```bash
# Install pytest if you haven't
pip install pytest

# Run all tests
pytest test_tasks.py -v

# Output:
# test_tasks.py::TestTask::test_create_task_with_title PASSED
# test_tasks.py::TestTask::test_task_starts_pending PASSED
# test_tasks.py::TestTask::test_complete_task PASSED
# test_tasks.py::TestTask::test_cannot_complete_already_completed_task PASSED
# test_tasks.py::TestTaskManager::test_create_empty_task_manager PASSED
# test_tasks.py::TestTaskManager::test_add_task PASSED
# test_tasks.py::TestTaskManager::test_add_multiple_tasks PASSED
# test_tasks.py::TestTaskManager::test_list_pending_tasks_only PASSED
# test_tasks.py::TestTaskManager::test_list_completed_tasks_only PASSED
# test_tasks.py::TestTaskManager::test_clear_completed_tasks PASSED
```

### Explanation

**What we built:**
1. **Task:** Represents a single task with title, status, and timestamps
2. **TaskStatus:** Enum for task states (better than strings)
3. **TaskManager:** Coordinates task collection and filtering

**Design decisions:**
- **Task validates itself:** Empty titles raise `ValueError` in `__init__`
- **Status is immutable direction:** Can go PENDING → COMPLETED, but not back
- **Manager encapsulates collection:** External code can't modify `_tasks` directly
- **Pure functions:** `list_pending_tasks()` doesn't modify state

**How TDD shaped the design:**
- Writing tests first made us think about the API: "How would I want to use this?"
- Tests revealed edge cases: What happens if you complete an already-completed task?
- Test names document behavior: Each test name explains what the code should do
- Refactoring is safe: We can change implementation without fear

## Benefits

### Safety Net for Refactoring

Tests let you refactor fearlessly. Want to change how `TaskManager` stores tasks? Go ahead—tests will catch breaks.

```python
# Could refactor to use a dict for O(1) lookup
class TaskManager:
    def __init__(self):
        self._tasks = {}  # Changed from list to dict
        self._next_id = 1
    
    # Implementation changes, but tests still pass
```

### Living Documentation

Tests are executable documentation. They show exactly how code should be used:

```python
def test_add_task(self):
    manager = TaskManager()
    task = manager.add_task("Buy milk")  # Clear usage example
    assert task.title == "Buy milk"
```

New developers read the tests to understand the system.

### Better Design

TDD forces you to think about:
- **Interfaces before implementation:** What do I want to call, and what should happen?
- **Dependencies:** Hard-to-test code often has tight coupling
- **Single responsibility:** Complex tests indicate complex classes

### Fast Feedback

Tests run in milliseconds. No need to manually test through a UI.

```bash
pytest test_tasks.py  # Runs in < 1 second
```

Compare this to: start app, click through UI, enter data, verify results.

## Trade-offs

### Time Investment

TDD takes longer upfront. Writing tests before code feels slower initially. But it pays off:
- Less debugging time later
- Fewer production bugs
- Faster refactoring

**Not worth it for:**
- Throwaway prototypes
- One-time scripts
- Highly exploratory work where requirements are completely unknown

### Learning Curve

TDD requires practice. You need to learn:
- What to test (behavior, not implementation)
- How to structure tests (arrange, act, assert)
- When to mock dependencies
- How to write testable code

It feels awkward at first. That's normal.

### Overhead for Simple Code

Sometimes the test is more complex than the code:

```python
def add(a, b):
    return a + b

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
```

For trivial functions, this might be overkill. Use judgment.

## Variations

### Outside-In TDD (Acceptance Test-Driven)

Start with high-level acceptance tests, then work inward:

```python
def test_user_can_complete_all_tasks():
    # High-level test of the whole workflow
    manager = TaskManager()
    manager.add_task("Task 1")
    manager.add_task("Task 2")
    
    for task in manager.list_tasks():
        task.complete()
    
    assert manager.list_pending_tasks() == []
    assert len(manager.list_completed_tasks()) == 2
```

Then write smaller unit tests to implement the details.

### Inside-Out TDD (Bottom-Up)

Start with small units, build up:

```python
# First test the smallest unit
def test_task_creation():
    task = Task("Test")
    assert task.title == "Test"

# Then compose into larger units
def test_manager_uses_tasks():
    manager = TaskManager()
    task = manager.add_task("Test")
    assert isinstance(task, Task)
```

### BDD (Behavior-Driven Development)

Focuses on behavior from user perspective:

```python
def test_when_user_completes_task_it_moves_to_completed_list():
    # Given a task manager with one pending task
    manager = TaskManager()
    task = manager.add_task("Finish report")
    
    # When the user completes the task
    task.complete()
    
    # Then it appears in completed tasks
    assert task in manager.list_completed_tasks()
    assert task not in manager.list_pending_tasks()
```

## Testing

Since this chapter is about testing, here's what to test:

### Test Behavior, Not Implementation

**Bad (tests implementation):**
```python
def test_tasks_stored_in_list():
    manager = TaskManager()
    assert isinstance(manager._tasks, list)  # Testing internal structure
```

**Good (tests behavior):**
```python
def test_can_add_and_retrieve_tasks():
    manager = TaskManager()
    task = manager.add_task("Test")
    assert task in manager.list_tasks()  # Testing observable behavior
```

### Test Edge Cases

```python
def test_empty_title_raises_error():
    with pytest.raises(ValueError):
        Task("")

def test_whitespace_only_title_raises_error():
    with pytest.raises(ValueError):
        Task("   ")

def test_clear_completed_when_no_completed_tasks():
    manager = TaskManager()
    manager.add_task("Pending")
    assert manager.clear_completed() == 0
```

### Test One Thing Per Test

```python
# Bad: Tests multiple behaviors
def test_task_lifecycle():
    task = Task("Test")
    assert task.is_pending()
    task.complete()
    assert task.is_completed()
    # What if the first assertion fails? You never see the second one.

# Good: Separate tests
def test_new_task_is_pending():
    task = Task("Test")
    assert task.is_pending()

def test_completed_task_is_not_pending():
    task = Task("Test")
    task.complete()
    assert not task.is_pending()
```

## Common Mistakes

### Writing Tests After Code

Defeats the purpose. Tests after code don't drive design—they just verify what you already built.

### Testing Implementation Details

```python
# Bad: Test breaks if you refactor internal structure
def test_tasks_stored_in_dictionary():
    manager = TaskManager()
    assert isinstance(manager._tasks, dict)

# Good: Test behavior remains stable through refactoring
def test_can_retrieve_added_tasks():
    manager = TaskManager()
    task = manager.add_task("Test")
    assert task in manager.list_tasks()
```

### Over-Mocking

```python
# Bad: Mocking everything makes tests brittle
def test_add_task_with_excessive_mocking():
    task = Mock()
    task.title = "Test"
    manager = TaskManager()
    manager._tasks = Mock()
    manager._tasks.append = Mock()
    # ... this test is fragile and hard to read

# Good: Only mock external dependencies
def test_add_task():
    manager = TaskManager()
    task = manager.add_task("Test")
    assert task.title == "Test"
```

### Skipping Refactor Step

The cycle is Red-Green-**Refactor**. Many developers stop at Green.

```python
# After getting test to pass, refactor:
# - Remove duplication
# - Extract methods
# - Improve names
# - Simplify logic

# Don't leave ugly code just because tests pass
```

## Related Patterns

- **Chapter 4: Single Responsibility Principle** - TDD naturally leads to focused classes
- **Chapter 8: Dependency Inversion** - Makes code testable by depending on abstractions
- **Chapter 14: Repository Pattern** - Easy to test with in-memory implementations

## Summary

Test-Driven Development is a design practice that happens to produce tests. By writing tests first, you design better interfaces, catch bugs early, and create a safety net for refactoring. The Red-Green-Refactor cycle keeps you focused on small, incremental progress.

TDD isn't appropriate for every situation, but when you need confidence that your code works—and will keep working as you change it—there's no better tool.

## Further Reading

- **Kent Beck** - *Test-Driven Development: By Example* - The original TDD book
- **Martin Fowler** - *Refactoring* - How to safely improve code with tests
- **Robert C. Martin** - *Clean Code* - Chapter on unit testing principles
- **Steve Freeman & Nat Pryce** - *Growing Object-Oriented Software, Guided by Tests* - TDD in practice
