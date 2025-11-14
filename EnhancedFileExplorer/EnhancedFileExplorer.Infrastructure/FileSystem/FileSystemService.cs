using System.IO;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Infrastructure.FileSystem;

/// <summary>
/// Implementation of IFileSystemService using .NET file system APIs.
/// </summary>
public class FileSystemService : IFileSystemService
{
    private readonly ILogger<FileSystemService> _logger;

    public FileSystemService(ILogger<FileSystemService> logger)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public Task<bool> ExistsAsync(string path, CancellationToken cancellationToken = default)
    {
        try
        {
            return Task.FromResult(System.IO.File.Exists(path) || System.IO.Directory.Exists(path));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error checking if path exists: {Path}", path);
            return Task.FromResult(false);
        }
    }

    public Task<bool> IsDirectoryAsync(string path, CancellationToken cancellationToken = default)
    {
        try
        {
            return Task.FromResult(System.IO.Directory.Exists(path));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error checking if path is directory: {Path}", path);
            return Task.FromResult(false);
        }
    }

    public async Task<IEnumerable<FileSystemItem>> GetItemsAsync(string directory, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(directory))
        {
            throw new ArgumentException("Directory path cannot be null or empty.", nameof(directory));
        }

        if (!await IsDirectoryAsync(directory, cancellationToken))
        {
            throw new DirectoryNotFoundException($"Directory does not exist: {directory}");
        }

        var items = new List<FileSystemItem>();

        try
        {
            // Get directories
            var directories = System.IO.Directory.GetDirectories(directory);
            foreach (var dir in directories)
            {
                if (cancellationToken.IsCancellationRequested)
                    break;

                try
                {
                    var dirInfo = new DirectoryInfo(dir);
                    items.Add(new FileSystemItem
                    {
                        Path = dir,
                        Name = dirInfo.Name,
                        IsDirectory = true,
                        Size = 0,
                        CreatedDate = dirInfo.CreationTime,
                        ModifiedDate = dirInfo.LastWriteTime,
                        AccessedDate = dirInfo.LastAccessTime,
                        Attributes = dirInfo.Attributes
                    });
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error reading directory: {Path}", dir);
                }
            }

            // Get files
            var files = System.IO.Directory.GetFiles(directory);
            foreach (var file in files)
            {
                if (cancellationToken.IsCancellationRequested)
                    break;

                try
                {
                    var fileInfo = new FileInfo(file);
                    items.Add(new FileSystemItem
                    {
                        Path = file,
                        Name = fileInfo.Name,
                        IsDirectory = false,
                        Size = fileInfo.Length,
                        CreatedDate = fileInfo.CreationTime,
                        ModifiedDate = fileInfo.LastWriteTime,
                        AccessedDate = fileInfo.LastAccessTime,
                        Attributes = fileInfo.Attributes
                    });
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Error reading file: {Path}", file);
                }
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting items from directory: {Directory}", directory);
            throw;
        }

        return items;
    }

    public Task<FileSystemItem> GetItemAsync(string path, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new ArgumentException("Path cannot be null or empty.", nameof(path));
        }

        try
        {
            if (System.IO.Directory.Exists(path))
            {
                var dirInfo = new DirectoryInfo(path);
                return Task.FromResult(new FileSystemItem
                {
                    Path = path,
                    Name = dirInfo.Name,
                    IsDirectory = true,
                    Size = 0,
                    CreatedDate = dirInfo.CreationTime,
                    ModifiedDate = dirInfo.LastWriteTime,
                    AccessedDate = dirInfo.LastAccessTime,
                    Attributes = dirInfo.Attributes
                });
            }
            else if (System.IO.File.Exists(path))
            {
                var fileInfo = new FileInfo(path);
                return Task.FromResult(new FileSystemItem
                {
                    Path = path,
                    Name = fileInfo.Name,
                    IsDirectory = false,
                    Size = fileInfo.Length,
                    CreatedDate = fileInfo.CreationTime,
                    ModifiedDate = fileInfo.LastWriteTime,
                    AccessedDate = fileInfo.LastAccessTime,
                    Attributes = fileInfo.Attributes
                });
            }
            else
            {
                throw new FileNotFoundException($"Path does not exist: {path}");
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting item: {Path}", path);
            throw;
        }
    }

    public Task<string?> GetParentDirectoryAsync(string path, CancellationToken cancellationToken = default)
    {
        try
        {
            var parent = System.IO.Directory.GetParent(path);
            return Task.FromResult(parent?.FullName);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting parent directory: {Path}", path);
            return Task.FromResult<string?>(null);
        }
    }
}

