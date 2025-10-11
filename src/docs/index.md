# FlyFlirt Documentation

Welcome to the official documentation for **FlyFlirt**, a PyQt6-based toolkit for automated Drosophila behavioral analysis.
This guide explains installation, configuration, and advanced usage for researchers and developers.

---

## 1. Overview

**FlyFlirt** detects and tracks *Drosophila melanogaster* (fruit flies) in video recordings to quantify behavioral events such as mating, movement, and center proximity.
It combines OpenCV-based ROI tracking with a responsive PyQt6 GUI, exporting reproducible CSV and JSON datasets.

---

## 2. Installation

### Prerequisites
- Python 3.9 or newer
- Git
- Recommended: virtual environment (`venv` or `conda`)

### Installation Steps

```bash
git clone https://github.com/yourusername/FlyFlirt.git
cd FlyFlirt
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Run the GUI:
```bash
flyflirt
```

---

## 3. Getting Started

### 3.1 Selecting Videos
- Click **Select Video** or **Add Videos to Queue** to load one or more `.mp4` files.
- FPS is automatically detected but can be manually entered if incorrect.

### 3.2 Starting Analysis
- Enter an optional **frame skip** value to improve performance.
- Click **Start Processing** to begin.
- The GUI will display processed frames with ROI overlays and real-time metrics.

### 3.3 Exporting Data
- Use **Export DataFrame** to export a `.csv` summary for each video.
- Use **Export ROI Locations** to export a `_roi_details_with_behavior.json` file with ROI geometry and trajectory data.

---

## 4. Output Format

### 4.1 CSV
Each ROI entry contains:
| Column | Description |
|:--|:--|
| ROI | ROI index |
| Adjusted Start Time | Mating start time (seconds) |
| Longest Duration | Longest detected mating duration |
| Mating Status | Boolean flag for confirmed mating |
| Center-Mating Duration | Duration mating near center |
| Male/Female Time in Center | Time per gender near center |
| Pre/Post-Mating Durations | Gender-specific center times before/after mating |

### 4.2 JSON
`*_roi_details_with_behavior.json` includes:
```json
{
  "video_path": "example.mp4",
  "video_dimensions": {"width": 1920, "height": 1080},
  "roi_details": [{"id": 0, "center": [500, 400], "radius": 52.3, "void": false}],
  "fly_trail_history": {"0": [[501, 398], [502, 399]]}
}
```

---

## 5. Performance Tips

- Reduce **frame skip** value to improve accuracy (default = 1).
- For large batches, queue videos under **Video Queue**.
- Avoid videos longer than 1 hour without splitting.
- Process under stable lighting conditions for best ROI detection.

---

## 6. Troubleshooting

| Issue | Possible Cause | Fix |
|:--|:--|:--|
| Video not loading | Corrupt file or unsupported codec | Re-encode to `.mp4` |
| GUI unresponsive | High resolution or CPU load | Increase frame skip or close other apps |
| Wrong timing | Incorrect FPS | Manually enter FPS |
| CSV missing ROIs | Void ROIs detected | Check ROI filters in output JSON |

---

## 7. Development Notes

### 7.1 Code Structure
```
flyflirt/
├── app.py              # GUI and logic
├── cli.py              # Command-line launcher
├── vision/             # Future image processing extensions
├── io/                 # File I/O, CSV/JSON writers
└── utils/              # Logging and helper utilities
```

### 7.2 Tests
Run all tests before commits:
```bash
pytest
```

### 7.3 Style Guide
- Follow **PEP 8** conventions.
- Use **type hints** and **docstrings**.
- Keep functions concise and documented.

---

## 8. Citation

If you use FlyFlirt in a publication, please cite:

```bibtex
@software{flyflirt2025,
  author       = {Srujan Yamali},
  title        = {FlyFlirt: ROI-based Drosophila Behavior Analysis Toolkit},
  year         = {2025},
  version      = {0.1.0},
  url          = {https://github.com/srujyama/FlyFlirt}
}
```

---

## 9. License

FlyFlirt is distributed under the MIT License.
See [LICENSE](../LICENSE) for details.

---

## 10. Contact

For bug reports, feature requests, or collaboration inquiries:
- GitHub Issues: [https://github.com/srujyama/FlyFlirt/issues](https://github.com/srujyama/FlyFlirt/issues)
- Maintainer: [srujanyamali@gmail.com](mailto:srujanyamali@gmail.com)
