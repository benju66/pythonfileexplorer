using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command for creating new directories.
/// </summary>
public class CreateFolderCommand : ICommand
{
    private readonly IFileOperationService _fileOperationService;
    private readonly string _directory;
    private readonly string _folderName;
    private string? _createdPath;

    public string Description => $"Create folder {_folderName}";
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    public bool CanUndo => true;

    public CreateFolderCommand(
        IFileOperationService fileOperationService,
        string directory,
        string folderName)
    {
        _fileOperationService = fileOperationService ?? throw new ArgumentNullException(nameof(fileOperationService));
        _directory = directory ?? throw new ArgumentNullException(nameof(directory));
        _folderName = folderName ?? throw new ArgumentNullException(nameof(folderName));
    }

    public async Task<bool> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        var result = await _fileOperationService.CreateFolderAsync(_directory, _folderName, cancellationToken);
        if (result.IsSuccess && result.ResultPath != null)
        {
            _createdPath = result.ResultPath;
            return true;
        }
        return false;
    }

    public async Task<bool> UndoAsync(CancellationToken cancellationToken = default)
    {
        if (_createdPath == null)
            return false;

        var result = await _fileOperationService.DeleteAsync(_createdPath, cancellationToken);
        return result.IsSuccess;
    }
}

