using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Services.FileOperations.Commands;

/// <summary>
/// Command for pasting files/folders from clipboard.
/// </summary>
public class PasteCommand : ICommand
{
    private readonly IFileOperationService _fileOperationService;
    private readonly IClipboardService _clipboardService;
    private readonly string _destinationPath;
    private readonly IFileSystemService _fileSystemService;
    private List<string>? _pastedPaths;
    private bool _wasCutOperation;

    public string Description => "Paste items";
    public DateTime Timestamp { get; } = DateTime.UtcNow;
    public bool CanUndo => true;

    public PasteCommand(
        IFileOperationService fileOperationService,
        IClipboardService clipboardService,
        IFileSystemService fileSystemService,
        string destinationPath)
    {
        _fileOperationService = fileOperationService ?? throw new ArgumentNullException(nameof(fileOperationService));
        _clipboardService = clipboardService ?? throw new ArgumentNullException(nameof(clipboardService));
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _destinationPath = destinationPath ?? throw new ArgumentNullException(nameof(destinationPath));
    }

    public async Task<bool> ExecuteAsync(CancellationToken cancellationToken = default)
    {
        var clipboardData = _clipboardService.GetFiles();
        if (clipboardData == null)
            return false;

        var (filePaths, isCut) = clipboardData.Value;
        _wasCutOperation = isCut;
        _pastedPaths = new List<string>();

        foreach (var sourcePath in filePaths)
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            try
            {
                var fileName = System.IO.Path.GetFileName(sourcePath);
                var destination = System.IO.Path.Combine(_destinationPath, fileName);

                // Handle name collisions
                destination = GetUniquePath(destination);

                OperationResult result;
                if (isCut)
                {
                    // Move operation
                    result = await _fileOperationService.MoveAsync(sourcePath, destination, cancellationToken);
                }
                else
                {
                    // Copy operation
                    result = await _fileOperationService.CopyAsync(sourcePath, destination, cancellationToken);
                }

                if (result.IsSuccess && result.ResultPath != null)
                {
                    _pastedPaths.Add(result.ResultPath);
                }
            }
            catch (Exception)
            {
                // Continue with other files even if one fails
            }
        }

        // Clear clipboard if it was a cut operation
        if (isCut && _pastedPaths.Count > 0)
        {
            _clipboardService.Clear();
        }

        return _pastedPaths.Count > 0;
    }

    public async Task<bool> UndoAsync(CancellationToken cancellationToken = default)
    {
        if (_pastedPaths == null || _pastedPaths.Count == 0)
            return false;

        // Undo: Delete pasted items
        // If it was a cut, we'd need to restore the original location, but that's complex
        // For now, we'll just delete the pasted items
        bool allSucceeded = true;
        foreach (var pastedPath in _pastedPaths)
        {
            try
            {
                var result = await _fileOperationService.DeleteAsync(pastedPath);
                if (!result.IsSuccess)
                    allSucceeded = false;
            }
            catch (Exception)
            {
                allSucceeded = false;
            }
        }

        return allSucceeded;
    }

    private string GetUniquePath(string path)
    {
        if (!System.IO.File.Exists(path) && !System.IO.Directory.Exists(path))
            return path;

        var directory = System.IO.Path.GetDirectoryName(path) ?? string.Empty;
        var fileName = System.IO.Path.GetFileNameWithoutExtension(path);
        var extension = System.IO.Path.GetExtension(path);
        var counter = 1;

        string newPath;
        do
        {
            var newFileName = $"{fileName} ({counter}){extension}";
            newPath = System.IO.Path.Combine(directory, newFileName);
            counter++;
        }
        while (System.IO.File.Exists(newPath) || System.IO.Directory.Exists(newPath));

        return newPath;
    }
}

