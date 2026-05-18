using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media.Animation;

namespace DualVoicerCS.Controls;

/// <summary>
/// Circular spectrum / rainbow mic button. Visually mirrors the
/// SpectrumButton from the Python widget so the PoC is recognisable
/// side-by-side.
///
/// Three things this control proves WPF can do that mattered in the
/// Python version:
///
/// <list type="bullet">
///   <item>Vector circular rendering with smooth gradients at native
///         DPI — no PIL.Image + bitmap-copy round-trip, so it looks
///         crisp on a 4K display without any GDI-scaling tricks.</item>
///   <item>State transitions (idle → recording → idle) via WPF
///         storyboards instead of after()-driven timer ticks. The
///         pulse animation runs on the compositor thread and stays
///         smooth even if the UI thread is briefly busy.</item>
///   <item>Hover scale-up for tactile feel — fires from a single
///         MouseEnter/MouseLeave pair rather than the per-button
///         enter/leave bindings the Python widget needed.</item>
/// </list>
/// </summary>
public partial class SpectrumButton : UserControl
{
    public static readonly DependencyProperty LabelProperty =
        DependencyProperty.Register(nameof(Label), typeof(string),
            typeof(SpectrumButton),
            new PropertyMetadata("BN", OnLabelChanged));

    public string Label
    {
        get => (string)GetValue(LabelProperty);
        set => SetValue(LabelProperty, value);
    }

