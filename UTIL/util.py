def fmt(val) -> str:
    """
    숫자(int/float/str) → '1,234' 형식으로 포맷
    숫자가 아니면 그대로 문자열 반환
    """
    try:
        # 👉 먼저 실제 숫자인 경우 바로 처리
        if isinstance(val, int):
            return f"{val:,}"

        if isinstance(val, float):
            # 소수점이 있으면 자연스럽게 처리 / 정수면 소수 제거
            if val.is_integer():
                return f"{int(val):,}"
            else:
                return f"{val:,.1f}"

        # 👉 문자열인 경우 처리
        text = str(val).replace(",", "").strip()

        # 문자열이지만 int/float로 변환 가능할 때
        if "." in text:
            num = float(text)
            if num.is_integer():
                return f"{int(num):,}"
            else:
                return f"{num:,.1f}"
        else:
            num = int(text)
            return f"{num:,}"

    except:
        # 숫자로 볼 수 없는 경우 → 그대로 텍스트 반환
        return str(val)