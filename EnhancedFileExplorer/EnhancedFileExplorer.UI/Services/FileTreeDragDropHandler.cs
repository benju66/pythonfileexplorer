using System.Windows;
using EnhancedFileExplorer.Core.Interfaces;
using EnhancedFileExplorer.Core.Models;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.UI.Services;

/// <summary>
/// Handler for file tree drag-drop operations.
/// Supports Phase 1 (single FileTreeView) with extensible design for future phases.
/// </summary>
public class FileTreeDragDropHandler : IDragDropHandler
{
    private readonly IFileOperationService _fileOperationService;
    private readonly IFileSystemService _fileSystemService;
    private readonly ILogger<FileTreeDragDropHandler> _logger;

    public FileTreeDragDropHandler(
        IFileOperationService fileOperationService,
        IFileSystemService fileSystemService,
        ILogger<FileTreeDragDropHandler> logger)
    {
        _fileOperationService = fileOperationService ?? throw new ArgumentNullException(nameof(fileOperationService));
        _fileSystemService = fileSystemService ?? throw new ArgumentNullException(nameof(fileSystemService));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }

    public DragDropResult CanDrag(DragDropContext context)
    {
        if (context.SourcePaths == null || !context.SourcePaths.Any())
            return DragDropResult.Invalid("No source paths provided");

        var sourcePaths = context.SourcePaths.ToArray();
        
        // Validate all source paths exist
        foreach (var path in sourcePaths)
        {
            if (string.IsNullOrWhiteSpace(path))
                return DragDropResult.Invalid("Invalid source path");
        }

        return DragDropResult.Valid(DragDropEffect.Move | DragDropEffect.Copy);
    }

    public DragDropResult CanDrop(DragDropContext context)
    {
        if (string.IsNullOrWhiteSpace(context.TargetPath))
            return DragDropResult.Invalid("No target path provided");

        if (!context.IsDirectory)
            return DragDropResult.Invalid("Can only drop on directories");

        if (context.SourcePaths == null || !context.SourcePaths.Any())
            return DragDropResult.Invalid("No source paths provided");

        var sourcePaths = context.SourcePaths.ToArray();
        var targetPath = context.TargetPath;

        // Validate target exists and is a directory
        try
        {
            if (!System.IO.Directory.Exists(targetPath))
                return DragDropResult.Invalid("Target directory does not exist");
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error validating target path: {Path}", targetPath);
            return DragDropResult.Invalid("Invalid target path");
        }

        // Prevent dropping item onto itself
        foreach (var sourcePath in sourcePaths)
        {
            if (string.Equals(sourcePath, targetPath, StringComparison.OrdinalIgnoreCase))
                return DragDropResult.Invalid("Cannot drop item onto itself");

            // Prevent dropping parent into child
            if (IsParentDirectory(sourcePath, targetPath))
                return DragDropResult.Invalid("Cannot drop parent directory into child directory");
        }

        // Determine allowed effects
        var allowedEffects = DragDropEffect.Move | DragDropEffect.Copy;
        
        // If Ctrl is pressed, prefer Copy; otherwise prefer Move
        if (context.RequestedEffect == DragDropEffect.Copy)
        {
            allowedEffects = DragDropEffect.Copy;
        }
        else if (context.RequestedEffect == DragDropEffect.Move)
        {
            allowedEffects = DragDropEffect.Move;
        }

        return DragDropResult.Valid(allowedEffects);
    }

    public async Task<OperationResult> ExecuteDropAsync(DragDropContext context, CancellationToken cancellationToken = default)
    {
        var validationResult = CanDrop(context);
        if (!validationResult.IsValid)
        {
            return OperationResult.Failure(validationResult.ErrorMessage ?? "Invalid drop operation");
        }

        var sourcePaths = context.SourcePaths.ToArray();
        var targetPath = context.TargetPath!;
        var isMove = context.RequestedEffect == DragDropEffect.Move;

        var errors = new List<string>();
        var successCount = 0;

        foreach (var sourcePath in sourcePaths)
        {
            try
            {
                var fileName = System.IO.Path.GetFileName(sourcePath);
                var destinationPath = System.IO.Path.Combine(targetPath, fileName);

                // Handle name conflicts - generate unique name
                destinationPath = await GenerateUniquePathAsync(destinationPath, cancellationToken);

                OperationResult result;
                if (isMove)
                {
                    result = await _fileOperationService.MoveAsync(sourcePath, destinationPath, cancellationToken);
                }
                else
                {
                    result = await _fileOperationService.CopyAsync(sourcePath, destinationPath, cancellationToken);
                }

                if (result.IsSuccess)
                {
                    successCount++;
                    _logger.LogInformation("Drag-drop {Operation} successful: {Source} -> {Destination}", 
                        isMove ? "move" : "copy", sourcePath, destinationPath);
                }
                else
                {
                    errors.Add($"{fileName}: {result.ErrorMessage}");
                    _logger.LogWarning("Drag-drop {Operation} failed: {Source} -> {Destination}: {Error}", 
                        isMove ? "move" : "copy", sourcePath, destinationPath, result.ErrorMessage);
                }
            }
            catch (Exception ex)
            {
                var fileName = System.IO.Path.GetFileName(sourcePath);
                errors.Add($"{fileName}: {ex.Message}");
                _logger.LogError(ex, "Error during drag-drop operation: {Source}", sourcePath);
            }
        }

        if (errors.Count > 0 && successCount == 0)
        {
            return OperationResult.Failure($"All operations failed:\n{string.Join("\n", errors)}");
        }
        else if (errors.Count > 0)
        {
            return OperationResult.Failure(
                $"Completed {successCount} operation(s), {errors.Count} failed:\n{string.Join("\n", errors)}");
        }

        return OperationResult.Success($"Successfully {((isMove ? "moved" : "copied"))} {successCount} item(s)");
    }

