"""tests/decode_ground_truth.py — JHora reverse-decoder. NO breakdown screens needed.
Identities: Ishta=sqrt(Uchcha*Chesta); Kashta=sqrt((60-U)(60-C)).
Uchcha is computed INDEPENDENTLY from longitude (validated <=0.1 vs JHora),
so Chesta = Ishta^2 / Uchcha. Kashta identity serves as typo checksum."""
DEEP_DEBIL = {"Sun":190,"Moon":213,"Mars":118,"Mercury":345,"Jupiter":275,"Venus":177,"Saturn":20}
def decode_row(planet, sid_lon, ishta, kashta):
    def arc(a,b):
        d = abs((a-b)%360); return min(d,360-d)
    U = arc(sid_lon, DEEP_DEBIL[planet])/3.0
    C = ishta*ishta/U
    K = ((60-U)*(60-C))**0.5
    assert abs(K-kashta) < 0.05, f"{planet}: checksum fail {K:.2f} vs {kashta} (transcription error?)"
    return {"uchcha": round(U,2), "cheshta": round(C,2)}
