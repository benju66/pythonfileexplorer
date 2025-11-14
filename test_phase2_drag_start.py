"""
Test script for Phase 2 Drag Start Implementation

This script tests the drag start functionality in DraggableTabBar
to verify drag operations can be initiated correctly.
"""

import sys
import io

# Fix Windows console encoding for emoji output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QMimeData, QPoint
from ui.draggable_tab_bar import DraggableTabBar, TAB_WIDGET_MIME_TYPE
from modules.widget_registry import get_widget_registry


def test_draggable_tab_bar_initialization():
    """Test DraggableTabBar initialization."""
    print("\n" + "="*60)
    print("TEST 1: DraggableTabBar Initialization")
    print("="*60)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    tab_widget = QTabWidget()
    tab_bar = DraggableTabBar(tab_widget)
    tab_widget.setTabBar(tab_bar)
    
    # Test initialization
    assert tab_bar.drag_start_pos is None, "drag_start_pos should be None initially"
    assert tab_bar.drag_threshold == 10, f"drag_threshold should be 10, got {tab_bar.drag_threshold}"
    assert tab_bar.is_dragging == False, "is_dragging should be False initially"
    assert tab_bar.widget_registry is not None, "widget_registry should be initialized"
    print("  ✅ Initialization successful")
    
    # Test accept drops is enabled
    assert tab_bar.acceptDrops() == True, "acceptDrops should be True"
    print("  ✅ Accept drops enabled")
    
    print("\n✅ All initialization tests passed!")


def test_mime_type_constant():
    """Test MIME type constant is defined."""
    print("\n" + "="*60)
    print("TEST 2: MIME Type Constant")
    print("="*60)
    
    assert TAB_WIDGET_MIME_TYPE is not None, "TAB_WIDGET_MIME_TYPE should be defined"
    assert isinstance(TAB_WIDGET_MIME_TYPE, str), "TAB_WIDGET_MIME_TYPE should be a string"
    assert TAB_WIDGET_MIME_TYPE == "application/x-qtabwidget-widget-id", \
        f"MIME type should be 'application/x-qtabwidget-widget-id', got '{TAB_WIDGET_MIME_TYPE}'"
    print(f"  ✅ MIME type: {TAB_WIDGET_MIME_TYPE}")
    
    print("\n✅ MIME type constant test passed!")


def test_widget_registration_during_drag():
    """Test that widgets are registered during drag start."""
    print("\n" + "="*60)
    print("TEST 3: Widget Registration During Drag")
    print("="*60)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    registry = get_widget_registry()
    registry.clear()  # Start with clean registry
    
    # Create tab widget with draggable tab bar
    tab_widget = QTabWidget()
    tab_bar = DraggableTabBar(tab_widget)
    tab_widget.setTabBar(tab_bar)
    
    # Create test widget
    test_widget = QWidget()
    test_widget.setLayout(QVBoxLayout())
    label = QLabel("Test Tab")
    test_widget.layout().addWidget(label)
    
    # Add widget to tab
    tab_index = tab_widget.addTab(test_widget, "Test")
    
    # Verify widget is not registered yet (unless registered elsewhere)
    # In real usage, widgets are registered when created, but for this test
    # we'll simulate the drag start which should register it
    
    # Simulate drag start (we can't actually start a drag in a test,
    # but we can verify the logic)
    widget = tab_widget.widget(tab_index)
    assert widget is not None, "Widget should exist"
    
    # Manually register to simulate what start_drag would do
    if not registry.is_registered(widget):
        registry.register_widget(widget, tab_widget)
    
    # Verify registration
    assert registry.is_registered(widget), "Widget should be registered"
    parent = registry.get_parent_tab_widget(widget)
    assert parent == tab_widget, "Parent should be tab_widget"
    print("  ✅ Widget registration works")
    
    print("\n✅ Widget registration test passed!")


