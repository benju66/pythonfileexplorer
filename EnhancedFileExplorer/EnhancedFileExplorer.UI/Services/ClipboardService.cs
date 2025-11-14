using System.Windows;
using EnhancedFileExplorer.Core.Interfaces;

namespace EnhancedFileExplorer.UI.Services;

/// <summary>
/// WPF implementation of clipboard service.
/// </summary>
public class ClipboardService : IClipboardService
{
    private const string CutFormat = "EnhancedFileExplorer.Cut";

    public void CopyFiles(IEnumerable<string> filePaths)
    {
        var paths = filePaths.ToArray();
        if (paths.Length == 0)
            return;

        var dataObject = new DataObject();
        
        // Set file drop format (for Windows Explorer compatibility)
        dataObject.SetData(DataFormats.FileDrop, paths);
        
        // Set our custom format to indicate this is a copy operation
        dataObject.SetData(CutFormat, false);
        
        // Also set as text for compatibility
        dataObject.SetText(string.Join("\n", paths));

        Clipboard.SetDataObject(dataObject, true);
    }

    public void CutFiles(IEnumerable<string> filePaths)
    {
        var paths = filePaths.ToArray();
        if (paths.Length == 0)
            return;

        var dataObject = new DataObject();
        
        // Set file drop format (for Windows Explorer compatibility)
        dataObject.SetData(DataFormats.FileDrop, paths);
        
        // Set our custom format to indicate this is a cut operation
        dataObject.SetData(CutFormat, true);
        
        // Also set as text for compatibility
        dataObject.SetText(string.Join("\n", paths));

        Clipboard.SetDataObject(dataObject, true);
    }

    public (IEnumerable<string> FilePaths, bool IsCut)? GetFiles()
    {
        if (!HasFiles())
            return null;

        try
        {
            var dataObject = Clipboard.GetDataObject();
            if (dataObject == null)
                return null;

            // Try to get file drop format first (Windows standard)
            if (dataObject.GetDataPresent(DataFormats.FileDrop))
            {
                var files = dataObject.GetData(DataFormats.FileDrop) as string[];
                if (files != null && files.Length > 0)
                {
                    // Check if this was a cut operation
                    bool isCut = false;
                    if (dataObject.GetDataPresent(CutFormat))
                    {
                        var cutValue = dataObject.GetData(CutFormat);
                        isCut = cutValue is bool cut && cut;
                    }

                    return (files, isCut);
                }
            }

            // Fallback: try to parse text format
            if (dataObject.GetDataPresent(DataFormats.Text))
            {
                var text = dataObject.GetData(DataFormats.Text) as string;
                if (!string.IsNullOrWhiteSpace(text))
                {
                    var files = text.Split(new[] { '\n', '\r' }, StringSplitOptions.RemoveEmptyEntries)
                        .Where(f => System.IO.File.Exists(f) || System.IO.Directory.Exists(f))
                        .ToArray();

                    if (files.Length > 0)
                    {
                        bool isCut = false;
                        if (dataObject.GetDataPresent(CutFormat))
                        {
                            var cutValue = dataObject.GetData(CutFormat);
                            isCut = cutValue is bool cut && cut;
                        }

                        return (files, isCut);
                    }
                }
            }
        }
        catch (Exception)
        {
            // Clipboard access can fail in some scenarios
            return null;
        }

        return null;
    }

    public bool HasFiles()
    {
        try
        {
            var dataObject = Clipboard.GetDataObject();
            if (dataObject == null)
                return false;

            return dataObject.GetDataPresent(DataFormats.FileDrop) || 
                   dataObject.GetDataPresent(DataFormats.Text);
        }
        catch (Exception)
        {
            return false;
        }
    }

    public void Clear()
    {
        try
        {
            Clipboard.Clear();
        }
        catch (Exception)
        {
            // Ignore clipboard clear errors
        }
    }
}