    public object CreateDragData(IEnumerable<string> sourcePaths, bool isCut = false)
    {
        var paths = sourcePaths.ToArray();
        if (paths.Length == 0)
            throw new ArgumentException("Source paths cannot be empty", nameof(sourcePaths));

        var dataObject = new DataObject();
        
        // Set file drop format (Windows standard)
        dataObject.SetData(DataFormats.FileDrop, paths);
        
        // Set custom format to indicate cut vs copy
        dataObject.SetData("EnhancedFileExplorer.Cut", isCut);
        
        // Set text format for compatibility
        dataObject.SetText(string.Join("\n", paths));

        return dataObject;
    }

    public (IEnumerable<string> FilePaths, bool IsCut, bool IsExternal)? ExtractDragData(object dataObject)
    {
        if (dataObject is not System.Windows.IDataObject wpfDataObject)
            return null;

        // Try to get file drop format first (Windows standard)
        if (wpfDataObject.GetDataPresent(DataFormats.FileDrop))
        {
            var files = wpfDataObject.GetData(DataFormats.FileDrop) as string[];
            if (files != null && files.Length > 0)
            {
                // Check if this was a cut operation
                bool isCut = false;
                if (wpfDataObject.GetDataPresent("EnhancedFileExplorer.Cut"))
                {
                    var cutValue = wpfDataObject.GetData("EnhancedFileExplorer.Cut");
                    isCut = cutValue is bool cut && cut;
                }

                // Check if this is an external drag (no custom format means external)
                bool isExternal = !wpfDataObject.GetDataPresent("EnhancedFileExplorer.Cut");

                return (files, isCut, isExternal);
            }
        }

        // Fallback: try text format
        if (wpfDataObject.GetDataPresent(DataFormats.Text))
        {
            var text = wpfDataObject.GetData(DataFormats.Text) as string;
            if (!string.IsNullOrWhiteSpace(text))
            {
                var files = text.Split(new[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries)
                    .Where(f => System.IO.File.Exists(f) || System.IO.Directory.Exists(f))
                    .ToArray();

                if (files.Length > 0)
                {
                    bool isCut = false;
                    if (wpfDataObject.GetDataPresent("EnhancedFileExplorer.Cut"))
                    {
                        var cutValue = wpfDataObject.GetData("EnhancedFileExplorer.Cut");
                        isCut = cutValue is bool cut && cut;
                    }

                    bool isExternal = !wpfDataObject.GetDataPresent("EnhancedFileExplorer.Cut");

                    return (files, isCut, isExternal);
                }
            }
        }

        return null;
    }

    private bool IsParentDirectory(string parentPath, string childPath)
    {
        try
        {
            var parentInfo = new System.IO.DirectoryInfo(parentPath);
            var childInfo = new System.IO.DirectoryInfo(childPath);

            var current = childInfo.Parent;
            while (current != null)
            {
                if (string.Equals(current.FullName, parentInfo.FullName, StringComparison.OrdinalIgnoreCase))
                    return true;
                current = current.Parent;
            }

            return false;
        }
        catch
        {
            return false;
        }
    }

    private async Task<string> GenerateUniquePathAsync(string originalPath, CancellationToken cancellationToken)
    {
        if (!await _fileSystemService.ExistsAsync(originalPath, cancellationToken))
            return originalPath;

        var directory = System.IO.Path.GetDirectoryName(originalPath) ?? string.Empty;
        var fileName = System.IO.Path.GetFileNameWithoutExtension(originalPath);
        var extension = System.IO.Path.GetExtension(originalPath);
        var isDirectory = await _fileSystemService.IsDirectoryAsync(originalPath, cancellationToken);

        int counter = 1;
        string newPath;
        do
        {
            if (isDirectory)
            {
                newPath = System.IO.Path.Combine(directory, $"{fileName} ({counter})");
            }
            else
            {
                newPath = System.IO.Path.Combine(directory, $"{fileName} ({counter}){extension}");
            }
            counter++;
        } while (await _fileSystemService.ExistsAsync(newPath, cancellationToken) && counter < 1000);

        return newPath;
    }
}

