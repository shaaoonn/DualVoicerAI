# Dual Voicer CS — Proof of Concept

C# / WPF rewrite spike of Dual Voicer AI, with **real-time word-by-word**
voice typing powered by Vosk (local, free, no cloud signup).

## What this PoC actually proves

| Concern | Result |
| --- | --- |
| **Widget look-and-feel** | WPF can reproduce the Python widget's circular gradient buttons + drawer arrows + icon cluster with no bitmap layer in the way |
| **4K rendering quality** | PerMonitorV2 set in the manifest → WPF renders at native pixels. No fuzzy text, no motion blur on scroll. Zero runtime hacks. |
| **Real-time streaming voice typing** | Vosk recognises 20-100 ms PCM chunks locally and streams partial hypotheses; the orchestrator diffs each interim against last-typed and `SendInput`s only the new characters. Exactly the Google-Translate-style word-by-word feel. |
| **Drawer pattern** | Borderless Topmost popup positioned under a ▼ arrow, closes on Escape or focus loss |
| **No cloud setup** | Vosk runs entirely offline. Download a model once, never sign up for anything. |

## Intentionally **not** in the PoC

So the diff stays small enough to read in one sitting:

- Settings panel (button is a stub `MessageBox`)
- AI / OpenRouter flows
- Pen tool / drawing overlay / editor window
- TTS reader (SND button)
- Auto-update
- Authentication / freemium gating
- Global hotkey registration (Alt+Z etc — adding NHotkey is a 10-min job)
- More than 2 spectrum buttons (BN / EN only; SND + AI columns will follow the same pattern)

## Prerequisites

1. **Windows 10 1809 or newer** (for the PerMonitorV2 / modern DPI API)
2. **.NET 8.0 SDK** — required for `dotnet build`:

    ```powershell
    winget install Microsoft.DotNet.SDK.8
    # then verify:
    dotnet --version    # should print 8.0.x
    ```

3. **Visual Studio 2022 Community** *(optional)* — `dotnet` CLI is enough for the PoC.

## Build & run

```powershell
cd desktop_csharp
dotnet restore
dotnet build -c Release
dotnet run --project DualVoicerCS -c Release
```

Or open `DualVoicerCS.sln` in Visual Studio 2022 and press **F5**.

The widget appears centered on the primary monitor. Voice typing won't work until you drop the Vosk models in the right place (next step).

## One-time Whisper model setup

