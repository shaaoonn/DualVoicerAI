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
    private bool _pressed;

    public SpectrumButton()
    {
        InitializeComponent();
        MouseEnter += OnHoverEnter;
        MouseLeave += OnHoverLeave;
        MouseLeftButtonDown += OnPressed;
        MouseLeftButtonUp += OnReleased;
    }

    private void OnHoverEnter(object sender, MouseEventArgs e)
    {
        AnimateScale(1.06, 120);
    }

    private void OnHoverLeave(object sender, MouseEventArgs e)
    {
        _pressed = false;
        AnimateScale(1.0, 120);
    }

    private void OnPressed(object sender, MouseButtonEventArgs e)
    {
        _pressed = true;
        AnimateScale(0.96, 80);
        // Don't fire Click yet — wait for clean release.
        CaptureMouse();
    }

    private void OnReleased(object sender, MouseButtonEventArgs e)
    {
        ReleaseMouseCapture();
        if (!_pressed) return;
        _pressed = false;
        AnimateScale(1.06, 120);
        // Fire Click only if the release lands on the control (host
        // gets MouseUp anywhere thanks to capture; we filter here).
        var p = e.GetPosition(this);
        if (p.X >= 0 && p.X <= ActualWidth && p.Y >= 0 && p.Y <= ActualHeight)
            Click?.Invoke(this, EventArgs.Empty);
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
        var pulse = new DoubleAnimation
        {
            From = 1.0,
            To = 1.10,
            Duration = TimeSpan.FromMilliseconds(700),
            AutoReverse = true,
            RepeatBehavior = RepeatBehavior.Forever,
            EasingFunction = new SineEase { EasingMode = EasingMode.EaseInOut },
        };
        _pulseStoryboard = new Storyboard();
        Storyboard.SetTarget(pulse, ScaleTx);
        Storyboard.SetTargetProperty(pulse,
            new PropertyPath(System.Windows.Media.ScaleTransform.ScaleXProperty));
        _pulseStoryboard.Children.Add(pulse);

        var pulseY = pulse.Clone();
        Storyboard.SetTarget(pulseY, ScaleTx);
        Storyboard.SetTargetProperty(pulseY,
            new PropertyPath(System.Windows.Media.ScaleTransform.ScaleYProperty));
        _pulseStoryboard.Children.Add(pulseY);

        _pulseStoryboard.Begin();
    }

    private void StopPulse()
    {
        _pulseStoryboard?.Stop();
        _pulseStoryboard = null;
        ScaleTx.ScaleX = 1.0;
        ScaleTx.ScaleY = 1.0;
    }
}
