using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Services.FileOperations;

/// <summary>
/// Service for file and directory operations.
/// </summary>
public class FileOperationService : IFileOperationService
{
    private readonly IFileSystemService _fileSystemService;
    private readonly ILogger<FileOperationService> _logger;

    public FileOperationService(
        IFileSystemService fileSystemService,
        ILogger<FileOperationService> logger)
    {
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public async Task<OperationResult> CopyAsync(string source, string destination, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(source))
            return OperationResult.Failure("Source path cannot be null or empty.");

        if (string.IsNullOrWhiteSpace(destination))
            return OperationResult.Failure("Destination path cannot be null or empty.");

        try
        {
            var exists = await _fileSystemService.ExistsAsync(source, cancellationToken);
            if (!exists)
                return OperationResult.Failure($"Source path does not exist: {source}");

            var isDirectory = await _fileSystemService.IsDirectoryAsync(source, cancellationToken);

            if (isDirectory)
            {
                await Task.Run(() => System.IO.Directory.CreateDirectory(destination), cancellationToken);
                await CopyDirectoryAsync(source, destination, cancellationToken);
            }
            else
            {
                await Task.Run(() => System.IO.File.Copy(source, destination, overwrite: false), cancellationToken);
            }

            _logger.LogInformation("Copied {Source} to {Destination}", source, destination);
            return OperationResult.Success(destination);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error copying {Source} to {Destination}", source, destination);
            return OperationResult.Failure($"Failed to copy: {ex.Message}", ex);
        }
    }

    public async Task<OperationResult> MoveAsync(string source, string destination, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(source))
            return OperationResult.Failure("Source path cannot be null or empty.");

        if (string.IsNullOrWhiteSpace(destination))
            return OperationResult.Failure("Destination path cannot be null or empty.");

