# Dual Voicer CS — Proof of Concept

C# / WPF rewrite spike of Dual Voicer AI, with **real-time word-by-word**
voice typing powered by Google Cloud Speech-to-Text streaming.

## What this PoC actually proves

| Concern | Result |
| --- | --- |
| **Widget look-and-feel** | WPF can reproduce the Python widget's circular gradient buttons + drawer arrows + icon cluster with no bitmap layer in the way |
| **DPI handling** | PerMonitorV2 set in the manifest → WPF renders at native pixels. No fuzzy text, no motion blur on settings scroll. Zero runtime hacks. |
| **Real-time streaming voice typing** | Google Cloud STT v1 bidirectional gRPC stream → interim hypotheses every ~200 ms → diffed against last-typed → only the new characters get sent via `SendInput` to whatever window has focus. Exactly the Google-Translate-style experience |
| **Drawer pattern** | Borderless Topmost popup positioned under a ▼ arrow, closes on Escape or focus loss |

## Intentionally **not** in the PoC

So the diff stays small enough to read in one sitting:

- Settings panel (button is a stub `MessageBox`)
- AI / OpenRouter flows
- Pen tool / drawing overlay / editor window
- TTS reader (SND button)
- Auto-update
- Authentication / freemium gating
- Global hotkey registration (Alt+Z etc — adding NHotkey to the project is a 10-min job)
- More than 2 spectrum buttons (BN / EN only; SND + AI columns will follow the same pattern)

## Prerequisites

1. **Windows 10 1809 or newer** (for the PerMonitorV2 / modern DPI API)
2. **.NET 8.0 SDK** — required for `dotnet build`. Two ways to install:

    ```powershell
    # Option A: winget (recommended, ships with Windows 11)
    winget install Microsoft.DotNet.SDK.8

    # Option B: direct installer
    # Download from https://dotnet.microsoft.com/download/dotnet/8.0
    # Pick "SDK 8.0.x" → Windows x64 installer
    ```

    Verify install:
    ```powershell
    dotnet --version
    # should print 8.0.something
    ```

3. **Visual Studio 2022 Community** *(optional)* — `dotnet` CLI is enough for the PoC. Install only if you want the integrated XAML designer + debugger; pick the **".NET desktop development"** workload.
4. A **Google Cloud project** with the Speech-to-Text API enabled

## First-time Google Cloud setup (~10 minutes)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or pick an existing one).
3. **Enable APIs**: Navigation menu → APIs & Services → Library → search for **"Cloud Speech-to-Text API"** → click Enable.
4. **Create a service account**: IAM & Admin → Service Accounts → Create service account. Name it anything, e.g. `dual-voicer-stt`.
5. **Grant role**: pick `Cloud Speech Client` (the smallest role that grants Recognize permission).
6. **Create a JSON key**: open the service account → Keys tab → Add Key → JSON. The download starts automatically.
7. **Rename the downloaded file** to `gcp-credentials.json` and save it inside the `DualVoicerCS/` project folder (same folder that contains `MainWindow.xaml`). The build copies it next to the EXE; it's gitignored so it won't end up in commits.

> **Free tier**: Google gives 60 minutes of streaming recognition per month at no cost. Plenty for a PoC. Past that, billing is ~$0.024 / minute.

## Build & run

From the repo root:

```powershell
cd desktop_csharp
dotnet restore
dotnet build -c Release
dotnet run --project DualVoicerCS -c Release
```

Or open `DualVoicerCS.sln` in Visual Studio 2022 and press **F5**.

The widget appears centered on the primary monitor.

## Using it

1. Open any text app and click into a text field — Notepad, browser address bar, a Discord chat box, anything that accepts keyboard input.
2. **Don't click the widget directly** — clicking would steal focus from the text app. Either:
    - Click your text app first to give it focus, then *hover over* and trigger the widget without taking focus, OR
    - In the full port we add `WS_EX_NOACTIVATE` (same flag the Python widget uses) so clicking the buttons doesn't change focus. The PoC skips this for simplicity — easiest workaround is keyboard: open your text app, then `Alt+Tab` to the widget, click the button, `Alt+Tab` back.
