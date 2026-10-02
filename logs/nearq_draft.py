import difflib
def _n(s): return "".join(str(s).split())
def nearest_line(quote, text):
    """원문 줄 중 quote 와 가장 많이 겹치는 줄 (공백 무시 비교). (줄, 겹친 비율)"""
    q=_n(quote); best=(None,0.0)
    for line in text.split("\n"):
        l=line.strip()
        if not l: continue
        sm=difflib.SequenceMatcher(None,q,_n(l),autojunk=False)
        k=sum(b.size for b in sm.get_matching_blocks())/max(1,len(q))
        if k>best[1]: best=(l,k)
    return best
