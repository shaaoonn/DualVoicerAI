using System;
using NAudio.Wave;

namespace DualVoicerCS.Services;

/// <summary>
/// Microphone capture pipeline tuned for Google Cloud STT v1.
///
/// Google's streaming endpoint accepts LINEAR16 PCM at 16 kHz mono.
/// We open the default input device with exactly that format so we
/// can hand the raw <c>byte[]</c> buffer straight through to the
/// gRPC stream — no resampling, no format conversion. BufferMs of
/// 100 means we emit ~10 buffers per second, each carrying 3200
/// bytes (16000 samples × 2 bytes ÷ 10), which is well under the
/// STT API's 25 KB per-message cap.
///
/// This is the C# counterpart to the Python pipeline's
/// <c>speech_recognition.Microphone</c> + chunk-based STT call.
/// The difference: we no longer accumulate-then-send; every 100 ms
/// chunk goes out immediately so Google can stream interim
/// hypotheses back as they're recognised.
/// </summary>
public sealed class AudioCaptureService : IDisposable
{
    public const int SampleRateHz = 16000;
    public const int ChannelCount = 1;
    public const int BitsPerSample = 16;

    private WaveInEvent? _waveIn;

    /// <summary>
    /// Fires every BufferMs (~100 ms) with the raw PCM bytes that
    /// were just captured. The byte[] is a fresh copy — safe to send
    /// across threads / await calls without worrying about NAudio
    /// reusing the buffer.
    /// </summary>
    public event Action<byte[]>? AudioReceived;

    /// <summary>Fired if NAudio reports an internal error so the
    /// orchestrator can surface it to the user.</summary>
    public event Action<Exception>? ErrorOccurred;

    public bool IsRecording => _waveIn is not null;

    public void Start()
    {
        if (_waveIn is not null) return;

        _waveIn = new WaveInEvent
        {
            WaveFormat = new WaveFormat(SampleRateHz, BitsPerSample, ChannelCount),
            BufferMilliseconds = 100,
            NumberOfBuffers = 3, // small queue so latency stays sub-200ms
        };

        _waveIn.DataAvailable += (_, e) =>
        {
            // Copy out of NAudio's reusable buffer before raising.
            var copy = new byte[e.BytesRecorded];
            Buffer.BlockCopy(e.Buffer, 0, copy, 0, e.BytesRecorded);
            AudioReceived?.Invoke(copy);
        };

        _waveIn.RecordingStopped += (_, e) =>
        {
            if (e.Exception is not null)
                ErrorOccurred?.Invoke(e.Exception);
            _waveIn?.Dispose();
            _waveIn = null;
        };

        _waveIn.StartRecording();
    }

    public void Stop()
    {
        _waveIn?.StopRecording();
        // Dispose happens in the RecordingStopped handler so we don't
        // tear down NAudio mid-buffer-callback.
    }

    public void Dispose()
    {
        Stop();
        _waveIn?.Dispose();
        _waveIn = null;
    }
}
