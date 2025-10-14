from dataclasses import dataclass

# 型エイリアス
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]

# 閾値定数
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.5


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

    def is_confident(self, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> bool:
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
