from __future__ import annotations


class Rect2D:
    """
    2次元矩形を表現するクラス
    """

    def __init__(self, x_min: float, y_min: float, x_max: float, y_max: float) -> None:
        """
        @brief コンストラクタ
        @param x_min 最小x座標
        @param y_min 最小y座標
        @param x_max 最大x座標
        @param y_max 最大y座標
        @exception ValueError 無効な座標が指定された場合の例外
        """
        self.x_min = x_min
        self.y_min = y_min
        self.x_max = x_max
        self.y_max = y_max
        self._validate()

    def is_valid(self) -> bool:
        """
        @brief 矩形の有効性チェック
        @return 有効な矩形ならTrue、そうでなければFalse
        """
        return self.x_min > self.x_max or self.y_min > self.y_max

    def _validate(self) -> None:
        """
        @brief 矩形座標の妥当性検証
        @exception ValueError 無効な座標が指定された場合の例外
        """
        if self.is_valid():
            raise ValueError(
                "Invalid rectangle coordinates: min must be less than or equal to max"
            )

    @property
    def width(self) -> float:
        """
        @brief 矩形の幅取得
        @return 矩形の幅
        """
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        """
        @brief 矩形の高さ取得
        @return 矩形の高さ
        """
        return self.y_max - self.y_min

    def __repr__(self) -> str:
        """
        @brief 矩形の文字列表現取得
        @return 矩形の文字列表現
        """
        return (
            f"{self.__class__.__name__}"
            f"(x_min={self.x_min}, y_min={self.y_min}, "
            f"x_max={self.x_max}, y_max={self.y_max})"
        )

    def add_margin(self, margin_x: float, margin_y: float) -> Rect2D:
        """
        @brief 指定マージンを加えた矩形生成
        @param margin_x x方向のマージン
        @param margin_y y方向のマージン
        @return 新しいRect2Dインスタンス
        @exception ValueError マージンが負の場合の例外
        """
        return self.add_margin_sides(margin_x, margin_x, margin_y, margin_y)

    def add_margin_sides(
        self, left: float, right: float, top: float, bottom: float
    ) -> Rect2D:
        """
        @brief 左右上下別々のマージンを加えた矩形生成
        @param left 左方向のマージン
        @param right 右方向のマージン
        @param top 上方向のマージン
        @param bottom 下方向のマージン
        @return 新しいRect2Dインスタンス
        @exception ValueError マージンが負の場合の例外
        """
        if left < 0 or right < 0 or top < 0 or bottom < 0:
            raise ValueError("Margins must be non-negative")
        return Rect2D(
            self.x_min - left,
            self.y_min - bottom,
            self.x_max + right,
            self.y_max + top,
        )

    def add_margin_ratio_sides(
        self,
        left_ratio: float,
        right_ratio: float,
        top_ratio: float,
        bottom_ratio: float,
    ) -> Rect2D:
        """
        @brief 左右上下別々のマージン比率を加えた矩形生成
        @param left_ratio 左方向のマージン比率
        @param right_ratio 右方向のマージン比率
        @param top_ratio 上方向のマージン比率
        @param bottom_ratio 下方向のマージン比率
        @return 新しいRect2Dインスタンス
        @exception ValueError マージン比率が負の場合の例外
        """
        return self.add_margin_sides(
            self.width * left_ratio,
            self.width * right_ratio,
            self.height * top_ratio,
            self.height * bottom_ratio,
        )

    def add_margin_ratio(self, n: float, m: float) -> Rect2D:
        """
        @brief 幅と高さに対する比率でマージンを加えた矩形生成
        @param n 幅に対するマージン比率
        @param m 高さに対するマージン比率
        @return 新しいRect2Dインスタンス
        @exception ValueError マージン比率が負の場合の例外
        """
        if n < 0 or m < 0:
            raise ValueError("Margin ratios must be non-negative")
        return self.add_margin(self.width * n, self.height * m)

    def clip(self, x_min: float, y_min: float, x_max: float, y_max: float) -> Rect2D:
        """
        @brief 指定範囲に矩形をクリップ
        @param x_min 許容される最小x座標
        @param y_min 許容される最小y座標
        @param x_max 許容される最大x座標
        @param y_max 許容される最大y座標
        @return 新しいRect2Dインスタンス
        @exception ValueError 無効なクリッピング座標が指定された場合の例外
        @exception ValueError クリッピング結果が空矩形となる場合の例外
        """
        if x_min > x_max or y_min > y_max:
            raise ValueError(
                "Invalid clipping coordinates: min must be less than or equal to max"
            )
        new_x_min = max(self.x_min, x_min)
        new_y_min = max(self.y_min, y_min)
        new_x_max = min(self.x_max, x_max)
        new_y_max = min(self.y_max, y_max)
        return Rect2D(new_x_min, new_y_min, new_x_max, new_y_max)

    def clip_0_1(self) -> Rect2D:
        """
        @brief 矩形を0.0から1.0の範囲にクリップ
        @return 新しいRect2Dインスタンス
        """
        return self.clip(0.0, 0.0, 1.0, 1.0)
