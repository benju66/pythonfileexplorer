using EnhancedFileExplorer.Core.Events;

namespace EnhancedFileExplorer.Services.Refresh;

/// <summary>
/// Per-path queue for refresh requests with priority management.
/// </summary>
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
    
    /// <summary>
    /// Dequeues a ready request based on priority and timing.
    /// Returns null if no request is ready or queue is empty.
    /// </summary>
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
    
    /// <summary>
    /// Cancels all requests with priority lower than the specified priority.
    /// </summary>
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

