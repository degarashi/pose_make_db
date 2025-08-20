import numpy as np


def vec_serialize(vector: list[float]) -> bytes:
    """
    floatのリスト（ベクトル）をバイト列にシリアライズ
    """
    return np.asarray(vector).astype(np.float32).tobytes()


def vec_deserialize(vector_bytes: bytes) -> list[float]:
    """
    バイト列からfloatのリスト（ベクトル）をデシリアライズ
    """
    return np.frombuffer(vector_bytes, dtype=np.float32).tolist()
