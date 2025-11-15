using EnhancedFileExplorer.Core.Interfaces;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command for moving files/folders.
/// </summary>
public class MoveCommand : ICommand
{
    private readonly IFileOperationService _fileOperationService;
    private readonly string _sourcePath;
    private readonly string _destinationPath;
    private string? _backupSourcePath; // For undo

    public string Description => $"Move {System.IO.Path.GetFileName(_sourcePath)}";
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    public bool CanUndo => true;

    public MoveCommand(
        IFileOperationService fileOperationService,
        string sourcePath,
        string destinationPath)
    {
        _fileOperationService = fileOperationService ?? throw new ArgumentNullException(nameof(fileOperationService));
        _sourcePath = sourcePath ?? throw new ArgumentNullException(nameof(sourcePath));
        _destinationPath = destinationPath ?? throw new ArgumentNullException(nameof(destinationPath));
    }

    public async Task<bool> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            // Store original location for undo
            _backupSourcePath = _sourcePath;

            var result = await _fileOperationService.MoveAsync(_sourcePath, _destinationPath, cancellationToken);
            return result.IsSuccess;
        }
        catch
        {
            return false;
        }
    }

    public async Task<bool> UndoAsync(CancellationToken cancellationToken = default)
    {
        if (_backupSourcePath == null)
            return false;

        try
        {
            // Move back to original location
            var result = await _fileOperationService.MoveAsync(_destinationPath, _backupSourcePath, cancellationToken);
            return result.IsSuccess;
        }
        catch
        {
            return false;
        }
    }
}

