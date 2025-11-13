using EnhancedFileExplorer.Core.Interfaces;
using System.Collections.Concurrent;

namespace EnhancedFileExplorer.Infrastructure.Events;

/// <summary>
/// Implementation of IEventAggregator for decoupled event communication.
/// </summary>
public class EventAggregator : IEventAggregator
{
    private readonly ConcurrentDictionary<Type, List<object>> _handlers = new();

    public void Subscribe<T>(Action<T> handler) where T : IEvent
    {
        if (handler == null)
            throw new ArgumentNullException(nameof(handler));

        var handlers = _handlers.GetOrAdd(typeof(T), _ => new List<object>());
        lock (handlers)
        {
            handlers.Add(handler);
        }
    }

    public void Unsubscribe<T>(Action<T> handler) where T : IEvent
    {
        if (handler == null)
            throw new ArgumentNullException(nameof(handler));

        if (_handlers.TryGetValue(typeof(T), out var handlers))
        {
            lock (handlers)
            {
                handlers.Remove(handler);
            }
        }
    }

    public void Publish<T>(T eventData) where T : IEvent
    {
        if (eventData == null)
            throw new ArgumentNullException(nameof(eventData));

        if (_handlers.TryGetValue(typeof(T), out var handlers))
        {
            // Create a snapshot to avoid issues if handlers are modified during iteration
            Action<T>[] handlerSnapshot;
            lock (handlers)
            {
                handlerSnapshot = handlers.Cast<Action<T>>().ToArray();
            }

            foreach (var handler in handlerSnapshot)
            {
                try
                {
                    handler(eventData);
                }
                catch (Exception ex)
                {
                    // Log error but don't stop other handlers
                    System.Diagnostics.Debug.WriteLine($"Error in event handler: {ex.Message}");
                }
            }
        }
    }
}

