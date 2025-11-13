using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command for renaming files or directories.
/// </summary>
public class RenameCommand : ICommand
{
    private readonly IFileOperationService _fileOperationService;
    private readonly string _oldPath;
    private readonly string _newName;
    private string? _newPath;
    private string? _oldName;

    public string Description => $"Rename {System.IO.Path.GetFileName(_oldPath)} to {_newName}";
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    public bool CanUndo => true;

    public RenameCommand(
        IFileOperationService fileOperationService,
        string oldPath,
        string newName)
    {
        _fileOperationService = fileOperationService ?? throw new ArgumentNullException(nameof(fileOperationService));
        _oldPath = oldPath ?? throw new ArgumentNullException(nameof(oldPath));
        _newName = newName ?? throw new ArgumentNullException(nameof(newName));
        _oldName = System.IO.Path.GetFileName(_oldPath);
    }

    public async Task<bool> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        var result = await _fileOperationService.RenameAsync(_oldPath, _newName, cancellationToken);
        if (result.IsSuccess && result.ResultPath != null)
        {
            _newPath = result.ResultPath;
            return true;
        }
        return false;
    }

    public async Task<bool> UndoAsync(CancellationToken cancellationToken = default)
    {
        if (_newPath == null || _oldName == null)
            return false;

        var result = await _fileOperationService.RenameAsync(_newPath, _oldName, cancellationToken);
        return result.IsSuccess;
    }
}

