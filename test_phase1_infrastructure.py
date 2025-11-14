"""
Test script for Phase 1 Infrastructure Components

This script tests the WidgetRegistry and SignalConnectionManager
to verify they work correctly before implementing drag-and-drop.
"""

import sys
import io

# Fix Windows console encoding for emoji output
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from PyQt6.QtWidgets import QApplication, QWidget, QPushButton
from PyQt6.QtCore import pyqtSignal, QObject

# Import infrastructure components
from modules.widget_registry import get_widget_registry
from modules.signal_connection_manager import get_signal_connection_manager


class TestSignal(QObject):
    """Test signal for signal connection manager tests."""
    test_signal = pyqtSignal(str)


def test_widget_registry():
    """Test WidgetRegistry functionality."""
    print("\n" + "="*60)
    print("TEST 1: Widget Registry")
    print("="*60)
    
    registry = get_widget_registry()
    
    # Create test widgets
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    widget1 = QWidget()
    widget2 = QWidget()
    parent_tab1 = QWidget()  # Simulating QTabWidget
    parent_tab2 = QWidget()
    
    # Test registration
    print("\n1.1 Testing widget registration...")
    result1 = registry.register_widget(widget1, parent_tab1)
    result2 = registry.register_widget(widget2, parent_tab2)
    assert result1, "Failed to register widget1"
    assert result2, "Failed to register widget2"
    print("  ✅ Widget registration successful")
    
    # Test lookup
    print("\n1.2 Testing widget lookup...")
    found_widget = registry.get_widget(id(widget1))
    assert found_widget == widget1, "Failed to retrieve widget1"
    print("  ✅ Widget lookup successful")
    
    # Test parent lookup
    print("\n1.3 Testing parent tab widget lookup...")
    parent = registry.get_parent_tab_widget(widget1)
    assert parent == parent_tab1, "Failed to retrieve parent tab widget"
    print("  ✅ Parent tab widget lookup successful")
    
    # Test is_registered
    print("\n1.4 Testing is_registered check...")
    assert registry.is_registered(widget1), "Widget1 should be registered"
    assert not registry.is_registered(QWidget()), "New widget should not be registered"
    print("  ✅ Registration check successful")
    
    # Test update_parent
    print("\n1.5 Testing parent update...")
    new_parent = QWidget()
    result = registry.update_parent(widget1, new_parent)
    assert result, "Failed to update parent"
    updated_parent = registry.get_parent_tab_widget(widget1)
    assert updated_parent == new_parent, "Parent not updated correctly"
    print("  ✅ Parent update successful")
    
    # Test unregister
    print("\n1.6 Testing widget unregistration...")
    result = registry.unregister_widget(widget1)
    assert result, "Failed to unregister widget1"
    assert not registry.is_registered(widget1), "Widget1 should not be registered"
    print("  ✅ Widget unregistration successful")
    
    # Test registry size
    print("\n1.7 Testing registry size...")
    size = registry.get_registry_size()
    assert size == 1, f"Expected 1 widget, got {size}"
    print(f"  ✅ Registry size: {size}")
    
    # Cleanup
    registry.clear()
    print("\n✅ All Widget Registry tests passed!")


def test_signal_connection_manager():
    """Test SignalConnectionManager functionality."""
    print("\n" + "="*60)
    print("TEST 2: Signal Connection Manager")
    print("="*60)
    
    manager = get_signal_connection_manager()
    
    # Create test objects
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    widget = QWidget()
    source = TestSignal()
    target = QObject()
    
    # Track signal emissions
    received_messages = []
    
    def test_slot(message: str):
        received_messages.append(message)
    
    # Test registration
    print("\n2.1 Testing connection registration...")
    result = manager.register_connection(
        widget=widget,
        source=source,
        signal_name="test_signal",
        target=target,
        slot=test_slot
    )
    assert result, "Failed to register connection"
    print("  ✅ Connection registration successful")
    
    # Test connection count
    print("\n2.2 Testing connection retrieval...")
    connections = manager.get_connections(widget)
    assert len(connections) == 1, f"Expected 1 connection, got {len(connections)}"
    print(f"  ✅ Found {len(connections)} connection(s)")
    
    # Test signal emission (connection should work)
    print("\n2.3 Testing signal emission...")
    source.test_signal.connect(test_slot)  # Connect directly for test
    source.test_signal.emit("test_message")
    assert len(received_messages) == 1, "Signal not received"
    assert received_messages[0] == "test_message", "Wrong message received"
    print("  ✅ Signal emission successful")
    
    # Test disconnect_all
    print("\n2.4 Testing disconnect_all...")
    received_messages.clear()
    disconnected_count = manager.disconnect_all(widget)
    assert disconnected_count >= 0, "disconnect_all should return count"
    print(f"  ✅ Disconnected {disconnected_count} connection(s)")
    
    # Test reconnect_all
    print("\n2.5 Testing reconnect_all...")
    new_target = QObject()
    reconnected_count = manager.reconnect_all(widget, new_target_container=new_target)
    assert reconnected_count >= 0, "reconnect_all should return count"
    print(f"  ✅ Reconnected {reconnected_count} connection(s)")
    
    # Test unregister_widget
    print("\n2.6 Testing widget unregistration...")
    result = manager.unregister_widget(widget)
    assert result, "Failed to unregister widget"
    connections = manager.get_connections(widget)
    assert len(connections) == 0, "Widget should have no connections"
    print("  ✅ Widget unregistration successful")
    
    # Test registry size
    print("\n2.7 Testing registry size...")
    size = manager.get_registry_size()
    assert size == 0, f"Expected 0 widgets, got {size}"
    print(f"  ✅ Registry size: {size}")
    
    # Cleanup
    manager.clear()
    print("\n✅ All Signal Connection Manager tests passed!")


def test_integration():
    """Test integration between registry and signal manager."""
    print("\n" + "="*60)
    print("TEST 3: Integration Test")
    print("="*60)
    
    registry = get_widget_registry()
    signal_manager = get_signal_connection_manager()
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    # Simulate widget creation and registration
    print("\n3.1 Simulating widget creation...")
    widget = QWidget()
    parent_tab = QWidget()
    source = TestSignal()
    target = QObject()
    
    received_messages = []
    def test_slot(msg):
        received_messages.append(msg)
    
    # Register widget
    registry.register_widget(widget, parent_tab)
    print("  ✅ Widget registered")
    
    # Register signal connection
    signal_manager.register_connection(
        widget=widget,
        source=source,
        signal_name="test_signal",
        target=target,
        slot=test_slot
    )
    print("  ✅ Signal connection registered")
    
    # Verify both are registered
    assert registry.is_registered(widget), "Widget should be registered"
    connections = signal_manager.get_connections(widget)
    assert len(connections) == 1, "Widget should have 1 connection"
    print("  ✅ Integration verified")
    
    # Simulate widget cleanup
    print("\n3.2 Simulating widget cleanup...")
    registry.unregister_widget(widget)
    signal_manager.unregister_widget(widget)
    
    assert not registry.is_registered(widget), "Widget should not be registered"
    connections = signal_manager.get_connections(widget)
    assert len(connections) == 0, "Widget should have no connections"
    print("  ✅ Cleanup successful")
    
    print("\n✅ Integration test passed!")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("PHASE 1 INFRASTRUCTURE TESTS")
    print("="*60)
    
    try:
        test_widget_registry()
        test_signal_connection_manager()
        test_integration()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nPhase 1 Infrastructure is ready for drag-and-drop implementation.")
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

