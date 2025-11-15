using System.Windows;

namespace EnhancedFileExplorer.UI.Controls;

/// <summary>
/// Manages column widths for synchronized header and item columns.
/// </summary>
public class ColumnWidthManager : DependencyObject
{
    private static ColumnWidthManager? _instance;
    public static ColumnWidthManager Instance => _instance ??= new ColumnWidthManager();

    private ColumnWidthManager() { }

    public double NameWidth
    {
        get => (double)GetValue(NameWidthProperty);
        set => SetValue(NameWidthProperty, value);
    }

    public static readonly DependencyProperty NameWidthProperty =
        DependencyProperty.Register(
            "NameWidth",
            typeof(double),
            typeof(ColumnWidthManager),
            new FrameworkPropertyMetadata(300.0, FrameworkPropertyMetadataOptions.AffectsMeasure));

    public double SizeWidth
    {
        get => (double)GetValue(SizeWidthProperty);
        set => SetValue(SizeWidthProperty, value);
    }

    public static readonly DependencyProperty SizeWidthProperty =
        DependencyProperty.Register(
            "SizeWidth",
            typeof(double),
            typeof(ColumnWidthManager),
            new FrameworkPropertyMetadata(100.0, FrameworkPropertyMetadataOptions.AffectsMeasure));

    public double ModifiedWidth
    {
        get => (double)GetValue(ModifiedWidthProperty);
        set => SetValue(ModifiedWidthProperty, value);
    }

    public static readonly DependencyProperty ModifiedWidthProperty =
        DependencyProperty.Register(
            "ModifiedWidth",
            typeof(double),
            typeof(ColumnWidthManager),
            new FrameworkPropertyMetadata(150.0, FrameworkPropertyMetadataOptions.AffectsMeasure));

    public double CreatedWidth
    {
        get => (double)GetValue(CreatedWidthProperty);
        set => SetValue(CreatedWidthProperty, value);
    }

    public static readonly DependencyProperty CreatedWidthProperty =
        DependencyProperty.Register(
            "CreatedWidth",
            typeof(double),
            typeof(ColumnWidthManager),
            new FrameworkPropertyMetadata(150.0, FrameworkPropertyMetadataOptions.AffectsMeasure));
}

