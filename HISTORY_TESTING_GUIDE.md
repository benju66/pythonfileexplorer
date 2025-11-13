# Tab History Testing Guide

This guide explains how to verify that the tab history refactoring is working correctly.

## Quick Verification Methods

### Method 1: Using Debug Methods (Recommended)

The `TabHistoryManager` and `TabManager` classes now include debug methods you can call from Python console or add to your code.

#### In Python Console (while app is running):

```python
# Get the current tab manager
from ui.main_window import MainWindow
app = QApplication.instance()
main_window = app.activeWindow()

# Get current container's tab manager
container = main_window.main_tabs.currentWidget()
tab_manager = container.tab_manager

# Debug current tab's history
tab_manager.debug_current_tab_history()

# Debug all tabs' histories
tab_manager.debug_all_tabs_history()

# Or use the history manager directly
tab_manager.history_manager.print_all_history()
```

#### Add Temporary Debug Button:

You can temporarily add a debug button to test. Add this to `ui/tab_manager.py` in the `__init__` method:

```python
# Temporary debug button (remove after testing)
debug_button = QPushButton("Debug History")
debug_button.clicked.connect(self.debug_current_tab_history)
self.top_right_layout.addWidget(debug_button)
```

### Method 2: Manual Testing Steps

#### Test 1: Basic History Initialization

1. **Start the app**
2. **Open a new tab** (click "+" button or use Ctrl+T)
3. **Check console output** - should see history initialized
4. **Run debug command:**
   ```python
   # In Python console
   container = app.activeWindow().main_tabs.currentWidget()
   container.tab_manager.debug_current_tab_history()
   ```
5. **Expected:** Should show history with initial path

#### Test 2: Navigation History (push_path)

1. **Navigate to a directory** (click on a folder)
2. **Navigate to another directory** (click on another folder)
3. **Navigate to a third directory**
4. **Run debug:**
   ```python
   container.tab_manager.debug_current_tab_history()
   ```
5. **Expected:** Should show history with all 3+ paths, current_index at the end

#### Test 3: Go Up (Alt+Up)

1. **Navigate to a nested folder** (e.g., `C:/Users/YourName/Documents/Projects`)
2. **Press Alt+Up** (or click Up button)
3. **Run debug:**
   ```python
   container.tab_manager.debug_current_tab_history()
   ```
4. **Expected:** 
   - Should navigate to parent directory
   - History should include parent path
   - Current path should be parent directory

#### Test 4: Tab Reordering (if tabs are movable)

1. **Create 2-3 tabs** with different directories
2. **Navigate in each tab** to build history
3. **Drag tabs to reorder** (if drag-and-drop is enabled)
4. **Run debug:**
   ```python
   container.tab_manager.debug_all_tabs_history()
   ```
5. **Expected:** Each tab should retain its history regardless of position

#### Test 5: Tab Closing

1. **Create multiple tabs** with navigation history
2. **Close a middle tab**
3. **Run debug:**
   ```python
   container.tab_manager.debug_all_tabs_history()
   ```
4. **Expected:** 
   - Closed tab's history should be removed
   - Remaining tabs should retain their history
   - No orphaned history entries

#### Test 6: Multiple Tab Managers (Split View)

1. **Enable split view** (if available)
2. **Navigate in left pane**
3. **Navigate in right pane**
4. **Run debug for each:**
   ```python
   container = app.activeWindow().main_tabs.currentWidget()
   left_manager = container.tab_manager
   right_manager = container.right_tab_manager  # if exists
   
   left_manager.debug_all_tabs_history()
   right_manager.debug_all_tabs_history()
   ```
5. **Expected:** Each TabManager should have separate histories

## What to Look For

### ✅ Success Indicators:

1. **History persists** when tabs are reordered
2. **History is unique** per tab widget (not per index)
3. **History cleanup** works when tabs are closed
4. **Navigation works** (go_up, go_back, go_forward)
5. **No crashes** during any operation
6. **Widget IDs are stable** (same widget = same ID)

### ❌ Failure Indicators:

1. **History lost** when tabs move
2. **Wrong history** shown after tab reorder
3. **History not cleaned up** after tab close
4. **Crashes** during navigation
5. **Index-based lookups** still present (check for old code)

## Debug Output Example

When you run `debug_current_tab_history()`, you should see:

```
============================================================
CURRENT TAB HISTORY DEBUG
============================================================
  widget_id: 123456789
  has_history: True
  history: ['C:/Users/YourName', 'C:/Users/YourName/Documents', 'C:/Users/YourName/Documents/Projects']
  current_index: 2
  current_path: C:/Users/YourName/Documents/Projects
  can_go_back: True
  can_go_forward: False
============================================================
```

## Common Issues and Solutions

### Issue: "No history found"
**Cause:** Tab widget not initialized with history  
**Solution:** Make sure `init_tab_history()` is called when tab is created

### Issue: "History lost after tab move"
**Cause:** Old index-based code still present  
**Solution:** Verify all call sites use widget-based API

### Issue: "Wrong history shown"
**Cause:** Widget ID mismatch  
**Solution:** Check that same widget is used for all operations

## Automated Testing (Future)

For more robust testing, consider adding unit tests:

```python
# tests/test_tab_history.py
def test_history_persistence():
    manager = TabHistoryManager()
    widget = QWidget()
    
    manager.init_tab_history(widget, "/path1")
    manager.push_path(widget, "/path2")
    
    # History should persist
    assert manager.get_current_path(widget) == "/path2"
    
    # History should survive widget move (simulated by using same widget)
    assert manager.get_current_path(widget) == "/path2"
```

## Quick Test Script

Save this as `test_history.py` and run it:

```python
#!/usr/bin/env python3
"""Quick test script for tab history."""

import sys
from PyQt6.QtWidgets import QApplication, QWidget
from modules.tab_history_manager import TabHistoryManager

def test_basic_history():
    """Test basic history operations."""
    manager = TabHistoryManager()
    widget = QWidget()
    
    print("Test 1: Initialize history")
    manager.init_tab_history(widget, "/test/path1")
    assert manager.get_current_path(widget) == "/test/path1"
    print("✅ Pass")
    
    print("\nTest 2: Push path")
    manager.push_path(widget, "/test/path2")
    assert manager.get_current_path(widget) == "/test/path2"
    print("✅ Pass")
    
    print("\nTest 3: Go back")
    path = manager.go_back(widget)
    assert path == "/test/path1"
    print("✅ Pass")
    
    print("\nTest 4: Go forward")
    path = manager.go_forward(widget)
    assert path == "/test/path2"
    print("✅ Pass")
    
    print("\nTest 5: Debug info")
    info = manager.get_history_debug_info(widget)
    assert info["has_history"] == True
    assert len(info["history"]) == 2
    print("✅ Pass")
    print(f"   Debug info: {info}")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    test_basic_history()
    sys.exit(0)
```

Run with: `python test_history.py`

