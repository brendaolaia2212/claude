"""Bordas dos cortes pelo som: só corta depois que a palavra termina de soar.

O whisper erra o começo e o fim das palavras em até uns 0,2 s. Cortar no tempo
dele come o fim da palavra (o "s" final, a vogal fraca do fim: "efeit(o)").
Aqui cada borda é conferida na energia do áudio (janela de 20 ms a cada 5 ms):

- fim de palavra: se ainda tem som no fim que o whisper deu, segue até o som
  cair num vale de verdade (>= VALE). Pedaços de som separados por menos que
  VALE contam como a mesma palavra (o "t" de "efeito" tem um silêncio curto no
  meio). Respiro ou suspiro que vem depois de um vale fica de fora.
- se no fim que o whisper deu já é silêncio, volta até o último som: nunca
  corta antes de o som acabar.
- começo de palavra: o mesmo, de trás pra frente.
"""
import numpy as np

SR = 16000
PASSO = 0.005
JANELA = 0.020
VALE = 0.10           # silêncio mínimo entre a palavra e o que vem depois
ESTICAR_MAX = 1.00    # o som pode passar até isso do tempo do whisper (limitado pela palavra vizinha)
FOLGA_FIM = 0.07      # respiro curto depois que a palavra acabou de soar
FOLGA_INICIO = 0.05   # antes do primeiro som da palavra


def _ler_wav(wav):
    import wave
    with wave.open(str(wav), "rb") as f:
        bruto = f.readframes(f.getnframes())
    return np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768.0


def _prob_voz(x):
    """Probabilidade de ser voz a cada 32 ms (Silero VAD, que já vem com o faster-whisper).
    Separa fala de respiro, suspiro e ruído, que têm energia parecida com o fim fraco
    de uma palavra."""
    try:
        from faster_whisper.vad import get_vad_model
    except Exception:
        return None
    x = np.pad(x, (0, (-len(x)) % 512))
    return np.asarray(get_vad_model()(x)).reshape(-1)


