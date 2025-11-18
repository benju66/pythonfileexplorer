using System.Collections.Concurrent;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Events;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Services.Refresh;

/// <summary>
/// Centralized service for coordinating file tree refresh operations from multiple sources.
/// Provides debouncing, prioritization, and batching of refresh requests.
/// </summary>
public class RefreshCoordinatorService : IRefreshCoordinator, IDisposable
{
    private readonly ILogger<RefreshCoordinatorService> _logger;
    private readonly IEventAggregator _eventAggregator;
    private readonly ConcurrentDictionary<string, RefreshQueue> _queues;
    private readonly ConcurrentDictionary<string, IFileTreeRefreshTarget> _registeredTreeViews;
    private readonly SemaphoreSlim _queueSemaphore;
    private readonly CancellationTokenSource _cancellationTokenSource;
    private readonly Timer? _cleanupTimer;
    
    // Configuration
    private readonly TimeSpan _debounceDelay = TimeSpan.FromMilliseconds(100);
    private readonly TimeSpan _lowPriorityDebounceDelay = TimeSpan.FromMilliseconds(200);
    private readonly int _maxConcurrentRefreshes = 3;
    private readonly TimeSpan _cleanupInterval = TimeSpan.FromMinutes(5);
    
    public RefreshCoordinatorService(
        ILogger<RefreshCoordinatorService> logger,
        IEventAggregator eventAggregator)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _eventAggregator = eventAggregator ?? throw new ArgumentNullException(nameof(eventAggregator));
        _queues = new ConcurrentDictionary<string, RefreshQueue>(StringComparer.OrdinalIgnoreCase);
        _registeredTreeViews = new ConcurrentDictionary<string, IFileTreeRefreshTarget>();
        _queueSemaphore = new SemaphoreSlim(_maxConcurrentRefreshes);
        _cancellationTokenSource = new CancellationTokenSource();
        
        // Start background processing
        _ = Task.Run(ProcessRefreshQueuesAsync, _cancellationTokenSource.Token);
        
        // Start cleanup timer
        _cleanupTimer = new Timer(_ => CleanupEmptyQueues(), null, _cleanupInterval, _cleanupInterval);
        
        _logger.LogInformation("RefreshCoordinatorService initialized");
    }
    
    public Task RequestRefreshAsync(RefreshRequest request)
    {
        if (request == null)
            throw new ArgumentNullException(nameof(request));
        
        if (string.IsNullOrWhiteSpace(request.Path))
        {
            _logger.LogWarning("Refresh request with empty path ignored");
            return Task.CompletedTask;
        }
        
        // Path is already normalized in RefreshRequest constructor
        var normalizedPath = request.Path;
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
    
    public Task RequestImmediateRefreshAsync(string path, RefreshSource source)
    {
        if (string.IsNullOrWhiteSpace(path))
            return Task.CompletedTask;
        
        var request = new RefreshRequest(path, source, RefreshPriority.High);
        return RequestRefreshAsync(request);
    }
    
    public void RegisterTreeView(IFileTreeRefreshTarget treeView)
    {
        if (treeView == null)
            throw new ArgumentNullException(nameof(treeView));
        
        if (string.IsNullOrWhiteSpace(treeView.InstanceId))
            throw new ArgumentException("Tree view InstanceId cannot be null or empty", nameof(treeView));
        
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
        
        try
        {
            var normalizedPath = Path.GetFullPath(path);
            if (_queues.TryGetValue(normalizedPath, out var queue))
            {
                lock (queue)
                {
                    return queue.Count;
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Invalid path for pending count: {Path}", path);
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
        
        // Process Low priority (longer debounce)
        foreach (var request in lowPriorityRequests)
        {
            _ = Task.Run(async () =>
            {
                await Task.Delay(_lowPriorityDebounceDelay, _cancellationTokenSource.Token);
                await ExecuteRefreshAsync(request);
            }, _cancellationTokenSource.Token);
        }
    }
    
    private async Task ExecuteRefreshAsync(RefreshRequest request)
    {
        await _queueSemaphore.WaitAsync(_cancellationTokenSource.Token);
        
        try
        {
            var normalizedPath = request.Path; // Already normalized
            
            var targetTreeViews = _registeredTreeViews.Values
                .Where(tv => tv.ShouldRefresh(normalizedPath))
                .ToList();
            
            if (targetTreeViews.Count == 0)
            {
                _logger.LogDebug("No tree views found for path: {Path}", normalizedPath);
                return;
            }
            
            var tasks = targetTreeViews.Select(async tv =>
            {
                try
                {
                    // Check if tree view is still registered (may have been unregistered)
                    if (!_registeredTreeViews.ContainsKey(tv.InstanceId))
                    {
                        _logger.LogDebug("Tree view {InstanceId} was unregistered, skipping refresh", tv.InstanceId);
                        return;
                    }
                    
                    // Check if path is loaded, use appropriate method
                    bool isLoaded = tv.IsPathLoaded(normalizedPath);
                    
                    if (isLoaded)
                    {
                        // Incremental refresh
                        await tv.RefreshDirectoryAsync(normalizedPath, preserveState: true);
                    }
                    else
                    {
                        // Full load for unloaded paths
                        _logger.LogDebug("Path not loaded, using LoadDirectoryAsync: {Path}", normalizedPath);
                        await tv.LoadDirectoryAsync(normalizedPath);
                    }
                    
                    _logger.LogDebug("Refreshed tree view: {InstanceId}, Path: {Path}",
                        tv.InstanceId, normalizedPath);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error refreshing tree view: {InstanceId}, Path: {Path}",
                        tv.InstanceId, normalizedPath);
                    
                    // Retry with LoadDirectoryAsync if RefreshDirectoryAsync fails
                    try
                    {
                        if (_registeredTreeViews.ContainsKey(tv.InstanceId))
                        {
                            _logger.LogDebug("Retrying with LoadDirectoryAsync: {Path}", normalizedPath);
                            await tv.LoadDirectoryAsync(normalizedPath);
                        }
                    }
                    catch (Exception retryEx)
                    {
                        _logger.LogError(retryEx, "LoadDirectoryAsync also failed: {Path}", normalizedPath);
                        throw;
                    }
                }
            });
            
            await Task.WhenAll(tasks);
            
            // Publish completion event
            _eventAggregator.Publish(new RefreshCompletedEvent(
                normalizedPath,
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
    
    private void CleanupEmptyQueues()
    {
        var emptyQueues = _queues
            .Where(kvp => 
            {
                lock (kvp.Value)
                {
                    return kvp.Value.Count == 0;
                }
            })
            .Select(kvp => kvp.Key)
            .ToList();
        
        foreach (var path in emptyQueues)
        {
            _queues.TryRemove(path, out _);
        }
        
        if (emptyQueues.Count > 0)
        {
            _logger.LogDebug("Cleaned up {Count} empty queues", emptyQueues.Count);
        }
    }
    
    public void Dispose()
    {
        _cancellationTokenSource.Cancel();
        _cleanupTimer?.Dispose();
        _queueSemaphore?.Dispose();
        _cancellationTokenSource?.Dispose();
        _logger.LogInformation("RefreshCoordinatorService disposed");
    }
}

