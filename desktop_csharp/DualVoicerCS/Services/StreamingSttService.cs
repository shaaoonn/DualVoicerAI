using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Whisper.net;

namespace DualVoicerCS.Services;

/// <summary>
/// Local pseudo-streaming speech-to-text via Whisper.net (whisper.cpp).
///
/// Why Whisper.net replaced the original Vosk plan: the user wanted
/// no-cloud setup, but the classic Bengali Vosk model has been
/// withdrawn from alphacephei.com (only the new ONNX-streaming
/// variant remains, which the Vosk-0.3.38 NuGet package doesn't
/// support yet). Whisper.net wraps whisper.cpp and ships
/// multilingual ggml models that handle Bengali AND English in a
/// single model file — exactly the offline-Bengali path we need.
///
/// ── Streaming model (and its honest limits) ──────────────────
///
/// Whisper is fundamentally a 30-second-window model: it was
/// designed for offline transcription of audio files, not for
/// real-time word-by-word emission. We approximate live streaming
/// via the sliding-window pattern from the Whisper.cpp examples:
///
/// <list type="number">
///   <item>Audio chunks from the mic accumulate into an in-memory
///         buffer.</item>
///   <item>A worker task ticks every <see cref="InferenceIntervalMs"/>
///         (~1500 ms) and re-runs Whisper on a sliding window of the
///         most recent <see cref="WindowSeconds"/> seconds of audio.</item>
///   <item>The recogniser yields one or more <c>SegmentData</c>
///         items per window. We concatenate them into the current
///         interim transcript and raise <see cref="TranscriptUpdated"/>
///         (isFinal=false). The interim-diff state machine in
///         <see cref="VoiceTypingOrchestrator"/> takes care of
///         emitting only the new characters to the focused window.</item>
///   <item>On <see cref="StopAsync"/> we run one last Whisper pass
///         over the full buffer and emit the result as
///         isFinal=true so the orchestrator commits the segment
///         (trailing space, reset diff baseline).</item>
/// </list>
///
/// Net felt latency: the first words usually appear ~1-1.5 seconds
/// after the user starts speaking, with continuous updates every
/// 1.5 seconds afterwards. Not the 200 ms feel of Vosk-streaming,
/// but a clear win over the Python widget's chunk-then-send model
/// (which incurs the same Whisper-style delay AND waits for the
/// user to stop speaking before sending anything).
///
/// ── Audio format ─────────────────────────────────────────────
///
/// NAudio gives us 16-bit signed PCM at 16 kHz mono — exactly what
/// Whisper accepts via WAV-stream input. We prepend a small RIFF/
/// fmt/data header (44 bytes) to the buffer snapshot each tick and
/// hand the in-memory WAV to <see cref="WhisperProcessor.ProcessAsync"/>.
/// </summary>
public sealed class StreamingSttService : IDisposable
{
    public const string LanguageBengaliBangladesh = "bn-BD";
    public const string LanguageBengaliIndia      = "bn-IN";
    public const string LanguageEnglishUS         = "en-US";
    public const string LanguageEnglishIN         = "en-IN";

    /// <summary>How often the worker re-runs Whisper while the user
    /// is speaking. Lower = more interim updates but more CPU.</summary>
    private const int InferenceIntervalMs = 1500;

    /// <summary>Sliding-window length. Whisper handles longer
    /// windows fine, but 30+ seconds per inference gets expensive
    /// on CPU. We cap at 20 s and rely on the FINAL pass at stop
    /// time to catch anything older still in the buffer.</summary>
    private const int WindowSeconds = 20;

    public event Action<string, bool>? TranscriptUpdated;
    public event Action<Exception>? ErrorOccurred;

    private WhisperFactory? _factory;
    private WhisperProcessor? _processor;

    private readonly object _bufferLock = new();
    private readonly List<byte> _audioBuffer = new(capacity: 16000 * 2 * 30); // 30s headroom
    private string _lastInterim = string.Empty;
    private CancellationTokenSource? _cts;
    private Task? _inferenceTask;

    public bool IsActive => _processor is not null;

