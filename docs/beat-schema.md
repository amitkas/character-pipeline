# Beat JSON schema (Engine B — the scripted pipeline)

A **beat** is the human-authored input to `pipelines/scripted.py`: one JSON
file describing M clips that get rendered, voiced, captioned, and muxed into
one finished vertical mp4. Engine B is a recipe — a deterministic composition
of `studio_skills` calls with zero runtime judgment. Nothing in the beat, and
nothing in this doc, is brand-specific; the character's look and voice come
from the host cabinet's BRAND & VOICE slot (`agents/character.py`), read once
per run and merged in by the pipeline's agents — never baked into the beat
or the skills.

See the worked examples in `beats/_examples/`:
- `example_two_clip.json` — two hero-direct clips, one locked script_line
  (would synthesize on a full render) and one placeholder script_line
  (ships silent).
- `example_realworld_cut.json` — a two-scene cut where scene 1 is silent
  (`script_line: ""`) and only the scene-2 punchline carries voice-over.

## Top level

| Key | Type | Notes |
|---|---|---|
| `beat_id` | string | Identifier for the beat. Used only for human reference; not read by the pipeline. |
| `line_ref` | string | Free-text note — creative context, provenance, scope. Not read by the pipeline. |
| `assembly` | object | Scene-assembly settings shared by all clips. See below. |
| `clips` | array of objects | The M clips, in the order they get concatenated. See below. |

## `assembly`

| Key | Type | Notes |
|---|---|---|
| `vo_offset_sec` | number | Delay (seconds) applied to every clip's voice-over, clearing an image-to-video model's ease-in. Required. |
| `overlays_enabled` | bool | Master switch for per-clip graphic overlays (`clips[].overlays`). Overlays are ignored entirely when this is false/absent. |
| `append_outro` | string (path) | Optional. A silent outro clip appended to the end of the assembled scene. Relative paths resolve under the **beat file's own directory** (a project asset, not a host asset). Omit to skip. |
| `music` | object | Optional music bed. `{"enabled": bool, "path": string, "volume": number}`. `path` resolves the same way as `append_outro`. Omit or set `enabled: false` to skip. |
| `subtitle_style` | object | Optional per-beat caption-style overrides. See "Caption-style resolution" below. |

## `clips[]`

| Key | Type | Notes |
|---|---|---|
| `clip_id` | string | Unique within the beat. Used to key every per-clip artifact map and as the `--clip-filter` value for a single-clip re-render. |
| `character_image` | string (path) | The clip's reference/keyframe image. Relative paths resolve under the **beat file's own directory**; absolute paths are used as-is. Missing/unresolvable path → that clip is skipped at the keyframe gate (logged), not a run-aborting error. |
| `animation_direction` | string | Motion/camera direction only — no style words. The render **style** comes from the host's BRAND slot (`animation_style`, falling back to `visual_short`) via `video_style_prefix()`; this field supplies the per-clip motion. |
| `script_line` | string | The line to voice. **Empty string or a value starting with `[PLACEHOLDER`** ⇒ the clip ships silent — the voice step refuses to spend on throwaway copy. A real line synthesizes VO on a full (non-keyframe-only) render. |
| `voice_id` | string | Optional. ElevenLabs voice id for this clip. Falls back to the BRAND slot's required `sound.voice_id` when omitted. |
| `voice_settings` | object | Optional. Passed straight through to the TTS call (`stability`, `similarity_boost`, `style`, `speed`). Omit to use the skill's defaults. |
| `aspect_ratio` | string | `"1:1"`, `"9:16"`, or `"16:9"`. Sets both the conformed-keyframe crop and (by following the input image) the rendered video's aspect ratio. |
| `kling_duration` | string | `"5"` or `"10"` (seconds) — the only durations the Kling endpoint accepts. |
| `target_duration_sec` | number | Optional. If set, the rendered clip is trimmed to this length after render (frame-accurate re-encode — Kling keyframes don't land on copy-safe cut points). Omit to use the full rendered duration. |
| `subtitles` | array | Optional. `{"text": string, "start": number, "end": number}` (seconds, relative to the clip's own timeline — `vo_offset_sec` is applied automatically). Omit or empty for no captions on that clip. |
| `overlays` | array | Optional; only used when `assembly.overlays_enabled` is true. `{"png": string (path), "width": number, "x": number, "y_frac": number, "start": number, "end": number, "fade": number}`. Relative `png` paths resolve under the **beat file's own directory**. |

## Caption-style resolution

Caption style is resolved by the pipeline (`agents/scene_assembler.py`), not
by the assembly skill — the skill only draws whatever style dict it's
handed. Resolution order, each layer overriding the keys it sets:

```
neutral defaults  <-  BRAND & VOICE slot's caption_style  <-  beat's assembly.subtitle_style
```

The neutral defaults are a plain white box with near-black text — captions
are never brand-yellow (or any other brand color) unless a layer above the
neutral default explicitly sets `box_rgb`/`text_rgb`.

Style keys: `font_path` (optional — a **host asset**, resolved under the
cabinet root when relative; omitted ⇒ a neutral system default font is
used), `font_px`, `weight`, `box_rgb`, `text_rgb`, `pad_x`, `pad_y`,
`radius`, `line_spacing`, `max_width_frac`, `y_frac`. A legacy beat using
the key `font` instead of `font_path` is translated automatically.

## Path resolution summary

| Path | Resolves under |
|---|---|
| `clips[].character_image` | the beat file's directory |
| `clips[].overlays[].png` | the beat file's directory |
| `assembly.append_outro` | the beat file's directory |
| `assembly.music.path` | the beat file's directory |
| caption `font_path` | the **host cabinet root** (`context_root.cabinet_root()`) |

Absolute paths are always used as-is, in every field.

## Running

```bash
# Free gate — conforms keyframes only, spends nothing:
python3 -c "from pipelines.scripted import run; run('beats/_examples/example_two_clip.json', keyframe_only=True)"

# Full render (spends on Kling + ElevenLabs for clips with a real script_line):
python3 -c "from pipelines.scripted import run; run('beats/_examples/example_two_clip.json')"

# Re-render a single clip only:
python3 -c "from pipelines.scripted import run; run('beats/_examples/example_two_clip.json', clip_filter='example_c1_intro')"
```
