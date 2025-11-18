# Refresh Coordinator Service - Integration Example

This document shows how to integrate the Refresh Coordinator Service into the existing codebase.

## Quick Start Integration

### Step 1: Register Service in Bootstrapper

```csharp
// Bootstrapper.cs
using EnhancedFileExplorer.Services.Refresh;

public static IServiceProvider ConfigureServices()
{
    var services = new ServiceCollection();
    
    // ... existing registrations ...
    
    // Add Refresh Coordinator (Singleton - app-wide coordination)
    services.AddSingleton<IRefreshCoordinator, RefreshCoordinatorService>();
    
    // ... rest of configuration ...
}
```

### Step 2: Update FileTreeView to Implement IFileTreeRefreshTarget

```csharp
// FileTreeView.xaml.cs
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Events;

public partial class FileTreeView : UserControl, IFileTreeRefreshTarget
{
    private IRefreshCoordinator? _refreshCoordinator;
    
    // IFileTreeRefreshTarget implementation
    public string? CurrentPath => _currentPath;
    public string InstanceId { get; } = Guid.NewGuid().ToString();
    
    public bool ShouldRefresh(string path)
    {
        if (string.IsNullOrWhiteSpace(_currentPath))
            return false;
        
        // Refresh if path matches current path or is a parent
        return _currentPath.Equals(path, StringComparison.OrdinalIgnoreCase) ||
               _currentPath.StartsWith(path + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    }
    
    public async Task RefreshDirectoryAsync(string path, bool preserveState = true)
    {
        // This is the existing RefreshDirectoryAsync method
        // The coordinator will call this when a refresh is needed
        await RefreshDirectoryAsync(path);
    }
    
    public void Initialize(
        IFileSystemService fileSystemService,
        IRefreshCoordinator? refreshCoordinator = null, // NEW parameter
        ILogger<FileTreeView>? logger = null,
        // ... other parameters
    )
    {
        _fileSystemService = fileSystemService;
        _refreshCoordinator = refreshCoordinator;
        
        // Register with coordinator
        _refreshCoordinator?.RegisterTreeView(this);
        
        // ... rest of initialization ...
    }
    
    protected override void OnUnloaded(RoutedEventArgs e)
    {
        // Unregister from coordinator
        _refreshCoordinator?.UnregisterTreeView(this);
        base.OnUnloaded(e);
    }
}
```

### Step 3: Update MainWindow to Use Coordinator

```csharp
// MainWindow.xaml.cs
using EnhancedFileExplorer.Core.Events;

public partial class MainWindow : Window
{
    private readonly IRefreshCoordinator _refreshCoordinator;
    
    public MainWindow(
        // ... existing parameters
        IRefreshCoordinator refreshCoordinator)
    {
        _refreshCoordinator = refreshCoordinator;
        
        // ... existing initialization ...
        
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
    
    private void OnFileSystemRenamed(object? sender, FileSystemRenamedEventArgs e)
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
    
    // Remove old RefreshTreeViewIfNeeded method - no longer needed!
}
```

### Step 4: Update Drag/Drop to Use Coordinator

```csharp
// FileTreeView.xaml.cs - FileTree_Drop method

private async void FileTree_Drop(object sender, DragEventArgs e)
{
    // ... existing validation logic ...
    
    // Remove: _isDragDropInProgress = true; (coordinator handles this)
    
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
    finally
    {
        // Remove: _isDragDropInProgress = false; (coordinator handles this)
    }
}
```

### Step 5: Update Refresh Button

```csharp
// MainWindow.xaml.cs - RefreshButton_Click

private async void RefreshButton_Click(object sender, RoutedEventArgs e)
{
    try
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
    catch (Exception ex)
    {
        _logger.LogError(ex, "Error refreshing");
        MessageBox.Show($"Error refreshing: {ex.Message}", "Error", 
            MessageBoxButton.OK, MessageBoxImage.Error);
    }
}
```

## Migration Checklist

