# FlyFlirt Usage Guide

This document explains how to operate the **FlyFlirt** graphical interface, interpret its metrics, and customize its behavior for advanced experiments.

---

## 1. Launching the Application

### From the command line
```bash
flyflirt
```

or equivalently:

```bash
python -m flyflirt
```

The GUI window will open and prompt you to load video files for analysis.

---

## 2. Interface Overview

### Main Components

| Section | Description |
|:--|:--|
| **Video Display** | Shows the active frame with ROI overlays and tracked fly positions. |
| **Video Controls** | Buttons to select videos, start/stop processing, and input FPS. |
| **Video List** | Displays all currently loaded or queued videos. |
| **Mating Durations / Verified Times** | Panels showing event timings and ROI IDs. |
| **Manual ROI Control** | Input fields to manually void or manage ROIs. |
| **Center Metrics** | Real-time display of center-mating and gender durations. |
| **Video Queue** | Allows batch processing of multiple videos sequentially. |

---

## 3. Typical Workflow

### Step 1 — Load videos
- Click **Select Video** to load one or more `.mp4` files,
  or use **Add Videos to Queue** to scan a folder recursively.
- FPS will be auto-detected. Adjust manually if incorrect.

### Step 2 — Configure settings
- **Frame Skip**: defines how many frames to skip between analyses.
  A higher value increases speed but may reduce accuracy.
- **Seconds to Skip**: start processing after skipping this many seconds from the beginning.

### Step 3 — Start analysis
- Press **Start Processing**.
- FlyFlirt will begin reading frames, detecting ROIs, and identifying mating events in real time.
- ROIs are drawn with numbered outlines and colored trails.

### Step 4 — Monitor progress
- The left panel displays ROI-specific metrics and frame/time updates.
- Events are logged in the terminal during processing.

### Step 5 — Export data
- Click **Export DataFrame** to generate a `.csv` file next to each video:
  ```
  example_video_analysis.csv
  ```
- Click **Export ROI Locations** to save ROI metadata and trajectories as:
  ```
  example_video_roi_details_with_behavior.json
  ```

---

## 4. Interpreting Metrics

| Metric | Meaning |
|:--|:--|
| **Adjusted Start Time** | The verified mating start time in seconds, adjusted for the event offset. |
| **Longest Duration** | The longest continuous detected mating period. |
| **Mating Status** | Boolean indicator of confirmed mating (True/False). |
| **Center-Mating Duration** | Time spent mating near the center of the ROI. |
| **Male/Female Time in Center** | Time each fly spends near ROI center before and during mating. |
| **Pre/Post-Mating Durations** | Time in center before and after the event. |
| **Outside Center Duration** | Mating time that occurred away from the ROI center. |

---

## 5. ROI Management

### Automatic ROI detection
- ROIs are auto-detected using contour analysis (OpenCV).
- Each ROI receives an integer ID shown on the video overlay.

### Manual voiding
- Use the **Manual ROI Control** panel to remove false-positive regions:
  - Input a single ROI ID (e.g., `3`)
  - Or a range/comma list (e.g., `2-4, 7, 10`)
- Click **Void Multiple ROIs** to mark those regions as invalid.
- Voided ROIs are excluded from exports.

---

## 6. Batch (Queue) Mode

### Adding videos
1. Click **Add Videos to Queue**.
2. Select a folder containing `.mp4` files.
3. All valid files will appear in the queue list.

### Running the queue
- Press **Start Processing Queue** to analyze all queued videos sequentially.
- Progress and status updates appear below the queue list.
- When finished, all data are exported automatically.

### Clearing the queue
- Click **Clear Queue** to reset the list.

---

## 7. Performance Recommendations

- Use **Frame Skip = 2–4** for long videos to reduce CPU usage.
- Limit simultaneous processing to one video per session.
- Avoid compressed or variable-FPS videos — re-encode with constant FPS for best accuracy.
- For high-throughput processing, use smaller frame size or crop videos beforehand.

---

## 8. Export File Locations

Exports are saved in the same directory as the video by default.

| File | Description |
|:--|:--|
| `<video>_analysis.csv` | ROI-level metrics table |
| `<video>_roi_details_with_behavior.json` | ROI geometry, trails, and void flags |
| `<video>_roi_summary.png` (optional) | Future visualization support |

---

## 9. Error Handling

| Symptom | Cause | Fix |
|:--|:--|:--|
| No ROIs detected | Low contrast or poor lighting | Increase brightness or re-encode video |
| Video stops mid-run | FPS mismatch or codec issue | Re-export with constant FPS |
| “Invalid ROI ID” warning | Typo in manual ROI input | Verify numeric input |
| GUI freezes | Processing very large frame | Increase frame skip or close other programs |

---

## 10. Advanced Options

| Setting | Description |
|:--|:--|
| **Frame Skip** | Controls analysis frequency (1 = every frame). |
| **Grace Frames** | Frames to tolerate after event end before resetting. |
| **Center Threshold** | Distance from ROI center considered “in center.” |
| **Mating Duration Threshold** | Duration (in seconds) for confirming a mating event. |

To adjust these defaults, modify the constants defined inside `VideoProcessingThread` in `flyflirt/app.py`.

---

## 11. Notes for Researchers

- FlyFlirt outputs deterministic data when videos are identical (no randomization).
- ROI numbering may vary between sessions if lighting or object count changes.
- To ensure reproducibility, store both `.csv` and `.json` outputs for each run.
- Include FPS, lighting, and video metadata when reporting results.

---

## 12. Support

For issues, bug reports, or feature suggestions:
Open a ticket on GitHub at
[https://github.com/srujyama/FlyFlirt/issues](https://github.com/srujyama/FlyFlirt/issues)
