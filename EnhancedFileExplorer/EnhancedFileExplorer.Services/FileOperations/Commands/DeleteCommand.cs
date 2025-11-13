using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command for deleting files or directories.
/// Note: This is a permanent delete. For undo to work properly, consider implementing
/// a recycle bin or temporary storage mechanism.
/// </summary>
public class DeleteCommand : ICommand
{
    private readonly IFileOperationService _fileOperationService;
    private readonly string _path;
    private readonly bool _isDirectory;
    private byte[]? _backupData;
    private Dictionary<string, byte[]?>? _directoryBackup;

    public string Description => $"Delete {System.IO.Path.GetFileName(_path)}";
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    public bool CanUndo => false; // Permanent delete - cannot undo without backup mechanism

    public DeleteCommand(
        IFileOperationService fileOperationService,
        string path,
        bool isDirectory)
    {
        _fileOperationService = fileOperationService ?? throw new ArgumentNullException(nameof(fileOperationService));
        _path = path ?? throw new ArgumentNullException(nameof(path));
        _isDirectory = isDirectory;
    }

    public async Task<bool> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        // TODO: Implement backup mechanism for undo support
        // For now, this is a permanent delete
        var result = await _fileOperationService.DeleteAsync(_path, cancellationToken);
        return result.IsSuccess;
    }

    public Task<bool> UndoAsync(CancellationToken cancellationToken = default)
    {
        // Cannot undo permanent delete without backup mechanism
        return Task.FromResult(false);
    }
}

