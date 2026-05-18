using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace DualVoicerCS.Services;

/// <summary>
/// Send Unicode characters and backspace strokes to whatever window
/// currently has focus, via Win32 <c>SendInput</c>.
///
/// We use <c>KEYEVENTF_UNICODE</c> + <c>VK = 0</c> instead of trying
/// to translate each char to a virtual-key — that's what makes
/// Bengali matras and ligatures arrive intact in apps that accept
/// WM_CHAR (Notepad, browsers, Word, etc). The receiving app sees a
/// proper WM_CHAR / WM_UNICHAR pair per codepoint and renders via
/// its normal font stack — no codepage juggling, no IME involvement.
///
/// Caveats this PoC accepts:
/// <list type="bullet">
///   <item>Surrogate-pair codepoints (e.g. emoji outside the BMP)
///         need to be sent as two separate INPUTs. Bengali script
///         lives entirely in U+0980–U+09FF inside the BMP, so this
///         doesn't matter for our primary use case.</item>
///   <item>Some games / fullscreen DirectInput apps don't accept
///         SendInput keystrokes. The Python widget had the same
///         limitation — we'd fall back to clipboard-paste only for
///         those, but the PoC doesn't bother.</item>
/// </list>
/// </summary>
public sealed class TextInjectionService
{
    // ── Win32 plumbing ────────────────────────────────────────────

    private const uint INPUT_KEYBOARD = 1;
    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const uint KEYEVENTF_UNICODE = 0x0004;
    private const ushort VK_BACK = 0x08;

    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT
    {
        public uint type;
        public InputUnion U;
        public static int Size => Marshal.SizeOf<INPUT>();
    }

    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)] public KEYBDINPUT ki;
        [FieldOffset(0)] public MOUSEINPUT mi;
        [FieldOffset(0)] public HARDWAREINPUT hi;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT
    {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MOUSEINPUT
    {
        public int dx;
        public int dy;
        public uint mouseData;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct HARDWAREINPUT
    {
        public uint uMsg;
        public ushort wParamL;
        public ushort wParamH;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder lpString, int nMaxCount);

    /// <summary>Returns the title of whichever window currently
    /// owns the keyboard focus — used purely for diagnostic logging
    /// so we can confirm SendInput is hitting the user's target app
    /// (Notepad/browser/etc) and not stealing into our own widget.</summary>
    public static string GetForegroundWindowTitle()
    {
        try
        {
            var hwnd = GetForegroundWindow();
            if (hwnd == IntPtr.Zero) return "(none)";
            var sb = new System.Text.StringBuilder(256);
            GetWindowText(hwnd, sb, sb.Capacity);
            return $"hwnd={hwnd:X} title='{sb}'";
        }
        catch { return "(query failed)"; }
    }

    // ── Public API ────────────────────────────────────────────────

    /// <summary>Send each character in <paramref name="text"/> to
    /// the focused window. No-op for empty / null input.</summary>
    public void TypeText(string text)
    {
        if (string.IsNullOrEmpty(text)) return;

        var inputs = new List<INPUT>(text.Length * 2);
        foreach (char c in text)
        {
            inputs.Add(MakeUnicodeKey(c, keyUp: false));
            inputs.Add(MakeUnicodeKey(c, keyUp: true));
        }
        var fg = GetForegroundWindowTitle();
        uint sent = SendInput((uint)inputs.Count, inputs.ToArray(), INPUT.Size);
        DiagLog.Write($"[Typer] TypeText({text.Length} chars) → sent {sent}/{inputs.Count}, fg={fg}");
    }

    /// <summary>Press Backspace <paramref name="count"/> times in
    /// the focused window.</summary>
    public void Backspace(int count)
    {
        if (count <= 0) return;

        var inputs = new List<INPUT>(count * 2);
        for (int i = 0; i < count; i++)
        {
            inputs.Add(MakeVirtualKey(VK_BACK, keyUp: false));
            inputs.Add(MakeVirtualKey(VK_BACK, keyUp: true));
        }
        uint sent = SendInput((uint)inputs.Count, inputs.ToArray(), INPUT.Size);
        DiagLog.Write($"[Typer] Backspace({count}) → SendInput sent {sent}/{inputs.Count} events");
    }

    private static INPUT MakeUnicodeKey(char c, bool keyUp) => new()
    {
        type = INPUT_KEYBOARD,
        U = new InputUnion
        {
            ki = new KEYBDINPUT
            {
                wVk = 0,
                wScan = c,
                dwFlags = KEYEVENTF_UNICODE | (keyUp ? KEYEVENTF_KEYUP : 0),
                time = 0,
                dwExtraInfo = IntPtr.Zero,
            },
        },
    };

    private static INPUT MakeVirtualKey(ushort vk, bool keyUp) => new()
    {
        type = INPUT_KEYBOARD,
        U = new InputUnion
        {
            ki = new KEYBDINPUT
            {
                wVk = vk,
                wScan = 0,
                dwFlags = keyUp ? KEYEVENTF_KEYUP : 0,
                time = 0,
                dwExtraInfo = IntPtr.Zero,
            },
        },
    };
}
