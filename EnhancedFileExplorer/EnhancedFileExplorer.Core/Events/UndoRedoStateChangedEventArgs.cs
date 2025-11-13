namespace EnhancedFileExplorer.Core.Events;

/// <summary>
/// Event arguments for undo/redo state changes.
/// </summary>
public class UndoRedoStateChangedEventArgs : EventArgs
{
    public bool CanUndo { get; }
    public bool CanRedo { get; }

    public UndoRedoStateChangedEventArgs(bool canUndo, bool canRedo)
    {
        CanUndo = canUndo;
        CanRedo = canRedo;
    }
}

