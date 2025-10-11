# FlyFlirt — Drosophila Behavior Analysis Toolkit

**FlyFlirt** is a PyQt6-based GUI for analyzing the courtship and mating behavior of *Drosophila melanogaster* (fruit flies).
It detects, tracks, and quantifies Regions of Interest (ROIs) in videos, identifies mating events, and exports structured CSV/JSON summaries for downstream behavioral analysis.

---

## Features

* **Interactive GUI** — intuitive PyQt6 interface for multi-video analysis
* **Automatic ROI detection** with OpenCV
* **Mating event detection** and time tracking with configurable grace periods
* **Center-of-ROI metrics** including gender-specific durations
* **Batch queue processing** for folders of `.mp4` videos
* **Export to CSV/JSON** for statistical or visualization pipelines
* **Research-ready** output structure for reproducibility and publication

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/srujyama/FlyFlirt.git
cd FlyFlirt

# optional: create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# install dependencies
pip install -e .
```

### 2. Run the app

```bash
flyflirt
# or
python -m flyflirt
```

### 3. Analyze your videos

1. Load one or more `.mp4` videos or an entire folder.
2. Set or confirm FPS.
3. Start processing — FlyFlirt will track ROIs, detect mating events, and show real-time annotations.
4. Use **Export DataFrame** to save a CSV summary and **Export ROI Locations** to save JSON metadata.

---

## Input and Output

### Input formats

* `.mp4` (preferred)
* `.avi` (compatible via OpenCV)

### CSV output columns

| Column                           | Description                             |
| :------------------------------- | :-------------------------------------- |
| ROI                              | ROI index                               |
| Adjusted Start Time              | Verified mating start time (seconds)    |
| Longest Duration                 | Longest mating duration per ROI         |
| Mating Status                    | True/False indicator of confirmed event |
| Center-Mating Duration           | Time spent mating near ROI center       |
| Male Time in Center              | Seconds male fly spent in center        |
| Female Time in Center            | Seconds female fly spent in center      |
| Average Non-Mating               | Average center occupancy outside mating |
| Outside Center Mating Duration   | Duration of mating outside center       |
| Pre/Post-Mating Center Durations | Gender-specific pre/post center times   |

### JSON export

`*_roi_details_with_behavior.json`

```json
{
  "video_path": "example.mp4",
  "video_dimensions": {"width":1920,"height":1080},
  "roi_details":[{"id":0,"center":[500,400],"radius":52.3,"void":false}],
  "fly_trail_history":{"0":[[501,398],[502,399]]}
}
```

---

## Requirements

| Dependency | Version |
| :--------- | :------ |
| Python     | ≥ 3.9   |
| PyQt6      | ≥ 6.5   |
| OpenCV     | ≥ 4.8   |
| NumPy      | ≥ 1.25  |
| Pandas     | ≥ 2.0   |
| SciPy      | ≥ 1.11  |

All dependencies install automatically from `pyproject.toml` or `requirements.txt`.

---

## Project Structure

```
FlyFlirt/
├── flyflirt/
│   ├── app.py              # Main GUI (your code)
│   ├── cli.py              # CLI launcher
│   ├── __init__.py
│   └── __main__.py
├── README.md
├── LICENSE
├── CITATION.cff
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── pyproject.toml
└── requirements.txt
```

---

## Citation

If you use **FlyFlirt** in academic work, please cite:

```bibtex
@software{flyflirt2025,
  author       = {Your Name},
  title        = {FlyFlirt: Drosophila Behavior Analysis Toolkit},
  year         = {2025},
  version      = {0.1.0},
  url          = {https://github.com/srujyama/Drosophila-Desire-Detector}
}
```

---

## Contributing

Contributions are welcome!
Please read [CONTRIBUTING.md](CONTRIBUTING.md) and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Troubleshooting

| Issue                  | Fix                                     |
| :--------------------- | :-------------------------------------- |
| Video doesn’t load     | Verify FPS or re-encode video to `.mp4` |
| GUI lag                | Increase “Frame Skip” value             |
| Incorrect time scaling | Manually set FPS in the field           |
| Missing dependencies   | Re-run `pip install -e .`               |

---

## License

This project is licensed under the [MIT License](LICENSE).
© 2025 Your Name — freely available for academic and commercial use with attribution.

---

## 🧠 Acknowledgments

Developed for behavioral neuroscience and computational ethology research on *Drosophila melanogaster*.
Inspired by previous ROI-tracking and behavioral quantification tools.
