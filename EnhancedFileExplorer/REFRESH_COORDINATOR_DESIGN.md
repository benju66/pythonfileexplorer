# Refresh Coordinator Service - Architecture Design

**Date:** January 2025  
**Status:** Design Document  
**Purpose:** Centralized, scalable refresh coordination for file tree updates

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Interfaces](#core-interfaces)
4. [Event System](#event-system)
5. [Implementation Details](#implementation-details)
6. [Integration Points](#integration-points)
7. [Migration Strategy](#migration-strategy)
8. [Usage Examples](#usage-examples)
9. [Performance Considerations](#performance-considerations)

---

## Overview

### Problem Statement

Currently, file tree refreshes are triggered from multiple sources:
- **FileSystemWatcher** events (rapid-fire, needs debouncing)
- **FileOperationCompleted** events (after copy/move/delete)
- **Manual drag/drop** operations (immediate, no debouncing)
- **User refresh button** (immediate)
- **Future:** External drag/drop, search results, filtered views

**Current Issues:**
- Refresh logic scattered across `FileTreeView` and `MainWindow`
- Inconsistent debouncing (broken logic)
- Silent failures when ViewModel not in cache
- No prioritization (all refreshes treated equally)
- Hard to extend for new refresh sources

### Solution

A centralized **Refresh Coordinator Service** that:
- **Queues** refresh requests from all sources
- **Debounces** FileSystemWatcher events intelligently
- **Prioritizes** user-initiated actions over background events
- **Batches** multiple rapid requests efficiently
- **Extends** easily for new refresh sources
- **Preserves** UI state (expansion, selection, scroll position)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Refresh Coordinator Service                   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Refresh Request Queue (per path)                  │  │
│  │  ┌────────────────────────────────────────────────────┐   │  │
│  │  │  Priority Queue:                                   │   │  │
│  │  │  - High: Manual, DragDrop                         │   │  │
│  │  │  - Normal: FileOperationCompleted                 │   │  │
│  │  │  - Low: FileSystemWatcher                         │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  │                                                           │  │
│  │  ┌────────────────────────────────────────────────────┐   │  │
│  │  │  Debouncing Logic:                                  │   │  │
│  │  │  - Skip debounce for High priority                 │   │  │
│  │  │  - Debounce Low priority (100ms)                   │   │  │
│  │  │  - Cancel older requests when new arrives          │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                          ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │         Refresh Executor                                  │  │
│  │  - Finds target FileTreeView(s)                          │  │
│  │  - Executes incremental refresh                          │  │
│  │  - Preserves UI state                                    │  │
│  │  - Handles errors gracefully                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         ↑                    ↑                    ↑
    FileSystemWatcher  FileOperation  Manual/External
```

---

## Core Interfaces

### IRefreshCoordinator

```csharp
namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Coordinates file tree refresh operations from multiple sources.
/// </summary>
public interface IRefreshCoordinator
{
    /// <summary>
    /// Requests a refresh for a specific directory path.
    /// </summary>
    /// <param name="request">Refresh request with path, source, and priority</param>
    /// <returns>Task that completes when refresh is queued (not when it executes)</returns>
    Task RequestRefreshAsync(RefreshRequest request);
    
    /// <summary>
    /// Requests immediate refresh (bypasses queue, no debouncing).
    /// Use sparingly for critical user actions.
    /// </summary>
    Task RequestImmediateRefreshAsync(string path, RefreshSource source);
    
    /// <summary>
    /// Registers a FileTreeView to receive refresh notifications.
    /// </summary>
    void RegisterTreeView(IFileTreeRefreshTarget treeView);
    
    /// <summary>
    /// Unregisters a FileTreeView.
    /// </summary>
    void UnregisterTreeView(IFileTreeRefreshTarget treeView);
    
    /// <summary>
    /// Gets the number of pending refresh requests for a path.
    /// </summary>
    int GetPendingRefreshCount(string path);
}
```

### IFileTreeRefreshTarget

```csharp
namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Interface for components that can receive refresh notifications.
/// </summary>
public interface IFileTreeRefreshTarget
{
    /// <summary>
    /// Gets the current root path of this tree view.
    /// </summary>
    string? CurrentPath { get; }
    
    /// <summary>
    /// Gets a unique identifier for this tree view instance.
    /// </summary>
    string InstanceId { get; }
    
    /// <summary>
    /// Refreshes the specified directory path incrementally.
    /// </summary>
    /// <param name="path">Directory path to refresh</param>
    /// <param name="preserveState">Whether to preserve expansion/selection/scroll state</param>
    Task RefreshDirectoryAsync(string path, bool preserveState = true);
    
    /// <summary>
    /// Checks if this tree view should receive refresh for the given path.
    /// </summary>
    bool ShouldRefresh(string path);
}
```

---

## Event System

### RefreshRequest

```csharp
namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Request to refresh a directory path.
/// </summary>
public class RefreshRequest : IEvent
{
    /// <summary>
    /// Directory path to refresh.
    /// </summary>
    public string Path { get; }
    
    /// <summary>
    /// Source that triggered the refresh.
    /// </summary>
    public RefreshSource Source { get; }
    
    /// <summary>
    /// Priority level for this refresh.
    /// </summary>
    public RefreshPriority Priority { get; }
    
    /// <summary>
    /// Optional context data (e.g., moved file paths for source refresh).
    /// </summary>
    public Dictionary<string, object>? Context { get; }
    
    /// <summary>
    /// Timestamp when request was created.
    /// </summary>
    public DateTime Timestamp { get; }
    
    /// <summary>
    /// Unique identifier for this request.
    /// </summary>
    public Guid RequestId { get; }
    
    public RefreshRequest(
        string path,
        RefreshSource source,
        RefreshPriority priority = RefreshPriority.Normal,
        Dictionary<string, object>? context = null)
    {
        Path = path ?? throw new ArgumentNullException(nameof(path));
        Source = source;
        Priority = priority;
        Context = context;
        Timestamp = DateTime.UtcNow;
        RequestId = Guid.NewGuid();
    }
}
```

### RefreshSource Enum

```csharp
namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Source that triggered a refresh request.
/// </summary>
public enum RefreshSource
{
    /// <summary>
    /// FileSystemWatcher detected a change.
    /// </summary>
    FileSystemWatcher,
    
    /// <summary>
    /// File operation completed (copy, move, delete, rename).
    /// </summary>
    FileOperationCompleted,
    
    /// <summary>
    /// Manual drag/drop operation within the application.
    /// </summary>
    ManualDragDrop,
    
    /// <summary>
    /// External drag/drop from outside the application.
    /// </summary>
    ExternalDragDrop,
    
    /// <summary>
    /// User clicked refresh button.
    /// </summary>
    UserRefresh,
    
    /// <summary>
    /// Search results changed.
    /// </summary>
    SearchResults,
    
    /// <summary>
    /// Filter changed.
    /// </summary>
    FilterChanged,
    
    /// <summary>
    /// Programmatic refresh (e.g., after undo/redo).
    /// </summary>
    Programmatic
}
```

### RefreshPriority Enum

```csharp
namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Priority level for refresh requests.
/// </summary>
public enum RefreshPriority
{
    /// <summary>
    /// Low priority - debounced, can be cancelled by higher priority requests.
    /// Used for FileSystemWatcher events.
    /// </summary>
    Low,
    
    /// <summary>
    /// Normal priority - debounced, but not cancelled by Low priority.
    /// Used for FileOperationCompleted events.
    /// </summary>
    Normal,
    
    /// <summary>
    /// High priority - no debouncing, executes immediately.
    /// Used for user-initiated actions (drag/drop, refresh button).
    /// </summary>
    High
}
```

### RefreshCompleted Event

```csharp
namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Event published when a refresh operation completes.
/// </summary>
public class RefreshCompletedEvent : IEvent
{
    public string Path { get; }
    public RefreshSource Source { get; }
    public bool IsSuccess { get; }
    public string? ErrorMessage { get; }
    public DateTime Timestamp { get; }
    public Guid RequestId { get; }
    
    public RefreshCompletedEvent(
        string path,
        RefreshSource source,
        bool isSuccess,
        string? errorMessage = null,
        Guid requestId = default)
    {
        Path = path;
        Source = source;
        IsSuccess = isSuccess;
        ErrorMessage = errorMessage;
        Timestamp = DateTime.UtcNow;
        RequestId = requestId;
    }
}
```

---

## Implementation Details

### RefreshCoordinatorService

```csharp
namespace EnhancedFileExplorer.Services.Refresh;

public class RefreshCoordinatorService : IRefreshCoordinator, IDisposable
{
    private readonly ILogger<RefreshCoordinatorService> _logger;
    private readonly IEventAggregator _eventAggregator;
    private readonly ConcurrentDictionary<string, RefreshQueue> _queues;
    private readonly ConcurrentDictionary<string, IFileTreeRefreshTarget> _registeredTreeViews;
    private readonly SemaphoreSlim _queueSemaphore;
    private readonly CancellationTokenSource _cancellationTokenSource;
    private readonly Timer? _debounceTimer;
    
    // Configuration
    private readonly TimeSpan _debounceDelay = TimeSpan.FromMilliseconds(100);
    private readonly int _maxConcurrentRefreshes = 3;
    
    public RefreshCoordinatorService(
        ILogger<RefreshCoordinatorService> logger,
        IEventAggregator eventAggregator)
    {
        _logger = logger;
        _eventAggregator = eventAggregator;
        _queues = new ConcurrentDictionary<string, RefreshQueue>(StringComparer.OrdinalIgnoreCase);
        _registeredTreeViews = new ConcurrentDictionary<string, IFileTreeRefreshTarget>();
        _queueSemaphore = new SemaphoreSlim(_maxConcurrentRefreshes);
        _cancellationTokenSource = new CancellationTokenSource();
        
        // Start background processing
        _ = Task.Run(ProcessRefreshQueuesAsync, _cancellationTokenSource.Token);
    }
    
    public Task RequestRefreshAsync(RefreshRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Path))
            return Task.CompletedTask;
        
        var normalizedPath = Path.GetFullPath(request.Path);
        var queue = _queues.GetOrAdd(normalizedPath, _ => new RefreshQueue(normalizedPath));
        
        lock (queue)
        {
            // For High priority, cancel all pending Low/Normal priority requests
            if (request.Priority == RefreshPriority.High)
            {
                queue.CancelLowerPriority(request.Priority);
            }
            
            // Add new request
            queue.Enqueue(request);
        }
        
        _logger.LogDebug("Queued refresh request: {Path}, Source: {Source}, Priority: {Priority}",
            normalizedPath, request.Source, request.Priority);
        
        return Task.CompletedTask;
    }
    
    public async Task RequestImmediateRefreshAsync(string path, RefreshSource source)
    {
        var request = new RefreshRequest(path, source, RefreshPriority.High);
        await RequestRefreshAsync(request);
        
        // Wait briefly for high-priority requests to process
        await Task.Delay(50);
    }
    
    public void RegisterTreeView(IFileTreeRefreshTarget treeView)
    {
        if (treeView == null)
            throw new ArgumentNullException(nameof(treeView));
        
        _registeredTreeViews.TryAdd(treeView.InstanceId, treeView);
        _logger.LogDebug("Registered tree view: {InstanceId}, Path: {Path}",
            treeView.InstanceId, treeView.CurrentPath);
    }
    
    public void UnregisterTreeView(IFileTreeRefreshTarget treeView)
    {
        if (treeView == null)
            return;
        
        _registeredTreeViews.TryRemove(treeView.InstanceId, out _);
        _logger.LogDebug("Unregistered tree view: {InstanceId}", treeView.InstanceId);
    }
    
    public int GetPendingRefreshCount(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
            return 0;
        
        var normalizedPath = Path.GetFullPath(path);
        if (_queues.TryGetValue(normalizedPath, out var queue))
        {
            lock (queue)
            {
                return queue.Count;
            }
        }
        
        return 0;
    }
    
    private async Task ProcessRefreshQueuesAsync()
    {
        while (!_cancellationTokenSource.Token.IsCancellationRequested)
        {
            try
            {
                await ProcessQueuesAsync();
                await Task.Delay(50, _cancellationTokenSource.Token); // Check every 50ms
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error processing refresh queues");
            }
        }
    }
    
    private async Task ProcessQueuesAsync()
    {
        var highPriorityRequests = new List<RefreshRequest>();
        var normalPriorityRequests = new List<RefreshRequest>();
        var lowPriorityRequests = new List<RefreshRequest>();
        
        // Collect requests by priority
        foreach (var kvp in _queues)
        {
            var queue = kvp.Value;
            RefreshRequest? request;
            
            lock (queue)
            {
                request = queue.DequeueReady();
            }
            
            if (request != null)
            {
                switch (request.Priority)
                {
                    case RefreshPriority.High:
                        highPriorityRequests.Add(request);
                        break;
                    case RefreshPriority.Normal:
                        normalPriorityRequests.Add(request);
                        break;
                    case RefreshPriority.Low:
                        lowPriorityRequests.Add(request);
                        break;
                }
            }
        }
        
        // Process High priority immediately (no debouncing)
        foreach (var request in highPriorityRequests)
        {
            _ = Task.Run(() => ExecuteRefreshAsync(request), _cancellationTokenSource.Token);
        }
        
        // Process Normal priority (debounced)
        foreach (var request in normalPriorityRequests)
        {
            _ = Task.Run(async () =>
            {
                await Task.Delay(_debounceDelay, _cancellationTokenSource.Token);
                await ExecuteRefreshAsync(request);
            }, _cancellationTokenSource.Token);
        }
        
        // Process Low priority (debounced, longer delay)
        foreach (var request in lowPriorityRequests)
        {
            _ = Task.Run(async () =>
            {
                await Task.Delay(_debounceDelay * 2, _cancellationTokenSource.Token);
                await ExecuteRefreshAsync(request);
            }, _cancellationTokenSource.Token);
        }
    }
    
    private async Task ExecuteRefreshAsync(RefreshRequest request)
    {
        await _queueSemaphore.WaitAsync(_cancellationTokenSource.Token);
        
        try
        {
            var targetTreeViews = _registeredTreeViews.Values
                .Where(tv => tv.ShouldRefresh(request.Path))
                .ToList();
            
            if (targetTreeViews.Count == 0)
            {
                _logger.LogDebug("No tree views found for path: {Path}", request.Path);
                return;
            }
            
            var tasks = targetTreeViews.Select(async tv =>
            {
                try
                {
                    await tv.RefreshDirectoryAsync(request.Path, preserveState: true);
                    _logger.LogDebug("Refreshed tree view: {InstanceId}, Path: {Path}",
                        tv.InstanceId, request.Path);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error refreshing tree view: {InstanceId}, Path: {Path}",
                        tv.InstanceId, request.Path);
                }
            });
            
            await Task.WhenAll(tasks);
            
            // Publish completion event
            _eventAggregator.Publish(new RefreshCompletedEvent(
                request.Path,
                request.Source,
                isSuccess: true,
                requestId: request.RequestId));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error executing refresh: {Path}", request.Path);
            
            _eventAggregator.Publish(new RefreshCompletedEvent(
                request.Path,
                request.Source,
                isSuccess: false,
                errorMessage: ex.Message,
                requestId: request.RequestId));
        }
        finally
        {
            _queueSemaphore.Release();
        }
    }
    
    public void Dispose()
    {
        _cancellationTokenSource.Cancel();
        _queueSemaphore?.Dispose();
        _cancellationTokenSource?.Dispose();
        _debounceTimer?.Dispose();
    }
}
```

### RefreshQueue

```csharp
namespace EnhancedFileExplorer.Services.Refresh;

internal class RefreshQueue
{
    private readonly string _path;
    private readonly Queue<RefreshRequest> _requests;
    private DateTime _lastDequeueTime;
    private readonly TimeSpan _minDequeueInterval = TimeSpan.FromMilliseconds(100);
    
    public RefreshQueue(string path)
    {
        _path = path;
        _requests = new Queue<RefreshRequest>();
        _lastDequeueTime = DateTime.MinValue;
    }
    
    public int Count => _requests.Count;
    
    public void Enqueue(RefreshRequest request)
    {
        _requests.Enqueue(request);
    }
    
    public RefreshRequest? DequeueReady()
    {
        if (_requests.Count == 0)
            return null;
        
        // Check if enough time has passed since last dequeue
        var timeSinceLastDequeue = DateTime.UtcNow - _lastDequeueTime;
        if (timeSinceLastDequeue < _minDequeueInterval && _requests.Count > 0)
        {
            // Keep the highest priority request, remove others
            var highestPriority = _requests.Max(r => r.Priority);
            while (_requests.Count > 0 && _requests.Peek().Priority < highestPriority)
            {
                _requests.Dequeue();
            }
            
            if (_requests.Count > 0 && _requests.Peek().Priority == highestPriority)
            {
                _lastDequeueTime = DateTime.UtcNow;
                return _requests.Dequeue();
            }
        }
        else
        {
            _lastDequeueTime = DateTime.UtcNow;
            return _requests.Dequeue();
        }
        
        return null;
    }
    
    public void CancelLowerPriority(RefreshPriority priority)
    {
        var requestsToKeep = _requests.Where(r => r.Priority >= priority).ToList();
        _requests.Clear();
        foreach (var request in requestsToKeep)
        {
            _requests.Enqueue(request);
        }
    }
}
```

---

## Integration Points

### 1. FileTreeView Integration

```csharp
// FileTreeView.xaml.cs

public partial class FileTreeView : UserControl, IFileTreeRefreshTarget
{
    private IRefreshCoordinator? _refreshCoordinator;
    
    public string? CurrentPath => _currentPath;
    public string InstanceId { get; } = Guid.NewGuid().ToString();
    
    public void Initialize(
        IFileSystemService fileSystemService,
        IRefreshCoordinator? refreshCoordinator = null, // NEW
        // ... other parameters
    )
    {
        _fileSystemService = fileSystemService;
        _refreshCoordinator = refreshCoordinator;
        
        // Register with coordinator
        _refreshCoordinator?.RegisterTreeView(this);
        
        // ... rest of initialization
    }
    
    public bool ShouldRefresh(string path)
    {
        if (string.IsNullOrWhiteSpace(_currentPath))
            return false;
        
        // Refresh if path matches current path or is a parent
        return _currentPath.Equals(path, StringComparison.OrdinalIgnoreCase) ||
               _currentPath.StartsWith(path, StringComparison.OrdinalIgnoreCase);
    }
    
    public async Task RefreshDirectoryAsync(string path, bool preserveState = true)
    {
        // Existing RefreshDirectoryAsync implementation
        // This is now called by the coordinator
    }
    
    protected override void OnUnloaded(RoutedEventArgs e)
    {
        // Unregister from coordinator
        _refreshCoordinator?.UnregisterTreeView(this);
        base.OnUnloaded(e);
    }
}
```

### 2. MainWindow Integration

```csharp
// MainWindow.xaml.cs

public partial class MainWindow : Window
{
    private readonly IRefreshCoordinator _refreshCoordinator;
    
    public MainWindow(
        // ... existing parameters
        IRefreshCoordinator refreshCoordinator)
    {
        _refreshCoordinator = refreshCoordinator;
        
        // Subscribe to FileSystemWatcher events
        _fileSystemWatcherService.DirectoryChanged += OnFileSystemChanged;
        _fileSystemWatcherService.FileChanged += OnFileSystemChanged;
        _fileSystemWatcherService.Renamed += OnFileSystemRenamed;
        
        // Subscribe to FileOperationCompleted events
        _undoRedoManager.FileOperationCompleted += OnFileOperationCompleted;
    }
    
    private void OnFileSystemChanged(object? sender, FileSystemChangedEventArgs e)
    {
        var directoryPath = Path.GetDirectoryName(e.FullPath);
        if (directoryPath != null)
        {
            var request = new RefreshRequest(
                directoryPath,
                RefreshSource.FileSystemWatcher,
                RefreshPriority.Low);
            
            _refreshCoordinator.RequestRefreshAsync(request);
        }
    }
    
    private void OnFileOperationCompleted(object? sender, FileOperationCompletedEventArgs e)
    {
        if (!e.IsSuccess)
            return;
        
        var request = new RefreshRequest(
            e.ParentPath ?? string.Empty,
            RefreshSource.FileOperationCompleted,
            RefreshPriority.Normal);
        
        _refreshCoordinator.RequestRefreshAsync(request);
    }
}
```

### 3. Drag/Drop Integration

```csharp
// FileTreeView.xaml.cs - FileTree_Drop method

private async void FileTree_Drop(object sender, DragEventArgs e)
{
    // ... existing validation logic ...
    
    try
    {
        var result = await _dragDropHandler!.ExecuteDropAsync(context, cancellationToken: default);
        
        if (result.IsSuccess)
        {
            e.Effects = wpfEffect;
            e.Handled = true;
            
            // Request refresh via coordinator (High priority, immediate)
            var targetRequest = new RefreshRequest(
                targetPath,
                RefreshSource.ManualDragDrop,
                RefreshPriority.High);
            
            await _refreshCoordinator!.RequestRefreshAsync(targetRequest);
            
            // If move operation, also refresh source directory
            if (requestedEffect == DragDropEffect.Move)
            {
                var sourcePath = Path.GetDirectoryName(dragData.Value.FilePaths.First());
                if (!string.IsNullOrWhiteSpace(sourcePath))
                {
                    var sourceRequest = new RefreshRequest(
                        sourcePath,
                        RefreshSource.ManualDragDrop,
                        RefreshPriority.High);
                    
                    await _refreshCoordinator.RequestRefreshAsync(sourceRequest);
                }
            }
        }
    }
    catch (Exception ex)
    {
        // ... error handling ...
    }
}
```

### 4. Bootstrapper Registration

```csharp
// Bootstrapper.cs

public static IServiceProvider ConfigureServices()
{
    var services = new ServiceCollection();
    
    // ... existing registrations ...
    
    // Register Refresh Coordinator (Singleton - app-wide coordination)
    services.AddSingleton<IRefreshCoordinator, RefreshCoordinatorService>();
    
    // ... rest of configuration ...
}
```

---

## Migration Strategy

### Phase 1: Add Coordinator (Non-Breaking)

1. **Add interfaces and events** to Core project
2. **Implement RefreshCoordinatorService** in Services project
3. **Register in Bootstrapper** as singleton
4. **Make FileTreeView implement IFileTreeRefreshTarget**
5. **Keep existing refresh methods** (backward compatible)

### Phase 2: Migrate Sources Gradually

1. **Migrate FileSystemWatcher** first (lowest risk)
2. **Migrate FileOperationCompleted** next
3. **Migrate drag/drop** last (most critical)

### Phase 3: Remove Old Code

1. **Remove debouncing logic** from FileTreeView
2. **Remove refresh coordination** from MainWindow
3. **Remove _isDragDropInProgress** flag (coordinator handles it)

### Migration Helper: Dual Mode

During migration, support both old and new approaches:

```csharp
// FileTreeView.xaml.cs

public async Task RefreshDirectoryAsync(string path, bool preserveState = true)
{
    // If coordinator is available, use it
    if (_refreshCoordinator != null)
    {
        // Coordinator will call this method back
        // Just ensure we're registered
        return;
    }
    
    // Fallback to old implementation during migration
    await RefreshDirectoryAsyncLegacy(path, preserveState);
}
```

---

## Usage Examples

### Example 1: User Refresh Button

```csharp
private async void RefreshButton_Click(object sender, RoutedEventArgs e)
{
    var activeTab = _tabManagerService.GetActiveTab();
    if (activeTab?.CurrentPath != null)
    {
        var request = new RefreshRequest(
            activeTab.CurrentPath,
            RefreshSource.UserRefresh,
            RefreshPriority.High);
        
        await _refreshCoordinator.RequestRefreshAsync(request);
    }
}
```

### Example 2: External Drag/Drop (Future)

```csharp
private async void FileTree_DropExternal(object sender, DragEventArgs e)
{
    // ... handle external drop ...
    
    var request = new RefreshRequest(
        targetPath,
        RefreshSource.ExternalDragDrop,
        RefreshPriority.High);
    
    await _refreshCoordinator.RequestRefreshAsync(request);
}
```

### Example 3: Search Results Changed

```csharp
private void OnSearchResultsChanged(object? sender, SearchResultsChangedEventArgs e)
{
    var request = new RefreshRequest(
        e.SearchPath,
        RefreshSource.SearchResults,
        RefreshPriority.Normal,
        context: new Dictionary<string, object> { ["Filter"] = e.Filter });
    
    _refreshCoordinator.RequestRefreshAsync(request);
}
```

---

## Performance Considerations

### 1. Concurrent Refresh Limits

- **Max concurrent refreshes:** 3 (configurable)
- **Prevents UI freezing** during bulk operations
- **Uses SemaphoreSlim** for efficient waiting

### 2. Queue Management

- **Per-path queues** prevent cross-path interference
- **Priority-based cancellation** prevents redundant work
- **Automatic cleanup** of empty queues

### 3. Debouncing Strategy

- **High priority:** No debounce (immediate)
- **Normal priority:** 100ms debounce
- **Low priority:** 200ms debounce
- **Configurable** via constructor parameters

### 4. Memory Management

- **Weak references** for tree views (future optimization)
- **Queue size limits** (prevent memory leaks)
- **Automatic disposal** on service shutdown

---

## Testing Strategy

### Unit Tests

1. **RefreshCoordinatorService**
   - Queue management
   - Priority handling
   - Debouncing logic
   - Error handling

2. **RefreshQueue**
   - Enqueue/dequeue
   - Priority cancellation
   - Timing logic

### Integration Tests

1. **FileSystemWatcher → Coordinator → FileTreeView**
2. **Drag/Drop → Coordinator → FileTreeView**
3. **Multiple tree views** receiving same refresh

### Performance Tests

1. **Rapid-fire FileSystemWatcher events**
2. **Concurrent refresh requests**
3. **Memory usage** under load

---

## Future Enhancements

1. **Refresh Batching:** Combine multiple paths into single refresh
2. **Refresh Scheduling:** Schedule refreshes for off-peak times
3. **Refresh Analytics:** Track refresh frequency and performance
4. **Refresh Policies:** Per-source refresh policies (e.g., ignore certain paths)
5. **Refresh Notifications:** UI feedback for refresh progress

---

## Summary

The Refresh Coordinator Service provides:
- ✅ **Centralized** refresh management
- ✅ **Scalable** architecture for future sources
- ✅ **Intelligent** debouncing and prioritization
- ✅ **Maintainable** separation of concerns
- ✅ **Testable** isolated components
- ✅ **Extensible** for new refresh sources

This design eliminates the current issues while providing a solid foundation for future enhancements.

