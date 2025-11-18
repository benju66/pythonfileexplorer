namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Source that triggered a refresh request.
/// Used to categorize refresh requests for logging, analytics, and priority determination.
/// </summary>
public enum RefreshSource
{
    /// <summary>
    /// FileSystemWatcher detected a file system change.
    /// Typically low priority, heavily debounced.
    /// </summary>
    FileSystemWatcher,
    
    /// <summary>
    /// File operation completed (copy, move, delete, rename, create).
    /// Normal priority, moderately debounced.
    /// </summary>
    FileOperationCompleted,
    
    /// <summary>
    /// Manual drag/drop operation within the application.
    /// High priority, no debouncing.
    /// </summary>
    ManualDragDrop,
    
    /// <summary>
    /// External drag/drop from outside the application.
    /// High priority, no debouncing.
    /// </summary>
    ExternalDragDrop,
    
    /// <summary>
    /// User clicked refresh button or pressed F5.
    /// High priority, no debouncing.
    /// </summary>
    UserRefresh,
    
    /// <summary>
    /// Search results changed.
    /// Normal priority, moderately debounced.
    /// </summary>
    SearchResults,
    
    /// <summary>
    /// Filter changed (e.g., file type filter, date filter).
    /// Normal priority, moderately debounced.
    /// </summary>
    FilterChanged,
    
    /// <summary>
    /// Programmatic refresh (e.g., after undo/redo, batch operations).
    /// Priority depends on context.
    /// </summary>
    Programmatic
}

