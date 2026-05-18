using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using DualVoicerCS.Controls;
using DualVoicerCS.Services;
using DualVoicerCS.Views;

namespace DualVoicerCS;

/// <summary>
/// The top-level widget window.
///
/// Holds two SpectrumButtons (BN / EN), two ▼ drawer arrows, and a
/// small icon cluster on the right. Owns one
/// <see cref="VoiceTypingOrchestrator"/> shared between both
/// languages — only one mic session can be active at a time, so the
/// orchestrator's <c>IsRunning</c> flag arbitrates which button is
/// "armed".
///
/// The PoC deliberately runs all wiring from code-behind. In the
/// full port we'd factor the wiring into a viewmodel + DI container
/// (the Phase B refactor pattern), but for showing the user the
/// language + drawer + voice-typing slice, a single 200-line code-
/// behind is more legible.
/// </summary>
public partial class MainWindow : Window
{
    // Per-language source preference. Drawer rows write these and
    // OnBengaliClicked / OnEnglishClicked read them to choose which
    // BCP-47 code to send to Google.
    private string _bengaliLang = StreamingSttService.LanguageBengaliBangladesh;
    private string _englishLang = StreamingSttService.LanguageEnglishUS;

    // Track which (if any) spectrum button currently owns the mic.
    private SpectrumButton? _activeButton;

    // Services live for the lifetime of the window.
    private readonly AudioCaptureService _audio = new();
    private readonly StreamingSttService _stt = new();
    private readonly TextInjectionService _typer = new();
    private readonly VoiceTypingOrchestrator _orchestrator;

    public MainWindow()
    {
        InitializeComponent();

        _orchestrator = new VoiceTypingOrchestrator(_audio, _stt, _typer);
        _orchestrator.ErrorOccurred += OnOrchestratorError;
        _orchestrator.TranscriptChanged += (text, isFinal) =>
            DiagLog.Write($"transcript [{(isFinal ? "FINAL" : "interim")}]: {text}");

        Closed += (_, _) => _orchestrator.Dispose();
        DiagLog.Write("=== MainWindow constructed ===");
    }

    // ── Win32: don't steal focus when user clicks the widget ──────
    //
    // Critical for voice typing: when the user clicks BN/EN with
    // Notepad (or any text app) in front, focus MUST stay on Notepad
    // so the SendInput keystrokes land in the right window. Without
    // WS_EX_NOACTIVATE, Windows would promote our widget to the
    // foreground on click, and the typed characters would arrive at
    // OUR window — which has no text input to receive them, so they
    // get silently dropped. (This is the exact failure mode the user
    // reported: "voice typing not working AND focus disappearing".)
    //
    // The Python widget had the same flag — see window_chrome.py's
    // `_set_no_activate`. We apply it once when the HWND becomes
    // available (SourceInitialized fires after CreateWindowEx).

    private const int GWL_EXSTYLE     = -20;
    private const int WS_EX_NOACTIVATE = 0x08000000;
    private const int WS_EX_TOOLWINDOW = 0x00000080;

    [DllImport("user32.dll")]
    private static extern int GetWindowLong(IntPtr hWnd, int nIndex);

    [DllImport("user32.dll")]
    private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

    protected override void OnSourceInitialized(EventArgs e)
    {
        base.OnSourceInitialized(e);
        try
        {
            var hwnd = new WindowInteropHelper(this).Handle;
            int ex = GetWindowLong(hwnd, GWL_EXSTYLE);
            // NOACTIVATE: clicks on our window don't steal focus from
            //             whatever app the user was working in.
            // TOOLWINDOW: don't show in Alt+Tab and don't take a slot
            //             in the taskbar. ShowInTaskbar=False already
            //             handles the taskbar side but TOOLWINDOW is
            //             what hides us from Alt+Tab.
            SetWindowLong(hwnd, GWL_EXSTYLE,
                ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW);
            DiagLog.Write("[Focus] WS_EX_NOACTIVATE applied — clicks won't steal focus");
        }
        catch (Exception ex)
        {
            DiagLog.Write($"[Focus] Failed to set NoActivate: {ex.Message}");
        }
    }

    // ── Drag-to-move ──────────────────────────────────────────────

    private void OnDragHandle(object sender, MouseButtonEventArgs e)
    {
        // The icon-cluster buttons capture their own mouse events;
        // anywhere else in the chrome lets the user grab and move
        // the widget. WPF's DragMove() handles the entire press →
        // move → release lifecycle for us.
        if (e.OriginalSource is Button) return;
        if (e.OriginalSource is SpectrumButton) return;
        try { DragMove(); } catch { /* swallowed — happens on rapid double-click */ }
    }

