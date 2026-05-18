using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace DualVoicerCS.Views;

/// <summary>
/// Slide-out drawer attached to a ▼ arrow under a main widget button.
///
/// Mirrors the Python DrawerMixin's <c>_build_compact_drawer</c> — a
/// vertical stack of selectable rows where the currently-selected
/// row is highlighted. The PoC instantiates two of these (one for
/// each spectrum button) to show the pattern works.
///
/// Architectural note: in the Python widget the drawer was an
/// embedded Frame that grew the main toolbar window's height. WPF
/// supports the same pattern via a child Grid row, but for the PoC
/// I'm using a standalone borderless Topmost Window — it positions
/// freely under the arrow, doesn't tangle with the host window's
/// layout, and closes cleanly on focus loss / Escape.
/// </summary>
public partial class VoiceDrawer : Window
{
    /// <summary>One selectable row in the drawer.</summary>
    public record DrawerRow(string Value, string Label);

    public string? SelectedValue { get; private set; }

    /// <summary>Fired when the user picks a row. Carries the row's
    /// <c>Value</c>, NOT the display label.</summary>
    public event EventHandler<string>? Selected;

    private readonly Dictionary<string, Border> _rowChromes = new();
    private string _current;

    public VoiceDrawer(IEnumerable<DrawerRow> rows, string currentValue)
    {
        InitializeComponent();
        _current = currentValue;
        SelectedValue = currentValue;
        BuildRows(rows.ToList(), currentValue);

        // Close on Escape or click-outside (LostKeyboardFocus would
        // fire spuriously when our own rows get hover focus, so we
        // hook Deactivated instead — clean intent).
        Deactivated += (_, _) => Close();
        PreviewKeyDown += (_, e) =>
        {
            if (e.Key == Key.Escape) Close();
        };
    }

    private void BuildRows(List<DrawerRow> rows, string currentValue)
    {
        RowHost.Children.Clear();
        _rowChromes.Clear();

        foreach (var row in rows)
        {
            bool isCurrent = row.Value == currentValue;

            var chrome = new Border
            {
                Background = isCurrent
                    ? (Brush)Application.Current.Resources["DrawerHeader"]
                    : (Brush)Application.Current.Resources["DrawerRowBg"],
                CornerRadius = new CornerRadius(5),
                Padding = new Thickness(10, 6, 10, 6),
                Margin = new Thickness(0, 1, 0, 1),
                Cursor = Cursors.Hand,
            };

            var label = new TextBlock
            {
                Text = row.Label,
                Foreground = isCurrent
                    ? (Brush)Application.Current.Resources["DrawerActive"]
                    : (Brush)Application.Current.Resources["DrawerText"],
                FontSize = 12,
                FontWeight = isCurrent ? FontWeights.SemiBold : FontWeights.Normal,
            };

            chrome.Child = label;

            // Hover effect — fire-and-forget brush swap, no animation
            // (we want responsive feedback, animations would feel
            // sluggish for a 30 ms hover state).
            chrome.MouseEnter += (_, _) =>
            {
                if (row.Value != _current)
                    chrome.Background = (Brush)Application.Current.Resources["DrawerRowHv"];
            };
            chrome.MouseLeave += (_, _) =>
            {
                if (row.Value != _current)
                    chrome.Background = (Brush)Application.Current.Resources["DrawerRowBg"];
            };
            chrome.MouseLeftButtonUp += (_, _) =>
            {
                SelectedValue = row.Value;
                Selected?.Invoke(this, row.Value);
                Close();
            };

            RowHost.Children.Add(chrome);
            _rowChromes[row.Value] = chrome;
        }
    }

    /// <summary>Position the drawer such that its TOP edge sits at
    /// <paramref name="screenX"/>, <paramref name="screenY"/> (real
    /// pixel coords). Caller is responsible for translating the
    /// anchor element's screen position to this coord space.</summary>
    public void ShowAt(double screenX, double screenY)
    {
        Left = screenX;
        Top = screenY;
        Show();
        Activate();
    }
}
