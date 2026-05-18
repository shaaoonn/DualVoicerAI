using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace DualVoicerCS.Services;

/// <summary>
/// Speech-to-text via Google's free unofficial
/// <c>/speech-api/v2/recognize</c> endpoint — the exact same one the
/// Python <c>speech_recognition</c> library uses against the public
/// Chromium API key.
///
/// Why we ended up here:
///
/// <list type="bullet">
///   <item>The initial PoC used Vosk locally — no setup, true
///         streaming — but Vosk doesn't have an official Bengali
///         model on AlphaCephei's release page, and bn-* support
///         in the small Whisper alternatives was poor.</item>
///   <item>The second iteration used Whisper.net with
///         ggml-base.bin (142 MB multilingual). It worked, but the
///         user tested Bengali speech and got Arabic-script output
///         instead — a known failure mode of the smaller Whisper
///         models which conflate Indic and Semitic scripts when
///         the audio is short or noisy.</item>
///   <item>The Python build the user is migrating from uses
///         Google's free unofficial endpoint via the same hardcoded
///         Chromium-extracted key. Quality is excellent for
///         Bengali, English, and 100+ other languages — and the
///         user is already familiar with the response pattern
///         (click → talk → click → text appears within ~1 s).</item>
/// </list>
///
/// ── Differences vs the previous Whisper streaming approach ────
///
/// The Google endpoint is NOT a true streaming API; each HTTP POST
/// carries a complete utterance and returns a final transcript.
/// To preserve the "real-time-ish" feel the user expects we do
/// our own VAD-based chunking: silence longer than ~1.2 s splits
/// the running buffer into a chunk, which fires off to Google
/// asynchronously while we keep listening. The orchestrator's
/// diff state machine treats every chunk's result as <c>isFinal=true</c>
/// so the typer commits and resets per chunk — no interim retraction
/// needed.
///
/// Trade-off the user has accepted: 0.5–1.5 s latency per chunk
/// (network round-trip + Google's recognition) in exchange for
/// the accuracy boost. The Python build has the same latency for
/// the same reason.
/// </summary>
public sealed class StreamingSttService : IDisposable
{
    public const string LanguageBengaliBangladesh = "bn-BD";
    public const string LanguageBengaliIndia      = "bn-IN";
    public const string LanguageEnglishUS         = "en-US";
    public const string LanguageEnglishIN         = "en-IN";

    // Chromium-extracted public API key. Google rate-limits it
    // (~50 requests/hour observed in practice) but it's the same
    // key the entire Python speech_recognition ecosystem leans on
    // and works reliably for moderate dictation use.
    private const string GoogleKey = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw";

    // RMS threshold below which a 100 ms PCM chunk counts as
    // silence. PCM samples normalised to [-1, 1] before RMS — so
    // 0.008 corresponds to a very quiet but non-zero microphone
    // floor. Lower → more aggressive chunking (catches quiet
    // voices); higher → ignores room noise but cuts off whispers.
    private const double SilenceRmsThreshold = 0.008;

    // Continuous silence ≥ this many ms after we've already heard
    // voice → flush the accumulated buffer as one chunk to Google.
    // User feedback after the first working build: "typing speed is
    // slow." Originally 1200 ms — felt sluggish because the user has
    // to perceive both the pause threshold AND the network round
    // trip before text appears. Dropped to 700 ms, which still
    // tolerates natural mid-sentence breaths (those are usually
    // ≤ 400 ms) but cuts ~500 ms off the perceived end-of-sentence
    // latency. Combined with the ~600-1100 ms Google round-trip, the
    // visible "click → finish sentence → see typing" delay is now
    // around 1.3 s instead of 1.8.
    private const int SilenceMsForChunkBreak = 700;

    // Hard ceiling per chunk so a non-stop talker doesn't blow
    // past Google's per-request audio length limit (~1 minute,
    // but quality degrades well before that).
    private const int MaxChunkMs = 12000;

    public event Action<string, bool>? TranscriptUpdated;
    public event Action<Exception>? ErrorOccurred;

    private readonly HttpClient _http;
    private readonly List<byte> _audioBuffer = new();
    private readonly object _lock = new();
    private string _language = LanguageBengaliBangladesh;
    private DateTime _lastVoiceTime = DateTime.MinValue;
    private bool _hasVoice;
    private bool _active;

