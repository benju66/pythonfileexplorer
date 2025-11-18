using EnhancedFileExplorer.Core.Interfaces;

namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Event published when a refresh operation completes.
/// Subscribers can use this for logging, analytics, or UI feedback.
/// </summary>
public class RefreshCompletedEvent : IEvent
{
    /// <summary>
    /// Directory path that was refreshed.
    /// </summary>
    public string Path { get; }
    
    /// <summary>
    /// Source that originally triggered the refresh.
    /// </summary>
    public RefreshSource Source { get; }
    
    /// <summary>
    /// Whether the refresh completed successfully.
    /// </summary>
    public bool IsSuccess { get; }
    
    /// <summary>
    /// Error message if refresh failed, null otherwise.
    /// </summary>
    public string? ErrorMessage { get; }
    
    /// <summary>
    /// Timestamp when refresh completed.
    /// </summary>
    public DateTime Timestamp { get; }
    
    /// <summary>
    /// Request ID that corresponds to the original RefreshRequest.
    /// Used for correlation and tracking.
    /// </summary>
    public Guid RequestId { get; }
    
    /// <summary>
    /// Initializes a new instance of RefreshCompletedEvent.
    /// </summary>
    /// <param name="path">Directory path that was refreshed</param>
    /// <param name="source">Source that triggered the refresh</param>
    /// <param name="isSuccess">Whether refresh succeeded</param>
    /// <param name="errorMessage">Error message if failed</param>
    /// <param name="requestId">Request ID from original RefreshRequest</param>
    public RefreshCompletedEvent(
        string path,
        RefreshSource source,
        bool isSuccess,
        string? errorMessage = null,
        Guid requestId = default)
    {
        Path = path ?? throw new ArgumentNullException(nameof(path));
        Source = source;
        IsSuccess = isSuccess;
        ErrorMessage = errorMessage;
        Timestamp = DateTime.UtcNow;
        RequestId = requestId;
    }
}

