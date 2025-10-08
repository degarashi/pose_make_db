from __future__ import annotations

import os
from typing import Any

import mediapipe as mp
import numpy as np
from PIL import Image, ImageOps

from common.constants import BLAZEPOSE_LANDMARK_LEN
from landmark import Landmark


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

    @staticmethod
    def _load_image_with_exif(img_path: str) -> mp.Image:
        """
        画像のEXIFの回転情報を適用したうえでmp.Imageを生成
        """
        try:
            with Image.open(img_path) as img:
                # EXIFの回転を適用（EXIFがない場合はそのまま）
                img = ImageOps.exif_transpose(img)
                # MediaPipeはRGBを期待
                img = img.convert("RGB")
                np_img = np.asarray(img)
        except Exception as e:
            raise EstimateFailed(f"画像読み込みに失敗しました: {e}")

        try:
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np_img)
        except Exception as e:
            raise EstimateFailed(f"画像の変換に失敗しました: {e}")

        return mp_image

    def estimate(self, img_path: str) -> list[list[Landmark]]:
        """
        指定された画像ファイルパスから姿勢推定を実行し、複数体のランドマークリストを返す

        Args:
            img_path: 姿勢推定を行う画像ファイルのパス

        Returns:
            推定されたランドマーク(Landmark)のリストのリスト
            （各人物ごとにランドマークのリストを持つ）

        Raises:
            EstimateFailed: 姿勢推定が失敗した場合
        """
        # ファイル存在確認と例外処理追加
        if not os.path.isfile(img_path):
            raise EstimateFailed(f"画像ファイルが存在しません: {img_path}")

        # EXIFの回転を適用してmp.Imageを生成
        mp_image = self._load_image_with_exif(img_path)

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

        all_marks: list[list[Landmark]] = []

        # 複数体のポーズに対応
        for idx, marks in enumerate(pose_landmarker_result.pose_world_landmarks):
            try:
                marks_2d = pose_landmarker_result.pose_landmarks[idx]
            except IndexError:
                raise EstimateFailed("ポーズデータが不足しています")

            if len(marks) != len(marks_2d):
                raise EstimateFailed("3Dと2Dのランドマーク数が一致しません")

            marksList: list[Landmark] = []
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

            all_marks.append(marksList)

        return all_marks
