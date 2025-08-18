import mediapipe as mp
from dataclasses import dataclass
from typing import List, Tuple, Any


@dataclass
class Landmark:
    """
    姿勢推定されたランドマークの情報を保持するデータクラス
    visibility: キーポイントがフレーム内に存在し、他のオブジェクトで遮蔽されていない確率
    presence: キーポイントがフレーム内に存在する確率
    pos: キーポイントの3次元座標 (x, y, z)
    """

    visibility: float
    presence: float
    pos: Tuple[float, float, float]


class EstimateFailed(BaseException):
    pass


class Estimate:
    """
    MediaPipe Pose Landmarkerを使用して画像から姿勢推定を行うクラス
    コンテキストマネージャーとして使用することを想定
    """

    landmarker: Any
    poseLandmarker: Any
    options: Any

    def __init__(self, model_path: str):
        """
        Pose Landmarkerの初期化
        指定されたモデルファイルを使用し、画像モードで一度に1つのポーズを検出するように設定
        """
        baseOptions = mp.tasks.BaseOptions
        self.poseLandmarker = mp.tasks.vision.PoseLandmarker
        poseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        visionRunningMode = mp.tasks.vision.RunningMode
        self.options: mp.tasks.vision.PoseLandmarkerOptions = poseLandmarkerOptions(
            base_options=baseOptions(model_asset_path=model_path),
            running_mode=visionRunningMode.IMAGE,
            num_poses=1,
        )  # とりあえず1人分の解析しかしない

    def __enter__(self) -> "Estimate":
        """
        コンテキストマネージャーのエントリポイント
        Pose Landmarkerインスタンスを作成し返す
        """
        self.landmarker = self.poseLandmarker.create_from_options(
            self.options
        ).__enter__()
        return self

    def __exit__(self, e_type, _, __) -> None:
        """
        コンテキストマネージャーの終了ポイント
        Pose Landmarkerのリソースを解放
        """
        self.landmarker.__exit__(e_type, _, __)

    def estimate(self, img_path: str) -> List[Landmark]:
        """
        指定された画像ファイルパスから姿勢推定を実行し、ランドマークのリストを返す

        Args:
            img_path: 姿勢推定を行う画像ファイルのパス

        Returns:
            推定されたランドマーク(Landmark)のリスト

        Raises:
            EstimateFailed: 姿勢推定が失敗した場合(例: ランドマークが33個未満しか検出されなかった場合)
        """
        # 画像ファイルの読み込み
        mp_image = mp.Image.create_from_file(img_path)
        # 解析実行
        pose_landmarker_result: mp.tasks.vision.PoseLandmarkerResult = (
            self.landmarker.detect(mp_image)
        )

        # visibility フレーム内に存在し他のオブジェクトで遮蔽されていないキーポイントのprobability
        # presence フレーム内に存在するキーポイントのprobability

        marksList: List[Landmark] = []
        # とりあえず姿勢の解析は考えず、全部の座標を格納
        # pose_world_landmarks は検出されたポーズごとにランドマークのリストを持つ
        # ここでは num_poses=1 なので最初のポーズのランドマークのみを処理する
        for marks in pose_landmarker_result.pose_world_landmarks:
            for lm in marks:
                marksList.append(
                    Landmark(lm.visibility, lm.presence, (lm.x, lm.y, lm.z))
                )
            break  # 最初のポーズのみを処理するため、ループを抜ける

        # mediapipeのランドマークポイントは33個
        # 検出された数がそれに満たない場合はエラーとする
        if len(marksList) < 33:
            raise EstimateFailed()
        return marksList
