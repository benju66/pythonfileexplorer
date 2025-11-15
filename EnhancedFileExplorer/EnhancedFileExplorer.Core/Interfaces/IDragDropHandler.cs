using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Drag-drop effect enumeration (abstracted from WPF).
/// </summary>
public enum DragDropEffect
{
    None = 0,
    Copy = 1,
    Move = 2,
    Link = 4,
    All = Copy | Move | Link
}

/// <summary>
/// Context information for drag-drop operations.
/// </summary>
public class DragDropContext
{
    public IEnumerable<string> SourcePaths { get; set; } = Enumerable.Empty<string>();
    public string? TargetPath { get; set; }
    public bool IsDirectory { get; set; }
    public DragDropEffect RequestedEffect { get; set; }
    public bool IsExternalDrag { get; set; }
    public object? DragSource { get; set; } // For future cross-tab/split view support
}

/// <summary>
/// Result of a drag-drop validation or operation.
/// </summary>
public class DragDropResult
{
    public bool IsValid { get; set; }
    public string? ErrorMessage { get; set; }
    public DragDropEffect AllowedEffects { get; set; }
    
    public static DragDropResult Valid(DragDropEffect allowedEffects) => new()
    {
        IsValid = true,
        AllowedEffects = allowedEffects
    };
    
    public static DragDropResult Invalid(string? errorMessage = null) => new()
    {
        IsValid = false,
        ErrorMessage = errorMessage,
        AllowedEffects = DragDropEffect.None
    };
}

/// <summary>
/// Interface for handling drag-drop operations in a extensible way.
/// Supports single FileTreeView (Phase 1) and can be extended for cross-tab, split view, etc.
/// </summary>
public interface IDragDropHandler
{
    /// <summary>
    /// Validates if a drag operation can be initiated from the given source.
    /// </summary>
    DragDropResult CanDrag(DragDropContext context);
    
    /// <summary>
    /// Validates if a drop operation can be performed at the given target.
    /// </summary>
    DragDropResult CanDrop(DragDropContext context);
    
    /// <summary>
    /// Executes the drag-drop operation (copy or move).
    /// </summary>
    Task<OperationResult> ExecuteDropAsync(DragDropContext context, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Gets the data object for initiating a drag operation.
    /// Returns object to avoid WPF dependency in Core.
    /// </summary>
    object CreateDragData(IEnumerable<string> sourcePaths, bool isCut = false);
    
    /// <summary>
    /// Extracts file paths from a drag data object.
    /// </summary>
    (IEnumerable<string> FilePaths, bool IsCut, bool IsExternal)? ExtractDragData(object dataObject);
}