### Phase 1: Add Infrastructure (Non-Breaking)
- [ ] Add `IRefreshCoordinator` interface
- [ ] Add `IFileTreeRefreshTarget` interface
- [ ] Add event classes (`RefreshRequest`, `RefreshSource`, `RefreshPriority`, `RefreshCompletedEvent`)
- [ ] Implement `RefreshCoordinatorService`
- [ ] Register service in `Bootstrapper`

### Phase 2: Integrate FileTreeView
- [ ] Make `FileTreeView` implement `IFileTreeRefreshTarget`
- [ ] Add `IRefreshCoordinator` parameter to `Initialize` method
- [ ] Register/unregister tree view in lifecycle methods
- [ ] Keep existing `RefreshDirectoryAsync` method (coordinator will call it)

### Phase 3: Migrate Refresh Sources
- [ ] Migrate `FileSystemWatcher` events → Coordinator
- [ ] Migrate `FileOperationCompleted` events → Coordinator
- [ ] Migrate drag/drop operations → Coordinator
- [ ] Migrate refresh button → Coordinator

### Phase 4: Cleanup
- [ ] Remove `_isDragDropInProgress` flag
- [ ] Remove `_pendingRefreshes` dictionary and debouncing logic from `FileTreeView`
- [ ] Remove `RefreshTreeViewIfNeeded` method from `MainWindow`
- [ ] Remove `IsDragDropInProgress` property check from `MainWindow`

## Backward Compatibility

During migration, the coordinator can work alongside existing refresh logic:

```csharp
// FileTreeView.xaml.cs - Hybrid approach during migration

public async Task RefreshDirectoryAsync(string path, bool preserveState = true)
{
    // If coordinator is available, it will call this method
    // Just ensure we're registered (already done in Initialize)
    
    // Existing implementation continues to work
    await RefreshDirectoryAsyncInternal(path, preserveState);
}

// Keep existing public method for backward compatibility
public async Task RefreshDirectoryAsync(string path)
{
    await RefreshDirectoryAsync(path, preserveState: true);
}
```

## Testing the Integration

### Test 1: FileSystemWatcher Refresh
1. Open a directory in FileTreeView
2. Create a file in that directory (outside the app)
3. Verify: File appears in tree after ~200ms debounce

### Test 2: Drag/Drop Refresh
1. Drag a file from one folder to another
2. Verify: Both source and target folders refresh immediately (no delay)

### Test 3: File Operation Refresh
1. Delete a file using context menu
2. Verify: Directory refreshes after operation completes (~100ms debounce)

### Test 4: Multiple Tree Views
1. Open same directory in multiple tabs
2. Create a file in that directory
3. Verify: All tabs refresh simultaneously

### Test 5: Priority Cancellation
1. Trigger FileSystemWatcher event (Low priority)
2. Immediately trigger drag/drop (High priority)
3. Verify: Low priority refresh is cancelled, High priority executes immediately

## Troubleshooting

### Issue: Tree view not refreshing
- **Check:** Is tree view registered? (`_refreshCoordinator?.RegisterTreeView(this)`)
- **Check:** Does `ShouldRefresh` return true for the path?
- **Check:** Is coordinator injected into FileTreeView?

### Issue: Refreshes happening too frequently
- **Check:** Debouncing configuration in `RefreshCoordinatorService`
- **Check:** Priority levels - Low priority should be debounced more

### Issue: Refreshes not happening fast enough
- **Check:** Priority level - use `RefreshPriority.High` for user actions
- **Check:** Debounce delays - High priority has 0ms delay

### Issue: Memory leaks
- **Check:** Are tree views unregistered in `OnUnloaded`?
- **Check:** Are empty queues cleaned up periodically?

## Performance Monitoring

Add logging to monitor coordinator performance:

```csharp
// In RefreshCoordinatorService
_logger.LogInformation(
    "Refresh completed: Path={Path}, Source={Source}, Duration={Duration}ms, TreeViews={Count}",
    path, source, duration, targetTreeViews.Count);
```

Monitor:
- Queue sizes
- Refresh durations
- Concurrent refresh count
- Debounce effectiveness