    // ── Spectrum button clicks (toggle mic per language) ──────────

    private async void OnBengaliClicked(object? sender, EventArgs e)
    {
        DiagLog.Write("[UI] BN button clicked");
        await ToggleRecording(BtnBengali, _bengaliLang);
    }

    private async void OnEnglishClicked(object? sender, EventArgs e)
    {
        DiagLog.Write("[UI] EN button clicked");
        await ToggleRecording(BtnEnglish, _englishLang);
    }

    private async Task ToggleRecording(SpectrumButton button, string languageCode)
    {
        // If THIS button is already active → stop and disarm.
        if (_activeButton == button && _orchestrator.IsRunning)
        {
            await _orchestrator.StopAsync();
            button.IsRecording = false;
            _activeButton = null;
            return;
        }

        // Switching language while another button is hot — stop the
        // old session first so we don't open a second gRPC stream.
        if (_activeButton is not null)
        {
            await _orchestrator.StopAsync();
            _activeButton.IsRecording = false;
            _activeButton = null;
        }

        await _orchestrator.StartAsync(languageCode);
        if (_orchestrator.IsRunning)
        {
            button.IsRecording = true;
            _activeButton = button;
        }
    }

    // ── Drawer arrows ─────────────────────────────────────────────

    private void OnBengaliDrawerClicked(object sender, RoutedEventArgs e)
    {
        ShowDrawerUnder(ArrowBengali, BuildBengaliRows(), _bengaliLang, value =>
        {
            _bengaliLang = value;
        });
    }

    private void OnEnglishDrawerClicked(object sender, RoutedEventArgs e)
    {
        ShowDrawerUnder(ArrowEnglish, BuildEnglishRows(), _englishLang, value =>
        {
            _englishLang = value;
        });
    }

    private static List<VoiceDrawer.DrawerRow> BuildBengaliRows() => new()
    {
        new(StreamingSttService.LanguageBengaliBangladesh, "🇧🇩  বাংলা — Bangladesh"),
        new(StreamingSttService.LanguageBengaliIndia,      "🇮🇳  বাংলা — India"),
    };

    private static List<VoiceDrawer.DrawerRow> BuildEnglishRows() => new()
    {
        new(StreamingSttService.LanguageEnglishUS, "🇺🇸  English — US"),
        new(StreamingSttService.LanguageEnglishIN, "🇮🇳  English — India"),
    };

    private void ShowDrawerUnder(
        FrameworkElement anchor,
        List<VoiceDrawer.DrawerRow> rows,
        string currentValue,
        Action<string> onSelected)
    {
        // Translate the anchor's bottom-left corner into screen
        // coords — DragMove + DPI awareness mean the widget's own
        // Left/Top are real pixels, so this is straightforward.
        var origin = anchor.PointToScreen(new Point(0, anchor.ActualHeight));
        var drawer = new VoiceDrawer(rows, currentValue)
        {
            Owner = this,
        };
        drawer.Selected += (_, value) => onSelected(value);
        drawer.ShowAt(origin.X, origin.Y + 4);
    }

    // ── Misc icon cluster ─────────────────────────────────────────

    private void OnSettingsClicked(object sender, RoutedEventArgs e)
    {
        MessageBox.Show(this,
            "Settings panel isn't built in the PoC. The point of the " +
            "PoC is to prove the widget look, the drawer pattern, and " +
            "real-time Google STT typing — settings will land in the " +
            "full port.",
            "Dual Voicer CS",
            MessageBoxButton.OK, MessageBoxImage.Information);
    }

    private void OnQuitClicked(object sender, RoutedEventArgs e)
    {
        Close();
    }

    // ── Error surface ─────────────────────────────────────────────

    private void OnOrchestratorError(Exception ex)
    {
        // Already on a non-UI thread potentially — marshal.
        Dispatcher.InvokeAsync(() =>
        {
            // Reset visual recording state since whatever button was
            // armed has now been torn down by the orchestrator.
            if (_activeButton is not null)
            {
                _activeButton.IsRecording = false;
                _activeButton = null;
            }
            MessageBox.Show(this,
                ex.Message,
                "Voice typing error",
                MessageBoxButton.OK, MessageBoxImage.Warning);
        });
    }
}
