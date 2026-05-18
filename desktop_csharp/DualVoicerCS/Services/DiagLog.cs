using System;
using System.IO;

namespace DualVoicerCS.Services;

/// <summary>
/// Append-only diagnostic log writer.
///
/// PoC has no settings UI for logging level / output target, so we
/// pin one shared log file at <c>%APPDATA%/DualVoicerCS/debug.log</c>
/// and dump every event there with a millisecond timestamp. Cheap
/// to call from any thread; failures are swallowed because the
/// alternative (an exception bubbling out of a logging call) would
/// hurt more than the missed log line.
///
/// Why a static class and not <c>Microsoft.Extensions.Logging</c>:
/// the PoC doesn't have a host builder. For a PoC, keeping log
/// plumbing to ~20 lines is the right call; the full port can swap
/// in proper logging when it adds DI.
/// </summary>
public static class DiagLog
{
    private static readonly object _lock = new();
    private static readonly string _path;

    static DiagLog()
    {
        var dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "DualVoicerCS");
        try
        {
            Directory.CreateDirectory(dir);
        }
        catch { /* swallowed — we'll just write nowhere if this fails */ }
        _path = Path.Combine(dir, "debug.log");

        // Truncate at process start so each run produces a fresh
        // file the user can hand back to us for debugging without
        // wading through history.
        try { File.WriteAllText(_path, $"=== DualVoicerCS started @ {DateTime.Now:O} ===\n"); }
        catch { }
    }

    public static string LogPath => _path;

    public static void Write(string line)
    {
        try
        {
            var stamped = $"[{DateTime.Now:HH:mm:ss.fff}] {line}{Environment.NewLine}";
            lock (_lock)
            {
                File.AppendAllText(_path, stamped);
            }
        }
        catch { /* swallowed */ }
    }
}
