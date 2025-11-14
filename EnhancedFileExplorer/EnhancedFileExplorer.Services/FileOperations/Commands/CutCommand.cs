using EnhancedFileExplorer.Core.Interfaces;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command for cutting files/folders to clipboard (marks for move operation).
/// </summary>
public class CutCommand : ICommand
{
    private readonly IClipboardService _clipboardService;
    private readonly string _sourcePath;

    public string Description => $"Cut {System.IO.Path.GetFileName(_sourcePath)}";
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    public bool CanUndo => false; // Clipboard operations don't need undo

    public CutCommand(
        IClipboardService clipboardService,
        string sourcePath)
    {
        _clipboardService = clipboardService ?? throw new ArgumentNullException(nameof(clipboardService));
        _sourcePath = sourcePath ?? throw new ArgumentNullException(nameof(sourcePath));
    }

    public Task<bool> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            _clipboardService.CutFiles(new[] { _sourcePath });
            return Task.FromResult(true);
        }
        catch (Exception)
        {
            return Task.FromResult(false);
        }
    }

    public Task<bool> UndoAsync(CancellationToken cancellationToken = default)
    {
        // Clipboard operations cannot be undone
        return Task.FromResult(false);
    }
}

