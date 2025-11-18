using EnhancedFileExplorer.Core.Interfaces;

namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Request to refresh a directory path.
/// Published to the Refresh Coordinator to queue a refresh operation.
/// </summary>
public class RefreshRequest : IEvent
{
    /// <summary>
    /// Directory path to refresh. Must be a full, normalized path.
    /// </summary>
    public string Path { get; }
    
    /// <summary>
    /// Source that triggered the refresh request.
    /// Used for logging, analytics, and priority determination.
    /// </summary>
    public RefreshSource Source { get; }
    
    /// <summary>
    /// Priority level for this refresh request.
    /// Determines debouncing behavior and execution order.
    /// </summary>
    public RefreshPriority Priority { get; }
    
    /// <summary>
    /// Optional context data for the refresh request.
    /// Examples: moved file paths, filter criteria, search parameters.
    /// </summary>
    public Dictionary<string, object>? Context { get; }
    
    /// <summary>
    /// Timestamp when request was created.
    /// Used for debouncing and queue management.
    /// </summary>
    public DateTime Timestamp { get; }
    
    /// <summary>
    /// Unique identifier for this request.
    /// Used for tracking and correlation with RefreshCompletedEvent.
    /// </summary>
    public Guid RequestId { get; }
    
    /// <summary>
    /// Initializes a new instance of RefreshRequest.
    /// </summary>
    /// <param name="path">Directory path to refresh</param>
    /// <param name="source">Source that triggered the refresh</param>
    /// <param name="priority">Priority level (defaults to Normal)</param>
    /// <param name="context">Optional context data</param>
    public RefreshRequest(
        string path,
        RefreshSource source,
        RefreshPriority priority = RefreshPriority.Normal,
        Dictionary<string, object>? context = null)
    {
        if (path == null)
            throw new ArgumentNullException(nameof(path));
        
        // Normalize path to ensure consistency
        try
        {
            Path = System.IO.Path.GetFullPath(path);
        }
        catch (Exception ex)
        {
            throw new ArgumentException($"Invalid path: {path}", nameof(path), ex);
        }
        
        Source = source;
        Priority = priority;
        Context = context;
        Timestamp = DateTime.UtcNow;
        RequestId = Guid.NewGuid();
    }
}

