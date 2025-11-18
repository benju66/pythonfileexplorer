namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Priority level for refresh requests.
/// Determines debouncing behavior, execution order, and cancellation rules.
/// </summary>
public enum RefreshPriority
{
    /// <summary>
    /// Low priority - heavily debounced, can be cancelled by higher priority requests.
    /// Used for FileSystemWatcher events that may fire rapidly.
    /// Debounce delay: ~200ms
    /// </summary>
    Low,
    
    /// <summary>
    /// Normal priority - moderately debounced, not cancelled by Low priority.
    /// Used for FileOperationCompleted events and most programmatic refreshes.
    /// Debounce delay: ~100ms
    /// </summary>
    Normal,
    
    /// <summary>
    /// High priority - no debouncing, executes immediately.
    /// Used for user-initiated actions (drag/drop, refresh button).
    /// Debounce delay: 0ms (immediate)
    /// </summary>
    High
}

