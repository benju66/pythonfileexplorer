using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace EnhancedFileExplorer.UI.Controls;

/// <summary>
/// Column header control with resizable columns.
/// </summary>
public partial class ColumnHeaderControl : UserControl
{
    private bool _isResizing;
    private int _resizingColumn = -1;
    private double _startWidth;
    private Point _startPoint;

    public event EventHandler<int>? ColumnHeaderClicked;

    public ColumnHeaderControl()
    {
        InitializeComponent();
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);

        if (_isResizing && _resizingColumn >= 0)
        {
            var currentPoint = e.GetPosition(this);
            var delta = currentPoint.X - _startPoint.X;
            var newWidth = Math.Max(50, _startWidth + delta);

            var manager = ColumnWidthManager.Instance;
            switch (_resizingColumn)
            {
                case 0:
                    manager.NameWidth = newWidth;
                    break;
                case 1:
                    manager.SizeWidth = newWidth;
                    break;
                case 2:
                    manager.ModifiedWidth = newWidth;
                    break;
                case 3:
                    manager.CreatedWidth = newWidth;
                    break;
            }
        }
        else
        {
            // Check if mouse is near column border for resize cursor
            var point = e.GetPosition(this);
            const double expanderColumnWidth = 19.0; // Match TreeViewItem expander column
            var columnWidths = new[]
            {
                ColumnWidthManager.Instance.NameWidth,
                ColumnWidthManager.Instance.SizeWidth,
                ColumnWidthManager.Instance.ModifiedWidth,
                ColumnWidthManager.Instance.CreatedWidth
            };

            double x = expanderColumnWidth; // Start after expander column
            bool nearBorder = false;
            for (int i = 0; i < columnWidths.Length - 1; i++)
            {
                x += columnWidths[i];
                if (Math.Abs(point.X - x) < 5)
                {
                    Cursor = Cursors.SizeWE;
                    nearBorder = true;
                    break;
                }
            }

            if (!nearBorder)
            {
                Cursor = Cursors.Arrow;
            }
        }
    }

    protected override void OnMouseLeftButtonDown(MouseButtonEventArgs e)
    {
        base.OnMouseLeftButtonDown(e);

        var point = e.GetPosition(this);
        const double expanderColumnWidth = 19.0; // Match TreeViewItem expander column
        var columnWidths = new[]
        {
            ColumnWidthManager.Instance.NameWidth,
            ColumnWidthManager.Instance.SizeWidth,
            ColumnWidthManager.Instance.ModifiedWidth,
            ColumnWidthManager.Instance.CreatedWidth
        };

        // Check if clicking on column border for resizing
        double x = expanderColumnWidth; // Start after expander column
        bool isResizeArea = false;
        for (int i = 0; i < columnWidths.Length - 1; i++)
        {
            x += columnWidths[i];
            if (Math.Abs(point.X - x) < 5)
            {
                _isResizing = true;
                _resizingColumn = i;
                _startWidth = columnWidths[i];
                _startPoint = point;
                CaptureMouse();
                e.Handled = true;
                isResizeArea = true;
                break;
            }
        }

        // If not resizing, check if clicking on column header for sorting
        if (!isResizeArea)
        {
            x = expanderColumnWidth; // Start after expander column
            for (int i = 0; i < columnWidths.Length; i++)
            {
                if (point.X >= x && point.X < x + columnWidths[i])
                {
                    ColumnHeaderClicked?.Invoke(this, i);
                    e.Handled = true;
                    break;
                }
                x += columnWidths[i];
            }
        }
    }

    protected override void OnMouseLeftButtonUp(MouseButtonEventArgs e)
    {
        base.OnMouseLeftButtonUp(e);

        if (_isResizing)
        {
            _isResizing = false;
            _resizingColumn = -1;
            ReleaseMouseCapture();
            Cursor = Cursors.Arrow;
        }
    }

    protected override void OnMouseLeave(MouseEventArgs e)
    {
        base.OnMouseLeave(e);
        if (!_isResizing)
        {
            Cursor = Cursors.Arrow;
        }
    }
}