    private static void OnLabelChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is SpectrumButton btn)
            btn.LabelText.Text = (string)e.NewValue;
    }

    /// <summary>True when this button is actively recording. Drives
    /// the pulse animation on the outer ring.</summary>
    public bool IsRecording
    {
        get => _isRecording;
        set
        {
            if (_isRecording == value) return;
            _isRecording = value;
            if (value) StartPulse();
            else StopPulse();
        }
    }
    private bool _isRecording;

    /// <summary>Click event — fires once on a clean press-release
    /// inside the bounds. Used by the host window to toggle
    /// recording state for this language.</summary>
    public event EventHandler? Click;

    private Storyboard? _pulseStoryboard;

    public SpectrumButton()
    {
        InitializeComponent();
        // Simple click model — works with WS_EX_NOACTIVATE.
        //
        // Original implementation used MouseLeftButtonDown → CaptureMouse
        // → wait for MouseLeftButtonUp inside bounds. That broke when
        // the host window got WS_EX_NOACTIVATE: a non-activatable
        // window can't reliably take mouse capture, so the Up event
        // never came back to us and Click never fired. End result:
        // user clicked, nothing happened (no log entry past
        // "Focus applied"). Confirmed via debug.log: zero
        // `[Orch] StartAsync` lines despite multiple button presses.
        //
        // New model: fire Click immediately on MouseLeftButtonDown.
        // We lose drag-out-to-cancel (which the Python widget also
        // doesn't have) but gain reliable activation under
        // WS_EX_NOACTIVATE. The press-scale-animation still runs so
        // there's tactile feedback.
        MouseEnter += OnHoverEnter;
        MouseLeave += OnHoverLeave;
        PreviewMouseLeftButtonDown += OnClickFire;
    }

    private void OnHoverEnter(object sender, MouseEventArgs e)
    {
        AnimateScale(1.06, 120);
    }

    private void OnHoverLeave(object sender, MouseEventArgs e)
    {
        AnimateScale(1.0, 120);
    }

    private void OnClickFire(object sender, MouseButtonEventArgs e)
    {
        // Brief press scale-down for tactile feel, then revert.
        AnimateScale(0.94, 70);
        Dispatcher.BeginInvoke(new Action(() => AnimateScale(1.06, 120)),
            System.Windows.Threading.DispatcherPriority.Background);
        Click?.Invoke(this, EventArgs.Empty);
        e.Handled = true; // don't let the click bubble into DragMove
    }

    private void AnimateScale(double target, int ms)
    {
        var anim = new DoubleAnimation
        {
            To = target,
            Duration = TimeSpan.FromMilliseconds(ms),
            EasingFunction = new System.Windows.Media.Animation.CubicEase
                { EasingMode = EasingMode.EaseOut },
        };
        ScaleTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleXProperty, anim);
        ScaleTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleYProperty, anim);
    }

    private void StartPulse()
    {
        // ── 1) Fade the LiveHalo into view ────────────────────
        // 200 ms fade from invisible to fully visible gives a
        // distinct "click → red glow appears" beat. The halo's
        // RadialGradientBrush is doughnut-shaped so it sits OUTSIDE
        // the spectrum ring rather than washing the button out.
        LiveHalo.BeginAnimation(OpacityProperty,
            new DoubleAnimation
            {
                To = 1.0,
                Duration = TimeSpan.FromMilliseconds(200),
            });

        // ── 2) Halo pulses at 700 ms heartbeat ────────────────
        // Bigger amplitude (1.00 ↔ 1.18) than the inner-button
        // pulse — the halo HAS to be the eye-catching cue at
        // glance distance.
        var haloPulseX = MakeRepeatingPulse(1.00, 1.18, 700);
        var haloPulseY = MakeRepeatingPulse(1.00, 1.18, 700);
        Storyboard.SetTarget(haloPulseX, HaloScaleTx);
        Storyboard.SetTargetProperty(haloPulseX,
            new PropertyPath(System.Windows.Media.ScaleTransform.ScaleXProperty));
        Storyboard.SetTarget(haloPulseY, HaloScaleTx);
        Storyboard.SetTargetProperty(haloPulseY,
            new PropertyPath(System.Windows.Media.ScaleTransform.ScaleYProperty));

        // ── 3) Inner disc tints red so the button core also reads
        //       as "active" — not just the surrounding halo.
        InnerDisc.Fill = new System.Windows.Media.SolidColorBrush(
            System.Windows.Media.Color.FromArgb(0xFF, 0x80, 0x18, 0x20));

        // ── 4) Subtle spectrum-ring pulse retained for depth.
        var ringPulseX = MakeRepeatingPulse(1.00, 1.08, 700);
        var ringPulseY = MakeRepeatingPulse(1.00, 1.08, 700);
        Storyboard.SetTarget(ringPulseX, ScaleTx);
        Storyboard.SetTargetProperty(ringPulseX,
            new PropertyPath(System.Windows.Media.ScaleTransform.ScaleXProperty));
        Storyboard.SetTarget(ringPulseY, ScaleTx);
        Storyboard.SetTargetProperty(ringPulseY,
            new PropertyPath(System.Windows.Media.ScaleTransform.ScaleYProperty));

        _pulseStoryboard = new Storyboard();
        _pulseStoryboard.Children.Add(haloPulseX);
        _pulseStoryboard.Children.Add(haloPulseY);
        _pulseStoryboard.Children.Add(ringPulseX);
        _pulseStoryboard.Children.Add(ringPulseY);
        _pulseStoryboard.Begin();
    }

    private static DoubleAnimation MakeRepeatingPulse(double from, double to, int periodMs) => new()
    {
        From = from,
        To = to,
        Duration = TimeSpan.FromMilliseconds(periodMs),
        AutoReverse = true,
        RepeatBehavior = RepeatBehavior.Forever,
        EasingFunction = new SineEase { EasingMode = EasingMode.EaseInOut },
    };

    private void StopPulse()
    {
        _pulseStoryboard?.Stop();
        _pulseStoryboard = null;
        ScaleTx.ScaleX = 1.0;
        ScaleTx.ScaleY = 1.0;
        HaloScaleTx.ScaleX = 1.0;
        HaloScaleTx.ScaleY = 1.0;

        // Fade the halo back out — gives a clear "click → red goes
        // away" cue. Hold over with BeginAnimation rather than
        // setting Opacity directly so we don't pop visually.
        LiveHalo.BeginAnimation(OpacityProperty,
            new DoubleAnimation
            {
                To = 0.0,
                Duration = TimeSpan.FromMilliseconds(180),
            });

        // Restore the dark inner disc.
        InnerDisc.Fill = new System.Windows.Media.SolidColorBrush(
            System.Windows.Media.Color.FromArgb(0xFF, 0x1A, 0x1B, 0x40));
    }
}
