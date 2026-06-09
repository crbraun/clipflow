# Clipflow

Interactive CLI for merging race camera clips and compositing a mirrored rear inset on forward footage.

## What it does

1. Multi-select forward `.MOV` clips (nothing selected by default; modified date/time shown in the list)
2. Auto-select rear `.MOV` clips by closest modified time to each forward clip
3. Sort forward clips by filename for timeline order and pair with matched rear clips
4. Align each rear overlay using embedded video creation metadata when available
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

## Notes

- Forward and rear lists must contain the same number of clips.
- Clips are paired by sorted filename order for forward video; rear clips keep matched order from selection.
- Overlay sync uses embedded MOV creation metadata when available; otherwise estimated recording start from file end time minus duration (not raw file created/modified times).
- Long race sessions can take a while to encode; progress is shown during processing.
- Temporary concat files are stored in `.clipflow-work/` next to your output file.
