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
    # --- sons divertidos (edição com mais impacto) ---
    # acorde que sobe, de "acertou!": quando ela aprova alguma coisa
    "aprovado": ("aevalsrc='0.5*sin(2*PI*1046.5*t)*exp(-5*t)*min(1,max(0,(t-0)*250))"
                 "+0.5*min(1,max(0,(t-0.09)*250))*sin(2*PI*1318.5*(t-0.09))*exp(-5*(t-0.09))"
                 "+0.6*min(1,max(0,(t-0.18)*250))*sin(2*PI*1568*(t-0.18))*exp(-3.2*(t-0.18))"
                 "+0.18*min(1,max(0,(t-0.18)*250))*sin(2*PI*3136*(t-0.18))*exp(-6*(t-0.18))':d=1.2",
                 "afade=t=in:d=0.004,afade=t=out:st=1.0:d=0.2"),
    # "uóóó uóóó" descendo: quando ela reprova
    "reprovado": ("aevalsrc='max(0,min(1,(0.34-t)*60))*min(1,max(0,(t-0)*250))*(0.6*sin(2*PI*(311-40*t)*t)+0.25*sin(4*PI*(311-40*t)*t))"
                  "+min(1,max(0,(t-0.38)*250))*(0.6*sin(2*PI*(262-70*(t-0.38))*(t-0.38))+0.25*sin(4*PI*(262-70*(t-0.38))*(t-0.38)))"
                  "*exp(-1.2*(t-0.38))*(0.8+0.2*sin(2*PI*7*t))':d=1.3",
                  "lowpass=f=2600,afade=t=in:d=0.01,afade=t=out:st=1.1:d=0.2"),
    # rufar de tambor que cresce + batida no fim: antes de abrir o pacote
    "tambor": ("aevalsrc='lt(t,1.6)*(random(0)*2-1)*(0.25+0.75*t/1.6)*(0.55+0.45*sin(2*PI*26*t))"
               "+gte(t,1.6)*((random(0)*2-1)*0.7*exp(-5*(t-1.6))+0.9*sin(2*PI*68*(t-1.6))*exp(-6*(t-1.6)))':d=2.4",
               "highpass=f=55,lowpass=f=2400,afade=t=out:st=2.1:d=0.3"),
    # brilho de revelação ("tcharam")
    "brilho": ("aevalsrc='0.45*sin(2*PI*1568*t)*exp(-6*t)*min(1,max(0,(t-0)*250))"
               "+0.4*min(1,max(0,(t-0.06)*250))*sin(2*PI*2093*(t-0.06))*exp(-6*(t-0.06))"
               "+0.38*min(1,max(0,(t-0.12)*250))*sin(2*PI*2637*(t-0.12))*exp(-5*(t-0.12))"
               "+0.35*min(1,max(0,(t-0.18)*250))*sin(2*PI*3136*(t-0.18))*exp(-4*(t-0.18))':d=1.1",
               "highpass=f=700,afade=t=in:d=0.003,afade=t=out:st=0.9:d=0.2"),
    # mola de desenho animado
    "boing": ("aevalsrc='sin(2*PI*(170*t+9*exp(-4*t)*sin(2*PI*9*t)))*exp(-3.2*t)':d=0.75",
              "lowpass=f=3000,afade=t=out:st=0.6:d=0.15"),
    # caixa registradora: quando fala de preço, oferta, compra
    "kaching": ("aevalsrc='gte(t,0.07)*(0.5*sin(2*PI*2637*(t-0.07))+0.35*sin(2*PI*3951*(t-0.07))"
                "+0.2*sin(2*PI*5274*(t-0.07)))*exp(-6*(t-0.07))+0.6*(random(0)*2-1)*exp(-55*t)':d=1.0",
                "highpass=f=400,afade=t=out:st=0.85:d=0.15"),
    # suspense subindo
    "suspense": ("aevalsrc='0.3*(random(0)*2-1)*pow(t/1.9,2)+0.4*(t/1.9)*sin(2*PI*(150*t+110*t*t))':d=1.95",
                 "highpass=f=180,lowpass=f=6000,afade=t=out:st=1.8:d=0.15"),
    # plim de aviso
    "plim": ("aevalsrc='0.7*sin(2*PI*1760*t)*exp(-9*t)+0.3*sin(2*PI*2640*t)*exp(-12*t)':d=0.55",
             "afade=t=in:d=0.003,afade=t=out:st=0.45:d=0.1"),
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
    """Nunca dois sons a menos de 0,6 s: fica o mais forte.
    Som marcado com "junto" (camadas do mesmo elemento, ex.: batida + acorde) sempre fica."""
    out = []
    for s in sorted(sons, key=lambda s: s["t"]):
        if s.get("junto"):
            out.append(s)
            continue
        if out and not out[-1].get("junto") and s["t"] - out[-1]["t"] < distancia:
            if s["db"] > out[-1]["db"]:
                out[-1] = s
            continue
        out.append(s)
    return out
