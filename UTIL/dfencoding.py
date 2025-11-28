import pandas as pd


def dfencoding_auto(df: pd.DataFrame) -> pd.DataFrame:
    """
    문자열 컬럼 중 한글 깨짐이 의심되는 컬럼을 자동 감지해 디코딩 처리
    - latin1 → euc-kr 디코딩 시도
    - bytes 타입은 건드리지 않음

    :param df: 원본 DataFrame
    :return: 디코딩 처리된 DataFrame
    """
    import re

    def is_mangled_korean(text: str) -> bool:
        """깨진 한글 추정 기준: 한글이 아닌 이상한 문자 + 특수문자가 반복"""
        if not isinstance(text, str):
            return False
        # 흔히 깨진 문자들 (몽골어, ï¿½, Ã­, Ã« 등)
        return bool(re.search(r'[Ã¤Ã«Ã­Ã©Ã¥Ã¼âˆ’ï¿½]', text))

    def decode_if_needed(val):
        if isinstance(val, str) and is_mangled_korean(val):
            try:
                return val.encode("latin1", errors="replace").decode("euc-kr", errors="replace")
            except:
                return val
        return val

    # 문자열 컬럼만 선택
    str_columns = df.select_dtypes(include='object').columns
    for col in str_columns:
        sample = df[col].dropna().astype(str).head(5).tolist()
        if any(is_mangled_korean(s) for s in sample):
            df[col] = df[col].apply(decode_if_needed)

    return df
