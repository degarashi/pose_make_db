from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import mediapipe as mp

from common.constants import BLAZEPOSE_LANDMARK_LEN

# 型エイリアス
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]


@dataclass(frozen=True)
class Landmark:
    """
    姿勢推定されたランドマークの情報を保持するデータクラス。

    Attributes
    ----------
    visibility : float
        キーポイントがフレーム内に存在し、他のオブジェクトで遮蔽されていない確率（0.0〜1.0）。
    presence : float
        キーポイントがフレーム内に存在する確率（0.0〜1.0）。
    pos : Vec3
        キーポイントの3次元座標 (x, y, z)。
        単位系や座標系は姿勢推定モデルに依存。
    pos_2d : Vec2
        キーポイントの2次元座標 (x, y)。
        画像座標系や正規化座標系など、用途に応じて解釈。
    """

    visibility: float
    presence: float
    pos: Vec3
    pos_2d: Vec2

    def __post_init__(self) -> None:
        # 値の範囲チェック
        if not (0.0 <= self.visibility <= 1.0):
            raise ValueError(
                f"visibility must be between 0.0 and 1.0, got {self.visibility}"
            )
        if not (0.0 <= self.presence <= 1.0):
            raise ValueError(
                f"presence must be between 0.0 and 1.0, got {self.presence}"
            )

    def is_confident(self, threshold: float = 0.5) -> bool:
        """
        visibility と presence が閾値以上かを判定。

        Parameters
        ----------
        threshold : float, optional
            判定に用いる閾値（デフォルトは0.5）。

        Returns
        -------
        bool
            両方の値が閾値以上なら True。
        """
        return self.visibility >= threshold and self.presence >= threshold


class EstimateFailed(Exception):
    pass


class Estimate:
    """
    MediaPipe Pose Landmarkerを使用して画像から姿勢推定を行うクラス
    コンテキストマネージャーとして使用することを想定
    """

    landmarker: Any
    poseLandmarker: Any
    options: Any

    def __init__(self, model_path: str, num_poses: int = 1):
        """
        Pose Landmarkerの初期化
        指定されたモデルファイルを使用し、画像モードで一度に指定数のポーズを検出するように設定
        """
        baseOptions = mp.tasks.BaseOptions
        self.poseLandmarker = mp.tasks.vision.PoseLandmarker
        poseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        visionRunningMode = mp.tasks.vision.RunningMode
        self.options: mp.tasks.vision.PoseLandmarkerOptions = poseLandmarkerOptions(
            base_options=baseOptions(model_asset_path=model_path),
            running_mode=visionRunningMode.IMAGE,
            num_poses=num_poses,
        )

    def __enter__(self) -> "Estimate":
        """
        コンテキストマネージャーのエントリポイント
        Pose Landmarkerインスタンスを作成し返す
        """
        self.landmarker = self.poseLandmarker.create_from_options(self.options)
        return self

    def __exit__(self, e_type, e_val, e_tb) -> None:
        """
        コンテキストマネージャーの終了ポイント
        Pose Landmarkerのリソースを解放
        """
        if hasattr(self.landmarker, "close"):
            self.landmarker.close()

    def estimate(self, img_path: str) -> list[Landmark]:
        """
        指定された画像ファイルパスから姿勢推定を実行し、ランドマークのリストを返す

        Args:
            img_path: 姿勢推定を行う画像ファイルのパス

        Returns:
            推定されたランドマーク(Landmark)のリスト

        Raises:
            EstimateFailed: 姿勢推定が失敗した場合
        """
        # ファイル存在確認と例外処理追加
        if not os.path.isfile(img_path):
            raise EstimateFailed(f"画像ファイルが存在しません: {img_path}")

        try:
            mp_image = mp.Image.create_from_file(img_path)
        except Exception as e:
            raise EstimateFailed(f"画像読み込みに失敗しました: {e}")

        # 解析実行と結果検証
        try:
            pose_landmarker_result: mp.tasks.vision.PoseLandmarkerResult = (
                self.landmarker.detect(mp_image)
            )
        except Exception as e:
            raise EstimateFailed(f"姿勢推定の実行に失敗しました: {e}")

        if (
            not pose_landmarker_result.pose_world_landmarks
            or not pose_landmarker_result.pose_landmarks
        ):
            raise EstimateFailed("ランドマークが検出されませんでした")

        marksList: list[Landmark] = []

        try:
            marks = pose_landmarker_result.pose_world_landmarks[0]
            marks_2d = pose_landmarker_result.pose_landmarks[0]
        except IndexError:
            raise EstimateFailed("ポーズデータが不足しています")

        if len(marks) != len(marks_2d):
            raise EstimateFailed("3Dと2Dのランドマーク数が一致しません")

        for lm_idx, lm in enumerate(marks):
            pos_2d = marks_2d[lm_idx]
            marksList.append(
                Landmark(
                    lm.visibility,
                    lm.presence,
                    (lm.x, lm.y, lm.z),
                    (pos_2d.x, pos_2d.y),
                )
            )

        if len(marksList) < BLAZEPOSE_LANDMARK_LEN:
            raise EstimateFailed(
                f"ランドマーク数が不足しています: {len(marksList)}/{BLAZEPOSE_LANDMARK_LEN}"
            )

        return marksList
