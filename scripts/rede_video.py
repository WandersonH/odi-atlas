#!/usr/bin/env python3
"""Rede de UM vídeo do YouTube (recorte pequeno, para o Fruchterman-Reingold): quem responde a quem e quem menciona quem.

Pedido do responsável (07/11/2026, 21h42), a partir do guia de layouts: testar o Fruchterman-Reingold "num recorte
pequeno, como a rede de menções de um vídeo só", para distinguir perfil muito mencionado de grupo que se menciona entre si.

Arestas (dirigidas, peso = contagem), com o tipo gravado para o filtro Edge Type do Gephi:
- "resposta": autor da resposta → autor do comentário que abriu o fio (é o que a API do YouTube informa);
- "menção": autor → @handle citado no texto, quando o handle é de um autor do mesmo vídeo. Mede quem foi respondido
  DENTRO do fio, que a API não informa (no 026, 5,5% das respostas começam com @).
Autores em código (V0001…), como nas redes públicas; o texto fica no privado.
Entrada: ODI_INTERNO_DIR/casos/<caso>/youtube_comentarios.csv.gz. Saída: data/casos/<caso>/rede_video_<id>.gexf.
Uso: python scripts/rede_video.py --caso 026 [--video <id> | --top 1]
"""
from __future__ import annotations

import csv
import gzip
import os
import re
import sys
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    a = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d  # noqa: E731
    caso, video, top = a("--caso"), a("--video"), int(a("--top", "1"))
    arq = Path(os.environ.get("ODI_INTERNO_DIR", "")) / "casos" / caso / "youtube_comentarios.csv.gz"
    if not arq.exists():
        print(f"⛔ {arq} não existe")
        return 1
    rows = list(csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";"))
    videos = [video] if video else [v for v, _ in Counter(r["video_id"] for r in rows).most_common(top)]
    for vid in videos:
        rs = [r for r in rows if r["video_id"] == vid]
        autor = {r["comment_id"]: (r.get("autor_canal") or r.get("autor_nome") or "?") for r in rs}
        handle = {}
        for r in rs:
            h = (r.get("autor_nome") or "").strip().lower()
            if h.startswith("@"):
                handle[h] = r.get("autor_canal") or h
        cod = {}
        c = lambda x: cod.setdefault(x, f"V{len(cod) + 1:04d}")  # noqa: E731
        ar = Counter()
        for r in rs:
            a_ = r.get("autor_canal") or r.get("autor_nome") or "?"
            c(a_)
            if r["tipo"] == "resposta" and r.get("parent_id") in autor and autor[r["parent_id"]] != a_:
                ar[(c(a_), c(autor[r["parent_id"]]), "resposta")] += 1
            for h in re.findall(r"@[\w.\-]+", r.get("texto") or ""):
                alvo = handle.get(h.lower())
                if alvo and alvo != a_:
                    ar[(c(a_), c(alvo), "menção")] += 1
        grau_in = Counter()
        for (s, t, _), w in ar.items():
            grau_in[t] += w
        out = Path("data/casos") / caso / f"rede_video_{vid}.gexf"
        with open(out, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<gexf xmlns="http://gexf.net/1.3" version="1.3">\n'
                    f'<meta><description>Respostas e menções entre autores de comentários do vídeo {escape(vid)} (caso {escape(caso)}); '
                    f'autores em código; {len(rs)} comentários lidos</description></meta>\n<graph defaultedgetype="directed">\n'
                    '<attributes class="node"><attribute id="0" title="tipo" type="string"/><attribute id="1" title="recebidas" type="integer"/></attributes>\n'
                    '<attributes class="edge"><attribute id="0" title="tipo" type="string"/></attributes>\n<nodes>\n')
            for k in cod.values():
                f.write(f'<node id="{k}" label="{k}"><attvalues><attvalue for="0" value="autor (código)"/><attvalue for="1" value="{grau_in.get(k, 0)}"/></attvalues></node>\n')
            f.write("</nodes>\n<edges>\n")
            for i, ((s, t, tp), w) in enumerate(sorted(ar.items())):
                f.write(f'<edge id="{i}" source="{s}" target="{t}" weight="{w}" label="{tp}"><attvalues><attvalue for="0" value="{tp}"/></attvalues></edge>\n')
            f.write("</edges>\n</graph>\n</gexf>\n")
        tipos = Counter()
        for (_, _, tp), w in ar.items():
            tipos[tp] += w
        print(f"{out}: {len(rs)} comentários, {len(cod)} autores, {len(ar)} arestas · " + " · ".join(f"{k} {v}" for k, v in tipos.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
