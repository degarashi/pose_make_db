import logging as L

def divide_to_tuple(tags: list[str]) -> list[tuple[str, str]]:
    """
    タグ文字列リストをキーと値のタプルのリストに分割

    Args:
        tags (list[str]): タグ文字列のリスト（例: ["dir1=tagA", "dir2=tagB"]）

    Returns:
        list[tuple[str, str]]: キーと値のタプルのリスト
    """
    parsed_tags: list[tuple[str, str]] = []
    for tag_str in tags:
        if "=" in tag_str:
            # (valueがスペースを含んでいる場合でも動く筈)
            key, value = tag_str.split("=", 1)
            parsed_tags.append((key, value))
        else:
            L.warning(
                f"Skipping malformed tag: {tag_str}. Expected format 'key=value'."
            )
    return parsed_tags