    public StreamingSttService()
    {
        _http = new HttpClient
        {
            // Worst-case Google round-trip we've seen is ~5 s on a
            // slow connection. 20 s gives generous headroom; if it
            // really times out the orchestrator surfaces the error
            // and the user can retry.
            Timeout = TimeSpan.FromSeconds(20),
        };
    }

    public bool IsActive => _active;

    public Task StartAsync(string languageCode)
    {
        DiagLog.Write($"[STT] StartAsync language={languageCode} (Google free endpoint)");
        lock (_lock)
        {
            _language = languageCode;
            _audioBuffer.Clear();
            _hasVoice = false;
            _active = true;
        }
        return Task.CompletedTask;
    }

    public Task SendAudioAsync(byte[] data)
    {
        if (!_active) return Task.CompletedTask;

        double rms = ComputeRms(data);
        bool isVoice = rms > SilenceRmsThreshold;
        byte[]? chunkToSend = null;

        lock (_lock)
        {
            // Only start accumulating once we hear actual voice —
            // saves Google a roundtrip on every silent gap before
            // the user starts talking.
            if (isVoice || _hasVoice)
            {
                _audioBuffer.AddRange(data);
                if (isVoice)
                {
                    _lastVoiceTime = DateTime.UtcNow;
                    _hasVoice = true;
                }
            }

            if (_hasVoice)
            {
                double silenceMs = (DateTime.UtcNow - _lastVoiceTime).TotalMilliseconds;
                double bufferMs = _audioBuffer.Count / 32.0; // bytes / 32 (16 kHz × 2 bytes × 1 ch / 1000 ms)

                if (silenceMs > SilenceMsForChunkBreak || bufferMs > MaxChunkMs)
                {
                    chunkToSend = _audioBuffer.ToArray();
                    _audioBuffer.Clear();
                    _hasVoice = false;
                }
            }
        }

        if (chunkToSend is not null)
        {
            // Fire-and-forget — don't block the audio capture thread
            // waiting on Google's HTTP round-trip. Multiple chunks
            // can be in-flight concurrently; for ~1 s pauses between
            // chunks they tend to arrive back in order, but if not
            // the orchestrator still types them in the order Google
            // responds — acceptable for a PoC.
            _ = TranscribeChunkAsync(chunkToSend);
        }

        return Task.CompletedTask;
    }

    public async Task StopAsync()
    {
        byte[]? finalChunk = null;
        lock (_lock)
        {
            _active = false;
            // Capture any tail audio (the user clicked stop mid-
            // sentence) and send it to Google so we don't lose
            // the last few words.
            if (_hasVoice && _audioBuffer.Count >= 16000) // ≥ 0.5 s
            {
                finalChunk = _audioBuffer.ToArray();
            }
            _audioBuffer.Clear();
            _hasVoice = false;
        }

        if (finalChunk is not null)
        {
            await TranscribeChunkAsync(finalChunk);
        }
        DiagLog.Write("[STT] StopAsync done");
    }

    private async Task TranscribeChunkAsync(byte[] pcmData)
    {
        try
        {
            var seconds = pcmData.Length / 32000.0;
            DiagLog.Write($"[STT] Posting chunk: {pcmData.Length} bytes (~{seconds:F2} s) lang={_language}");

            // We first send RAW Linear16 PCM with the
            // `audio/l16; rate=16000` content type. The first
            // attempt with `audio/x-wav` returned 400 — the
            // unofficial endpoint apparently doesn't parse RIFF
            // containers, only the formats Chromium itself emits.
            // Python's speech_recognition uses FLAC but encoding
            // FLAC in pure managed C# would require either a
            // bundled libFLAC native DLL or hundreds of lines of
            // custom bit-packing code. Raw l16 is documented to
            // work for the chromium client and avoids the whole
            // encoder problem.
            //
            // Important: the URL is HTTP (matches Python upstream);
            // switching to HTTPS earlier caused the same 400 in
            // some quick smoke tests because the SSL endpoint
            // honours stricter audio-format validation.
            var url = "http://www.google.com/speech-api/v2/recognize" +
                $"?client=chromium" +
                $"&lang={Uri.EscapeDataString(_language)}" +
                $"&key={GoogleKey}" +
                $"&pFilter=0";

            using var content = new ByteArrayContent(pcmData);
            content.Headers.Add("Content-Type", "audio/l16; rate=16000");

            var sw = System.Diagnostics.Stopwatch.StartNew();
            using var response = await _http.PostAsync(url, content);
            sw.Stop();

            var body = await response.Content.ReadAsStringAsync();
            DiagLog.Write($"[STT] Google replied in {sw.ElapsedMilliseconds} ms, status={(int)response.StatusCode}, body={body.Length} chars");

            if (!response.IsSuccessStatusCode)
            {
                DiagLog.Write($"[STT] Body on error: {Trim(body, 400)}");
                ErrorOccurred?.Invoke(new HttpRequestException(
                    $"Google STT returned {response.StatusCode}: {Trim(body, 200)}"));
                return;
            }

            var transcript = ExtractFirstTranscript(body);
            if (string.IsNullOrWhiteSpace(transcript))
            {
                DiagLog.Write("[STT] No transcript in response (audio too quiet / unclear / rate-limited)");
                return;
            }

            DiagLog.Write($"[STT] Transcribed: {transcript}");
            // Action<string, bool> doesn't have named params — pass
            // the isFinal flag positionally (true = "this chunk is
            // closed, never revisited").
            TranscriptUpdated?.Invoke(transcript, true);
        }
        catch (Exception ex)
        {
            DiagLog.Write($"[STT] TranscribeChunkAsync FAILED: {ex.GetType().Name}: {ex.Message}");
            ErrorOccurred?.Invoke(ex);
        }
    }

