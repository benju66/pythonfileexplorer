"""
Widget Registry for Drag-and-Drop Tab Functionality

This module provides a registry to track widgets and their relationships
during drag-and-drop operations. It maps widget IDs to widget references
and their parent tab widgets, enabling reliable widget lookup during drag operations.

Design Pattern: Singleton (module-level instance)
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import QWidget, QTabWidget


class WidgetRegistry:
    """
    Registry for tracking widgets and their parent relationships during drag operations.
    
    This registry maintains a mapping of widget IDs to widget metadata, including
    the parent QTabWidget that contains the widget. This enables reliable widget
    lookup and parent relationship tracking during drag-and-drop operations.
    
    Usage:
        registry = WidgetRegistry()
        registry.register_widget(widget, parent_tab_widget)
        parent = registry.get_parent_tab_widget(widget)
        registry.unregister_widget(widget)
    """
    
    def __init__(self):
        """
        Initialize the widget registry.
        
        Internal structure:
            {
                widget_id: {
                    'widget': QWidget,
                    'parent_tab_widget': QTabWidget,
                    'registered_at': float (timestamp)
                }
            }
        """
        self._registry: Dict[int, Dict[str, Any]] = {}
    
    def register_widget(self, widget: QWidget, parent_tab_widget: QTabWidget) -> bool:
        """
        Register a widget with its parent tab widget.
        
        Args:
            widget: The widget to register (typically a FileTree container widget)
            parent_tab_widget: The QTabWidget that contains this widget
            
        Returns:
            bool: True if registration successful, False otherwise
            
        Raises:
            ValueError: If widget or parent_tab_widget is None
        """
        if widget is None:
            raise ValueError("Widget cannot be None")
        if parent_tab_widget is None:
            raise ValueError("Parent tab widget cannot be None")
        
        widget_id = id(widget)
        
        # Unregister if already registered (update registration)
        if widget_id in self._registry:
            self.unregister_widget(widget)
        
        import time
        self._registry[widget_id] = {
            'widget': widget,
            'parent_tab_widget': parent_tab_widget,
            'registered_at': time.time()
        }
        
        return True
    
    def get_widget(self, widget_id: int) -> Optional[QWidget]:
        """
        Get a widget by its ID.
        
        Args:
            widget_id: The widget ID (from id(widget))
            
        Returns:
            QWidget: The widget if found, None otherwise
        """
        entry = self._registry.get(widget_id)
        if entry:
            widget = entry['widget']
            # Verify widget still exists (hasn't been deleted)
            if widget is not None:
                return widget
            else:
                # Clean up stale entry
                self._registry.pop(widget_id, None)
        return None
    
    def get_parent_tab_widget(self, widget: QWidget) -> Optional[QTabWidget]:
        """
        Get the parent QTabWidget for a registered widget.
        
        Args:
            widget: The widget to look up
            
        Returns:
            QTabWidget: The parent tab widget if found, None otherwise
        """
        if widget is None:
            return None
        
        widget_id = id(widget)
        entry = self._registry.get(widget_id)
        
        if entry:
            parent = entry['parent_tab_widget']
            # Verify parent still exists
            if parent is not None:
                return parent
            else:
                # Clean up stale entry
                self._registry.pop(widget_id, None)
        
        return None
    
    def is_registered(self, widget: QWidget) -> bool:
        """
        Check if a widget is registered.
        
        Args:
            widget: The widget to check
            
        Returns:
            bool: True if widget is registered, False otherwise
        """
        if widget is None:
            return False
        
        widget_id = id(widget)
        return widget_id in self._registry
    
    def unregister_widget(self, widget: QWidget) -> bool:
        """
        Unregister a widget from the registry.
        
        Args:
            widget: The widget to unregister
            
        Returns:
            bool: True if unregistered, False if not found
        """
        if widget is None:
            return False
        
        widget_id = id(widget)
        if widget_id in self._registry:
            del self._registry[widget_id]
            return True
        
        return False
    
    def update_parent(self, widget: QWidget, new_parent_tab_widget: QTabWidget) -> bool:
        """
        Update the parent tab widget for a registered widget.
        
        This is useful when a widget is moved to a different tab widget.
        
        Args:
            widget: The widget to update
            new_parent_tab_widget: The new parent tab widget
            
        Returns:
            bool: True if update successful, False if widget not registered
        """
        if widget is None or new_parent_tab_widget is None:
            return False
        
        widget_id = id(widget)
        if widget_id in self._registry:
            self._registry[widget_id]['parent_tab_widget'] = new_parent_tab_widget
            return True
        
        return False
    
    def clear(self) -> None:
        """
        Clear all registrations from the registry.
        
        Use with caution - this removes all tracked widgets.
        """
        self._registry.clear()
    
    def get_registry_size(self) -> int:
        """
        Get the number of widgets currently registered.
        
        Returns:
            int: Number of registered widgets
        """
        return len(self._registry)
    
    def get_all_widgets(self) -> list[QWidget]:
        """
        Get all registered widgets.
        
        Returns:
            list[QWidget]: List of all registered widgets
        """
        widgets = []
        for entry in self._registry.values():
            widget = entry['widget']
            if widget is not None:
                widgets.append(widget)
        return widgets
    
    def cleanup_stale_entries(self) -> int:
        """
        Remove entries for widgets that have been deleted.
        
        This is a safety mechanism to prevent memory leaks from deleted widgets.
        
        Returns:
            int: Number of stale entries removed
        """
        stale_ids = []
        for widget_id, entry in self._registry.items():
            widget = entry.get('widget')
            parent = entry.get('parent_tab_widget')
            
            # Check if widget or parent has been deleted
            if widget is None or parent is None:
                stale_ids.append(widget_id)
        
        for widget_id in stale_ids:
            del self._registry[widget_id]
        
        return len(stale_ids)


# Module-level singleton instance
# This allows the registry to be accessed from anywhere in the application
_registry_instance: Optional[WidgetRegistry] = None


def get_widget_registry() -> WidgetRegistry:
    """
    Get the global widget registry instance.
    
    Returns:
        WidgetRegistry: The singleton registry instance
    """
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = WidgetRegistry()
    return _registry_instance

