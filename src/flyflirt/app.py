import json
import os
import sys

import cv2
import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from scipy import stats


class VideoProcessingThread(QThread):
    finished = pyqtSignal()
    frame_processed = pyqtSignal(str, np.ndarray, dict)
    frame_info = pyqtSignal(int, float)
    verified_mating_start_times = pyqtSignal(str, dict)
    void_roi_signal = pyqtSignal(str, int)
    mating_analysis_complete = pyqtSignal(str)
    center_mating_duration_signal = pyqtSignal(int, float)   # ROI ID, duration (s)
    center_gender_duration_signal = pyqtSignal(int, float, float)  # ROI ID, male (s), female (s)
    # Fix 1: flies_count_signal must be a class-level attribute, not assigned in __init__
    flies_count_signal = pyqtSignal(str, int, int)

    def __init__(self, video_path, initial_contours, fps, skip_frames=0, perf_frame_skips=1):
        super().__init__()
        self.video_path = video_path
        self.initial_contours = initial_contours
        self.is_running = False
        self.roi_ids = {}
        self.mating_start_times = {}
        self.mating_durations = {}          # roi_id -> current duration (float, not list)
        self.fps = fps
        self.mating_start_frames = {}
        self.mating_grace_frames = {}
        self.flies_count_per_ROI = {}
        self.void_rois = {}
        self.skip_frames = skip_frames
        self.previous_fly_positions_per_ROI = {}
        self.mating_event_detected = {}
        self.mating_status_per_ROI = {}
        self.mating_event_ongoing = {}
        self.perf_frame_skips = perf_frame_skips
        self.roi_centers = {}
        self.center_mating_duration = {}    # roi_id -> running total (float)
        self.center_mating_start_frame = {}
        self.center_mating_event_end_threshold = 3
        self.fly_size_history = {}
        self.fly_position_history = {}
        self.fly_trail_history = {}
        self.center_gender_duration = {}
        self.pre_mating_center_gender_duration = {}
        self.roi_details = {}
        # Fix 2: separate raw-frame counter from processed-frame counter
        self._processed_frame_count = 0

    def run(self):
        self.is_running = True
        self.flies_count_per_ROI.clear()

        cap = cv2.VideoCapture(self.video_path)

        # Skip the specified number of frames from the start
        for _ in range(self.skip_frames):
            ret, _ = cap.read()
            if not ret:
                break

        raw_frame_index = 0
        self._processed_frame_count = 0

        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                break

            # Fix 2: only process every nth raw frame; threshold checks use processed count
            if raw_frame_index % self.perf_frame_skips == 0:
                self.frame_info.emit(raw_frame_index, raw_frame_index / self.fps)

                processed_frame, masks = self.process_frame(
                    frame, self.initial_contours, self._processed_frame_count
                )
                self.detect_flies(processed_frame, masks, self._processed_frame_count)

                for roi_id, is_mating in self.mating_event_ongoing.items():
                    self.mating_status_per_ROI[roi_id] = is_mating

                self._processed_frame_count += 1

            raw_frame_index += 1

        self.mating_analysis_complete.emit(self.video_path)
        cap.release()
        self.finished.emit()

    def stop(self):
        self.is_running = False

    def process_frame(self, frame, initial_contours, processed_frame_count):
        top_padding = bottom_padding = left_padding = right_padding = 50

        frame_with_padding = cv2.copyMakeBorder(
            frame,
            top_padding, bottom_padding, left_padding, right_padding,
            cv2.BORDER_CONSTANT,
            value=[0, 0, 0],
        )

        gray = cv2.cvtColor(frame_with_padding, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        def custom_sort(contour):
            x, y, w, h = cv2.boundingRect(contour)
            y_tolerance = 200
            return (y // y_tolerance) * 1000 + x

        contours_list = sorted(list(contours), key=custom_sort)

        # Fix 6: build ROI list incrementally during the first 500 *processed* frames,
        # but do NOT clear on every frame — only update if a better set is found.
        # We accumulate a candidate list and commit it once the window closes.
        if processed_frame_count < 500:
            # Rebuild candidate contours from this frame
            candidate = []
            for contour in contours_list:
                area = cv2.contourArea(contour)
                if area > 500:
                    candidate.append({"contour": contour, "edge_duration": 0})
            # Only replace if we found at least as many ROIs as before
            if len(candidate) >= len(initial_contours):
                initial_contours.clear()
                initial_contours.extend(candidate)
                # Fix 5+7: use 0-based index as ROI ID (consistent with all other dicts)
                self.roi_ids.clear()
                for i, cd in enumerate(initial_contours):
                    self.roi_ids[i] = i
        else:
            # After initialization: track edge proximity for each known ROI
            for contour_data in initial_contours:
                contour = contour_data["contour"]
                x, y, w, h = cv2.boundingRect(contour)
                if (
                    x <= 5
                    or y <= 5
                    or (x + w) >= frame_with_padding.shape[1] - 5
                    or (y + h) >= frame_with_padding.shape[0] - 5
                ):
                    contour_data["edge_duration"] += 1
                else:
                    contour_data["edge_duration"] = 0

        # Calculate mode radius across all ROIs
        radii = []
        for contour_data in initial_contours:
            x, y, w, h = cv2.boundingRect(contour_data["contour"])
            radii.append(int(round((w + h) / 4)))
        mode_radius = int(stats.mode(radii)[0]) if radii else 0

        # Create masks and draw ROI circles
        masks = []
        processed_frame = frame_with_padding.copy()
        for contour_data in initial_contours:
            x, y, w, h = cv2.boundingRect(contour_data["contour"])
            center_x = int(x + w / 2)
            center_y = int(y + h / 2)

            mask = np.zeros(processed_frame.shape[:2], dtype="uint8")
            cv2.circle(mask, (center_x, center_y), mode_radius, (255,), -1)
            masks.append(mask)

            if (
                x > 5
                and y > 5
                and (x + w) < frame_with_padding.shape[1] - 5
                and (y + h) < frame_with_padding.shape[0] - 5
            ) or contour_data["edge_duration"] >= 90:
                cv2.circle(processed_frame, (center_x, center_y), mode_radius, (0, 255, 0), 2)

        # Draw ROI numbers and store roi_details
        for i, contour_data in enumerate(initial_contours):
            # Fix 5: compute bounding rect at top of loop (was using stale x,y,w,h)
            x, y, w, h = cv2.boundingRect(contour_data["contour"])
            center_x = int(x + w / 2)
            center_y = int(y + h / 2)
            radius = max(w, h) / 2

            self.roi_details[i] = {"center": (center_x, center_y), "radius": radius}
            self.roi_centers[i] = (center_x, center_y)

            text_position = (center_x, center_y - 55)
            # Fix 8: label matches 0-based index used everywhere else
            cv2.putText(
                processed_frame,
                str(i),
                text_position,
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 105, 180),
                2,
                cv2.LINE_AA,
            )

        return processed_frame, masks

    def detect_flies(self, frame_with_padding, masks, processed_frame_count):
        params = cv2.SimpleBlobDetector_Params()
        params.filterByArea = True
        params.minArea = 1
        params.filterByCircularity = False
        params.filterByConvexity = False
        params.filterByInertia = False
        detector = cv2.SimpleBlobDetector_create(params)

        dot_radius = 6
        dot_thickness = -1

        grace_frames_threshold = int(self.fps * 10 / self.perf_frame_skips)
        center_threshold = 32

        for i, mask in enumerate(masks):
            if self.void_rois.get(i, False):
                continue

            masked_frame = cv2.bitwise_and(frame_with_padding, frame_with_padding, mask=mask)
            gray = cv2.cvtColor(masked_frame, cv2.COLOR_BGR2GRAY)

            kernel = np.ones((6, 6), np.uint8)
            gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel, iterations=1)
            gray = cv2.morphologyEx(gray, cv2.MORPH_DILATE, kernel, iterations=1)
            gray = cv2.morphologyEx(gray, cv2.MORPH_ERODE, kernel, iterations=1)

            keypoints = detector.detect(gray)

            if i not in self.fly_trail_history:
                self.fly_trail_history[i] = []

            roi_center = self.roi_centers.get(i, (0, 0))

            cv2.circle(frame_with_padding, roi_center, center_threshold, (255, 0, 255), 2)

            # ----------------------------------------------------------------
            # Calibration window: detect fly count and check for void ROIs
            # Fix 3: use processed_frame_count so threshold counts processed frames
            # ----------------------------------------------------------------
            if processed_frame_count < 500:
                flies_count = len(keypoints)
                current_positions = [kp.pt for kp in keypoints]

                # Detect 2→1 transition as a mating event signal
                if flies_count == 1 and i in self.previous_fly_positions_per_ROI:
                    prev_positions = self.previous_fly_positions_per_ROI[i]
                    if len(prev_positions) == 2:
                        dist = np.linalg.norm(
                            np.array(prev_positions[0]) - np.array(prev_positions[1])
                        )
                        if dist > 30:
                            self.mating_event_detected[i] = True

                # Fix 4: only store positions when there are exactly 2 flies;
                # do NOT unconditionally overwrite at the end of the block.
                if flies_count == 2:
                    self.previous_fly_positions_per_ROI[i] = current_positions
                elif flies_count == 1 and i in self.previous_fly_positions_per_ROI:
                    # Keep the last 2-fly positions for transition detection;
                    # delete only after we've already used them above.
                    del self.previous_fly_positions_per_ROI[i]

                if i not in self.flies_count_per_ROI:
                    self.flies_count_per_ROI[i] = []
                self.flies_count_per_ROI[i].append(flies_count)

                if len(self.flies_count_per_ROI[i]) == 200:
                    more_than_two = sum(c > 2 for c in self.flies_count_per_ROI[i])
                    less_than_two = sum(c < 2 for c in self.flies_count_per_ROI[i])
                    threshold = 200 * 0.75
                    if more_than_two > threshold or (
                        less_than_two > threshold
                        and not self.mating_event_detected.get(i, False)
                    ):
                        self.void_rois[i] = True
                        self.void_roi_signal.emit(self.video_path, i)

            # ----------------------------------------------------------------
            # Mating event detection and tracking
            # ----------------------------------------------------------------

            # Fix 10: ensure mating_event_ongoing always has a value for this ROI
            if i not in self.mating_event_ongoing:
                self.mating_event_ongoing[i] = False

            if len(keypoints) == 1:
                # Skip if mating already confirmed + ended + grace period expired
                if (
                    i in self.mating_start_times
                    and not self.mating_event_ongoing.get(i, False)
                    and self.mating_grace_frames.get(i, 0) > grace_frames_threshold
                ):
                    continue

                self.mating_event_ongoing[i] = True

                x, y = int(keypoints[0].pt[0]), int(keypoints[0].pt[1])

                if i not in self.mating_start_frames:
                    self.mating_start_frames[i] = processed_frame_count

                self.mating_grace_frames[i] = 0

                # Fix 11: overwrite current duration instead of appending every frame
                mating_duration = (
                    processed_frame_count - self.mating_start_frames[i]
                ) / self.fps
                self.mating_durations[i] = mating_duration

                # Fix 12: record the actual start time, not the confirmation time
                if mating_duration >= 360 and i not in self.mating_start_times:
                    actual_start_time = self.mating_start_frames[i] / self.fps
                    self.mating_start_times[i] = actual_start_time
                    self.verified_mating_start_times.emit(
                        self.video_path, self.mating_start_times
                    )

                # Confirmed mating trail: only record/draw after 360s confirmed
                confirmed_mating = mating_duration >= 360 or i in self.mating_start_times
                if confirmed_mating:
                    if i not in self.mating_start_times:
                        # First confirmation frame — clear any pre-confirmation points
                        self.fly_trail_history[i] = []
                    self.fly_trail_history[i].append((x, y))

                if len(self.fly_trail_history[i]) > 1:
                    for j in range(len(self.fly_trail_history[i]) - 1):
                        cv2.line(
                            frame_with_padding,
                            self.fly_trail_history[i][j],
                            self.fly_trail_history[i][j + 1],
                            (0, 255, 0),
                            2,
                        )

                # Center mating duration tracking
                distance_to_center = np.sqrt(
                    (x - roi_center[0]) ** 2 + (y - roi_center[1]) ** 2
                )
                in_center = distance_to_center <= center_threshold

                if in_center:
                    if i not in self.center_mating_start_frame:
                        self.center_mating_start_frame[i] = processed_frame_count
                    else:
                        interval = (
                            processed_frame_count - self.center_mating_start_frame[i]
                        ) / self.fps
                        # Fix 29: maintain a running total instead of a list + sum
                        if i not in self.center_mating_duration:
                            self.center_mating_duration[i] = 0.0
                        self.center_mating_duration[i] += interval
                        self.center_mating_duration_signal.emit(
                            i, self.center_mating_duration[i]
                        )
                        self.center_mating_start_frame[i] = processed_frame_count
                else:
                    # Fix 9: do NOT set mating_event_ongoing=False here.
                    # The pair has just drifted away from center — mating is still ongoing.
                    # Only reset the center-proximity start frame.
                    if i in self.center_mating_start_frame:
                        duration_since_center = (
                            processed_frame_count - self.center_mating_start_frame[i]
                        )
                        if duration_since_center > self.center_mating_event_end_threshold:
                            self.center_mating_start_frame[i] = processed_frame_count

            else:
                # Mating event has potentially ended
                self.mating_event_ongoing[i] = False
                self.mating_grace_frames[i] = self.mating_grace_frames.get(i, 0) + 1

                if i in self.mating_start_frames:
                    mating_duration = (
                        processed_frame_count - self.mating_start_frames[i]
                    ) / self.fps
                    if mating_duration < 360 and i in self.center_mating_duration:
                        del self.center_mating_duration[i]

                # Fix 10: use .get() to avoid KeyError after deletion
                if self.mating_grace_frames.get(i, 0) > grace_frames_threshold:
                    if i in self.mating_start_frames:
                        del self.mating_start_frames[i]
                    if i in self.mating_grace_frames:
                        del self.mating_grace_frames[i]
                    # Clear unconfirmed trail
                    if i not in self.mating_start_times:
                        self.fly_trail_history[i] = []

            # ----------------------------------------------------------------
            # Per-ROI fly identity & gender tracking (2-fly frames)
            # ----------------------------------------------------------------
            if i not in self.fly_size_history:
                self.fly_size_history[i] = {"slot0": [], "slot1": []}
                self.fly_position_history[i] = {"female": []}

            if len(keypoints) == 2:
                size_history_limit = 30

                prev_slots = self.fly_position_history[i].get("_slots")
                kp_pts = [np.array(kp.pt) for kp in keypoints]

                if prev_slots is not None and len(prev_slots) == 2:
                    prev0, prev1 = np.array(prev_slots[0]), np.array(prev_slots[1])
                    d00 = np.linalg.norm(kp_pts[0] - prev0)
                    d01 = np.linalg.norm(kp_pts[0] - prev1)
                    d10 = np.linalg.norm(kp_pts[1] - prev0)
                    d11 = np.linalg.norm(kp_pts[1] - prev1)
                    if d00 + d11 <= d01 + d10:
                        slot0_kp, slot1_kp = keypoints[0], keypoints[1]
                    else:
                        slot0_kp, slot1_kp = keypoints[1], keypoints[0]
                else:
                    sorted_by_size = sorted(keypoints, key=lambda k: k.size, reverse=True)
                    slot0_kp, slot1_kp = sorted_by_size[0], sorted_by_size[1]

                self.fly_position_history[i]["_slots"] = [
                    (int(slot0_kp.pt[0]), int(slot0_kp.pt[1])),
                    (int(slot1_kp.pt[0]), int(slot1_kp.pt[1])),
                ]

                self.fly_size_history[i]["slot0"].append(slot0_kp.size)
                self.fly_size_history[i]["slot1"].append(slot1_kp.size)
                for slot in ["slot0", "slot1"]:
                    if len(self.fly_size_history[i][slot]) > size_history_limit:
                        self.fly_size_history[i][slot].pop(0)

                min_history = 10
                avg0 = np.mean(self.fly_size_history[i]["slot0"])
                avg1 = np.mean(self.fly_size_history[i]["slot1"])
                enough_history = (
                    len(self.fly_size_history[i]["slot0"]) >= min_history
                    and len(self.fly_size_history[i]["slot1"]) >= min_history
                )

                if enough_history:
                    if avg0 >= avg1:
                        female_fly, male_fly = slot0_kp, slot1_kp
                    else:
                        female_fly, male_fly = slot1_kp, slot0_kp
                else:
                    if slot0_kp.size >= slot1_kp.size:
                        female_fly, male_fly = slot0_kp, slot1_kp
                    else:
                        female_fly, male_fly = slot1_kp, slot0_kp

                sorted_keypoints = [female_fly, male_fly]

                self.fly_position_history[i]["female"].append(
                    (int(female_fly.pt[0]), int(female_fly.pt[1]))
                )
                if len(self.fly_position_history[i]["female"]) > 10:
                    self.fly_position_history[i]["female"].pop(0)

                # Draw female trail
                for p1, p2 in zip(
                    self.fly_position_history[i]["female"],
                    self.fly_position_history[i]["female"][1:],
                ):
                    cv2.line(frame_with_padding, p1, p2, (255, 0, 0), 2)

                cv2.circle(
                    frame_with_padding,
                    (int(female_fly.pt[0]), int(female_fly.pt[1])),
                    dot_radius, (0, 0, 255), dot_thickness,
                )
                cv2.circle(
                    frame_with_padding,
                    (int(male_fly.pt[0]), int(male_fly.pt[1])),
                    dot_radius, (255, 255, 0), dot_thickness,
                )

                for fly, gender in zip(sorted_keypoints, ["female", "male"]):
                    fx, fy = int(fly.pt[0]), int(fly.pt[1])
                    dist = np.sqrt((fx - roi_center[0]) ** 2 + (fy - roi_center[1]) ** 2)
                    in_center = dist <= center_threshold

                    if i not in self.pre_mating_center_gender_duration:
                        self.pre_mating_center_gender_duration[i] = {"male": 0.0, "female": 0.0}
                    if i not in self.center_gender_duration:
                        self.center_gender_duration[i] = {"male": 0.0, "female": 0.0}

                    if not self.mating_event_ongoing.get(i, False) and in_center:
                        if self.mating_durations.get(i, 0) < 360:
                            self.pre_mating_center_gender_duration[i][gender] += 1.0 / self.fps

                    if in_center:
                        self.center_gender_duration[i][gender] += 1.0 / self.fps
                        self.center_gender_duration_signal.emit(
                            i,
                            self.center_gender_duration[i]["male"],
                            self.center_gender_duration[i]["female"],
                        )

            # Draw dots for all detected flies
            for keypoint in keypoints:
                kx = int(keypoint.pt[0])
                ky = int(keypoint.pt[1])
                dist = np.sqrt((kx - roi_center[0]) ** 2 + (ky - roi_center[1]) ** 2)
                in_center = dist <= center_threshold
                mating_ongoing = self.mating_event_ongoing.get(i, False)
                within_grace = self.mating_grace_frames.get(i, 0) <= grace_frames_threshold

                if mating_ongoing or within_grace:
                    current_dur = self.mating_durations.get(i, 0)
                    color = (255, 0, 0) if current_dur >= 360 else (0, 255, 255)
                else:
                    color = (0, 0, 255)

                if in_center:
                    color = (0, 255, 0)

                cv2.circle(frame_with_padding, (kx, ky), dot_radius, color, dot_thickness)

        # Fix 23: emit a copy of the frame so the main thread holds a stable buffer
        self.frame_processed.emit(
            self.video_path, frame_with_padding.copy(), self.mating_durations.copy()
        )

    def generate_contour_id(self, contour):
        # Fix 5: use centroid as a more unique identifier than area alone
        M = cv2.moments(contour)
        if M["m00"] == 0:
            return (0, 0)
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return (cx, cy)

    def void_roi(self, roi_id):
        self.void_rois[roi_id] = True
        self.void_roi_signal.emit(self.video_path, roi_id)

    def export_roi_locations(self):
        video_info = {
            "video_path": self.video_path,
            "video_dimensions": {"width": None, "height": None},
            "processing_parameters": {
                "resize_dimensions": None,
                "crop_dimensions": None,
            },
            "roi_details": [],
            "fly_trail_history": {},
        }

        cap = cv2.VideoCapture(self.video_path)
        if cap.isOpened():
            video_info["video_dimensions"]["width"] = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            video_info["video_dimensions"]["height"] = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        cap.release()

        for roi_id, details in self.roi_details.items():
            video_info["roi_details"].append({
                "id": roi_id,
                "center": details["center"],
                "radius": details["radius"],
                "void": self.void_rois.get(roi_id, False),
                "has_mating_start_time": roi_id in self.mating_start_times,
            })

        for roi_id, trail in self.fly_trail_history.items():
            video_info["fly_trail_history"][roi_id] = [list(pt) for pt in trail]

        export_path = os.path.splitext(self.video_path)[0] + "_roi_details_with_behavior.json"
        with open(export_path, "w") as f:
            json.dump(video_info, f, indent=4)
        print(f"ROI details exported to {export_path}")

    def export_combined_mating_times(self):
        """Return a DataFrame of mating start times, merging events within 1 second."""
        combined_mating_times = {}
        for roi_id, mating_time in self.mating_start_times.items():
            merged = False
            for cid, ctime in combined_mating_times.items():
                if abs(mating_time - ctime) <= 1:
                    # Keep the earlier start time rather than averaging
                    combined_mating_times[cid] = min(ctime, mating_time)
                    merged = True
                    break
            if not merged:
                combined_mating_times[roi_id] = mating_time

        rows = []
        for roi_id, start_time in combined_mating_times.items():
            rows.append({
                "ROI": roi_id,
                "Start Time": start_time,
                "Mating Duration": self.mating_durations.get(roi_id, 0),
            })
        return pd.DataFrame(rows)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fly Behavior Analysis")
        self.setGeometry(200, 200, 1700, 1400)

        self.video_path = None
        self.initial_contours = []
        self.video_paths = []
        self.video_threads = {}
        self.current_video_index = 0
        self.latest_frames = {}
        self.latest_mating_durations = {}
        self.mating_start_times_dfs = {}
        self.center_gender_duration_labels = {}
        self.video_queue = []
        # Fix 24: store per-video FPS instead of overwriting a shared field
        self.video_fps = {}

        self.init_ui()

    def init_ui(self):
        # --- Video Display ---
        video_display_group = QGroupBox("Video Display", self)
        video_display_group.setGeometry(10, 10, 870, 500)
        vbox = QVBoxLayout()
        self.video_label = QLabel()
        self.video_label.setFixedSize(860, 440)
        vbox.addWidget(self.video_label)
        hbox = QHBoxLayout()
        self.frame_label = QLabel("Frame: 0")
        hbox.addWidget(self.frame_label)
        self.time_label = QLabel("Time (s): 0")
        hbox.addWidget(self.time_label)
        vbox.addLayout(hbox)
        video_display_group.setLayout(vbox)

        # --- Video Controls ---
        video_control_group = QGroupBox("Video Controls", self)
        video_control_group.setGeometry(10, 520, 870, 140)
        vbox = QVBoxLayout()

        self.fps_input = QLineEdit()
        self.fps_input.setPlaceholderText("Enter Video FPS (auto-filled on video select)")
        vbox.addWidget(self.fps_input)

        # Fix 18: skip_frames_input placed inside the controls group with a label
        skip_hbox = QHBoxLayout()
        skip_hbox.addWidget(QLabel("Skip (s):"))
        self.skip_frames_input = QLineEdit()
        self.skip_frames_input.setPlaceholderText("Seconds to skip at start")
        skip_hbox.addWidget(self.skip_frames_input)
        skip_hbox.addWidget(QLabel("Frame skip:"))
        self.frame_skip_input = QLineEdit()
        self.frame_skip_input.setPlaceholderText("Process every Nth frame")
        skip_hbox.addWidget(self.frame_skip_input)
        vbox.addLayout(skip_hbox)

        hbox = QHBoxLayout()
        self.select_button = QPushButton("Select Video")
        self.select_button.clicked.connect(self.select_video)
        hbox.addWidget(self.select_button)
        self.start_button = QPushButton("Start Processing")
        self.start_button.clicked.connect(self.start_processing)
        hbox.addWidget(self.start_button)
        self.stop_button = QPushButton("Stop Processing")
        self.stop_button.clicked.connect(self.stop_processing)
        hbox.addWidget(self.stop_button)
        vbox.addLayout(hbox)
        video_control_group.setLayout(vbox)

        # --- Video List ---
        video_list_group = QGroupBox("Video List", self)
        video_list_group.setGeometry(10, 670, 870, 120)
        vbox = QVBoxLayout()
        self.video_list_widget = QListWidget()
        vbox.addWidget(self.video_list_widget)
        video_list_group.setLayout(vbox)

        # --- Mating Info ---
        mating_info_area = QWidget(self)
        mating_info_area.setGeometry(10, 800, 870, 150)
        hbox = QHBoxLayout()

        mating_duration_group = QGroupBox("Mating Durations", mating_info_area)
        vbox = QVBoxLayout()
        self.mating_duration_label = QLabel("Mating Durations:")
        vbox.addWidget(self.mating_duration_label)
        mating_duration_scroll = QScrollArea()
        mating_duration_scroll.setWidgetResizable(True)
        mating_duration_scroll.setWidget(mating_duration_group)
        mating_duration_group.setLayout(vbox)
        hbox.addWidget(mating_duration_scroll)

        verified_times_group = QGroupBox("Verified Mating Times", mating_info_area)
        vbox = QVBoxLayout()
        self.verified_mating_times_label = QLabel("Verified Mating Times:")
        vbox.addWidget(self.verified_mating_times_label)
        verified_times_scroll = QScrollArea()
        verified_times_scroll.setWidgetResizable(True)
        verified_times_scroll.setWidget(verified_times_group)
        verified_times_group.setLayout(vbox)
        hbox.addWidget(verified_times_scroll)

        mating_info_area.setLayout(hbox)

        # --- Navigation ---
        nav_group = QGroupBox("Navigation", self)
        nav_group.setGeometry(10, 960, 870, 80)
        hbox = QHBoxLayout()
        self.prev_button = QPushButton("← Previous Video")
        self.prev_button.clicked.connect(self.previous_video)
        hbox.addWidget(self.prev_button)
        self.next_button = QPushButton("Next Video →")
        self.next_button.clicked.connect(self.next_video)
        hbox.addWidget(self.next_button)
        nav_group.setLayout(hbox)

        # --- Data Export ---
        export_group = QGroupBox("Data Export", self)
        export_group.setGeometry(10, 1050, 870, 80)
        hbox = QHBoxLayout()
        self.export_button = QPushButton("Export DataFrame")
        self.export_button.clicked.connect(self.export_dataframe)
        self.export_button.setToolTip("Export the mating data as a CSV file.")
        hbox.addWidget(self.export_button)
        self.export_roi_button = QPushButton("Export ROI Locations")
        self.export_roi_button.clicked.connect(self.export_roi_locations)
        hbox.addWidget(self.export_roi_button)
        self.processing_status_label = QLabel("Status: Awaiting action.")
        hbox.addWidget(self.processing_status_label)
        export_group.setLayout(hbox)

        # --- Manual ROI Control ---
        # Fix 14: only one roi_control_group (removed first duplicate)
        self.roi_control_group = QGroupBox("Manual ROI Control", self)
        self.roi_control_group.setGeometry(890, 35, 300, 200)
        roi_control_layout = QVBoxLayout()
        self.multi_roi_input = QLineEdit(self)
        self.multi_roi_input.setPlaceholderText("ROI IDs to void (e.g. 0,2,4-7)")
        roi_control_layout.addWidget(self.multi_roi_input)
        self.void_multi_roi_button = QPushButton("Void Multiple ROIs", self)
        self.void_multi_roi_button.clicked.connect(self.void_multiple_rois)
        roi_control_layout.addWidget(self.void_multi_roi_button)
        self.roi_void_list = QListWidget(self)
        roi_control_layout.addWidget(self.roi_void_list)
        self.roi_control_group.setLayout(roi_control_layout)

        # --- Center Mating Duration ---
        self.center_mating_duration_labels = {}  # Fix 19: dict keyed by roi_id
        self.center_mating_duration_group = QGroupBox("Center Mating Duration", self)
        self.center_mating_duration_group.setGeometry(890, 250, 300, 300)
        self.center_mating_duration_layout = QVBoxLayout()
        self.center_mating_duration_group.setLayout(self.center_mating_duration_layout)
        self.scroll_widget_for_center_mating_duration = QWidget()
        self.scroll_layout_for_center_mating_duration = QVBoxLayout(
            self.scroll_widget_for_center_mating_duration
        )
        self.scroll_area_for_center_mating_duration = QScrollArea()
        self.scroll_area_for_center_mating_duration.setWidgetResizable(True)
        self.scroll_area_for_center_mating_duration.setWidget(
            self.scroll_widget_for_center_mating_duration
        )
        self.center_mating_duration_layout.addWidget(
            self.scroll_area_for_center_mating_duration
        )

        # --- Center Gender Duration ---
        self.center_gender_duration_group = QGroupBox("Center Gender Duration", self)
        self.center_gender_duration_group.setGeometry(890, 560, 300, 300)
        self.center_gender_duration_layout = QVBoxLayout()
        self.center_gender_duration_group.setLayout(self.center_gender_duration_layout)
        self.scroll_widget_for_center_gender_duration = QWidget()
        # Fix 31: corrected typo "gating" → "gender"
        self.scroll_layout_for_center_gender_duration = QVBoxLayout(
            self.scroll_widget_for_center_gender_duration
        )
        self.scroll_area_for_center_gender_duration = QScrollArea()
        self.scroll_area_for_center_gender_duration.setWidgetResizable(True)
        self.scroll_area_for_center_gender_duration.setWidget(
            self.scroll_widget_for_center_gender_duration
        )
        self.center_gender_duration_layout.addWidget(
            self.scroll_area_for_center_gender_duration
        )

        # --- Video Queue ---
        video_queue_group = QGroupBox("Video Queue", self)
        video_queue_group.setGeometry(1200, 40, 300, 400)
        queue_layout = QVBoxLayout()
        self.add_to_queue_button = QPushButton("Add Videos to Queue")
        self.add_to_queue_button.clicked.connect(self.add_videos_to_queue)
        queue_layout.addWidget(self.add_to_queue_button)
        self.clear_queue_button = QPushButton("Clear Queue")
        self.clear_queue_button.clicked.connect(self.clear_video_queue)
        queue_layout.addWidget(self.clear_queue_button)
        self.video_queue_list_widget = QListWidget()
        queue_layout.addWidget(self.video_queue_list_widget)
        video_queue_group.setLayout(queue_layout)

        self.start_queue_button = QPushButton("Start Processing Queue", self)
        self.start_queue_button.clicked.connect(self.start_processing_queue)
        self.start_queue_button.setGeometry(1200, 440, 300, 30)

    # ----------------------------------------------------------------
    # ROI Export
    # ----------------------------------------------------------------
    def export_roi_locations(self):
        # Fix 26: guard against empty video list
        if not self.video_paths:
            self.show_error("No video loaded.")
            return
        current_video_path = self.video_paths[self.current_video_index]
        video_thread = self.video_threads.get(current_video_path)
        if video_thread:
            video_thread.export_roi_locations()
        else:
            self.show_error("No active video thread found for the current video.")

    # ----------------------------------------------------------------
    # Queue management
    # ----------------------------------------------------------------
    def add_videos_to_queue(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory with Video Files")
        if directory:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    if filename.endswith(".mp4") and not filename.startswith("._"):
                        video_path = os.path.join(root, filename)
                        if video_path not in self.video_queue:
                            # Fix 24: store FPS per video, don't overwrite shared field
                            self._store_fps_from_video(video_path)
                            self.video_queue.append(video_path)
                            relative_path = os.path.relpath(video_path, directory)
                            self.video_queue_list_widget.addItem(relative_path)

    def clear_video_queue(self):
        self.video_queue.clear()
        self.video_queue_list_widget.clear()
        self.processing_status_label.setText("Video queue cleared.")
        self.start_queue_button.setEnabled(False)

    def start_processing_queue(self):
        if not self.video_queue:
            self.show_error("The video queue is empty.")
            return
        # Fix 32: validate FPS input
        fps = self._parse_fps()
        if fps is None:
            return
        self.start_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.processing_status_label.setText("Starting to process the video queue...")
        first_video_path = self.video_queue.pop(0)
        self.start_processing_video(first_video_path)

    def start_processing_video(self, video_path):
        # Fix 24: use per-video stored FPS, fall back to UI input
        fps = self.video_fps.get(video_path) or self._parse_fps()
        if fps is None:
            self.show_error("Could not determine FPS for this video.")
            return

        skip_seconds = float(self.skip_frames_input.text()) if self.skip_frames_input.text() else 0
        skip_frames = int(skip_seconds * fps)

        try:
            perf_frame_skips = int(self.frame_skip_input.text())
            if perf_frame_skips < 1:
                perf_frame_skips = 1
        except ValueError:
            perf_frame_skips = 1

        video_thread = VideoProcessingThread(video_path, [], fps, skip_frames, perf_frame_skips)
        self.video_threads[video_path] = video_thread

        # Fix 33: clean up finished threads
        video_thread.finished.connect(lambda: self._on_thread_finished(video_thread))
        video_thread.finished.connect(self.process_next_video_in_queue)
        video_thread.frame_processed.connect(self.update_video_frame)
        video_thread.frame_info.connect(self.update_frame_info)
        # Fix 17: wrap export_dataframe in lambda to discard the video_path str argument
        video_thread.mating_analysis_complete.connect(lambda _: self.export_dataframe())
        video_thread.center_mating_duration_signal.connect(self.update_center_mating_duration)
        video_thread.verified_mating_start_times.connect(self.update_verified_mating_times)
        video_thread.center_gender_duration_signal.connect(self.update_center_gender_duration)
        video_thread.void_roi_signal.connect(self.void_roi_handler)

        video_thread.start()

    def _on_thread_finished(self, thread):
        # Fix 33: schedule deletion of finished thread objects
        thread.deleteLater()

    def process_next_video_in_queue(self):
        if self.video_queue:
            next_video_path = self.video_queue.pop(0)
            self.start_processing_video(next_video_path)
        else:
            self.processing_status_label.setText("Video queue processing completed.")
            self.start_button.setEnabled(True)
            self.select_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    # ----------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------
    def show_error(self, message):
        QMessageBox.critical(self, "Error", message)

    def show_info(self, title, message):
        QMessageBox.information(self, title, message)

    def _store_fps_from_video(self, video_path):
        """Read and cache the FPS of a video file."""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        if fps > 0:
            self.video_fps[video_path] = fps
        return fps

    def _parse_fps(self):
        """Parse the FPS input field; show error and return None if invalid."""
        # Fix 32: wrap conversion in try/except
        try:
            fps = float(self.fps_input.text())
            if fps <= 0:
                raise ValueError
            return fps
        except ValueError:
            self.show_error("Please enter a valid FPS value (positive number).")
            return None

    # ----------------------------------------------------------------
    # Void ROI
    # ----------------------------------------------------------------
    # Fix 15: removed dead void_roi() method that referenced non-existent roi_id_input

    def void_multiple_rois(self):
        # Fix 25: guard against empty video list
        if not self.video_paths:
            self.show_error("No video loaded.")
            return

        roi_input = self.multi_roi_input.text().strip()
        roi_ids = []
        for entry in roi_input.split(","):
            entry = entry.strip()
            if "-" in entry:
                try:
                    start, end = map(int, entry.split("-"))
                    roi_ids.extend(range(start, end + 1))
                except ValueError:
                    self.show_error(f"Invalid ROI range: {entry}")
                    return
            else:
                try:
                    roi_ids.append(int(entry))
                except ValueError:
                    self.show_error(f"Invalid ROI ID: {entry}")
                    return

        current_video_path = self.video_paths[self.current_video_index]
        video_thread = self.video_threads.get(current_video_path)
        if video_thread:
            for roi_id in roi_ids:
                video_thread.void_roi(roi_id)
                self.roi_void_list.addItem(f"ROI {roi_id} voided in {current_video_path}")
        else:
            self.show_error("No video thread found for the current video.")

    # Fix 16: removed dead add_export_button() and enable_export_button() methods

    # ----------------------------------------------------------------
    # Center duration labels
    # ----------------------------------------------------------------
    def _get_or_create_center_mating_label(self, roi_id):
        # Fix 19: use dict instead of list to avoid IndexError gaps
        if roi_id not in self.center_mating_duration_labels:
            label = QLabel(f"ROI {roi_id}: Center Mating Duration: N/A")
            label.setWordWrap(True)
            self.scroll_layout_for_center_mating_duration.addWidget(label)
            self.center_mating_duration_labels[roi_id] = label
        return self.center_mating_duration_labels[roi_id]

    def update_center_mating_duration(self, roi_id, duration):
        label = self._get_or_create_center_mating_label(roi_id)
        label.setText(f"ROI {roi_id}: Center Mating Duration: {duration:.2f} s")

    def add_center_gender_duration_label(self, roi_id, gender):
        key = (roi_id, gender)
        if key not in self.center_gender_duration_labels:
            label = QLabel(f"ROI {roi_id} ({gender}): Center Duration: N/A")
            label.setWordWrap(True)
            # Fix 31: use corrected attribute name
            self.scroll_layout_for_center_gender_duration.addWidget(label)
            self.center_gender_duration_labels[key] = label

    def update_center_gender_duration(self, roi_id, male_duration, female_duration):
        self.add_center_gender_duration_label(roi_id, "male")
        self.add_center_gender_duration_label(roi_id, "female")
        male_key = (roi_id, "male")
        female_key = (roi_id, "female")
        if male_key in self.center_gender_duration_labels:
            self.center_gender_duration_labels[male_key].setText(
                f"ROI {roi_id} (male): Center Duration: {male_duration:.2f} s"
            )
        if female_key in self.center_gender_duration_labels:
            self.center_gender_duration_labels[female_key].setText(
                f"ROI {roi_id} (female): Center Duration: {female_duration:.2f} s"
            )

    # ----------------------------------------------------------------
    # Export
    # ----------------------------------------------------------------
    def export_dataframe(self):
        for video_path, video_thread in list(self.video_threads.items()):
            if not video_thread:
                continue

            default_export_name = os.path.splitext(video_path)[0] + "_analysis.csv"
            data = []
            num_rois = len(video_thread.initial_contours)

            for roi in range(num_rois):
                # Fix 12: start_time is now the real start time (no -360 adjustment needed)
                start_time = video_thread.mating_start_times.get(roi, "N/A")

                # Fix 11: mating_durations[roi] is now a single float, not a list
                current_duration = video_thread.mating_durations.get(roi, 0)
                longest_duration = current_duration if current_duration >= 360 else 0

                # Fix 21: use the actual duration value for mating_status
                mating_status = current_duration >= 360

                # Fix 29: center_mating_duration is now a running total float
                total_center_mating_duration = video_thread.center_mating_duration.get(roi, 0.0)
                # Fix 22: removed unexplained magic -15 subtraction

                outside_center_mating_duration = max(
                    0.0, longest_duration - total_center_mating_duration
                )

                center_male_duration = video_thread.center_gender_duration.get(roi, {}).get("male", 0)
                center_female_duration = video_thread.center_gender_duration.get(roi, {}).get("female", 0)
                pre_mating_male = video_thread.pre_mating_center_gender_duration.get(roi, {}).get("male", 0)
                pre_mating_female = video_thread.pre_mating_center_gender_duration.get(roi, {}).get("female", 0)
                post_mating_male = center_male_duration - pre_mating_male
                post_mating_female = center_female_duration - pre_mating_female
                non_mating_center = (center_male_duration + center_female_duration) / 2

                data.append({
                    "ROI": roi,
                    "Mating Start Time (s)": start_time,
                    "Longest Duration (s)": longest_duration,
                    "Mating Status": mating_status,
                    "Center-Mating Duration (s)": total_center_mating_duration,
                    "Male Time in Center (s)": center_male_duration,
                    "Female Time in Center (s)": center_female_duration,
                    "Average Non-Mating Center (s)": non_mating_center,
                    "Outside Center Mating Duration (s)": outside_center_mating_duration,
                    "Pre-mating Male Center (s)": pre_mating_male,
                    "Post-mating Male Center (s)": post_mating_male,
                    "Pre-mating Female Center (s)": pre_mating_female,
                    "Post-mating Female Center (s)": post_mating_female,
                })

            df = pd.DataFrame(data)

            # Mark void ROIs
            void_rois = video_thread.void_rois
            for col in ["Mating Start Time (s)", "Longest Duration (s)", "Mating Status"]:
                df[col] = df.apply(
                    lambda row: "N/A" if void_rois.get(row["ROI"], False) else row[col],
                    axis=1,
                )

            df.to_csv(default_export_name, index=False)
            self.processing_status_label.setText(
                f"DataFrame for {video_path} exported successfully."
            )
            print(f"Exported: {default_export_name}")

    # ----------------------------------------------------------------
    # Navigation
    # ----------------------------------------------------------------
    def previous_video(self):
        if self.current_video_index > 0:
            self.current_video_index -= 1
            current_video_path = self.video_paths[self.current_video_index]
            if current_video_path in self.latest_frames:
                frame = self.latest_frames[current_video_path]
                # Fix 27: use .get() to avoid KeyError
                mating_durations = self.latest_mating_durations.get(current_video_path, {})
                self.update_video_frame(current_video_path, frame, mating_durations)

    def next_video(self):
        if self.current_video_index < len(self.video_paths) - 1:
            self.current_video_index += 1
            current_video_path = self.video_paths[self.current_video_index]
            if current_video_path in self.latest_frames:
                frame = self.latest_frames[current_video_path]
                # Fix 27: use .get() to avoid KeyError
                mating_durations = self.latest_mating_durations.get(current_video_path, {})
                self.update_video_frame(current_video_path, frame, mating_durations)

    # ----------------------------------------------------------------
    # Mating times display
    # ----------------------------------------------------------------
    def update_verified_mating_times(self, video_path, mating_times_dict):
        if not self.video_paths:
            return
        if not (0 <= self.current_video_index < len(self.video_paths)):
            return
        if video_path != self.video_paths[self.current_video_index]:
            return

        adjusted = {roi_id: t for roi_id, t in mating_times_dict.items()}
        rows = []
        for roi_id, start_time in adjusted.items():
            # Fix 20: mating_durations[roi] is now a float, not a list
            duration = self.video_threads[video_path].mating_durations.get(roi_id, 0)
            rows.append({"ROI": roi_id, "Start Time": start_time, "Mating Duration": duration})

        mating_times_df = pd.DataFrame(rows)
        self.mating_start_times_dfs[video_path] = mating_times_df

        mating_time_text = "\n".join(
            f"ROI {row['ROI']}: {row['Start Time']:.2f} s"
            for _, row in mating_times_df.iterrows()
        )
        self.verified_mating_times_label.setText(mating_time_text)

    # ----------------------------------------------------------------
    # Video selection and processing start
    # ----------------------------------------------------------------
    def select_video(self):
        video_paths, _ = QFileDialog.getOpenFileNames(self, "Select Videos")
        if video_paths:
            self.video_paths.extend(video_paths)
            for video_path in video_paths:
                # Fix 24: store FPS per video and update the shared field to the last selected
                fps = self._store_fps_from_video(video_path)
                if fps:
                    self.fps_input.setText(str(fps))
                self.video_threads[video_path] = None
                self.video_list_widget.addItem(video_path.split("/")[-1])
            self.start_button.setEnabled(len(self.video_paths) > 0)

    def start_processing(self):
        if not self.video_paths:
            self.show_error("No videos selected.")
            return
        # Fix 32: validate FPS
        fps = self._parse_fps()
        if fps is None:
            return

        self.start_button.setEnabled(False)
        self.select_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        skip_seconds = float(self.skip_frames_input.text()) if self.skip_frames_input.text() else 0
        skip_frames = int(skip_seconds * fps)
        try:
            perf_frame_skips = int(self.frame_skip_input.text())
            if perf_frame_skips < 1:
                perf_frame_skips = 1
        except ValueError:
            perf_frame_skips = 1

        for video_path in self.video_paths:
            if video_path not in self.video_threads or not self.video_threads[video_path]:
                # Fix 24: use per-video FPS if available
                video_fps = self.video_fps.get(video_path, fps)
                video_thread = VideoProcessingThread(
                    video_path, [], video_fps, skip_frames, perf_frame_skips
                )
                self.video_threads[video_path] = video_thread
                video_thread.frame_info.connect(self.update_frame_info)
                video_thread.frame_processed.connect(self.update_video_frame)
                video_thread.finished.connect(self.processing_finished)
                video_thread.finished.connect(lambda: self._on_thread_finished(video_thread))
                # Fix 17: wrap to discard the str argument from the signal
                video_thread.mating_analysis_complete.connect(lambda _: self.export_dataframe())
                video_thread.center_mating_duration_signal.connect(
                    self.update_center_mating_duration
                )
                video_thread.verified_mating_start_times.connect(
                    self.update_verified_mating_times
                )
                video_thread.center_gender_duration_signal.connect(
                    self.update_center_gender_duration
                )
                video_thread.void_roi_signal.connect(self.void_roi_handler)
                video_thread.start()

        self.prev_button.setEnabled(len(self.video_paths) > 1)
        self.next_button.setEnabled(len(self.video_paths) > 1)

    def stop_processing(self):
        for video_thread in self.video_threads.values():
            if video_thread and video_thread.is_running:
                video_thread.stop()
        self.processing_status_label.setText("Video processing stopped.")
        self.start_button.setEnabled(True)
        self.select_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def processing_finished(self):
        self.processing_status_label.setText("Video processing finished.")
        self.start_button.setEnabled(True)
        self.select_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    # ----------------------------------------------------------------
    # Frame update
    # ----------------------------------------------------------------
    def update_video_frame(self, video_path, frame, mating_durations):
        if 0 <= self.current_video_index < len(self.video_paths):
            current_video_path = self.video_paths[self.current_video_index]
            if video_path == current_video_path:
                height, width, channel = frame.shape
                bytes_per_line = 3 * width
                q_img = QImage(
                    frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888
                ).rgbSwapped()
                pixmap = QPixmap.fromImage(q_img)
                pixmap = pixmap.scaled(
                    self.video_label.width(),
                    self.video_label.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
                self.video_label.setPixmap(pixmap)

                # Fix 11: mating_durations values are now floats
                mating_duration_text = ""
                for roi_id, duration in mating_durations.items():
                    mating_duration_text += f"ROI {roi_id}: {duration:.2f} s\n"
                self.mating_duration_label.setText(mating_duration_text)

                if video_path in self.mating_start_times_dfs:
                    df = self.mating_start_times_dfs[video_path]
                    text = "\n".join(
                        f"ROI {row['ROI']}: {row['Start Time']:.2f} s"
                        for _, row in df.iterrows()
                    )
                    self.verified_mating_times_label.setText(text)
                else:
                    self.verified_mating_times_label.setText("")

        self.latest_frames[video_path] = frame
        self.latest_mating_durations[video_path] = mating_durations

    def update_frame_info(self, frame, time):
        self.frame_label.setText(f"Frame: {frame}")
        self.time_label.setText(f"Time (s): {time:.2f}")

    def void_roi_handler(self, video_path, roi_id):
        print(f"ROI {roi_id} in video {video_path} has been marked as void.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