The Whisper.net recogniser needs one ggml model file on disk. The same multilingual model handles BOTH Bengali and English (you don't need a separate file per language). The model file lives next to the EXE under `models/`.

### Pick a size and download

| File | Size | Bengali quality | CPU load |
| --- | --- | --- | --- |
| `ggml-tiny.bin` | 75 MB | Borderline | Lightest |
| `ggml-base.bin` | 142 MB | **Good — recommended default** | Modest |
| `ggml-small.bin` | 466 MB | Excellent | Heavier (~1.5s per inference on modern CPU) |
| `ggml-medium.bin` | 1.5 GB | Near-cloud | Heavy — needs a fast CPU or GPU runtime |

Direct download URLs (Hugging Face):

```
ggml-base.bin   →  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
ggml-small.bin  →  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
ggml-tiny.bin   →  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin
```

### Place it next to the EXE

```
desktop_csharp\DualVoicerCS\bin\Release\net8.0-windows\models\ggml-base.bin
```

*(or, if you ran `dotnet publish`, `…\win-x64\publish\models\ggml-base.bin`)*

The app searches `models\` in priority order `ggml-small.bin` → `ggml-base.bin` → `ggml-tiny.bin` and uses the first one it finds. Drop in whichever you downloaded — no config needed.

**Tip:** the app raises a clear error showing the exact `models\` path when no model is found, so you can drop the file in without restarting the app each time.

## Using it

1. Open any text app and click into a text field — Notepad, browser address bar, a Discord chat box.
2. **Don't click the widget directly** — clicking would steal focus from the text app. Either:
    - Click your text app first, then trigger the widget with a global hotkey (full port will add this; PoC doesn't have it yet), OR
    - Use Alt+Tab to round-trip between the text app and the widget.
3. Click the **BN** (left) spectrum button — it starts pulsing.
4. Speak Bengali — words appear in your text app within ~200-400 ms.
5. Click the **BN** button again to stop.
6. Same with **EN** for English.
7. Click the small **▼** arrow under **BN** for the drawer demo (Bangladesh / India variants).

## How real-time typing actually works

`Services/VoiceTypingOrchestrator.cs` has the full state-machine comment; short version:

Vosk emits a fresh interim hypothesis ~10 times per second while the user is talking. Each interim is the recogniser's current best guess for the in-progress utterance:

```
"আমি"
"আমি একটা"
"আমি একটা পরী"
"আমি একটা পরীক্ষা"
"আমি একটা পরীক্ষা করছি"            ← interim
"আমি একটা পরীক্ষা করছি"            ← FINAL, then Vosk closes the utterance
```

For each new interim we compute the common prefix with what we last typed, backspace any retracted suffix, then type the new suffix via `SendInput`. On the FINAL marker we append a trailing space and reset the diff baseline. Net effect: clean word-by-word streaming with rare and tiny corrections when Vosk reconsiders.

## Project layout

```
desktop_csharp/
├── DualVoicerCS.sln
├── README.md
├── .gitignore                        # ignores bin/, models/, credentials
└── DualVoicerCS/
    ├── DualVoicerCS.csproj           # net8.0-windows, NAudio + Vosk
    ├── app.manifest                  # PerMonitorV2 DPI awareness
    ├── App.xaml / App.xaml.cs        # Shared palette + spectrum gradient
    ├── MainWindow.xaml / .cs         # Widget chrome + service wiring
    ├── Controls/
    │   └── SpectrumButton.xaml/.cs   # Circular mic button w/ pulse animation
    ├── Views/
    │   └── VoiceDrawer.xaml/.cs      # ▼-arrow drawer popup
    └── Services/
        ├── AudioCaptureService.cs        # NAudio 16 kHz PCM mic capture
        ├── StreamingSttService.cs        # Vosk local streaming recogniser
        ├── TextInjectionService.cs       # SendInput w/ KEYEVENTF_UNICODE
        └── VoiceTypingOrchestrator.cs    # Interim-diff state machine
```

About 1340 lines total. The Python widget that does the same three things (button + drawer + voice typing) is closer to 3000 once you count the mixin scaffolding it depends on.

## Honest list of things you'd hit in a full port

These don't show up in the PoC but worth flagging upfront so the migration estimate stays honest:

1. **`WS_EX_NOACTIVATE`** for the widget — one-liner via `[DllImport]` but needs to be reapplied on resize.
2. **Click-through transparent fullscreen overlay** for pen mode — WPF supports it (`WS_EX_LAYERED` + `WS_EX_TRANSPARENT`), but it's hand-coded with P/Invoke, not pure XAML.
3. **InkCanvas vs custom drawing engine** — WPF has a built-in `InkCanvas` that handles strokes, eraser, undo/redo natively. Huge simplification for most of the Python `drawing_engine.py`; the text tool + handwrite mode need custom work either way.
4. **Edge TTS in C#** — the Python `edge-tts` library is a thin REST wrapper over Microsoft's edge endpoint. There's a community port (`Edge-TTS-CSharp`) but it's not on NuGet; safest path is wrapping the REST endpoint ourselves (~150 lines).
5. **Bengali rendering edge cases** — DirectWrite handles ligatures and matras correctly out of the box; we shouldn't see the Tk/Uniscribe quirks the Python version dealt with.
6. **Vosk vs cloud STT** — Vosk's small models give acceptable Bengali accuracy. Large models (~1.5 GB) get closer to Google quality if needed. The full port can keep Vosk as the offline default + add Google Cloud STT as an optional "high-accuracy" mode behind a Settings toggle.

## License

Same as the parent project.
