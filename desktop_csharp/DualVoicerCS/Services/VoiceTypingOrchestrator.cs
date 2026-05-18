using System;
using System.Threading.Tasks;
using System.Windows;

namespace DualVoicerCS.Services;

/// <summary>
/// Glues the three services into one click-to-speak voice typing
/// session. Owns the diffing state machine that turns Google's
/// stream of evolving interim transcripts into a smooth typing
/// experience for the user's foreground app.
///
/// ── The interim-diff state machine ────────────────────────────
///
/// Google's streaming API emits interim hypotheses ~3-5× per second
/// while the user is talking. Each interim is a complete guess at
/// what's been said SO FAR in the current utterance. So for "I want
/// to go home", we might see:
///
///   "I"
///   "I want"
///   "I want to"
///   "I want to go"
///   "I went a go"          ← Google reconsidered, common prefix shrank
///   "I want to go"
///   "I want to go home"
///   "I want to go home."   ← FINAL — utterance closed
///
/// A naive typer that just appended each interim would produce
/// duplicated and contradictory text in Notepad. So we:
///
/// 1. Track the last interim we typed in <c>_typedInterim</c>.
/// 2. On each new interim, find the common prefix with what we typed.
/// 3. Backspace the portion of <c>_typedInterim</c> AFTER the
///    common prefix.
/// 4. Type the portion of the new interim AFTER the common prefix.
/// 5. Save the new interim as <c>_typedInterim</c>.
///
/// When the FINAL marker arrives, we treat the segment as committed:
/// append a trailing space, then reset <c>_typedInterim</c> to empty
/// so the next utterance starts a fresh diff baseline.
///
/// In the common path where Google never retracts, this collapses
/// to "type the new suffix" — i.e. real word-by-word streaming with
/// zero backspaces. Retractions cost one backspace per reverted
/// character, which is still imperceptible at human reading speed.
/// </summary>
public sealed class VoiceTypingOrchestrator : IDisposable
{
    private readonly AudioCaptureService _audio;
    private readonly StreamingSttService _stt;
    private readonly TextInjectionService _typer;

    private string _typedInterim = string.Empty;
    private bool _running;

    /// <summary>UI helper: fired whenever the latest interim/final
    /// transcript changes, so the host window can show it for
    /// debugging. Not required for typing to work — the typing
    /// itself is fully handled inside this class.</summary>
    public event Action<string, bool>? TranscriptChanged;

    /// <summary>UI helper: fired on errors so the host can show a
    /// toast or message box.</summary>
    public event Action<Exception>? ErrorOccurred;

    public bool IsRunning => _running;

    public VoiceTypingOrchestrator(
        AudioCaptureService audio,
        StreamingSttService stt,
        TextInjectionService typer)
    {
        _audio = audio;
        _stt = stt;
        _typer = typer;

        _audio.AudioReceived += OnAudioReceived;
        _audio.ErrorOccurred += RaiseError;
        _stt.TranscriptUpdated += OnTranscript;
        _stt.ErrorOccurred += RaiseError;
    }

    public async Task StartAsync(string languageCode)
    {
        if (_running) return;
        _typedInterim = string.Empty;

        DiagLog.Write($"[Orch] StartAsync({languageCode}) — bringing STT + Audio up");
        try
        {
            await _stt.StartAsync(languageCode);
            _audio.Start();
            _running = true;
            DiagLog.Write("[Orch] Session armed; awaiting first transcript");
        }
        catch (Exception ex)
        {
            DiagLog.Write($"[Orch] StartAsync FAILED: {ex.GetType().Name}: {ex.Message}");
            RaiseError(ex);
            await StopAsync();
        }
    }

    public async Task StopAsync()
    {
        if (!_running && _stt.IsActive == false) return;
        _audio.Stop();
        await _stt.StopAsync();
        _running = false;

        // Flush any remaining interim by treating it as final — type
        // a trailing space so the next session starts cleanly.
        if (!string.IsNullOrEmpty(_typedInterim))
        {
            await DispatchAsync(() => _typer.TypeText(" "));
            _typedInterim = string.Empty;
        }
    }

    private async void OnAudioReceived(byte[] data)
    {
        // SendAudioAsync is fire-and-forget from the audio callback's
        // perspective — we don't want to back up the NAudio buffer
        // pump if gRPC has a momentary stall.
        try { await _stt.SendAudioAsync(data); }
        catch (Exception ex) { RaiseError(ex); }
    }

    private void OnTranscript(string newInterim, bool isFinal)
    {
        TranscriptChanged?.Invoke(newInterim, isFinal);

        // The Win32 SendInput call has to happen on the UI thread so
        // it interleaves cleanly with the user's other input. The
        // gRPC reader fires on a threadpool thread, so we marshal.
        _ = DispatchAsync(() => ApplyInterim(newInterim, isFinal));
    }

    private void ApplyInterim(string newInterim, bool isFinal)
    {
        // Compute the diff between what we've already typed and the
        // new candidate. Common-prefix length tells us how many
        // characters need to be removed from the previously-typed
        // interim and how many to type fresh from the new one.
        int common = CommonPrefixLength(_typedInterim, newInterim);
        int toBackspace = _typedInterim.Length - common;
        string toType = newInterim.Substring(common);

        if (toBackspace > 0) _typer.Backspace(toBackspace);
        if (toType.Length > 0) _typer.TypeText(toType);

        _typedInterim = newInterim;

        if (isFinal)
        {
            // Commit: trailing space, reset diff baseline. The next
            // utterance starts a brand new diff against empty —
            // Google can't retract anything from before the final
            // marker.
            _typer.TypeText(" ");
            _typedInterim = string.Empty;
        }
    }

    private static int CommonPrefixLength(string a, string b)
    {
        int max = Math.Min(a.Length, b.Length);
        int i = 0;
        while (i < max && a[i] == b[i]) i++;
        return i;
    }

    private static Task DispatchAsync(Action a)
    {
        var app = Application.Current;
        if (app is null)
        {
            a();
            return Task.CompletedTask;
        }
        return app.Dispatcher.InvokeAsync(a).Task;
    }

    private void RaiseError(Exception ex) => ErrorOccurred?.Invoke(ex);

    public void Dispose()
    {
        try { StopAsync().GetAwaiter().GetResult(); } catch { }
        _audio.Dispose();
        _stt.Dispose();
    }
}
