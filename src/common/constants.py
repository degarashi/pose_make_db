from enum import Enum, auto


class BlazePoseLandmark(Enum):
    """BlazePoseのランドマークを表すEnum"""

    def _generate_next_value_(name, start, count, last_values):
        return count  # count は0から始まるので、0,1,2,...となる

    nose = auto()
    left_eye_inner = auto()
    left_eye = auto()
    left_eye_outer = auto()
    right_eye_inner = auto()
    right_eye = auto()
    right_eye_outer = auto()
    left_ear = auto()
    right_ear = auto()
    mouth_left = auto()
    mouth_right = auto()
    left_shoulder = auto()
    right_shoulder = auto()
    left_elbow = auto()
    right_elbow = auto()
    left_wrist = auto()
    right_wrist = auto()
    left_pinky = auto()
    right_pinky = auto()
    left_index = auto()
    right_index = auto()
    left_thumb = auto()
    right_thumb = auto()
    left_hip = auto()
    right_hip = auto()
    left_knee = auto()
    right_knee = auto()
    left_ankle = auto()
    right_ankle = auto()
    left_heel = auto()
    right_heel = auto()
    left_foot_index = auto()
    right_foot_index = auto()


assert BlazePoseLandmark.nose.value == 0

BLAZEPOSE_LANDMARK_LEN = 33
assert (
    len(BlazePoseLandmark) == BLAZEPOSE_LANDMARK_LEN
)  # Enumのメンバー数が一致することを確認


class CocoLandmark(Enum):
    """COCO（person keypoints）のランドマークを表すEnum"""

    def _generate_next_value_(name, start, count, last_values):
        return count  # 0,1,2,...となる

    nose = auto()
    left_eye = auto()
    right_eye = auto()
    left_ear = auto()
    right_ear = auto()
    left_shoulder = auto()
    right_shoulder = auto()
    left_elbow = auto()
    right_elbow = auto()
    left_wrist = auto()
    right_wrist = auto()
    left_hip = auto()
    right_hip = auto()
    left_knee = auto()
    right_knee = auto()
    left_ankle = auto()
    right_ankle = auto()


assert CocoLandmark.nose.value == 0

COCO_LANDMARK_LEN = 17
assert len(CocoLandmark) == COCO_LANDMARK_LEN  # Enumのメンバー数が一致することを確認


# BlazePose → COCO の変換辞書
BLAZEPOSE_TO_COCO = {
    BlazePoseLandmark.nose: CocoLandmark.nose,
    BlazePoseLandmark.left_eye: CocoLandmark.left_eye,
    BlazePoseLandmark.right_eye: CocoLandmark.right_eye,
    BlazePoseLandmark.left_ear: CocoLandmark.left_ear,
    BlazePoseLandmark.right_ear: CocoLandmark.right_ear,
    BlazePoseLandmark.left_shoulder: CocoLandmark.left_shoulder,
    BlazePoseLandmark.right_shoulder: CocoLandmark.right_shoulder,
    BlazePoseLandmark.left_elbow: CocoLandmark.left_elbow,
    BlazePoseLandmark.right_elbow: CocoLandmark.right_elbow,
    BlazePoseLandmark.left_wrist: CocoLandmark.left_wrist,
    BlazePoseLandmark.right_wrist: CocoLandmark.right_wrist,
    BlazePoseLandmark.left_hip: CocoLandmark.left_hip,
    BlazePoseLandmark.right_hip: CocoLandmark.right_hip,
    BlazePoseLandmark.left_knee: CocoLandmark.left_knee,
    BlazePoseLandmark.right_knee: CocoLandmark.right_knee,
    BlazePoseLandmark.left_ankle: CocoLandmark.left_ankle,
    BlazePoseLandmark.right_ankle: CocoLandmark.right_ankle,
}

# COCO → BlazePose の変換辞書
COCO_TO_BLAZEPOSE = {v: k for k, v in BLAZEPOSE_TO_COCO.items()}


# BlazePose → COCO
def blazepose_to_coco(landmark: BlazePoseLandmark) -> CocoLandmark:
    if landmark not in BLAZEPOSE_TO_COCO:
        raise ValueError(f"対応するCOCOランドマークが存在しません: {landmark}")
    return BLAZEPOSE_TO_COCO[landmark]


# COCO → BlazePose
def coco_to_blazepose(landmark: CocoLandmark) -> BlazePoseLandmark:
    if landmark not in COCO_TO_BLAZEPOSE:
        raise ValueError(f"対応するBlazePoseランドマークが存在しません: {landmark}")
    return COCO_TO_BLAZEPOSE[landmark]
