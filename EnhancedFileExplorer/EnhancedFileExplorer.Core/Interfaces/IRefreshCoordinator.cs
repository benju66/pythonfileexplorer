namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Coordinates file tree refresh operations from multiple sources.
/// Provides centralized debouncing, prioritization, and batching of refresh requests.
/// </summary>
public interface IRefreshCoordinator
{
    /// <summary>
    /// Requests a refresh for a specific directory path.
    /// The refresh will be queued and processed according to priority and debouncing rules.
    /// </summary>
    /// <param name="request">Refresh request with path, source, and priority</param>
    /// <returns>Task that completes when refresh is queued (not when it executes)</returns>
    Task RequestRefreshAsync(Core.Events.RefreshRequest request);
    
    /// <summary>
    /// Requests immediate refresh (bypasses queue, no debouncing).
    /// Use sparingly for critical user actions that require instant feedback.
    /// </summary>
    /// <param name="path">Directory path to refresh</param>
    /// <param name="source">Source that triggered the refresh</param>
    Task RequestImmediateRefreshAsync(string path, Core.Events.RefreshSource source);
    
    /// <summary>
    /// Registers a FileTreeView to receive refresh notifications.
    /// The coordinator will call RefreshDirectoryAsync on registered views when their paths need refreshing.
    /// </summary>
    /// <param name="treeView">Tree view instance to register</param>
    void RegisterTreeView(IFileTreeRefreshTarget treeView);
    
    /// <summary>
    /// Unregisters a FileTreeView.
    /// Call this when a tree view is disposed or no longer needs refresh notifications.
    /// </summary>
    /// <param name="treeView">Tree view instance to unregister</param>
    void UnregisterTreeView(IFileTreeRefreshTarget treeView);
    
    /// <summary>
    /// Gets the number of pending refresh requests for a specific path.
    /// Useful for debugging and monitoring refresh queue status.
    /// </summary>
    /// <param name="path">Directory path to check</param>
    /// <returns>Number of pending refresh requests</returns>
    int GetPendingRefreshCount(string path);
}

