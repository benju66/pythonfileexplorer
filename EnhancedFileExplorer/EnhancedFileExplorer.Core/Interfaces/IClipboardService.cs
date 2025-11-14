namespace EnhancedFileExplorer.Core.Interfaces;

/// <summary>
/// Service for clipboard operations.
/// </summary>
public interface IClipboardService
{
    /// <summary>
    /// Copies file paths to the clipboard.
    /// </summary>
    void CopyFiles(IEnumerable<string> filePaths);

    /// <summary>
    /// Cuts file paths to the clipboard (marks them for move operation).
    /// </summary>
    void CutFiles(IEnumerable<string> filePaths);

    /// <summary>
    /// Gets file paths from the clipboard if available.
    /// </summary>
    /// <returns>Tuple containing file paths and whether they were cut (true) or copied (false).</returns>
    (IEnumerable<string> FilePaths, bool IsCut)? GetFiles();

    /// <summary>
    /// Checks if the clipboard contains file paths.
    /// </summary>
    bool HasFiles();

    /// <summary>
    /// Clears the clipboard.
    /// </summary>
    void Clear();
}

