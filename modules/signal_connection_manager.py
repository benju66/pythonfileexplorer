"""
Signal Connection Manager for Drag-and-Drop Tab Functionality

This module provides a manager to track and reconnect signal connections
when widgets are moved between tab widgets during drag-and-drop operations.

Design Pattern: Singleton (module-level instance)
"""

from typing import Optional, List, Tuple, Callable, Dict, Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget


class SignalConnection:
    """
    Represents a signal connection with metadata for reconnection.
    """
    
    def __init__(
        self,
        source: QObject,
        signal_name: str,
        target: QObject,
        slot: Callable,
        connection_type: str = "direct"
    ):
        """
        Initialize a signal connection record.
        
        Args:
            source: The object emitting the signal
            signal_name: Name of the signal (e.g., "location_changed")
            target: The object containing the slot
            slot: The callable slot function
            connection_type: Type of connection ("direct", "lambda", "method")
        """
        self.source = source
        self.signal_name = signal_name
        self.target = target
        self.slot = slot
        self.connection_type = connection_type
    
    def disconnect(self) -> bool:
        """
        Disconnect this signal connection.
        
        Returns:
            bool: True if disconnected successfully, False otherwise
        """
        try:
            signal = getattr(self.source, self.signal_name, None)
            if signal:
                signal.disconnect(self.slot)
                return True
        except (TypeError, RuntimeError) as e:
            # Connection may not exist or already disconnected
            print(f"[DEBUG] Failed to disconnect signal {self.signal_name}: {e}")
            return False
        return False
    
    def reconnect(self) -> bool:
        """
        Reconnect this signal connection.
        
        Returns:
            bool: True if reconnected successfully, False otherwise
        """
        try:
            signal = getattr(self.source, self.signal_name, None)
            if signal:
                signal.connect(self.slot)
                return True
        except (TypeError, RuntimeError) as e:
            print(f"[DEBUG] Failed to reconnect signal {self.signal_name}: {e}")
            return False
        return False