class Energia:
    def __init__(self, wav, usar_voz=True):
        x = _ler_wav(wav)
        y = np.empty_like(x)
        y[0] = x[0]
        y[1:] = x[1:] - 0.95 * x[:-1]          # pré-ênfase: tira zumbido, valoriza "s" e "f"
        hop, win = int(SR * PASSO), int(SR * JANELA)
        c = np.concatenate([[0.0], np.cumsum(y.astype(np.float64) ** 2)])
        n = max(1, (len(y) - win) // hop + 1)
        idx = np.arange(n) * hop
        self.db = 10 * np.log10((c[idx + win] - c[idx]) / win + 1e-12)
        self.piso = float(np.percentile(self.db, 8))
        self.fala = float(np.percentile(self.db, 95))
        self.limiar = self.piso + max(6.0, 0.20 * (self.fala - self.piso))
        # acima disso é som de fala com certeza (respiro e suspiro ficam bem abaixo)
        self.limiar_alto = self.piso + 0.45 * (self.fala - self.piso)
        self.som = self.db > self.limiar
        self.n = n
        voz = _prob_voz(x) if usar_voz else None
        if voz is not None and len(voz):
            # alarga a voz 64 ms pra cada lado: a consoante fraca do começo e o fim da
            # palavra continuam dentro; respiro separado da palavra fica fora
            dil = np.maximum.reduce([np.roll(voz, d) for d in (-2, -1, 0, 1, 2)])
            centro = (np.arange(n) * PASSO + JANELA / 2) / (512 / SR)
            v = dil[np.minimum(centro.astype(int), len(dil) - 1)]
            self.voz = v
            self.som = self.som & ((v > 0.35) | (self.db > self.limiar_alto))
            # estalo de boca (som curtinho, sem voz) não é começo nem fim de palavra
            d = np.diff(np.concatenate([[0], self.som.astype(np.int8), [0]]))
            for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
                if b - a < int(0.05 / PASSO) and v[a:b].max() < 0.5:
                    self.som[a:b] = False
        else:
            self.voz = None

    # tempo <-> quadro de energia (o centro da janela)
    def k(self, t):
        return int(min(self.n - 1, max(0, round((t - JANELA / 2) / PASSO))))

    def t(self, k):
        return k * PASSO + JANELA / 2

    def _vale_depois(self, k, kmax):
        """Primeiro quadro >= k que começa um silêncio de pelo menos VALE (ou kmax)."""
        precisa = int(round(VALE / PASSO))
        corrida = 0
        while k < kmax:
            corrida = corrida + 1 if not self.som[k] else 0
            if corrida >= precisa:
                return k - precisa + 1
            k += 1
        return kmax

    def _vale_antes(self, k, kmin):
        precisa = int(round(VALE / PASSO))
        corrida = 0
        while k > kmin:
            corrida = corrida + 1 if not self.som[k] else 0
            if corrida >= precisa:
                return k + precisa - 1
            k -= 1
        return kmin

    def minimo(self, a, b):
        """Instante mais quieto entre a e b (pra cortar fala emendada)."""
        ka, kb = self.k(a), self.k(b)
        if kb <= ka:
            return (a + b) / 2
        return self.t(ka + int(np.argmin(self.db[ka:kb + 1])))

    def fim_real(self, s, e, limite):
        """Onde a palavra [s, e] termina de soar, sem passar de `limite`."""
        ks, ke, kl = self.k(s), self.k(e), self.k(limite)
        kmax = min(kl, self.k(e + ESTICAR_MAX))
        if not self.som[ke]:
            k = ke
            while k > ks and not self.som[k]:
                k -= 1
            if not self.som[k]:
                return e                      # palavra sem som nenhum: confia no whisper
            ke = k
        fim = self._vale_depois(ke, kmax)
        if fim >= kmax:
            # o som continua até o limite (fala emendada, muleta): corta no ponto mais quieto
            return max(self.t(ke), self.minimo(e - 0.03, self.t(kmax)))
        return self.t(fim)

    def inicio_real(self, s, e, limite):
        """Onde a palavra [s, e] começa a soar, sem voltar antes de `limite`."""
        ks, ke, kl = self.k(s), self.k(e), self.k(limite)
        kmin = max(kl, self.k(s - ESTICAR_MAX))
        if not self.som[ks]:
            k = ks
            while k < ke and not self.som[k]:
                k += 1
            if not self.som[k]:
                return s
            ks = k
        ini = self._vale_antes(ks, kmin)
        if ini <= kmin:
            return min(self.t(ks), self.minimo(self.t(kmin), s + 0.03))
        return self.t(ini)

    def proximo_som(self, t, ate):
        """Primeiro instante com som depois de t (ou `ate`)."""
        k, kmax = self.k(t), self.k(ate)
        while k < kmax and not self.som[k]:
            k += 1
        return self.t(k)

    def ultimo_som(self, t, desde):
        k, kmin = self.k(t), self.k(desde)
        while k > kmin and not self.som[k]:
            k -= 1
        return self.t(k)

    def silencios_dentro(self, a, b, minimo):
        """Silêncios inteiros (>= minimo) dentro de [a, b]."""
        ka, kb = self.k(a), self.k(b)
        out, ini = [], None
        for k in range(ka, kb + 1):
            if not self.som[k]:
                ini = k if ini is None else ini
            else:
                if ini is not None and (k - ini) * PASSO >= minimo:
                    out.append((self.t(ini), self.t(k)))
                ini = None
        return out

    def tem_som(self, t):
        return bool(self.som[self.k(t)])


def trechos_por_energia(manter, palavras, en, duracao, pausa_max):
    """Palavras mantidas -> trechos [ini, fim] cortando só fora do som das palavras.

    pausa_max: silêncio maior que isso entre duas palavras mantidas sai (fica só a folga).
    """
    if not manter:
        return []
    n = len(palavras)
    fim_r, ini_r = {}, {}
    for i in manter:
        w = palavras[i]
        prox = palavras[i + 1]["s"] if i + 1 < n else duracao
        ant = palavras[i - 1]["e"] if i > 0 else 0.0
        # limite: não invade a palavra vizinha (mesmo que ela vá sair)
        fim_r[i] = min(en.fim_real(w["s"], w["e"], prox + 0.02), max(prox + 0.02, w["e"]))
        ini_r[i] = max(en.inicio_real(w["s"], w["e"], ant - 0.02), min(ant - 0.02, w["s"]))

    # agrupa palavras mantidas em blocos contínuos
    blocos = []
    for i in manter:
        if blocos and blocos[-1][-1] == i - 1 and ini_r[i] - fim_r[i - 1] <= pausa_max:
            blocos[-1].append(i)
        else:
            blocos.append([i])

    trechos = []
    for b in blocos:
        pri, ult = b[0], b[-1]
        ini, fim = ini_r[pri], fim_r[ult]
        # folga, sem pegar o som que vem antes/depois (respiro, palavra cortada)
        antes = palavras[pri - 1]["e"] if pri > 0 else 0.0
        depois = palavras[ult + 1]["s"] if ult + 1 < n else duracao
        som_antes = en.ultimo_som(ini - 0.01, max(0.0, ini - FOLGA_INICIO - 0.05))
        som_depois = en.proximo_som(fim + 0.01, min(duracao, fim + FOLGA_FIM + 0.05))
        a = max(0.0, ini - FOLGA_INICIO)
        if en.tem_som(som_antes) and som_antes < ini - 0.011:
            a = max(a, som_antes + 0.01)
        z = min(duracao, fim + FOLGA_FIM)
        if en.tem_som(som_depois) and som_depois > fim + 0.011:
            z = min(z, som_depois - 0.01)
        if pri > 0:
            a = max(a, min(antes, ini))
        if ult + 1 < n:
            z = min(z, max(depois, fim))
        # silêncio longo dentro do bloco (o whisper às vezes estica uma palavra): divide
        partes, cur = [], a
        for sa, sb in en.silencios_dentro(ini, fim, pausa_max + 0.15):
            partes.append([cur, sa + FOLGA_FIM])
            cur = sb - FOLGA_INICIO
        partes.append([cur, z])
        trechos.extend(p for p in partes if p[1] - p[0] > 0.05)

    unidos = []
    for s, e in trechos:
        if unidos and s <= unidos[-1][1] + 0.02:
            unidos[-1][1] = max(unidos[-1][1], e)
        else:
            unidos.append([s, e])
    return unidos


def conferir(trechos, en):
    """Bordas de corte que caem com som (risco de cortar palavra). Devolve a lista."""
    ruins = []
    for s, e in trechos:
        for t, lado in ((s + 0.012, "início"), (e - 0.012, "fim")):
            if en.tem_som(t):
                ruins.append((round(t, 2), lado))
    return ruins
