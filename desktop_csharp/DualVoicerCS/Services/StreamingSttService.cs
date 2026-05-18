using System;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using Google.Cloud.Speech.V1;
using Google.Protobuf;

namespace DualVoicerCS.Services;

/// <summary>
/// Google Cloud Speech-to-Text v1 streaming wrapper.
///
/// Architectural shape of the streaming call:
///
/// <pre>
///                 ┌──────────────┐
///   mic bytes ───▶│              │── interim ───▶ UI / typer
///                 │  bidirectional│
///   start/stop ──▶│   gRPC stream │── final  ───▶ UI / typer
///                 │              │── error  ───▶ ErrorOccurred
///                 └──────────────┘
/// </pre>
///
/// Each <see cref="StartAsync(string)"/> opens a new session,
/// pushes a one-shot <c>StreamingConfig</c> message with the
/// language code + interim-results flag, then we feed audio via
/// <see cref="SendAudioAsync"/> as it arrives from the mic.
/// Google sends back a stream of <c>StreamingRecognizeResponse</c>
/// messages — for each one we surface every alternative through
/// <see cref="TranscriptUpdated"/>, tagged as interim or final.
///
/// Single-utterance vs continuous: Google's v1 streaming endpoint
/// has a 5-minute hard limit per session. The PoC is well under
/// that for a click-to-speak flow; for production we'd implement
/// the "stitch sessions" pattern (close + reopen on the silence
/// boundary) used by the Speech sample app.
/// </summary>
public sealed class StreamingSttService : IDisposable
{
    public const string LanguageBengaliBangladesh = "bn-BD";
    public const string LanguageBengaliIndia      = "bn-IN";
    public const string LanguageEnglishUS         = "en-US";
    public const string LanguageEnglishIN         = "en-IN";

    /// <summary>Fired on every transcript update. <c>isFinal</c>
    /// indicates this segment will not be revised — append it and
    /// reset the interim diff state.</summary>
    public event Action<string, bool>? TranscriptUpdated;

    public event Action<Exception>? ErrorOccurred;

    private SpeechClient.StreamingRecognizeStream? _stream;
    private Task? _readerTask;
    private CancellationTokenSource? _cts;

    public bool IsActive => _stream is not null;

    /// <summary>
    /// Open a streaming session. <paramref name="languageCode"/> is
    /// a BCP-47 code like "bn-BD" or "en-US".
    /// </summary>
    public async Task StartAsync(string languageCode)
    {
        if (_stream is not null)
            throw new InvalidOperationException("STT stream already active");

        var client = await BuildClientAsync();
        _stream = client.StreamingRecognize();
        _cts = new CancellationTokenSource();

        await _stream.WriteAsync(new StreamingRecognizeRequest
        {
            StreamingConfig = new StreamingRecognitionConfig
            {
                Config = new RecognitionConfig
                {
                    Encoding = RecognitionConfig.Types.AudioEncoding.Linear16,
                    SampleRateHertz = AudioCaptureService.SampleRateHz,
                    LanguageCode = languageCode,
                    // Punctuation makes the transcript more usable
                    // straight into the typer — same setting our
                    // Python wrapper uses for the v2 unofficial
                    // endpoint.
                    EnableAutomaticPunctuation = true,
                    // Voice typing is mostly conversational; this
                    // model balances Bengali + English well.
                    Model = "latest_long",
                },
                InterimResults = true,
            },
        });

        // Reader runs on the threadpool so SendAudioAsync (which
        // runs on UI thread continuations) never blocks waiting for
        // a response.
        _readerTask = Task.Run(ReadLoopAsync);
    }

    /// <summary>Push a PCM audio chunk into the active session.
    /// Silent no-op if the stream isn't running.</summary>
    public async Task SendAudioAsync(byte[] audioData)
    {
        var stream = _stream;
        if (stream is null) return;
        try
        {
            await stream.WriteAsync(new StreamingRecognizeRequest
            {
                AudioContent = ByteString.CopyFrom(audioData),
            });
        }
        catch (InvalidOperationException)
        {
            // Stream was closed under us — Google will surface the
            // real reason via the reader loop, no need to double-
            // report from here.
        }
    }

    /// <summary>Cleanly close the session and wait for the reader
    /// to drain any in-flight responses.</summary>
    public async Task StopAsync()
    {
        var stream = _stream;
        if (stream is null) return;

        try { await stream.WriteCompleteAsync(); }
        catch (Exception) { /* already closed */ }

        _cts?.Cancel();
        if (_readerTask is not null)
        {
            try { await _readerTask; }
            catch (OperationCanceledException) { }
        }

        _stream = null;
        _readerTask = null;
        _cts?.Dispose();
        _cts = null;
    }

    private async Task ReadLoopAsync()
    {
        var stream = _stream;
        var token = _cts?.Token ?? CancellationToken.None;
        try
        {
            await foreach (var response in stream!.GetResponseStream().WithCancellation(token))
            {
                foreach (var result in response.Results)
                {
                    if (result.Alternatives.Count == 0) continue;
                    var transcript = result.Alternatives[0].Transcript;
                    TranscriptUpdated?.Invoke(transcript, result.IsFinal);
                }
            }
        }
        catch (OperationCanceledException) { /* normal stop */ }
        catch (Exception ex)
        {
            ErrorOccurred?.Invoke(ex);
        }
    }

    /// <summary>
    /// Locate <c>gcp-credentials.json</c> next to the EXE and build
    /// a <see cref="SpeechClient"/> from it. We deliberately don't
    /// fall back to GOOGLE_APPLICATION_CREDENTIALS — for a PoC,
    /// being explicit about where the file lives makes setup
    /// debugging far easier.
    /// </summary>
    private static async Task<SpeechClient> BuildClientAsync()
    {
        var credPath = Path.Combine(AppContext.BaseDirectory, "gcp-credentials.json");
        if (!File.Exists(credPath))
        {
            throw new FileNotFoundException(
                $"Google Cloud credentials not found at {credPath}. " +
                "See README — you need to drop a service account JSON " +
                "there before voice typing will work.");
        }

        // SpeechClientBuilder reads the service account JSON,
        // negotiates the OAuth flow, and hands back a fully-armed
        // gRPC channel. No need to touch Grpc.Auth ourselves.
        var builder = new SpeechClientBuilder
        {
            CredentialsPath = credPath,
        };
        return await builder.BuildAsync();
    }

    public void Dispose()
    {
        try { StopAsync().GetAwaiter().GetResult(); } catch { }
    }
}