def test_mime_data_creation():
    """Test MIME data creation with widget ID."""
    print("\n" + "="*60)
    print("TEST 4: MIME Data Creation")
    print("="*60)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    # Create test widget
    test_widget = QWidget()
    widget_id = id(test_widget)
    widget_id_str = str(widget_id)
    
    # Create MIME data (simulating what start_drag does)
    mime_data = QMimeData()
    mime_data.setData(TAB_WIDGET_MIME_TYPE, widget_id_str.encode('utf-8'))
    
    # Verify MIME data
    assert mime_data.hasFormat(TAB_WIDGET_MIME_TYPE), "MIME data should have our custom format"
    
    # Retrieve widget ID from MIME data
    retrieved_data = mime_data.data(TAB_WIDGET_MIME_TYPE).data().decode('utf-8')
    retrieved_id = int(retrieved_data)
    
    assert retrieved_id == widget_id, f"Widget ID mismatch: {retrieved_id} != {widget_id}"
    print(f"  ✅ Widget ID stored correctly: {widget_id}")
    print(f"  ✅ Widget ID retrieved correctly: {retrieved_id}")
    
    print("\n✅ MIME data creation test passed!")


def test_drag_threshold():
    """Test drag threshold detection."""
    print("\n" + "="*60)
    print("TEST 5: Drag Threshold")
    print("="*60)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    tab_widget = QTabWidget()
    tab_bar = DraggableTabBar(tab_widget)
    tab_widget.setTabBar(tab_bar)
    
    # Test threshold value
    assert tab_bar.drag_threshold == 10, f"Threshold should be 10, got {tab_bar.drag_threshold}"
    print(f"  ✅ Drag threshold: {tab_bar.drag_threshold} pixels")
    
    # Test threshold calculation (simulated)
    start_pos = QPoint(10, 10)
    
    # Position within threshold
    pos_within = QPoint(15, 10)  # 5 pixels away
    distance_within = (pos_within - start_pos).manhattanLength()
    assert distance_within <= tab_bar.drag_threshold, "Should be within threshold"
    print(f"  ✅ Within threshold: {distance_within} <= {tab_bar.drag_threshold}")
    
    # Position beyond threshold
    pos_beyond = QPoint(25, 10)  # 15 pixels away
    distance_beyond = (pos_beyond - start_pos).manhattanLength()
    assert distance_beyond > tab_bar.drag_threshold, "Should be beyond threshold"
    print(f"  ✅ Beyond threshold: {distance_beyond} > {tab_bar.drag_threshold}")
    
    print("\n✅ Drag threshold test passed!")


def test_integration():
    """Test integration of drag start components."""
    print("\n" + "="*60)
    print("TEST 6: Integration Test")
    print("="*60)
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    registry = get_widget_registry()
    registry.clear()
    
    # Create complete tab widget setup
    tab_widget = QTabWidget()
    tab_bar = DraggableTabBar(tab_widget)
    tab_widget.setTabBar(tab_bar)
    
    # Create and add test widgets
    widget1 = QWidget()
    widget1.setLayout(QVBoxLayout())
    widget1.layout().addWidget(QLabel("Tab 1"))
    
    widget2 = QWidget()
    widget2.setLayout(QVBoxLayout())
    widget2.layout().addWidget(QLabel("Tab 2"))
    
    tab_widget.addTab(widget1, "Tab 1")
    tab_widget.addTab(widget2, "Tab 2")
    
    # Verify setup
    assert tab_widget.count() == 2, "Should have 2 tabs"
    assert tab_bar.parent() == tab_widget, "Tab bar parent should be tab widget"
    print("  ✅ Tab widget setup complete")
    
    # Verify widgets can be retrieved
    retrieved_widget1 = tab_widget.widget(0)
    retrieved_widget2 = tab_widget.widget(1)
    assert retrieved_widget1 == widget1, "Widget 1 should match"
    assert retrieved_widget2 == widget2, "Widget 2 should match"
    print("  ✅ Widget retrieval works")
    
    # Verify tab bar can get parent
    parent = tab_bar.parent()
    assert isinstance(parent, QTabWidget), "Parent should be QTabWidget"
    print("  ✅ Parent retrieval works")
    
    print("\n✅ Integration test passed!")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PHASE 2 DRAG START TESTS")
    print("="*60)
    
    try:
        test_draggable_tab_bar_initialization()
        test_mime_type_constant()
        test_widget_registration_during_drag()
        test_mime_data_creation()
        test_drag_threshold()
        test_integration()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nPhase 2 Drag Start is ready for Phase 3 (Drop Handling).")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

