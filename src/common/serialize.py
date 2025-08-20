import struct


def vec_serialize(vector: list[float]) -> bytes:
    """
    floatのリストをコンパクトなbytes形式にシリアライズ
    """
    return struct.pack("%sf" % len(vector), *vector)


def vec_deserialize(vector_bytes: bytes) -> list[float]:
    """
    バイト列からfloatのリスト(ベクトル)をデシリアライズ
    """
    # バイト列の長さを取得
    byte_length: int = len(vector_bytes)
    # floatのサイズは通常4バイトなので、要素数を計算
    num_elements: int = byte_length // 4
    # バイト列をfloatのリストにアンパック
    return list(struct.unpack("%sf" % num_elements, vector_bytes))


# pythonコマンドから呼び出された時のみ実行
if __name__ == "__main__":

    def test_vec_serialize_deserialize():
        """
        vec_serializeとvec_deserializeのテスト
        """
        test_vector = [1.0, 2.5, -3.14, 0.0, 100.5]
        serialized_vector = vec_serialize(test_vector)
        deserialized_vector = vec_deserialize(serialized_vector)

        # 元のベクトルとデシリアライズされたベクトルが(ほぼ)一致するか確認
        assert all(
            abs(a - b) < 1e-6
            for a, b in zip(test_vector, deserialized_vector)
        ), "Serialization/Deserialization failed!"
        print("vec_serialize and vec_deserialize tests passed.")

    # テストを実行
    test_vec_serialize_deserialize()
