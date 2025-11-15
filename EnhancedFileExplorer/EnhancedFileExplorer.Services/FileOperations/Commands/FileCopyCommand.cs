using EnhancedFileExplorer.Core.Interfaces;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command for copying files/folders (used in drag-drop operations).
/// </summary>
public class FileCopyCommand : ICommand
{
    private readonly IFileOperationService _fileOperationService;
    private readonly string _sourcePath;
    private readonly string _destinationPath;

    public string Description => $"Copy {System.IO.Path.GetFileName(_sourcePath)}";
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    public bool CanUndo => true;

    public FileCopyCommand(
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
            var result = await _fileOperationService.CopyAsync(_sourcePath, _destinationPath, cancellationToken);
            return result.IsSuccess;
        }
        catch
        {
            return false;
        }
    }

    public async Task<bool> UndoAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            // Undo copy by deleting the copied file/folder
            var result = await _fileOperationService.DeleteAsync(_destinationPath, cancellationToken);
            return result.IsSuccess;
        }
        catch
        {
            return false;
        }
    }
}