    /// <summary>
    /// Google's response is a series of JSON objects separated by
    /// newlines. The first is usually <c>{"result":[]}</c> (empty
    /// placeholder); subsequent lines carry
    /// <c>{"result":[{"alternative":[{"transcript":"…"}], "final":true}]}</c>.
    /// We scan every line and return the first non-empty transcript.
    /// </summary>
    private static string ExtractFirstTranscript(string body)
    {
        foreach (var line in body.Split('\n'))
        {
            if (string.IsNullOrWhiteSpace(line)) continue;
            try
            {
                using var doc = JsonDocument.Parse(line);
                if (!doc.RootElement.TryGetProperty("result", out var results)) continue;
                if (results.ValueKind != JsonValueKind.Array || results.GetArrayLength() == 0) continue;

                foreach (var r in results.EnumerateArray())
                {
                    if (!r.TryGetProperty("alternative", out var alts)) continue;
                    if (alts.ValueKind != JsonValueKind.Array || alts.GetArrayLength() == 0) continue;

                    var first = alts[0];
                    if (first.TryGetProperty("transcript", out var t)
                        && t.ValueKind == JsonValueKind.String)
                    {
                        return t.GetString() ?? string.Empty;
                    }
                }
            }
            catch (JsonException) { /* skip malformed line */ }
        }
        return string.Empty;
    }

    private static double ComputeRms(byte[] pcm16)
    {
        if (pcm16.Length < 2) return 0;
        long sumSq = 0;
        int count = pcm16.Length / 2;
        for (int i = 0; i + 1 < pcm16.Length; i += 2)
        {
            short sample = (short)((pcm16[i + 1] << 8) | pcm16[i]);
            sumSq += sample * sample;
        }
        double meanSq = (double)sumSq / count;
        return Math.Sqrt(meanSq) / 32768.0;
    }

    private static byte[] WrapPcmAsWav(byte[] pcm, int sampleRate, int channels, int bitsPerSample)
    {
        int byteRate = sampleRate * channels * bitsPerSample / 8;
        short blockAlign = (short)(channels * bitsPerSample / 8);

        using var ms = new MemoryStream(44 + pcm.Length);
        using var bw = new BinaryWriter(ms);
        bw.Write(Encoding.ASCII.GetBytes("RIFF"));
        bw.Write(36 + pcm.Length);          // chunk size
        bw.Write(Encoding.ASCII.GetBytes("WAVE"));
        bw.Write(Encoding.ASCII.GetBytes("fmt "));
        bw.Write(16);                       // PCM fmt chunk size
        bw.Write((short)1);                 // PCM format tag
        bw.Write((short)channels);
        bw.Write(sampleRate);
        bw.Write(byteRate);
        bw.Write(blockAlign);
        bw.Write((short)bitsPerSample);
        bw.Write(Encoding.ASCII.GetBytes("data"));
        bw.Write(pcm.Length);
        bw.Write(pcm);
        return ms.ToArray();
    }

    private static string Trim(string s, int max) =>
        s.Length <= max ? s : s.Substring(0, max) + "…";

    public void Dispose()
    {
        try { StopAsync().GetAwaiter().GetResult(); } catch { }
        _http.Dispose();
    }
}
