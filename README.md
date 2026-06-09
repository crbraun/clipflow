# Clipflow

Interactive CLI for merging race camera clips and compositing a mirrored rear inset on forward footage.

## What it does

1. Multi-select forward `.MOV` clips (nothing selected by default; modified date/time shown in the list)
2. Auto-select rear `.MOV` clips by closest modified time to each forward clip
3. Sort forward clips by filename for timeline order and pair with matched rear clips
4. Automatically align each rear overlay by cross-correlating the two cameras' audio (see [Automatic camera sync](#automatic-camera-sync))
5. Composite each clip pair, then concatenate into the final video
6. Crop the rear video to remove the bottom 45%, mirror it, and shrink it to 45% for the inset overlay
7. Overlay the rear inset at the top center of the forward video
8. Export a single MP4 using **forward camera audio only**

## Requirements

- Python 3.11+
- FFmpeg on your `PATH` (`ffmpeg -version`)

## Install

```bash
cd ~/Projects/clipflow
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
clipflow
```

Follow the prompts to choose folders, select clips, confirm pairings, and set output path.

## Automatic camera sync

The forward and rear cameras run independently, so their clips almost never start
at the same instant — and their internal clocks usually disagree by tens of
seconds. That means embedded timestamps alone can't tell you how to line up the
two views.

Clipflow solves this **automatically, with no manual marking and no need to scrub
the footage**, by listening to both cameras:

1. **Coarse guess from metadata.** Each clip's embedded `creation_time` (or, as a
   fallback, file end time minus duration) gives a rough idea of how far apart the
   clips started. This is only used to narrow the search.
2. **Precise lock from audio.** Both cameras sit in the same car and record the
   same engine, exhaust, and track noise. Clipflow extracts a low-rate loudness
   envelope from each soundtrack and cross-correlates them within a window around
   the metadata guess to find the exact offset — the same principle pro multicam
   tools use.
3. **Confidence check with fallback.** If the audio match is strong, that offset
   drives the overlay timing. If it's weak (for example, a near-silent clip), the
   tool falls back to the metadata estimate. Either way, the pairing preview shows
   which method was used and the match confidence, e.g.
   `+43.7s overlay [audio 0.86]`.

This is robust to unsynchronized camera clocks, needs no GPS or timecode track,
and stays accurate across a full session (the measured offset is stable to a
fraction of a second over an hour of footage).

## Notes

- Forward and rear lists must contain the same number of clips.
- Clips are paired by sorted filename order for forward video; rear clips keep matched order from selection.
- The rear overlay appears only once the rear camera's timeline catches up to the forward video, so a delayed rear inset at the very start of a clip is expected.
- Long race sessions can take a while to encode; progress is shown during processing. The audio sync analysis adds a few seconds per clip pair up front.
- Temporary concat files are stored in `.clipflow-work/` next to your output file.
