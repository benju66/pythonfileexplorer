using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command for creating new files.
/// </summary>
public class CreateFileCommand : ICommand
{
    private readonly IFileOperationService _fileOperationService;
    private readonly string _directory;
    private readonly string _fileName;
    private string? _createdPath;

    public string Description => $"Create file {_fileName}";
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    public bool CanUndo => true;

    public CreateFileCommand(
        IFileOperationService fileOperationService,
        string directory,
        string fileName)
    {
        _fileOperationService = fileOperationService ?? throw new ArgumentNullException(nameof(fileOperationService));
        _directory = directory ?? throw new ArgumentNullException(nameof(directory));
        _fileName = fileName ?? throw new ArgumentNullException(nameof(fileName));
    }

    public async Task<bool> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        var result = await _fileOperationService.CreateFileAsync(_directory, _fileName, cancellationToken);
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

