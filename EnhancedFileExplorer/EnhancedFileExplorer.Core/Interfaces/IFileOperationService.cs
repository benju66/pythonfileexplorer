using EnhancedFileExplorer.Core.Models;

namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Service for file and directory operations.
/// </summary>
public interface IFileOperationService
{
    /// <summary>
    /// Copies a file or directory to a new location.
    /// </summary>
    Task<OperationResult> CopyAsync(
        string source,
        string destination,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Moves a file or directory to a new location.
    /// </summary>
    Task<OperationResult> MoveAsync(
        string source,
        string destination,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Deletes a file or directory.
    /// </summary>
    Task<OperationResult> DeleteAsync(
        string path,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Renames a file or directory.
    /// </summary>
    Task<OperationResult> RenameAsync(
        string path,
        string newName,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Creates a new file.
    /// </summary>
    Task<OperationResult> CreateFileAsync(
        string directory,
        string fileName,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Creates a new directory.
    /// </summary>
    Task<OperationResult> CreateFolderAsync(
        string directory,
        string folderName,
        CancellationToken cancellationToken = default);
}

