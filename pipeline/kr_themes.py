"""
kr_themes.py — 테마↔국내 종목 관계도 + 미국 촉발 이벤트→국내 섹터 연결 규칙.
AI(analyze)가 '오늘 국내에서 먼저 움직일 종목'을 자동 추출할 때 참조하는 지식베이스.
※ 투자 권유가 아니라 '뉴스와 연관성이 높은 종목' 후보를 뽑기 위한 참고 맵.
"""

# 테마 → 국내 대표 종목(관련성 높은 순). 필요 시 여기만 갱신하면 됨.
THEME_STOCKS = {
    "AI반도체": ["SK하이닉스", "한미반도체", "이수페타시스", "삼성전자", "리노공업"],
    "HBM": ["SK하이닉스", "한미반도체", "이수페타시스", "테크윙", "오픈엣지테크놀로지"],
    "반도체장비": ["한미반도체", "주성엔지니어링", "원익IPS", "HPSP", "이오테크닉스"],
    "반도체소부장": ["동진쎄미켐", "솔브레인", "티씨케이", "하나머티리얼즈", "원익QnC"],
    "전력기기": ["제룡전기", "LS ELECTRIC", "HD현대일렉트릭", "효성중공업", "산일전기"],
    "전선": ["LS", "대한전선", "가온전선"],
    "원전_SMR": ["두산에너빌리티", "비에이치아이", "한전기술", "우리기술", "보성파워텍"],
    "데이터센터_냉각": ["LG전자", "에스에이엠지", "GST", "케이엔솔", "누리플렉스"],
    "PCB_기판": ["이수페타시스", "대덕전자", "심텍", "코리아써키트", "해성디에스"],
    "2차전지": ["LG에너지솔루션", "삼성SDI", "에코프로비엠", "포스코퓨처엠", "엘앤에프"],
    "방산": ["한화에어로스페이스", "현대로템", "LIG넥스원", "한국항공우주", "풍산"],
    "조선": ["HD한국조선해양", "한화오션", "삼성중공업", "HD현대중공업", "STX중공업"],
    "바이오": ["삼성바이오로직스", "셀트리온", "알테오젠", "유한양행", "리가켐바이오"],
    "자동차": ["현대차", "기아", "현대모비스", "HL만도"],
    "인터넷_플랫폼": ["네이버", "카카오", "크래프톤"],
    "로봇": ["두산로보틱스", "레인보우로보틱스", "에스비비테크"],
    "우주항공": ["한국항공우주", "쎄트렉아이", "인텔리안테크"],
    "엔터_미디어": ["하이브", "에스엠", "JYP Ent.", "와이지엔터테인먼트"],
}

# 미국/글로벌 촉발 신호(키워드) → 국내 우선 반응 섹터
# 뉴스 헤드라인/종목명에 아래 키워드가 있으면 해당 국내 섹터를 후보로 끌어올림.
US_TRIGGER_TO_KR = {
    "nvidia":       ["AI반도체", "HBM", "PCB_기판", "전력기기"],
    "엔비디아":      ["AI반도체", "HBM", "PCB_기판", "전력기기"],
    "amd":          ["AI반도체", "반도체장비"],
    "broadcom":     ["AI반도체", "PCB_기판"],
    "micron":       ["HBM", "반도체소부장"],
    "tsmc":         ["반도체장비", "반도체소부장"],
    "asml":         ["반도체장비", "반도체소부장"],
    "microsoft":    ["AI반도체", "데이터센터_냉각"],
    "openai":       ["AI반도체", "데이터센터_냉각", "전력기기"],
    "data center":  ["전력기기", "데이터센터_냉각", "원전_SMR"],
    "power grid":   ["전력기기", "전선", "원전_SMR"],
    "nuclear":      ["원전_SMR", "전력기기"],
    "smr":          ["원전_SMR"],
    "tesla":        ["2차전지", "자동차"],
    "battery":      ["2차전지"],
    "ev ":          ["2차전지", "자동차"],
    "defense":      ["방산"],
    "지정학":        ["방산", "조선"],
    "oil":          ["조선"],
    "shipbuild":    ["조선"],
    "robot":        ["로봇"],
    "biotech":      ["바이오"],
    "obesity":      ["바이오"],
}

def stocks_for_theme(theme, n=5):
    return THEME_STOCKS.get(theme, [])[:n]

def themes_from_headlines(headlines):
    """헤드라인 리스트에서 촉발 키워드를 찾아 국내 섹터 후보를 우선순위대로 반환."""
    hits, seen = [], set()
    joined = " ".join(headlines).lower()
    for kw, themes in US_TRIGGER_TO_KR.items():
        if kw.lower() in joined:
            for t in themes:
                if t not in seen:
                    seen.add(t); hits.append(t)
    return hits

def context_block(headlines):
    """analyze 프롬프트에 넣을 '테마→종목 관계도' 텍스트. 오늘 뉴스와 관련된 것만 추림."""
    themes = themes_from_headlines(headlines) or list(THEME_STOCKS.keys())[:6]
    lines = [f"- {t}: {', '.join(stocks_for_theme(t))}" for t in themes[:8]]
    return "오늘 뉴스와 연관성 높은 테마→국내 대표종목(참고용):\n" + "\n".join(lines)

if __name__ == "__main__":
    hs = ["Nvidia jumps on AI data center deal", "Oil rises on supply fears"]
    print(themes_from_headlines(hs))
    print(context_block(hs))
