#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone test script for TabHistoryManager.
Tests the core functionality without requiring the full GUI application.
"""

import sys
import os
import io

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from PyQt6.QtWidgets import QApplication, QWidget

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.tab_history_manager import TabHistoryManager


def test_basic_history():
    """Test basic history operations."""
    print("\n" + "="*60)
    print("TEST 1: Basic History Operations")
    print("="*60)
    
    manager = TabHistoryManager()
    widget = QWidget()
    
    # Test initialization
    print("\n1.1 Testing init_tab_history...")
    manager.init_tab_history(widget, "/test/path1")
    current = manager.get_current_path(widget)
    assert current == "/test/path1", f"Expected '/test/path1', got '{current}'"
    print("   [OK] History initialized correctly")
    
    # Test push_path
    print("\n1.2 Testing push_path...")
    manager.push_path(widget, "/test/path2")
    current = manager.get_current_path(widget)
    assert current == "/test/path2", f"Expected '/test/path2', got '{current}'"
    print("   [OK] Path pushed correctly")
    
    # Test multiple pushes
    print("\n1.3 Testing multiple push_path...")
    manager.push_path(widget, "/test/path3")
    manager.push_path(widget, "/test/path4")
    current = manager.get_current_path(widget)
    assert current == "/test/path4", f"Expected '/test/path4', got '{current}'"
    print("   [OK] Multiple paths pushed correctly")
    
    # Test go_back
    print("\n1.4 Testing go_back...")
    path = manager.go_back(widget)
    assert path == "/test/path3", f"Expected '/test/path3', got '{path}'"
    current = manager.get_current_path(widget)
    assert current == "/test/path3", f"Expected '/test/path3', got '{current}'"
    print("   [OK] Go back works correctly")
    
    # Test go_forward
    print("\n1.5 Testing go_forward...")
    path = manager.go_forward(widget)
    assert path == "/test/path4", f"Expected '/test/path4', got '{path}'"
    current = manager.get_current_path(widget)
    assert current == "/test/path4", f"Expected '/test/path4', got '{current}'"
    print("   [OK] Go forward works correctly")
    
    # Test go_back multiple times
    print("\n1.6 Testing multiple go_back...")
    manager.go_back(widget)
    manager.go_back(widget)
    current = manager.get_current_path(widget)
    assert current == "/test/path2", f"Expected '/test/path2', got '{current}'"
    print("   [OK] Multiple go_back works correctly")
    
    # Test push_path after going back (should truncate forward history)
    print("\n1.7 Testing push_path after go_back (truncate forward)...")
    manager.push_path(widget, "/test/path5")
    current = manager.get_current_path(widget)
    assert current == "/test/path5", f"Expected '/test/path5', got '{current}'"
    # Should not be able to go forward to path4 anymore
    forward_path = manager.go_forward(widget)
    assert forward_path == "", f"Expected empty string (no forward), got '{forward_path}'"
    print("   [OK] Forward history truncated correctly")
    
    print("\n[PASS] TEST 1: Basic history operations work correctly")


def test_widget_id_stability():
    """Test that widget IDs are stable."""
    print("\n" + "="*60)
    print("TEST 2: Widget ID Stability")
    print("="*60)
    
    manager = TabHistoryManager()
    widget1 = QWidget()
    widget2 = QWidget()
    
    # Initialize history for two widgets
    manager.init_tab_history(widget1, "/widget1/path1")
    manager.init_tab_history(widget2, "/widget2/path1")
    
    # Get widget IDs
    widget1_id = id(widget1)
    widget2_id = id(widget2)
    
    print(f"\n2.1 Widget 1 ID: {widget1_id}")
    print(f"    Widget 2 ID: {widget2_id}")
    assert widget1_id != widget2_id, "Widget IDs should be different"
    print("   [OK] Widget IDs are unique")
    
    # Verify history is separate
    path1 = manager.get_current_path(widget1)
    path2 = manager.get_current_path(widget2)
    assert path1 == "/widget1/path1", f"Expected '/widget1/path1', got '{path1}'"
    assert path2 == "/widget2/path1", f"Expected '/widget2/path1', got '{path2}'"
    print("   [OK] History is separate per widget")
    
    # Verify ID stability (same widget = same ID)
    widget1_id_again = id(widget1)
    assert widget1_id == widget1_id_again, "Widget ID should be stable"
    print("   [OK] Widget IDs are stable")
    
    print("\n[PASS] TEST 2: Widget ID stability verified")


def test_history_migration():
    """Test history migration between widgets."""
    print("\n" + "="*60)
    print("TEST 3: History Migration")
    print("="*60)
    
    manager = TabHistoryManager()
    source_widget = QWidget()
    target_widget = QWidget()
    
    # Build up history in source widget
    manager.init_tab_history(source_widget, "/source/path1")
    manager.push_path(source_widget, "/source/path2")
    manager.push_path(source_widget, "/source/path3")
    manager.go_back(source_widget)  # Move back to path2
    
    print("\n3.1 Source widget history before migration:")
    debug_info = manager.get_history_debug_info(source_widget)
    print(f"   History: {debug_info['history']}")
    print(f"   Current Index: {debug_info['current_index']}")
    print(f"   Current Path: {debug_info['current_path']}")
    
    # Migrate history
    print("\n3.2 Migrating history...")
    manager.migrate_history(source_widget, target_widget)
    
    # Verify source history is gone
    source_path = manager.get_current_path(source_widget)
    assert source_path == "", f"Expected empty (history removed), got '{source_path}'"
    print("   [OK] Source widget history removed")
    
    # Verify target has the history
    target_path = manager.get_current_path(target_widget)
    assert target_path == "/source/path2", f"Expected '/source/path2', got '{target_path}'"
    print("   [OK] Target widget has migrated history")
    
    # Verify history index is preserved
    debug_info = manager.get_history_debug_info(target_widget)
    assert debug_info['current_index'] == 1, f"Expected index 1, got {debug_info['current_index']}"
    print("   [OK] History index preserved")
    
    # Verify can go forward/back
    forward_path = manager.go_forward(target_widget)
    assert forward_path == "/source/path3", f"Expected '/source/path3', got '{forward_path}'"
    print("   [OK] Forward navigation works after migration")
    
    print("\n[PASS] TEST 3: History migration works correctly")


def test_error_handling():
    """Test error handling."""
    print("\n" + "="*60)
    print("TEST 4: Error Handling")
    print("="*60)
    
    manager = TabHistoryManager()
    
    # Test None widget
    print("\n4.1 Testing None widget handling...")
    try:
        path = manager.get_current_path(None)
        assert path == "", f"Expected empty string for None widget, got '{path}'"
        print("   [OK] None widget handled gracefully")
    except Exception as e:
        print(f"   [FAIL] Unexpected error: {e}")
        raise
    
    # Test operations on widget without history
    print("\n4.2 Testing operations on widget without history...")
    widget = QWidget()
    path = manager.get_current_path(widget)
    assert path == "", f"Expected empty string, got '{path}'"
    print("   [OK] get_current_path returns empty for no history")
    
    back_path = manager.go_back(widget)
    assert back_path == "", f"Expected empty string, got '{back_path}'"
    print("   [OK] go_back returns empty for no history")
    
    forward_path = manager.go_forward(widget)
    assert forward_path == "", f"Expected empty string, got '{forward_path}'"
    print("   [OK] go_forward returns empty for no history")
    
    # Test remove_tab_history on widget without history
    print("\n4.3 Testing remove_tab_history on widget without history...")
    try:
        manager.remove_tab_history(widget)  # Should not raise error
        print("   [OK] remove_tab_history handles missing history gracefully")
    except Exception as e:
        print(f"   [FAIL] Unexpected error: {e}")
        raise
    
    print("\n[PASS] TEST 4: Error handling works correctly")


def test_debug_methods():
    """Test debug methods."""
    print("\n" + "="*60)
    print("TEST 5: Debug Methods")
    print("="*60)
    
    manager = TabHistoryManager()
    widget = QWidget()
    
    # Build history
    manager.init_tab_history(widget, "/debug/path1")
    manager.push_path(widget, "/debug/path2")
    manager.push_path(widget, "/debug/path3")
    manager.go_back(widget)
    
    print("\n5.1 Testing get_history_debug_info...")
    debug_info = manager.get_history_debug_info(widget)
    
    assert debug_info['has_history'] == True, "Should have history"
    assert debug_info['widget_id'] == id(widget), "Widget ID should match"
    assert len(debug_info['history']) == 3, f"Expected 3 paths, got {len(debug_info['history'])}"
    assert debug_info['current_index'] == 1, f"Expected index 1, got {debug_info['current_index']}"
    assert debug_info['current_path'] == "/debug/path2", f"Expected '/debug/path2', got '{debug_info['current_path']}'"
    assert debug_info['can_go_back'] == True, "Should be able to go back"
    assert debug_info['can_go_forward'] == True, "Should be able to go forward"
    
    print("   [OK] Debug info structure correct")
    print(f"   Debug info: {debug_info}")
    
    print("\n5.2 Testing print_all_history...")
    # This will print to console
    manager.print_all_history()
    print("   [OK] print_all_history executed without error")
    
    print("\n[PASS] TEST 5: Debug methods work correctly")


def test_go_up():
    """Test go_up functionality."""
    print("\n" + "="*60)
    print("TEST 6: Go Up Functionality")
    print("="*60)
    
    manager = TabHistoryManager()
    widget = QWidget()
    
    # Use a real path structure for go_up test
    test_path = os.path.abspath(".")
    parent_path = os.path.dirname(test_path)
    
    if parent_path and os.path.exists(parent_path):
        manager.init_tab_history(widget, test_path)
        
        print(f"\n6.1 Current path: {test_path}")
        print(f"    Parent path: {parent_path}")
        
        up_path = manager.go_up(widget)
        assert up_path == parent_path, f"Expected '{parent_path}', got '{up_path}'"
        print("   [OK] go_up navigates to parent correctly")
        
        current = manager.get_current_path(widget)
        assert current == parent_path, f"Expected '{parent_path}', got '{current}'"
        print("   [OK] Current path updated correctly")
        
        # Verify parent was added to history
        debug_info = manager.get_history_debug_info(widget)
        assert parent_path in debug_info['history'], "Parent path should be in history"
        print("   [OK] Parent path added to history")
    else:
        print("   [SKIP] Skipping go_up test (no valid parent path)")
    
    print("\n[PASS] TEST 6: Go up functionality works correctly")


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("TAB HISTORY MANAGER - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    tests = [
        test_basic_history,
        test_widget_id_stability,
        test_history_migration,
        test_error_handling,
        test_debug_methods,
        test_go_up,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] TEST FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n[ERROR] TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("="*70)
    
    if failed == 0:
        print("\n[SUCCESS] ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n[WARNING] {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    # Create QApplication (required for QWidget)
    app = QApplication(sys.argv)
    
    # Run tests
    exit_code = run_all_tests()
    
    sys.exit(exit_code)

