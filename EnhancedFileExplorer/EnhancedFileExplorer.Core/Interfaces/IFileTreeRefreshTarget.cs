namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Interface for components that can receive refresh notifications from the Refresh Coordinator.
/// FileTreeView implements this interface to participate in centralized refresh coordination.
/// </summary>
public interface IFileTreeRefreshTarget
{
    /// <summary>
    /// Gets the current root path of this tree view.
    /// Used by the coordinator to determine if this view should receive refresh notifications.
    /// </summary>
    string? CurrentPath { get; }
    
    /// <summary>
    /// Gets a unique identifier for this tree view instance.
    /// Used for registration/unregistration tracking.
    /// </summary>
    string InstanceId { get; }
    
    /// <summary>
    /// Refreshes the specified directory path incrementally.
    /// This method is called by the Refresh Coordinator when a refresh is needed.
    /// </summary>
    /// <param name="path">Directory path to refresh</param>
    /// <param name="preserveState">Whether to preserve expansion/selection/scroll state during refresh</param>
    /// <returns>Task that completes when refresh is finished</returns>
    Task RefreshDirectoryAsync(string path, bool preserveState = true);
    
    /// <summary>
    /// Checks if this tree view should receive refresh for the given path.
    /// Typically returns true if the path matches CurrentPath or is a parent directory.
    /// Paths should be normalized (full paths) before calling this method.
    /// </summary>
    /// <param name="path">Directory path to check (should be normalized)</param>
    /// <returns>True if this tree view should refresh for the given path</returns>
    bool ShouldRefresh(string path);
    
    /// <summary>
    /// Checks if the specified path is currently loaded in this tree view.
    /// Used to determine whether to use RefreshDirectoryAsync (incremental) or LoadDirectoryAsync (full).
    /// </summary>
    /// <param name="path">Directory path to check (should be normalized)</param>
    /// <returns>True if path is loaded (either current path or in cache)</returns>
    bool IsPathLoaded(string path);
    
    /// <summary>
    /// Loads a directory path with a full refresh (clears tree, rebuilds from scratch).
    /// Used for initial loads or when incremental refresh fails.
    /// </summary>
    /// <param name="path">Directory path to load (should be normalized)</param>
    /// <returns>Task that completes when load is finished</returns>
    Task LoadDirectoryAsync(string path);
}

