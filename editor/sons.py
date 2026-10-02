"""Efeitos sonoros simples gerados com o próprio ffmpeg (sem pacote externo)."""
from .base import RECURSOS, ffmpeg

PASTA = RECURSOS / "sons"

RECEITAS = {
    "whoosh": ("anoisesrc=color=pink:d=0.55:a=0.9", "bandpass=f=1400:w=1800,afade=t=in:d=0.3:curve=exp,"
               "afade=t=out:st=0.3:d=0.25"),
    "whoosh_sobe": ("anoisesrc=color=white:d=0.6:a=0.8", "highpass=f=600,lowpass=f=5000,"
                    "afade=t=in:d=0.45:curve=qsin,afade=t=out:st=0.45:d=0.15"),
    "swish": ("anoisesrc=color=white:d=0.22:a=0.8", "highpass=f=2500,afade=t=in:d=0.08,afade=t=out:st=0.08:d=0.14"),
    "pop": ("aevalsrc='sin(2*PI*(380+700*exp(-t*45))*t)*exp(-t*28)':d=0.16", "highpass=f=120"),
    "clique": ("aevalsrc='(random(0)*2-1)*exp(-t*900)+sin(2*PI*2400*t)*exp(-t*300)':d=0.04", "highpass=f=800"),
    "tique": ("aevalsrc='sin(2*PI*2200*t)*exp(-mod(t,0.08)*220)*lt(mod(t,0.08),0.012)':d=0.8", "highpass=f=500"),
    "ding": ("aevalsrc='(0.6*sin(2*PI*1318*t)+0.3*sin(2*PI*2637*t)+0.15*sin(2*PI*3955*t))*exp(-t*4.5)':d=1.0",
             "afade=t=in:d=0.004"),
    "impacto": ("aevalsrc='sin(2*PI*(55+90*exp(-t*18))*t)*exp(-t*5)+(random(0)*2-1)*exp(-t*35)*0.5':d=0.7",
                "lowpass=f=2500"),
    "impacto_seco": ("aevalsrc='sin(2*PI*(90+120*exp(-t*40))*t)*exp(-t*14)+(random(0)*2-1)*exp(-t*60)*0.6':d=0.3",
                     "lowpass=f=3500"),
    "rabisco": ("anoisesrc=color=pink:d=0.45:a=0.7", "bandpass=f=3000:w=2500,"
                "volume='0.6+0.4*sin(2*PI*14*t)':eval=frame,afade=t=out:st=0.3:d=0.15"),
    "teclado": ("aevalsrc='(random(0)*2-1)*exp(-mod(t,0.09)*500)*(0.6+0.4*sin(t*37))':d=1.2",
                "highpass=f=1500,afade=t=out:st=1.0:d=0.2"),
}


def arquivo(tipo):
    PASTA.mkdir(parents=True, exist_ok=True)
    saida = PASTA / f"{tipo}.wav"
    if not saida.exists():
        fonte_lavfi, filtro = RECEITAS[tipo]
        tmp = PASTA / f"_{tipo}.wav"
        ffmpeg("-f", "lavfi", "-i", fonte_lavfi, "-af", filtro + ",aresample=48000",
               "-ac", 2, "-ar", 48000, tmp)
        # pico em -1 dBFS; o volume final é dado na mixagem
        from .base import rodar
        import re
        r = rodar(["ffmpeg", "-hide_banner", "-i", str(tmp), "-af", "volumedetect", "-f", "null", "-"])
        pico = float(re.search(r"max_volume: (-?[\d.]+)", r.stderr).group(1))
        ffmpeg("-i", tmp, "-af", f"volume={-1 - pico}dB", saida)
        tmp.unlink()
    return saida


def espalhar(sons, distancia=0.6):
    """Nunca dois sons a menos de 0,6 s: fica o mais forte."""
    out = []
    for s in sorted(sons, key=lambda s: s["t"]):
        if out and s["t"] - out[-1]["t"] < distancia:
            if s["db"] > out[-1]["db"]:
                out[-1] = s
            continue
        out.append(s)
    return out