    public async Task StartAsync(string languageCode)
    {
        if (_processor is not null)
            throw new InvalidOperationException("STT processor already active");

        try
        {
            DiagLog.Write($"[STT] StartAsync requested language={languageCode}");
            var modelPath = ResolveModelPath();
            DiagLog.Write($"[STT] Loading model: {modelPath}");
            var sw = System.Diagnostics.Stopwatch.StartNew();
            _factory = WhisperFactory.FromPath(modelPath);
            sw.Stop();
            DiagLog.Write($"[STT] Model loaded in {sw.ElapsedMilliseconds} ms");

            // Whisper expects a 2-letter ISO 639-1 code, not BCP-47.
            // Map our app-internal codes (bn-BD, en-US, etc) by
            // taking the family prefix.
            var lang = languageCode.Split('-')[0].ToLowerInvariant();

            _processor = _factory.CreateBuilder()
                .WithLanguage(lang)
                // SingleSegment=false lets Whisper emit multiple
                // segments per inference, which keeps interim
                // updates flowing for long utterances.
                .Build();

            _audioBuffer.Clear();
            _lastInterim = string.Empty;
            _cts = new CancellationTokenSource();
            _inferenceTask = Task.Run(() => InferenceLoop(_cts.Token));
            DiagLog.Write($"[STT] Processor ready, inference loop started (tick every {InferenceIntervalMs} ms)");
        }
        catch (Exception ex)
        {
            DiagLog.Write($"[STT] StartAsync FAILED: {ex.GetType().Name}: {ex.Message}");
            ErrorOccurred?.Invoke(ex);
            await StopAsync();
            throw;
        }
    }

    public Task SendAudioAsync(byte[] audioData)
    {
        if (_processor is null) return Task.CompletedTask;
        lock (_bufferLock)
        {
            _audioBuffer.AddRange(audioData);
        }
        return Task.CompletedTask;
    }

    public async Task StopAsync()
    {
        if (_processor is null && _factory is null && _cts is null)
            return;

        // Cancel the periodic worker and wait for it to drain.
        _cts?.Cancel();
        if (_inferenceTask is not null)
        {
            try { await _inferenceTask; }
            catch (OperationCanceledException) { }
        }

        // One last pass over the full buffer so we don't lose the
        // tail of what the user was saying. Emit as FINAL so the
        // orchestrator commits the segment and resets its diff.
        try
        {
            byte[] snapshot;
            lock (_bufferLock)
            {
                snapshot = _audioBuffer.ToArray();
                _audioBuffer.Clear();
            }
            if (_processor is not null && snapshot.Length >= 16000) // >= 0.5 s
            {
                var text = await TranscribeOnce(snapshot);
                if (!string.IsNullOrWhiteSpace(text))
                    TranscriptUpdated?.Invoke(text, true);
            }
        }
        catch (Exception ex)
        {
            ErrorOccurred?.Invoke(ex);
        }
        finally
        {
            _processor?.Dispose();
            _factory?.Dispose();
            _processor = null;
            _factory = null;
            _cts?.Dispose();
            _cts = null;
            _inferenceTask = null;
            _lastInterim = string.Empty;
        }
    }

    private async Task InferenceLoop(CancellationToken ct)
    {
        try
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    await Task.Delay(InferenceIntervalMs, ct);
                }
                catch (OperationCanceledException) { return; }

                // Take a snapshot of the most recent window of audio.
                byte[] snapshot;
                lock (_bufferLock)
                {
                    int windowBytes = WindowSeconds
                        * AudioCaptureService.SampleRateHz
                        * AudioCaptureService.ChannelCount
                        * (AudioCaptureService.BitsPerSample / 8);
                    int start = Math.Max(0, _audioBuffer.Count - windowBytes);
                    int len = _audioBuffer.Count - start;
                    if (len < AudioCaptureService.SampleRateHz) // <0.5s — nothing useful
                        continue;
                    snapshot = new byte[len];
                    _audioBuffer.CopyTo(start, snapshot, 0, len);
                }

                DiagLog.Write($"[STT] Inference tick: window={snapshot.Length} bytes (~{snapshot.Length / 32000.0:F1} s)");
                var swTick = System.Diagnostics.Stopwatch.StartNew();
                var text = await TranscribeOnce(snapshot);
                swTick.Stop();
                DiagLog.Write($"[STT] Transcribe took {swTick.ElapsedMilliseconds} ms, text={(text.Length > 80 ? text.Substring(0, 80) + "…" : text)}");
                if (string.IsNullOrWhiteSpace(text)) continue;
                if (text == _lastInterim) continue;

