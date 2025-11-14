using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Provider interface for context menu actions.
/// </summary>
public interface IContextMenuProvider
{
    /// <summary>
    /// Gets menu actions for the given context.
    /// </summary>
    Task<IEnumerable<MenuAction>> GetMenuActionsAsync(ContextMenuContext context);
}

