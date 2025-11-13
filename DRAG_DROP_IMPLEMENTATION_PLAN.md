# Drag-and-Drop Tab Implementation Plan - Comprehensive Review

**Date:** January 2025  
**Status:** Ready for Implementation  
**Confidence:** 90% (after gap elimination)

---

## Executive Summary

This document outlines a comprehensive plan for implementing robust drag-and-drop tab functionality for both `MainWindowTabs` (top-level) and `TabManager` (nested) tab systems. The plan addresses all identified gaps and dependencies.

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Identified Gaps & Dependencies](#identified-gaps--dependencies)
3. [Implementation Phases](#implementation-phases)
4. [Signal Reconnection Strategy](#signal-reconnection-strategy)
5. [Widget Lifecycle Management](#widget-lifecycle-management)
6. [Edge Cases & Special Scenarios](#edge-cases--special-scenarios)
7. [Testing Strategy](#testing-strategy)
8. [Risk Assessment](#risk-assessment)

---

## Current State Analysis

### ✅ Completed Foundation

1. **TabHistoryManager Refactoring** ✅
   - Uses widget IDs instead of indices
   - `migrate_history()` method ready
   - All call sites updated
   - Tests passing

2. **Existing Detachment Methods**
   - `MainWindowTabs.detach_main_tab()` - Works via context menu
   - `TabManager.detach_nested_tab()` - Works via context menu
   - `TabManager.reattach_tab()` - Basic reattachment exists

3. **Current Signal Connections**
   - Well-documented signal/slot patterns
   - Parent-child relationships established
   - Address bar updates working

---

## Identified Gaps & Dependencies

### 🔴 Critical Gaps

#### 1. **Signal Reconnection System** (CRITICAL)

**Problem:** When a widget moves between tab widgets, all signal connections break.

**Affected Signals:**

**For TabManager:**
- `FileTree.location_changed` → `MainWindowContainer.update_address_bar`
- `FileTree.file_tree_clicked` → `TabManager.handle_file_tree_clicked`
- `FileTree.context_menu_action_triggered` → `TabManager.handle_context_menu_action`
- `TabManager.active_manager_changed` → `MainWindowContainer.on_active_manager_changed`
- `TabManager.pin_item_requested` → `MainWindowContainer.handle_pin_request`
- `TabManager.currentChanged` → `MainWindowContainer.update_file_tree_connections`
- `TabManager.tabCloseRequested` → `TabManager.close_tab`
- `TabManager.tabBarDoubleClicked` → `TabManager.handle_tab_bar_double_click`
- `TabManager.customContextMenuRequested` → `TabManager.show_tab_context_menu`

**For MainWindowTabs:**
- `MainWindowTabs.new_tab_added` → `MainWindow.on_new_tab_added`
- `MainWindowTabs.currentChanged` → `MainWindow.update_address_bar_on_tab_change`
- `MainWindowTabs.tabCloseRequested` → `MainWindowTabs.close_tab`
- `MainWindowTabs.customContextMenuRequested` → `MainWindowTabs.show_tab_context_menu`
- `PinnedPanel` signals → `MainWindow.refresh_all_pinned_panels`

**Solution:** Create a `SignalConnectionManager` that:
- Tracks all signal connections for each widget
- Disconnects signals before widget move
- Reconnects signals after widget move
- Handles both widget-level and parent-level signals

---

#### 2. **Parent-Child Relationship Management** (CRITICAL)

**Problem:** Methods rely on `parentWidget()` traversal which breaks after move.

**Affected Methods:**
- `TabManager.get_main_window_container()` - Uses `parentWidget()` traversal
- `MainWindowContainer` methods using `window()` - Should still work
- `findChild()` calls - Should still work (searches within widget hierarchy)

**Solution:** 
- Store container reference in widget's `setProperty()` or custom attribute
- Update `get_main_window_container()` to check stored reference first
- Fall back to `parentWidget()` traversal if reference missing

---

#### 3. **Split View Compatibility** (HIGH PRIORITY)

**Problem:** Split view creates complex widget hierarchy with two `TabManager` instances.

**Scenarios to Handle:**
1. Drag tab from left pane to right pane (same container)
2. Drag tab from right pane to left pane (same container)
3. Drag tab from split view to non-split container
4. Drag tab from non-split container to split view
5. Drag tab between different containers (one or both in split view)

**Solution:**
- Detect split view state before/after move
- Handle `QSplitter` widget relationships
- Update `MainWindowContainer.update_file_tree_connections()` to handle new location
- Ensure address bar updates correctly

---

#### 4. **Address Bar Update After Move** (HIGH PRIORITY)

**Problem:** Address bar doesn't update when tab becomes active in new location.

**Current Flow:**
1. Tab moved → widget added to new location
2. Tab becomes active → `currentChanged` signal emitted
3. `MainWindowContainer.update_file_tree_connections()` called
4. Address bar should update

**Solution:**
- Ensure `update_file_tree_connections()` is called after move
- Ensure `on_tab_changed()` is called after move
- Ensure `active_manager_changed` signal is emitted
- Test address bar updates in all scenarios

---

#### 5. **Active Tab Management** (MEDIUM PRIORITY)

**Problem:** Moved tab should become active in its new location.

**Solution:**
- After adding widget to target, call `setCurrentWidget(widget)`
- Ensure `currentChanged` signal is emitted
- Update UI state appropriately

---

#### 6. **Detached Window Integration** (MEDIUM PRIORITY)

**Problem:** Existing detachment methods don't integrate with drag-and-drop.

**Current Methods:**
- `MainWindowTabs.detach_main_tab()` - Creates new `MainWindow`
- `TabManager.detach_nested_tab()` - Creates new `QMainWindow` with `TabManager`

**Solution:**
- Detect when drag goes outside application bounds
- Create new window similar to `detach_main_tab()`
- Migrate history
- Reconnect signals
- Handle reattachment via drag-and-drop back to original window

---

#### 7. **MIME Data Format** (MEDIUM PRIORITY)

**Problem:** Need to store widget reference in MIME data.

**Solution:**
- Use custom MIME type: `"application/x-qtabwidget-widget-id"`
- Store widget ID (`id(widget)`) in MIME data
- Create widget registry to map ID → widget
- Handle widget lookup during drop

**Alternative:** Store widget reference directly (if Qt allows)

---

#### 8. **Widget Registry** (MEDIUM PRIORITY)

**Problem:** Need to track widgets during drag operations.

**Solution:**
- Create `WidgetRegistry` class
- Map widget ID → widget reference
- Map widget → parent tab widget
- Map widget → signal connections
- Clean up on widget deletion

---

#### 9. **Error Handling & Edge Cases** (LOW PRIORITY)

**Scenarios:**
- Drag cancelled (widget not moved)
- Invalid drop target
- Widget deleted during drag
- Multiple simultaneous drags
- Drag to same location (no-op)

**Solution:**
- Validate drop target before move
- Check widget validity before operations
- Handle exceptions gracefully
- Log errors for debugging

---

#### 10. **History Cleanup** (LOW PRIORITY)

**Problem:** History should be cleaned up if widget is deleted (not moved).

**Current:** `remove_tab_history()` called in `close_tab()`

**Solution:**
- Ensure history cleanup happens on widget deletion
- Don't clean up on move (history migrates)
- Handle edge cases where widget is deleted during drag

---

## Implementation Phases

### Phase 1: Infrastructure (Foundation)

#### 1.1 Widget Registry (`modules/widget_registry.py`)

**Purpose:** Track widgets and their relationships during drag operations.

**API:**
```python
class WidgetRegistry:
    def register_widget(widget, parent_tab_widget)
    def get_widget(widget_id)
    def get_parent_tab_widget(widget)
    def unregister_widget(widget)
    def clear()
```

**Implementation:**
- Use dictionary: `{widget_id: {'widget': widget, 'parent': parent_tab_widget}}`
- Thread-safe (if needed)
- Cleanup on widget deletion

---

#### 1.2 Signal Connection Manager (`modules/signal_connection_manager.py`)

**Purpose:** Track and reconnect signal connections when widgets move.

**API:**
```python
class SignalConnectionManager:
    def register_connection(source, signal, target, slot)
    def disconnect_all(widget)
    def reconnect_all(widget, new_parent)
    def get_connections(widget)
```

**Implementation:**
- Track connections: `{widget_id: [(source, signal, target, slot), ...]}`
- Store connection metadata
- Disconnect before move
- Reconnect after move

**Connection Patterns to Track:**

**For TabManager widgets:**
1. `FileTree.location_changed` → `MainWindowContainer.update_address_bar`
2. `FileTree.file_tree_clicked` → `TabManager.handle_file_tree_clicked`
3. `FileTree.context_menu_action_triggered` → `TabManager.handle_context_menu_action`

**For TabManager itself:**
1. `TabManager.active_manager_changed` → `MainWindowContainer.on_active_manager_changed`
2. `TabManager.pin_item_requested` → `MainWindowContainer.handle_pin_request`
3. `TabManager.currentChanged` → `MainWindowContainer.update_file_tree_connections`

**For MainWindowTabs:**
1. `MainWindowTabs.new_tab_added` → `MainWindow.on_new_tab_added`
2. `MainWindowTabs.currentChanged` → `MainWindow.update_address_bar_on_tab_change`

---

#### 1.3 Parent Reference Storage

**Purpose:** Store container reference in widget to avoid `parentWidget()` traversal issues.

**Implementation:**
- Add `setProperty("main_window_container", container)` when widget created
- Update `TabManager.get_main_window_container()` to check property first
- Fall back to `parentWidget()` traversal if property missing

---

### Phase 2: Drag Start Implementation

#### 2.1 Enable Drag in `DraggableTabBar`

**File:** `ui/draggable_tab_bar.py`

**Changes:**
1. Re-enable `setAcceptDrops(True)`
2. Implement `startDrag()` method:
   - Get widget from tab index
   - Register widget in `WidgetRegistry`
   - Create MIME data with widget ID
   - Start drag operation
   - Store drag state

**MIME Data:**
```python
mime_data = QMimeData()
mime_data.setData("application/x-qtabwidget-widget-id", str(id(widget)).encode())
```

---

#### 2.2 Drag Threshold & Visual Feedback

**Implementation:**
- Set drag threshold (e.g., 10 pixels)
- Visual feedback during drag (optional)
- Cursor changes

---

### Phase 3: Drop Handling (Same Widget)

#### 3.1 Handle Drops Within Same `QTabWidget`

**Files:** `ui/tab_manager.py`, `ui/main_window.py`

**Implementation:**
- Override `dropEvent()` in `QTabWidget` subclasses
- Check if drop is within same widget
- Use Qt's built-in reordering (already enabled with `setMovable(True)`)
- No signal reconnection needed (same parent)
- No history migration needed (same widget)

**Note:** Qt's `setMovable(True)` already handles this, but we need to ensure it doesn't conflict with our custom drag-and-drop.

---

### Phase 4: Drop Handling (Different Widget)

#### 4.1 Handle Drops Between Different `QTabWidget` Instances

**Files:** `ui/tab_manager.py`, `ui/main_window.py`

**Implementation:**
1. **Detect Drop Target:**
   - Get widget ID from MIME data
   - Look up widget in `WidgetRegistry`
   - Determine source and target `QTabWidget` instances

2. **Before Move:**
   - Disconnect all signals (`SignalConnectionManager.disconnect_all()`)
   - Get tab title from source
   - Get widget from source

3. **Move Widget:**
   - Remove widget from source: `source_tab_widget.removeTab(index)`
   - Add widget to target: `target_tab_widget.addTab(widget, title)`
   - Set as active: `target_tab_widget.setCurrentWidget(widget)`

4. **Migrate History:**
   - Call `history_manager.migrate_history(source_widget, target_widget)`
   - Note: Widget ID doesn't change, so history stays with widget

5. **Update Parent Reference:**
   - Update `setProperty("main_window_container", new_container)`
   - Update `TabManager` parent if needed

6. **Reconnect Signals:**
   - Determine new parent container
   - Reconnect all signals (`SignalConnectionManager.reconnect_all()`)

7. **Update UI:**
   - Call `MainWindowContainer.update_file_tree_connections()`
   - Emit `active_manager_changed` signal
   - Update address bar

---

#### 4.2 Handle Drops Between `MainWindowTabs` and `TabManager`

**Scenarios:**
- Drag `MainWindowContainer` from `MainWindowTabs` to another `MainWindowTabs` (shouldn't happen - different widget types)
- Drag `FileTree` widget from `TabManager` to another `TabManager` ✅
- Drag `FileTree` widget from `TabManager` to `MainWindowTabs` ❌ (incompatible)
- Drag `MainWindowContainer` from `MainWindowTabs` to `TabManager` ❌ (incompatible)

**Solution:**
- Validate widget types before drop
- Only allow compatible drops
- Show visual feedback for invalid drops

---

### Phase 5: External Window Support

#### 5.1 Detect External Window Drops

**Implementation:**
- Detect when drag goes outside application window bounds
- Create new `MainWindow` instance (similar to `detach_main_tab()`)
- Move widget to new window
- Migrate history
- Reconnect signals
- Show new window

---

#### 5.2 Handle Reattachment

**Implementation:**
- Detect when drag from detached window goes back to main window
- Close detached window (if last tab)
- Move widget back to main window
- Migrate history
- Reconnect signals

---

### Phase 6: Split View Compatibility

#### 6.1 Detect Split View State

**Implementation:**
- Check for `splitter` attribute in `MainWindowContainer`
- Check `splitter.count() > 1` for active split view
- Handle both left and right panes

---

#### 6.2 Handle Drops in Split View

**Scenarios:**
1. **Drag from left pane to right pane:**
   - Same container, different `TabManager`
   - Migrate history
   - Reconnect signals (new parent `TabManager`)

2. **Drag from right pane to left pane:**
   - Same container, different `TabManager`
   - Migrate history
   - Reconnect signals

3. **Drag from split view to non-split container:**
   - Different container
   - Migrate history
   - Reconnect signals
   - Update address bar

4. **Drag from non-split container to split view:**
   - Determine target pane (left or right)
   - Migrate history
   - Reconnect signals
   - Update address bar

---

### Phase 7: Testing & Refinement

#### 7.1 Unit Tests

**Test Cases:**
1. Widget registry registration/unregistration
2. Signal connection tracking
3. History migration
4. Parent reference storage

---

#### 7.2 Integration Tests

**Test Scenarios:**
1. Drag tab within same `TabManager` (reorder)
2. Drag tab between different `TabManager` instances
3. Drag tab from `TabManager` to detached window
4. Drag tab from detached window back to `TabManager`
5. Drag tab in split view (all scenarios)
6. Drag tab with history (back/forward navigation)
7. Drag tab with active selection
8. Drag tab with address bar updates
9. Multiple simultaneous drags (should be prevented)
10. Drag cancelled (no move)

---

#### 7.3 Edge Case Tests

**Test Scenarios:**
1. Drag to invalid target (should be rejected)
2. Widget deleted during drag (should handle gracefully)
3. Drag to same location (no-op)
4. Drag last tab (should prevent or handle specially)
5. Drag with split view active (all combinations)

---

## Signal Reconnection Strategy

### Connection Patterns

#### Pattern 1: Widget → Container Signals

**Example:** `FileTree.location_changed` → `MainWindowContainer.update_address_bar`

**Reconnection Logic:**
1. Find new `MainWindowContainer` parent
2. Disconnect old connection
3. Connect to new container

**Code:**
```python
# Before move
file_tree.location_changed.disconnect(old_container.update_address_bar)

# After move
file_tree.location_changed.connect(new_container.update_address_bar)
```

---

#### Pattern 2: TabManager → Container Signals

**Example:** `TabManager.active_manager_changed` → `MainWindowContainer.on_active_manager_changed`

**Reconnection Logic:**
1. Find new `MainWindowContainer` parent
2. Disconnect old connection
3. Connect to new container

**Code:**
```python
# Before move
tab_manager.active_manager_changed.disconnect(old_container.on_active_manager_changed)

# After move
tab_manager.active_manager_changed.connect(new_container.on_active_manager_changed)
```

---

#### Pattern 3: TabManager Internal Signals

**Example:** `TabManager.currentChanged` → `TabManager.on_tab_changed` (internal)

**Reconnection Logic:**
- These are internal to `TabManager`, so they persist
- No reconnection needed

---

#### Pattern 4: FileTree → TabManager Signals

**Example:** `FileTree.file_tree_clicked` → `TabManager.handle_file_tree_clicked`

**Reconnection Logic:**
1. Find new `TabManager` parent
2. Disconnect old connection
3. Connect to new `TabManager`

**Code:**
```python
# Before move
file_tree.file_tree_clicked.disconnect(old_tab_manager.handle_file_tree_clicked)

# After move
file_tree.file_tree_clicked.connect(new_tab_manager.handle_file_tree_clicked)
```

---

### Automatic Reconnection

**Implementation:**
1. When widget is created, register all signal connections
2. When widget moves, disconnect all registered connections
3. When widget is added to new parent, reconnect all connections

**Helper Method:**
```python
def reconnect_widget_signals(widget, new_parent_container, new_parent_tab_manager):
    """Reconnect all signals for a moved widget."""
    # Get FileTree from widget
    file_tree = widget.findChild(FileTree)
    if file_tree:
        # Reconnect FileTree signals
        file_tree.location_changed.connect(new_parent_container.update_address_bar)
        file_tree.file_tree_clicked.connect(new_parent_tab_manager.handle_file_tree_clicked)
        file_tree.context_menu_action_triggered.connect(new_parent_tab_manager.handle_context_menu_action)
    
    # Reconnect TabManager signals (if widget is TabManager)
    if isinstance(widget, TabManager):
        widget.active_manager_changed.connect(new_parent_container.on_active_manager_changed)
        widget.pin_item_requested.connect(new_parent_container.handle_pin_request)
        widget.currentChanged.connect(new_parent_container.update_file_tree_connections)
```

---

## Widget Lifecycle Management

### Widget Creation

**Current Flow:**
1. `TabManager.add_new_file_tree_tab()` creates widget
2. Widget added to `TabManager`
3. Signals connected
4. History initialized

**After Drag-and-Drop:**
- Widget creation unchanged
- Signal registration added
- Parent reference stored

---

### Widget Movement

**Flow:**
1. **Before Move:**
   - Disconnect signals
   - Store widget reference
   - Get tab title

2. **Move:**
   - Remove from source
   - Add to target
   - Set as active

3. **After Move:**
   - Update parent reference
   - Migrate history
   - Reconnect signals
   - Update UI

---

### Widget Deletion

**Current Flow:**
1. `TabManager.close_tab()` called
2. History removed: `history_manager.remove_tab_history(widget)`
3. Widget deleted: `widget.deleteLater()`

**After Drag-and-Drop:**
- Unregister from `WidgetRegistry`
- Disconnect signals
- Remove history
- Delete widget

---

## Edge Cases & Special Scenarios

### Scenario 1: Drag Last Tab

**Problem:** Dragging the last tab leaves source empty.

**Solution:**
- Prevent drag if it's the last tab (optional)
- Or create new empty tab after drag
- Or allow drag and handle empty state

**Recommendation:** Allow drag, create new empty tab if needed.

---

### Scenario 2: Drag to Same Location

**Problem:** Dragging tab to its current location is a no-op.

**Solution:**
- Detect same location
- Cancel drag operation
- No signal reconnection needed
- No history migration needed

---

### Scenario 3: Widget Deleted During Drag

**Problem:** Widget is deleted while drag is in progress.

**Solution:**
- Check widget validity before drop
- Cancel drop if widget invalid
- Clean up drag state
- Log error

---

### Scenario 4: Multiple Simultaneous Drags

**Problem:** User starts multiple drags at once.

**Solution:**
- Track active drag state
- Prevent new drags while one is active
- Or queue drags (complex, not recommended)

**Recommendation:** Prevent multiple simultaneous drags.

---

### Scenario 5: Drag with Split View Active

**Problem:** Complex widget hierarchy with splitter.

**Solution:**
- Detect split view state
- Determine target pane
- Handle widget relationships correctly
- Update address bar appropriately

---

## Testing Strategy

### Unit Tests

**Files to Test:**
1. `modules/widget_registry.py`
2. `modules/signal_connection_manager.py`
3. `modules/tab_history_manager.py` (already tested)

**Test Coverage:**
- Registration/unregistration
- Lookup operations
- Signal tracking
- Connection management

---

### Integration Tests

**Manual Test Scenarios:**

1. **Basic Drag-and-Drop:**
   - Create 2 tabs in `TabManager`
   - Drag tab 1 to position after tab 2
   - Verify tab order changed
   - Verify history intact
   - Verify signals working

2. **Cross-Container Drag:**
   - Create 2 `MainWindowContainer` instances
   - Drag tab from container 1 to container 2
   - Verify widget moved
   - Verify history migrated
   - Verify signals reconnected
   - Verify address bar updates

3. **Split View Drag:**
   - Enable split view
   - Drag tab from left pane to right pane
   - Verify widget moved
   - Verify history migrated
   - Verify signals reconnected
   - Verify address bar updates

4. **External Window Drag:**
   - Drag tab outside application
   - Verify new window created
   - Verify widget moved
   - Verify history migrated
   - Verify signals reconnected

5. **Reattachment Drag:**
   - Detach tab to new window
   - Drag tab back to original window
   - Verify widget moved back
   - Verify history migrated
   - Verify signals reconnected
   - Verify detached window closed (if last tab)

---

### Regression Tests

**Verify Existing Functionality Still Works:**
1. Tab creation
2. Tab closing
3. Tab navigation (back/forward)
4. Address bar updates
5. Split view toggle
6. Panel toggling
7. Context menus
8. Keyboard shortcuts

---

## Risk Assessment

### High Risk Areas

1. **Signal Reconnection** - Complex, many connections
   - **Mitigation:** Comprehensive testing, incremental implementation

2. **Split View Compatibility** - Complex widget hierarchy
   - **Mitigation:** Test all scenarios, handle edge cases

3. **Parent Reference Management** - Critical for many operations
   - **Mitigation:** Store references, fall back to traversal

---

### Medium Risk Areas

1. **External Window Support** - New functionality
   - **Mitigation:** Reuse existing `detach_main_tab()` logic

2. **Widget Registry** - New infrastructure
   - **Mitigation:** Simple implementation, thorough testing

3. **MIME Data Format** - Custom format
   - **Mitigation:** Use standard Qt patterns, test thoroughly

---

### Low Risk Areas

1. **History Migration** - Already implemented and tested
2. **Widget Lifecycle** - Standard Qt patterns
3. **UI Updates** - Existing methods, just need to call them

---

## Implementation Order

### Recommended Sequence

1. **Phase 1: Infrastructure** (Widget Registry, Signal Manager, Parent References)
2. **Phase 2: Drag Start** (Enable drag in `DraggableTabBar`)
3. **Phase 3: Same Widget Drops** (Reordering within same `QTabWidget`)
4. **Phase 4: Different Widget Drops** (Between `TabManager` instances)
5. **Phase 5: External Window Support** (Detached windows)
6. **Phase 6: Split View Compatibility** (All split view scenarios)
7. **Phase 7: Testing & Refinement** (Comprehensive testing)

---

## Success Criteria

### Functional Requirements

✅ Tabs can be dragged within same `TabManager` (reorder)  
✅ Tabs can be dragged between different `TabManager` instances  
✅ Tabs can be dragged to external windows  
✅ Tabs can be dragged back from external windows  
✅ History persists through all drag operations  
✅ Signals reconnect correctly after drag  
✅ Address bar updates correctly after drag  
✅ Split view works with drag-and-drop  
✅ No crashes or memory leaks  
✅ Existing functionality unchanged  

---

### Performance Requirements

✅ Drag operation feels responsive (< 100ms)  
✅ No UI freezing during drag  
✅ Memory usage stable (no leaks)  

---

### Code Quality Requirements

✅ Clean, maintainable code  
✅ Comprehensive error handling  
✅ Logging for debugging  
✅ Type hints throughout  
✅ Docstrings for all methods  

---

## Conclusion

This plan addresses all identified gaps and provides a clear path to robust drag-and-drop tab functionality. The phased approach allows for incremental implementation and testing, reducing risk and ensuring quality.

**Next Step:** Begin Phase 1 implementation (Infrastructure).

---

## Appendix: Signal Connection Reference

### TabManager Widget Signals

**FileTree → TabManager:**
- `file_tree_clicked` → `handle_file_tree_clicked`
- `context_menu_action_triggered` → `handle_context_menu_action`

**FileTree → MainWindowContainer:**
- `location_changed` → `update_address_bar`

**TabManager → MainWindowContainer:**
- `active_manager_changed` → `on_active_manager_changed`
- `pin_item_requested` → `handle_pin_request`
- `currentChanged` → `update_file_tree_connections`

**TabManager Internal:**
- `tabCloseRequested` → `close_tab`
- `tabBarDoubleClicked` → `handle_tab_bar_double_click`
- `customContextMenuRequested` → `show_tab_context_menu`

---

### MainWindowTabs Signals

**MainWindowTabs → MainWindow:**
- `new_tab_added` → `on_new_tab_added`
- `currentChanged` → `update_address_bar_on_tab_change`

**MainWindowTabs Internal:**
- `tabCloseRequested` → `close_tab`
- `customContextMenuRequested` → `show_tab_context_menu`

---

### PinnedPanel Signals

**PinnedPanel → MainWindow:**
- `pinned_item_added_global` → `refresh_all_pinned_panels`
- `pinned_item_modified` → `refresh_all_pinned_panels`
- `pinned_item_removed` → `refresh_all_pinned_panels`

---

**End of Document**