3. Click the **BN** (bottom-left) spectrum button — it starts pulsing.
4. Speak Bengali — words appear in your text app within ~200-400 ms of each utterance.
5. Click the **BN** button again to stop.
6. Same flow with **EN** for English.
7. Click the small **▼** arrow under **BN** to see the drawer with `Bangladesh` / `India` Bengali variants.

## How real-time typing actually works

`Services/VoiceTypingOrchestrator.cs` carries the full state-machine comment, but the short version:

Google's streaming endpoint emits a fresh "best guess so far" 3-5 times per second:

```
"আমি"
"আমি একটা"
"আমি একটা পরী"
"আমি একটা পরীক্ষা"
"আমি একটা পরীক্ষা করছি"            ← interim
"আমি একটা পরীক্ষা করছি।"           ← FINAL, then Google moves on
```

For each new guess we compute the common prefix with what we last typed, backspace any retracted suffix, then type the new suffix. On the FINAL marker we append a trailing space and reset the diff baseline. Net effect: clean word-by-word streaming, with rare and tiny corrections when Google reconsiders.

## Project layout

```
desktop_csharp/
├── DualVoicerCS.sln
├── README.md
├── .gitignore
└── DualVoicerCS/
    ├── DualVoicerCS.csproj         # net8.0-windows, NAudio + Google.Cloud.Speech.V1
    ├── app.manifest                # PerMonitorV2 DPI awareness
    ├── App.xaml / App.xaml.cs      # Shared resources (palette, gradients)
    ├── MainWindow.xaml / .cs       # The widget itself — wires services to buttons
    ├── Controls/
    │   └── SpectrumButton.xaml/.cs # Reusable circular mic button w/ pulse animation
    ├── Views/
    │   └── VoiceDrawer.xaml/.cs    # ▼-arrow drawer popup
    └── Services/
        ├── AudioCaptureService.cs       # NAudio 16 kHz PCM mic capture
        ├── StreamingSttService.cs       # Google STT v1 bidirectional gRPC stream
        ├── TextInjectionService.cs      # SendInput w/ KEYEVENTF_UNICODE for Bengali
        └── VoiceTypingOrchestrator.cs   # Glues the three together + interim-diff state machine
```

About 850 lines total. The Python widget that does the same three things (button + drawer + voice typing) is closer to 3000 once you count the mixin scaffolding it depends on — the C# version is more concise because:

- The widget chrome lives in XAML, not procedural Tk widget calls.
- DPI and animation are framework-handled instead of stitched together by hand.
- The interim-diff state machine is one comparison and two `SendInput` calls; in Python it was tangled with the `_trans_buffer*` translation pipeline because both shared the same `type_text` codepath.

## Honest list of things you'd hit in a full port

These don't show up in the PoC but I want to flag them upfront so the migration estimate stays honest:

1. **`WS_EX_NOACTIVATE`** for the widget — a one-liner via `[DllImport]` but needs to be reapplied on resize.
2. **Click-through transparent fullscreen overlay** for pen mode — WPF supports it (we'd build it on `WS_EX_LAYERED` + `WS_EX_TRANSPARENT`), but it's hand-coded with P/Invoke, not pure XAML.
3. **InkCanvas vs custom drawing engine** — WPF has a built-in `InkCanvas` that handles strokes, eraser, undo/redo natively. For most of the Python `drawing_engine.py` features this is a giant simplification; the text tool + handwrite mode need custom work either way.
4. **Edge TTS in C#** — the Python `edge-tts` library is a thin REST wrapper over Microsoft's edge endpoint. There's a community C# port (`Edge-TTS-CSharp`) but it's not on NuGet; safest path is wrapping the REST endpoint ourselves (~150 lines).
5. **Bengali rendering edge cases** — DirectWrite handles ligatures and matras correctly out of the box; we shouldn't see the Tk/Uniscribe quirks the Python version dealt with.

## License

Same as the parent project.
