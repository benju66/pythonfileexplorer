namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Event aggregator for decoupled communication between components.
/// </summary>
public interface IEventAggregator
{
    /// <summary>
    /// Subscribes to events of type T.
    /// </summary>
    void Subscribe<T>(Action<T> handler) where T : IEvent;

    /// <summary>
    /// Unsubscribes from events of type T.
    /// </summary>
    void Unsubscribe<T>(Action<T> handler) where T : IEvent;

    /// <summary>
    /// Publishes an event to all subscribers.
    /// </summary>
    void Publish<T>(T eventData) where T : IEvent;
}