                _lastInterim = text;
                TranscriptUpdated?.Invoke(text, false);
            }
        }
        catch (Exception ex) when (ex is not OperationCanceledException)
        {
            ErrorOccurred?.Invoke(ex);
        }
    }

    private async Task<string> TranscribeOnce(byte[] pcm16kMono16bit)
    {
        var processor = _processor;
        if (processor is null) return string.Empty;

        // Whisper.net's stream API accepts a WAV-formatted stream
        // (RIFF/fmt/data). Build one in-memory from the PCM buffer.
        using var ms = new MemoryStream(pcm16kMono16bit.Length + 44);
        WriteWavHeader(ms, pcm16kMono16bit.Length);
        ms.Write(pcm16kMono16bit, 0, pcm16kMono16bit.Length);
        ms.Position = 0;

        var combined = new System.Text.StringBuilder();
        await foreach (var segment in processor.ProcessAsync(ms))
        {
            // Concatenate all segments produced by this pass.
            // Whisper may split a long utterance into 2-3 segments;
            // joining them gives a single coherent interim string
            // for the diff state machine to operate on.
            if (combined.Length > 0) combined.Append(' ');
            combined.Append(segment.Text.Trim());
        }
        return combined.ToString();
    }

    private static void WriteWavHeader(Stream s, int pcmByteCount)
    {
        const int sampleRate = AudioCaptureService.SampleRateHz;
        const int channels   = AudioCaptureService.ChannelCount;
        const int bitsPer    = AudioCaptureService.BitsPerSample;
        int byteRate   = sampleRate * channels * (bitsPer / 8);
        int blockAlign = channels * (bitsPer / 8);

        Span<byte> hdr = stackalloc byte[44];
        // "RIFF"
        hdr[0] = 0x52; hdr[1] = 0x49; hdr[2] = 0x46; hdr[3] = 0x46;
        // chunk size = 36 + data size
        BinaryPrimitives.WriteUInt32LittleEndian(hdr.Slice(4, 4),
            (uint)(36 + pcmByteCount));
        // "WAVE"
        hdr[8] = 0x57; hdr[9] = 0x41; hdr[10] = 0x56; hdr[11] = 0x45;
        // "fmt "
        hdr[12] = 0x66; hdr[13] = 0x6D; hdr[14] = 0x74; hdr[15] = 0x20;
        BinaryPrimitives.WriteUInt32LittleEndian(hdr.Slice(16, 4), 16);   // fmt chunk size
        BinaryPrimitives.WriteUInt16LittleEndian(hdr.Slice(20, 2), 1);    // PCM
        BinaryPrimitives.WriteUInt16LittleEndian(hdr.Slice(22, 2),
            (ushort)channels);
        BinaryPrimitives.WriteUInt32LittleEndian(hdr.Slice(24, 4),
            (uint)sampleRate);
        BinaryPrimitives.WriteUInt32LittleEndian(hdr.Slice(28, 4),
            (uint)byteRate);
        BinaryPrimitives.WriteUInt16LittleEndian(hdr.Slice(32, 2),
            (ushort)blockAlign);
        BinaryPrimitives.WriteUInt16LittleEndian(hdr.Slice(34, 2),
            (ushort)bitsPer);
        // "data"
        hdr[36] = 0x64; hdr[37] = 0x61; hdr[38] = 0x74; hdr[39] = 0x61;
        BinaryPrimitives.WriteUInt32LittleEndian(hdr.Slice(40, 4),
            (uint)pcmByteCount);

        s.Write(hdr);
    }

    private static string ResolveModelPath()
    {
        var baseDir = AppContext.BaseDirectory;
        var modelsRoot = Path.Combine(baseDir, "models");

        // Pick whichever ggml-*.bin the user dropped in. README
        // suggests ggml-base.bin (~142 MB) as the default but ggml-
        // small.bin (~466 MB) gives noticeably better Bengali.
        if (Directory.Exists(modelsRoot))
        {
            foreach (var preferred in new[]
            {
                "ggml-small.bin",
                "ggml-base.bin",
                "ggml-tiny.bin",
            })
            {
                var path = Path.Combine(modelsRoot, preferred);
                if (File.Exists(path)) return path;
            }
            // Fallback to any ggml-*.bin
            foreach (var path in Directory.EnumerateFiles(modelsRoot, "ggml-*.bin"))
                return path;
        }

        throw new FileNotFoundException(
            $"No Whisper model found under '{modelsRoot}'.\n\n" +
            "Download a multilingual ggml model from\n" +
            "  https://huggingface.co/ggerganov/whisper.cpp/tree/main\n" +
            $"and save it as '{Path.Combine(modelsRoot, "ggml-base.bin")}'.\n" +
            "(README has direct download URLs and size guidance.)");
    }

    public void Dispose()
    {
        try { StopAsync().GetAwaiter().GetResult(); } catch { }
    }
}