class SignalConnectionManager:
    """
    Manager for tracking and reconnecting signal connections during widget moves.
    
    This manager maintains a registry of signal connections for each widget,
    allowing them to be disconnected before a move and reconnected after the move
    with updated target objects.
    
    Usage:
        manager = SignalConnectionManager()
        manager.register_connection(widget, source, "signal_name", target, slot)
        manager.disconnect_all(widget)
        manager.reconnect_all(widget, new_target_container, new_target_tab_manager)
    """
    
    def __init__(self):
        """
        Initialize the signal connection manager.
        
        Internal structure:
            {
                widget_id: [
                    SignalConnection(...),
                    SignalConnection(...),
                    ...
                ]
            }
        """
        self._connections: Dict[int, List[SignalConnection]] = {}
    
    def register_connection(
        self,
        widget: QWidget,
        source: QObject,
        signal_name: str,
        target: QObject,
        slot: Callable,
        connection_type: str = "direct"
    ) -> bool:
        """
        Register a signal connection for a widget.
        
        Args:
            widget: The widget this connection is associated with
            source: The object emitting the signal
            signal_name: Name of the signal
            target: The object containing the slot
            slot: The callable slot function
            connection_type: Type of connection ("direct", "lambda", "method")
            
        Returns:
            bool: True if registration successful, False otherwise
        """
        if widget is None or source is None or target is None:
            return False
        
        widget_id = id(widget)
        
        if widget_id not in self._connections:
            self._connections[widget_id] = []
        
        connection = SignalConnection(
            source=source,
            signal_name=signal_name,
            target=target,
            slot=slot,
            connection_type=connection_type
        )
        
        self._connections[widget_id].append(connection)
        return True
    
    def disconnect_all(self, widget: QWidget) -> int:
        """
        Disconnect all registered signal connections for a widget.
        
        Args:
            widget: The widget whose connections should be disconnected
            
        Returns:
            int: Number of connections disconnected
        """
        if widget is None:
            return 0
        
        widget_id = id(widget)
        connections = self._connections.get(widget_id, [])
        
        disconnected_count = 0
        for connection in connections:
            if connection.disconnect():
                disconnected_count += 1
        
        return disconnected_count
    
    def reconnect_all(
        self,
        widget: QWidget,
        new_target_container: Optional[QWidget] = None,
        new_target_tab_manager: Optional[QWidget] = None
    ) -> int:
        """
        Reconnect all registered signal connections for a widget.
        
        This method attempts to reconnect connections, updating target objects
        if new targets are provided. The reconnection logic tries to match
        connection patterns and update targets accordingly.
        
        Args:
            widget: The widget whose connections should be reconnected
            new_target_container: Optional new container to connect to
            new_target_tab_manager: Optional new tab manager to connect to
            
        Returns:
            int: Number of connections reconnected
        """
        if widget is None:
            return 0
        
        widget_id = id(widget)
        connections = self._connections.get(widget_id, [])
        
        if not connections:
            return 0
        
        reconnected_count = 0
        
        for connection in connections:
            # Try to determine new target based on connection pattern
            new_target = connection.target
            
            # Update target if we have a new container/tab manager
            # This is a simplified approach - in practice, you may need
            # more sophisticated logic to match connection patterns
            if new_target_container is not None:
                # Check if old target was a container-related object
                if hasattr(connection.target, 'update_address_bar'):
                    new_target = new_target_container
                elif hasattr(connection.target, 'on_active_manager_changed'):
                    new_target = new_target_container
                elif hasattr(connection.target, 'handle_pin_request'):
                    new_target = new_target_container
            
            if new_target_tab_manager is not None:
                # Check if old target was a tab manager-related object
                if hasattr(connection.target, 'handle_file_tree_clicked'):
                    new_target = new_target_tab_manager
                elif hasattr(connection.target, 'handle_context_menu_action'):
                    new_target = new_target_tab_manager
            
            # Update connection target
            connection.target = new_target
            
            # Reconnect
            if connection.reconnect():
                reconnected_count += 1
        
        return reconnected_count
    
    def get_connections(self, widget: QWidget) -> List[SignalConnection]:
        """
        Get all registered connections for a widget.
        
        Args:
            widget: The widget to get connections for
            
        Returns:
            list[SignalConnection]: List of signal connections
        """
        if widget is None:
            return []
        
        widget_id = id(widget)
        return self._connections.get(widget_id, []).copy()
    
    def unregister_widget(self, widget: QWidget) -> bool:
        """
        Unregister all connections for a widget.
        
        This disconnects all connections and removes them from tracking.
        
        Args:
            widget: The widget to unregister
            
        Returns:
            bool: True if unregistered, False if not found
        """
        if widget is None:
            return False
        
        widget_id = id(widget)
        if widget_id in self._connections:
            # Disconnect all connections
            self.disconnect_all(widget)
            # Remove from registry
            del self._connections[widget_id]
            return True
        
        return False
    
    def clear(self) -> None:
        """
        Clear all registered connections.
        
        Use with caution - this disconnects all tracked connections.
        """
        # Disconnect all connections before clearing
        for widget_id in list(self._connections.keys()):
            connections = self._connections[widget_id]
            for connection in connections:
                connection.disconnect()
        
        self._connections.clear()
    
    def get_registry_size(self) -> int:
        """
        Get the number of widgets with registered connections.
        
        Returns:
            int: Number of widgets with connections
        """
        return len(self._connections)
    
    def cleanup_stale_entries(self) -> int:
        """
        Remove entries for widgets that have been deleted.
        
        Returns:
            int: Number of stale entries removed
        """
        stale_ids = []
        for widget_id, connections in self._connections.items():
            # Check if any connection has a deleted source or target
            is_stale = False
            for connection in connections:
                if connection.source is None or connection.target is None:
                    is_stale = True
                    break
            
            if is_stale:
                stale_ids.append(widget_id)
        
        for widget_id in stale_ids:
            # Disconnect before removing
            connections = self._connections[widget_id]
            for connection in connections:
                connection.disconnect()
            del self._connections[widget_id]
        
        return len(stale_ids)


# Module-level singleton instance
_manager_instance: Optional[SignalConnectionManager] = None


def get_signal_connection_manager() -> SignalConnectionManager:
    """
    Get the global signal connection manager instance.
    
    Returns:
        SignalConnectionManager: The singleton manager instance
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = SignalConnectionManager()
    return _manager_instance

