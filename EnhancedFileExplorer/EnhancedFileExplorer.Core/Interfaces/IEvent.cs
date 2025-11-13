namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Base interface for all events.
/// </summary>
public interface IEvent
{
    /// <summary>
    /// Timestamp when the event occurred.
    /// </summary>
    DateTime Timestamp { get; }
}

