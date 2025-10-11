# FlyFlirt Configuration Guide

This document describes all configurable parameters, thresholds, and internal constants that affect FlyFlirt’s detection accuracy and computational performance.

---

## 1. Configuration Overview

FlyFlirt does not require manual configuration for most use cases.
However, advanced users can tune analysis sensitivity, frame skipping, and behavioral thresholds directly inside the code or through input fields in the GUI.

You can configure parameters in two ways:

1. **Runtime GUI inputs** — frame skip, FPS, seconds to skip.
2. **Code-level settings** — modify constants in `VideoProcessingThread` (inside `flyflirt/app.py`).

---

## 2. Runtime Configuration (GUI)

| Parameter | Location | Description | Recommended Range |
|:--|:--|:--|:--|
| **FPS** | Input field under *Video Controls* | Frames per second of video. Auto-detected, can be manually set. | 25–120 |
| **Seconds to Skip** | Input field next to *Export Controls* | Number of seconds to skip at video start. | 0–30 |
| **Frame Skip** | Input field near *Manual ROI Control* | Number of frames to skip per analysis cycle. Higher = faster. | 1–4 |
| **Video Queue** | Queue panel | Directory batch processing. | N/A |

---

## 3. Core Algorithm Parameters

These constants are defined in `VideoProcessingThread` within `flyflirt/app.py`.

### 3.1 Frame & Contour Processing
```python
top_padding, bottom_padding, left_padding, right_padding = 50, 50, 50, 50
```
Adds black borders around frames to prevent edge artifacts.

```python
area > 500
```
Minimum contour area required to be considered an ROI.
Increase this threshold to ignore noise or small reflections.

```python
y_tolerance = 200
```
Controls how ROIs are grouped vertically. Lower values = stricter ordering.

---

### 3.2 Center & Distance Thresholds
```python
center_threshold = 32
```
Pixels from the ROI center considered part of the “center region.”
Affects `Center-Mating Duration` and gender duration calculations.

```python
self.center_mating_event_end_threshold = 3
```
Grace period (frames) to consider mating “ongoing” even after temporary movement away from the center.

---

### 3.3 Detection Logic
```python
params.minArea = 1
```
Blob detector threshold for minimum fly size in pixels.
Increase to filter out dust or tracking noise.

```python
grace_frames_threshold = int(self.fps * 10 / self.perf_frame_skips)
```
Defines how many frames (10 seconds by default) are tolerated after mating ends before it resets.

```python
if mating_duration >= 360:
```
Defines the minimum mating duration (in seconds) for an event to be officially classified as mating.
**360 seconds (6 minutes)** is the default biological cutoff for *Drosophila* mating confirmation.

---

### 3.4 ROI Labeling and Coloring
- Green circle = active ROI.
- Yellow dot = ongoing mating (shorter than 6 minutes).
- Blue dot = confirmed mating (≥6 minutes).
- Red dot = isolated fly.
- Magenta circle = center region boundary.
- Green ROI text = valid ROI ID.
- Hot pink text = voided or excluded ROI.

---

## 4. Performance Parameters

| Variable | Description | Typical Value | Effect |
|:--|:--|:--|:--|
| `perf_frame_skips` | Frames skipped during analysis | 1–4 | Higher = faster, lower = more accurate |
| `skip_frames` | Frames skipped at start | 0–1000 | Skip startup stabilization |
| `fps` | Frames per second | auto-detected | Timing and duration accuracy |
| `roi_centers` | Cached ROI positions | auto-generated | Used for center tracking |

---

## 5. ROI Export Configuration

Export logic lives in `export_roi_locations()`:

| Field | Description |
|:--|:--|
| `video_dimensions` | Width and height detected via OpenCV |
| `roi_details` | ROI coordinates, radii, and void status |
| `fly_trail_history` | Sequence of centroid coordinates per ROI |
| `export_path` | Derived automatically as `<video>_roi_details_with_behavior.json` |

Output example:
```json
{
  "video_path": "example.mp4",
  "video_dimensions": {"width": 1920, "height": 1080},
  "roi_details": [
    {"id": 0, "center": [530, 400], "radius": 48.5, "void": false}
  ],
  "fly_trail_history": {"0": [[530, 400], [531, 401]]}
}
```

---

## 6. Mating Event Logic Summary

| Phase | Condition | Action |
|:--|:--|:--|
| **Detection Start** | Two flies → one fly transition | Start mating timer |
| **Ongoing** | Single blob persists | Increment duration |
| **Verification** | Duration ≥ 360 s | Confirm mating |
| **End** | Fly count increases or grace threshold exceeded | Stop mating event |
| **Center Analysis** | Blob near ROI center | Count as center mating |
| **Gender Separation** | Blob size comparison | Label as male/female |
| **Export** | After completion | Write CSV + JSON outputs |

---

## 7. Customizing Defaults

You can override parameters globally by editing a `config.json` file (optional).
When present in the project root, FlyFlirt automatically loads it at startup.

Example:
```json
{
  "center_threshold": 30,
  "mating_duration_threshold": 300,
  "frame_skip": 2,
  "minimum_contour_area": 600
}
```

---

## 8. Recommendations for Experimenters

- Keep video resolution between **1080p–2K**.
- Use **constant lighting** and avoid shadows or reflections.
- Record at **≥30 FPS** for accurate timing.
- Trim the first few seconds of idle footage.
- Verify FPS metadata manually if camera frame rate is variable.

---

## 9. Future Configurable Additions

| Planned Parameter | Description |
|:--|:--|
| `auto_roi_merge` | Automatically merge overlapping ROIs |
| `adaptive_thresholding` | Dynamically adjusts threshold per frame |
| `roi_exclusion_mask` | Allow user-drawn exclusion zones |
| `metadata_export` | Add date/time and user tags to exports |

---

## 10. Resetting to Defaults

If the configuration becomes unstable or inconsistent:
1. Delete `config.json` (if present).
2. Reinstall dependencies:
   ```bash
   pip install -e .
   ```
3. Relaunch FlyFlirt — defaults will be restored automatically.

---

## 11. Notes

All configuration values are **human-readable** and **experiment-reproducible**.
Changing constants affects detection sensitivity, but all exported results remain timestamped and version-tracked.

---

**FlyFlirt v0.1.0 — Configuration Reference**
Maintainer: *Srujan Yamali*
Repository: [https://github.com/srujyama/FlyFlirt](https://github.com/srujyama/FlyFlirt)
