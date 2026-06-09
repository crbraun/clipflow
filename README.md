# Clipflow

Interactive CLI for merging race camera clips and compositing a mirrored rear inset on forward footage.

## What it does

1. Multi-select forward `.MOV` clips (nothing selected by default; modified date/time shown in the list)
2. Auto-select rear `.MOV` clips by closest modified time to each forward clip
3. Sort forward clips by filename for timeline order and pair with matched rear clips
4. Concatenate both sequences
5. Crop the rear video to remove the bottom 45%, mirror it, and shrink it to 45% for the inset overlay
6. Overlay the rear inset at the top center of the forward video
7. Export a single MP4 using **forward camera audio only**

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
- Clips are paired by sorted filename order, not by matching names.
- Long race sessions can take a while to encode; progress is shown during processing.
- Temporary concat files are stored in `.clipflow-work/` next to your output file.
