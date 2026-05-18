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
        // Recording state has three layered animations:
        //   1. Rainbow ring rotates slowly (4 s per revolution).
        //   2. Red voice-pulse ellipse inside the disc breathes
        //      (opacity + scale) — INSIDE the button, not the outer
        //      halo the previous version had.
        //   3. Subtle scale-pulse on the rainbow ring itself for
        //      depth.

        // ── 1) Rainbow rotation ──────────────────────────────
        // Forever loop, 4 s period, linear (no easing) so the
        // motion looks like a smooth turntable rather than a
        // wobble.
        var rotate = new DoubleAnimation
        {
            From = 0,
            To = 360,
            Duration = TimeSpan.FromSeconds(4),
            RepeatBehavior = RepeatBehavior.Forever,
        };
        RotateTx.BeginAnimation(System.Windows.Media.RotateTransform.AngleProperty, rotate);

        // ── 2) Inner red voice-pulse: opacity 0 ↔ 0.7, scale
        //       0.55 ↔ 0.95 — feels like a heartbeat synced to
        //       speech, INSIDE the mic icon's surrounding disc.
        var pulseOpacity = new DoubleAnimation
        {
            From = 0.0,
            To = 0.7,
            Duration = TimeSpan.FromMilliseconds(450),
            AutoReverse = true,
            RepeatBehavior = RepeatBehavior.Forever,
            EasingFunction = new SineEase { EasingMode = EasingMode.EaseInOut },
        };
        VoicePulse.BeginAnimation(OpacityProperty, pulseOpacity);

        var pulseScaleX = MakeRepeatingPulse(0.55, 0.95, 450);
        var pulseScaleY = MakeRepeatingPulse(0.55, 0.95, 450);
        PulseTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleXProperty, pulseScaleX);
        PulseTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleYProperty, pulseScaleY);

        // ── 3) Subtle spectrum-ring scale pulse for depth.
        var ringPulseX = MakeRepeatingPulse(1.00, 1.06, 700);
        var ringPulseY = MakeRepeatingPulse(1.00, 1.06, 700);
        ScaleTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleXProperty, ringPulseX);
        ScaleTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleYProperty, ringPulseY);
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
        // Cancel each animation by setting the property to null
        // (DependencyProperty animation reset), then snap back to
        // the resting visual state.
        RotateTx.BeginAnimation(System.Windows.Media.RotateTransform.AngleProperty, null);
        RotateTx.Angle = 0;

        ScaleTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleXProperty, null);
        ScaleTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleYProperty, null);
        ScaleTx.ScaleX = 1.0;
        ScaleTx.ScaleY = 1.0;

        // Voice-pulse: cancel the scale animations first so the
        // fade-out doesn't visually wobble, then fade opacity to
        // zero. Snap the scale transform back to its resting size.
        PulseTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleXProperty, null);
        PulseTx.BeginAnimation(System.Windows.Media.ScaleTransform.ScaleYProperty, null);
        PulseTx.ScaleX = 0.55;
        PulseTx.ScaleY = 0.55;
        VoicePulse.BeginAnimation(OpacityProperty,
            new DoubleAnimation
            {
                To = 0.0,
                Duration = TimeSpan.FromMilliseconds(150),
            });
    }
}
