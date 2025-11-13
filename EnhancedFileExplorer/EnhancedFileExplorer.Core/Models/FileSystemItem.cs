namespace EnhancedFileExplorer.Core.Models;

/// <summary>
/// Represents a file or directory in the file system.
/// </summary>
public class FileSystemItem
{
    public string Path { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public bool IsDirectory { get; set; }
    public long Size { get; set; }
    public DateTime CreatedDate { get; set; }
    public DateTime ModifiedDate { get; set; }
    public DateTime AccessedDate { get; set; }
    public FileAttributes Attributes { get; set; }
    public string? Extension => IsDirectory ? null : System.IO.Path.GetExtension(Name);
}

