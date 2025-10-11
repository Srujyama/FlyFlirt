# FlyFlirt — Drosophila Behavior Analysis Toolkit

**FlyFlirt** is a PyQt6-based GUI for analyzing the courtship and mating behavior of *Drosophila melanogaster* (fruit flies).  
It detects, tracks, and quantifies Regions of Interest (ROIs) in videos, identifies mating events, and exports structured CSV/JSON summaries for downstream behavioral analysis.

---

## Key Features

- **Interactive GUI:** Built with PyQt6 for easy selection, visualization, and control of videos and ROIs.  
- **Automated ROI Detection:** Detects fly regions using OpenCV and maintains consistent labeling across frames.  
- **Mating Event Detection:** Automatically identifies mating events and logs start times, durations, and event metadata.  
- **Center-of-ROI Metrics:** Tracks how long flies spend near ROI centers, with gender-specific center-time measurements.  
- **Batch Queue Mode:** Process entire directories of `.mp4` videos sequentially with queue management.  
- **Comprehensive Exports:** Generate per-ROI CSV summaries and JSONs with coordinates, radii, and trails.  
- **Built for Research:** Outputs are structured for reproducibility and statistical post-processing (e.g., in Pandas or R).

---

## uickstart

### 1. Clone and install

```bash
git clone https://github.com/YourUsername/Drosophila-Desire-Detector.git
cd Drosophila-Desire-Detector

# (recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# install dependencies and CLI entrypoint
pip install -e .