        try
        {
            var exists = await _fileSystemService.ExistsAsync(source, cancellationToken);
            if (!exists)
                return OperationResult.Failure($"Source path does not exist: {source}");

            var isDirectory = await _fileSystemService.IsDirectoryAsync(source, cancellationToken);

            if (isDirectory)
            {
                await Task.Run(() => System.IO.Directory.Move(source, destination), cancellationToken);
            }
            else
            {
                await Task.Run(() => System.IO.File.Move(source, destination), cancellationToken);
            }

            _logger.LogInformation("Moved {Source} to {Destination}", source, destination);
            return OperationResult.Success(destination);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error moving {Source} to {Destination}", source, destination);
            return OperationResult.Failure($"Failed to move: {ex.Message}", ex);
        }
    }

    public async Task<OperationResult> DeleteAsync(string path, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(path))
            return OperationResult.Failure("Path cannot be null or empty.");

        try
        {
            var exists = await _fileSystemService.ExistsAsync(path, cancellationToken);
            if (!exists)
                return OperationResult.Failure($"Path does not exist: {path}");

            var isDirectory = await _fileSystemService.IsDirectoryAsync(path, cancellationToken);

            if (isDirectory)
            {
                await Task.Run(() => System.IO.Directory.Delete(path, recursive: true), cancellationToken);
            }
            else
            {
                await Task.Run(() => System.IO.File.Delete(path), cancellationToken);
            }

            _logger.LogInformation("Deleted {Path}", path);
            return OperationResult.Success();
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error deleting {Path}", path);
            return OperationResult.Failure($"Failed to delete: {ex.Message}", ex);
        }
    }

    public async Task<OperationResult> RenameAsync(string path, string newName, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(path))
            return OperationResult.Failure("Path cannot be null or empty.");

        if (string.IsNullOrWhiteSpace(newName))
            return OperationResult.Failure("New name cannot be null or empty.");

        // Validate new name
        var invalidChars = System.IO.Path.GetInvalidFileNameChars();
        if (newName.Any(c => invalidChars.Contains(c)))
            return OperationResult.Failure($"New name contains invalid characters: {newName}");

        try
        {
            var exists = await _fileSystemService.ExistsAsync(path, cancellationToken);
            if (!exists)
                return OperationResult.Failure($"Path does not exist: {path}");

            var directory = System.IO.Path.GetDirectoryName(path) ?? throw new InvalidOperationException("Cannot get directory name");
            var newPath = System.IO.Path.Combine(directory, newName);

            // Check if new path already exists
            if (await _fileSystemService.ExistsAsync(newPath, cancellationToken))
                return OperationResult.Failure($"A file or directory with the name '{newName}' already exists.");

            var isDirectory = await _fileSystemService.IsDirectoryAsync(path, cancellationToken);

            if (isDirectory)
            {
                await Task.Run(() => System.IO.Directory.Move(path, newPath), cancellationToken);
            }
            else
            {
                await Task.Run(() => System.IO.File.Move(path, newPath), cancellationToken);
            }

            _logger.LogInformation("Renamed {Path} to {NewPath}", path, newPath);
            return OperationResult.Success(newPath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error renaming {Path} to {NewName}", path, newName);
            return OperationResult.Failure($"Failed to rename: {ex.Message}", ex);
        }
    }

    public async Task<OperationResult> CreateFileAsync(string directory, string fileName, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(directory))
            return OperationResult.Failure("Directory path cannot be null or empty.");

        if (string.IsNullOrWhiteSpace(fileName))
            return OperationResult.Failure("File name cannot be null or empty.");

        try
        {
            var isDirectory = await _fileSystemService.IsDirectoryAsync(directory, cancellationToken);
            if (!isDirectory)
                return OperationResult.Failure($"Directory does not exist: {directory}");

            var filePath = System.IO.Path.Combine(directory, fileName);

            // Check if file already exists, generate unique name if needed
            var counter = 1;
            var baseName = System.IO.Path.GetFileNameWithoutExtension(fileName);
            var extension = System.IO.Path.GetExtension(fileName);
            var uniquePath = filePath;

            while (await _fileSystemService.ExistsAsync(uniquePath, cancellationToken))
            {
                var newFileName = $"{baseName} ({counter}){extension}";
                uniquePath = System.IO.Path.Combine(directory, newFileName);
                counter++;
            }

            await Task.Run(() =>
            {
                using (System.IO.File.Create(uniquePath)) { }
            }, cancellationToken);

            _logger.LogInformation("Created file {FilePath}", uniquePath);
            return OperationResult.Success(uniquePath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error creating file {FileName} in {Directory}", fileName, directory);
            return OperationResult.Failure($"Failed to create file: {ex.Message}", ex);
        }
    }

    public async Task<OperationResult> CreateFolderAsync(string directory, string folderName, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(directory))
            return OperationResult.Failure("Directory path cannot be null or empty.");

        if (string.IsNullOrWhiteSpace(folderName))
            return OperationResult.Failure("Folder name cannot be null or empty.");

        try
        {
            var isDirectory = await _fileSystemService.IsDirectoryAsync(directory, cancellationToken);
            if (!isDirectory)
                return OperationResult.Failure($"Directory does not exist: {directory}");

            var folderPath = System.IO.Path.Combine(directory, folderName);

            // Check if folder already exists, generate unique name if needed
            var counter = 1;
            var uniquePath = folderPath;

            while (await _fileSystemService.ExistsAsync(uniquePath, cancellationToken))
            {
                var newFolderName = $"{folderName} ({counter})";
                uniquePath = System.IO.Path.Combine(directory, newFolderName);
                counter++;
            }

            await Task.Run(() => System.IO.Directory.CreateDirectory(uniquePath), cancellationToken);

            _logger.LogInformation("Created folder {FolderPath}", uniquePath);
            return OperationResult.Success(uniquePath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error creating folder {FolderName} in {Directory}", folderName, directory);
            return OperationResult.Failure($"Failed to create folder: {ex.Message}", ex);
        }
    }

    private async Task CopyDirectoryAsync(string sourceDir, string destDir, CancellationToken cancellationToken = default)
    {
        var dir = new DirectoryInfo(sourceDir);
        var dirs = dir.GetDirectories();

        Directory.CreateDirectory(destDir);

        foreach (var file in dir.GetFiles())
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            var targetFilePath = Path.Combine(destDir, file.Name);
            file.CopyTo(targetFilePath);
        }

        foreach (var subDir in dirs)
        {
            if (cancellationToken.IsCancellationRequested)
                break;

            var newDestDir = Path.Combine(destDir, subDir.Name);
            await CopyDirectoryAsync(subDir.FullName, newDestDir, cancellationToken);
        }
    }
}

