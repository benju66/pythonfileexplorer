using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using EnhancedFileExplorer.Core.Interfaces;
using Microsoft.Extensions.Logging;

namespace EnhancedFileExplorer.Infrastructure.Icon;

/// <summary>
/// Windows Shell API implementation for retrieving file system icons.
/// </summary>
public class IconService : IIconService
{
    private readonly ILogger<IconService> _logger;
    private readonly Dictionary<string, ImageSource> _iconCache;
    private readonly int _maxCacheSize;
    private readonly object _cacheLock = new();

    // Windows Shell API constants
    private const uint SHGFI_ICON = 0x000000100;
    private const uint SHGFI_SMALLICON = 0x000000001;
    private const uint SHGFI_LARGEICON = 0x000000000;
    private const uint SHGFI_USEFILEATTRIBUTES = 0x000000010;

    [DllImport("shell32.dll", CharSet = CharSet.Auto)]
    private static extern IntPtr SHGetFileInfo(string pszPath, uint dwFileAttributes, ref SHFILEINFO psfi, uint cbSizeFileInfo, uint uFlags);

    [DllImport("user32.dll")]
    private static extern bool DestroyIcon(IntPtr hIcon);

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    private struct SHFILEINFO
    {
        public IntPtr hIcon;
        public int iIcon;
        public uint dwAttributes;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string szDisplayName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 80)]
        public string szTypeName;
    }

    public IconService(ILogger<IconService> logger, int maxCacheSize = 1000)
    {
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _iconCache = new Dictionary<string, ImageSource>(StringComparer.OrdinalIgnoreCase);
        _maxCacheSize = maxCacheSize;
    }

    public Task<object?> GetIconAsync(string path, bool isDirectory, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(path))
            return Task.FromResult<object?>(null);

        // Check cache first
        lock (_cacheLock)
        {
            var cacheKey = GetCacheKey(path, isDirectory);
            if (_iconCache.TryGetValue(cacheKey, out var cachedIcon))
            {
                return Task.FromResult<object?>(cachedIcon);
            }
        }

        // Extract icon on background thread
        return Task.Run(() =>
        {
            try
            {
                var icon = ExtractIcon(path, isDirectory);
                if (icon != null)
                {
                    // Add to cache
                    lock (_cacheLock)
                    {
                        var cacheKey = GetCacheKey(path, isDirectory);
                        if (!_iconCache.ContainsKey(cacheKey))
                        {
                            // Evict oldest entries if cache is full
                            if (_iconCache.Count >= _maxCacheSize)
                            {
                                var firstKey = _iconCache.Keys.First();
                                _iconCache.Remove(firstKey);
                            }
                            _iconCache[cacheKey] = icon;
                        }
                    }
                }
                return (object?)icon;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Failed to extract icon for: {Path}", path);
                return (object?)null;
            }
        }, cancellationToken);
    }

    public void ClearCache()
    {
        lock (_cacheLock)
        {
            _iconCache.Clear();
        }
        _logger.LogInformation("Icon cache cleared");
    }

    public int CacheSize
    {
        get
        {
            lock (_cacheLock)
            {
                return _iconCache.Count;
            }
        }
    }

    private ImageSource? ExtractIcon(string path, bool isDirectory)
    {
        try
        {
            var shinfo = new SHFILEINFO();
            uint flags = SHGFI_ICON | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES;
            uint fileAttributes = isDirectory ? 0x00000010u : 0x00000000u; // FILE_ATTRIBUTE_DIRECTORY

            IntPtr hIcon = SHGetFileInfo(path, fileAttributes, ref shinfo, (uint)Marshal.SizeOf<SHFILEINFO>(), flags);

            if (hIcon == IntPtr.Zero || shinfo.hIcon == IntPtr.Zero)
            {
                // Fallback: try without USEFILEATTRIBUTES for existing files
                if (System.IO.File.Exists(path) || System.IO.Directory.Exists(path))
                {
                    hIcon = SHGetFileInfo(path, 0, ref shinfo, (uint)Marshal.SizeOf<SHFILEINFO>(), SHGFI_ICON | SHGFI_SMALLICON);
                }

                if (hIcon == IntPtr.Zero || shinfo.hIcon == IntPtr.Zero)
                {
                    return null;
                }
            }

            // Convert HICON to ImageSource
            var iconSource = Imaging.CreateBitmapSourceFromHIcon(
                shinfo.hIcon,
                Int32Rect.Empty,
                BitmapSizeOptions.FromEmptyOptions());

            // Clean up icon handle
            DestroyIcon(shinfo.hIcon);

            // Freeze for thread safety
            iconSource.Freeze();

            return iconSource;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Error extracting icon: {Path}", path);
            return null;
        }
    }

    private string GetCacheKey(string path, bool isDirectory)
    {
        // Use extension for files, "DIR" for directories
        if (isDirectory)
            return "DIR";
        
        var extension = System.IO.Path.GetExtension(path).ToLowerInvariant();
        return string.IsNullOrEmpty(extension) ? "FILE" : extension;
    }
}

