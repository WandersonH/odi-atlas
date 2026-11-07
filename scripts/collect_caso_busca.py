"""Casos de busca (buscas no Google + vídeos do YouTube + imprensa + checagens), grátis. Configuração por caso em CASOS.

- 002: consulta depreciativa associada a um candidato no Google ("onde mora/nasceu o ladrão").
- 005: caso Ana Clara (menina de 5 anos morta por tiro de PM em Niterói, 2021; citado por Lula no debate de 18/10/2026).

Camadas (pedido do usuário em 20/10/2026, 12h45):
1. Google Trends: as variantes da consulta e controles, em 5 anos, 12 meses e 7 dias; interesse por UF (12 meses);
   consultas relacionadas (12 meses). Variantes não são agrupadas.
2. YouTube (Data API, YOUTUBE_API_KEY): vídeos com as expressões, de 2022 em diante; comentários dos mais vistos
   (relevância + recentes, com respostas). Comentários só no privado; no público, contagens e pré-codificação.
3. Google Notícias (RSS) e checagens (Google Fact Check Tools, FACTCHECK_API_KEY ou a chave do YouTube).
4. Linha de base de 2022: cópia do artigo de Victor Gabry no Internet Archive (consulta e, se não houver, pedido de cópia).
A bateria manual de consultas ao Google (com e sem IA) não é automatizada: o Google não oferece API para isso
(a Custom Search API recusou o projeto) e bloqueia robôs. O modelo de registro fica em data/casos/002/bateria_modelo.csv.

Uso: python scripts/collect_caso_busca.py --caso 002|005 [--sem-trends] [--sem-youtube]
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from net import get_json, now_utc, open_url, read_body  # noqa: E402
import build_conteudo as bc  # noqa: E402

CASOS = {
    "002": {"variantes": ["onde mora o ladrão", "onde nasceu o ladrão", "quantos anos tem o ladrão", "qual a idade do ladrão", "aonde nasceu o ladrão"],
            "controles": ["onde mora o ladrão", "onde mora o político", "onde nasceu o político corrupto", "onde nasceu Lula"],  # 1º = âncora comum
            "janelas": ["today 5-y", "today 12-m", "now 7-d"], "youtube": None, "desde_yt": "2022-01-01T00:00:00Z",
            # 20/10: "anos"/"mora" soltos traziam vídeos de assalto; exige a estrutura da consulta ou o Google
            "rx_titulo": r"ladr[aã]o", "rx_atributo": r"\b(a?onde (mora|nasceu|nasce)|quantos anos|idade do ladr|em que ano nasceu|google)",
            "checagens": ["onde mora o ladrão", "onde nasceu o ladrão", "quantos anos tem o ladrão", "ladrão Google Lula"],
            "arquivo_web": ["https://victorgabry.com/onde-mora-o-ladrao-resultado-do-google/"]},
    "005": {"variantes": ["caso Ana Clara", "Ana Clara Niterói", "Ana Clara Flávio Bolsonaro", "Ana Clara PM"],
            "controles": ["caso Ana Clara", "Flávio Bolsonaro"],
            "janelas": ["today 5-y", "today 12-m", "now 7-d"],
            "youtube": ["caso Ana Clara", "Ana Clara Niterói", "Ana Clara Flávio Bolsonaro", "Flávio Bolsonaro advogado PM criança", "menina Ana Clara tiro fuzil"],
            "desde_yt": "2021-02-01T00:00:00Z", "rx_titulo": r"ana clara",
            # 20/10: só "ana clara" trazia outros casos com o mesmo nome; exige um elemento deste caso
            "rx_atributo": r"niter[oó]i|fl[aá]vio|bolsonaro|\bpm\b|policial|fuzil|\bbala\b|\btiro|delaroli|j[uú]ri|julgamento que nunca|debate|\blula\b|cristiane|largo da batalha|5 anos",
            "checagens": ["Ana Clara Flávio Bolsonaro", "caso Ana Clara"],
            "arquivo_web": ["https://apublica.org/2026/10/silencio-de-flavio-sobre-ana-clara-foi-desesperador-diz-a-mae-da-menina/"]},
    # 20/10 (13h2x): o usuário pediu o mesmo padrão (Trends, YouTube, checagens, redes, IRaMuTeQ) para todos os casos
    "001": {"variantes": ["brasil inteiro", "verde e amarelo", "brasilinteiro"], "controles": ["brasil inteiro", "Lula"],
            "janelas": ["today 12-m", "now 7-d"], "youtube": ["#brasilinteiro", "brasil inteiro Lula", "#verdeeamarelo Lula"],
            "desde_yt": "2026-10-10T00:00:00Z", "rx_titulo": r"brasil ?inteiro|verde ?e ?amarelo", "rx_atributo": r"lula|elei|campanha|\b13\b|brasil",
            "checagens": ["brasil inteiro Lula", "verde e amarelo Lula"], "arquivo_web": []},
    "003": {"variantes": ["ninguém morre nos devendo", "flamengo bets", "proibição das bets"], "controles": ["ninguém morre nos devendo", "Flamengo"],
            "janelas": ["today 12-m", "now 7-d"],
            "youtube": ["ninguém morre nos devendo", "flamengo ninguém morre nos devendo", "torcida do flamengo bets protesto"],
            "desde_yt": "2026-09-25T00:00:00Z", "rx_titulo": r"devendo|\bbets?\b|apostas", "rx_atributo": r"flamengo|lula|torcida|meng[aã]o",
            "checagens": ["ninguém morre nos devendo", "Flamengo bets protesto torcida"],
            "arquivo_web": ["https://www.aosfatos.org/noticias/posts-nao-mostram-protesto-da-torcida-do-flamengo-contra-fim-das-bets/"]},
    # 22/10 (01h05): PCC e CV classificados como organizações terroristas pelos EUA (post de Marco Rubio, 28/05/2026)
    "006": {"variantes": ["PCC terrorista", "Comando Vermelho terrorista", "PCC organização terrorista", "Rubio PCC"],
            "controles": ["PCC", "Comando Vermelho"], "janelas": ["today 12-m", "now 7-d"],
            "youtube": ["PCC organização terrorista", "EUA PCC Comando Vermelho terroristas", "Rubio PCC Comando Vermelho", "PCC CV terroristas Trump"],
            "desde_yt": "2026-05-01T00:00:00Z", "rx_titulo": r"\bpcc\b|comando vermelho|\bcv\b|primeiro comando",
            "rx_atributo": r"terror|rubio|\beua\b|estados unidos|trump|designa|classifica|narco",
            "checagens": ["PCC terrorista", "Comando Vermelho terrorista Estados Unidos"], "arquivo_web": []},
    # 22/10 (01h09): fake news "Lula amassa a bandeira no dia da eleição" (reel de 04/10/2026)
    "007": {"variantes": ["Lula amassa bandeira", "Lula bandeira amassada", "Lula bandeira do Brasil"],
            "controles": ["Lula bandeira", "bandeira do Brasil"], "janelas": ["today 12-m", "now 7-d"],
            "youtube": ["Lula amassa bandeira", "Lula amassou a bandeira", "Lula bandeira do Brasil eleição"],
            "desde_yt": "2026-10-01T00:00:00Z", "rx_titulo": r"bandeira", "rx_atributo": r"lula|amass|elei|vot|urna",
            "checagens": ["Lula amassa bandeira", "Lula bandeira do Brasil amassada"], "arquivo_web": []},
    # 22/10 (18h48): reel do Instagram sobre camisas do PT em Piracicaba (21–22/10) e a denúncia do PT em 22/10
    "008": {"variantes": ["camisetas PT Piracicaba", "PM camiseta Lula presos", "Piracicaba camiseta Lula", "Derrite camisetas PT"],
            "controles": ["Piracicaba", "camiseta Lula"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["PM camisetas PT Piracicaba", "presos camiseta Lula Piracicaba", "PM obriga presos camiseta Lula", "Derrite camisetas PT",
                        "PT denúncia PM camisetas", "policiais camiseta Lula militantes"],
            "desde_yt": "2026-10-21T00:00:00Z", "rx_titulo": r"camis",
            "rx_atributo": r"piracicaba|\bpm\b|pol[ií]cia|policiais|pres[oa]s|jovens|derrite|tarc[ií]sio|militantes|incrimin|arma[cç][aã]o|\bpt\b|lula",
            # 22/10 (19h): sem aspas e só dos últimos 3 dias; os títulos quase nunca trazem "Piracicaba"
            "noticias": ["PM Piracicaba camisetas PT", "presos camiseta Lula PM", "Derrite camisetas PT", "PT denúncia PM camisetas Lula",
                         "jovens presos camiseta Lula", "PM camiseta Lula Piracicaba"], "janela_noticias": "3d",
            "checagens": ["camisetas PT Piracicaba", "PM presos camiseta Lula"], "arquivo_web": ["https://www.instagram.com/reel/DewwdGCR_Qn/"]},
    # 27/10 (23h04): "demita um petista", boicote à esquerda, empresas e prestadores "petistas" depois do 2º turno
    "014": {"variantes": ["demita um petista", "boicote petista", "professor petista", "direita apoia direita", "demitido por votar"],
            "controles": ["assédio eleitoral", "petista"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["demita um petista", "demitir petista", "boicote empresas petistas", "lista de empresas petistas", "demitido por votar em Lula", "assédio eleitoral eleição 2026",
                        "professor petista", "direita apoia direita"],
            "desde_yt": "2026-10-25T00:00:00Z", "rx_titulo": r"demit|demiss|boicot|lista|ass[eé]dio|persegu|empresa|prestador|patr[aã]o|funcion[aá]ri|professor|direita apoia",
            # 30/10/2026, 22h45: "vamos adicionar aqui as buscas relativas a assédio eleitoral" — grupo próprio, com janela 2022 → 2026
            "grupos_extra": {"assedio": {"titulo": "Buscas sobre assédio eleitoral",
                                         "termos": ["assédio eleitoral", "denunciar assédio eleitoral", "demitido por votar", "denúncia MPT", "assédio eleitoral no trabalho"],
                                         "janelas": ["now 7-d", "today 1-m", "today 12-m", "2022-08-01 2026-10-31"]},
                            # 01/11/2026, 17h33: nova tag do caso
                            "nova_tag": {"titulo": "\"Não contrate quem odeia os empresários\" × \"demita um petista\"",
                                         "termos": ["não contrate quem odeia os empresários", "demita um petista", "boicote petista"],
                                         "janelas": ["now 7-d", "today 1-m"]}},
            "rx_atributo": r"petist|\bpt\b|lula|esquerd|direita|elei|vot",
            "noticias": ["\"demita um petista\"", "\"não contrate quem odeia os empresários\"", "boicote empresas petistas", "demitido por votar em Lula", "assédio eleitoral MPT", "denúncias de assédio eleitoral", "assédio eleitoral demissão", "listas de empresas petistas", "demissão eleitor petista",
                         "\"professor petista\"", "\"direita apoia direita\""],
            "janela_noticias": "7d", "checagens": ["demita um petista", "lista empresas petistas boicote"], "arquivo_web": []},
    # 27/10 (22h45): "Onde está Flávio?" e "Flávio fugiu" depois do 2º turno; Trends de 12 meses para comparar com jul/2025 e mai/2026
    "013": {"variantes": ["onde está flávio", "flávio fugiu", "flávio bolsonaro fugiu", "cadê o flávio"],
            "controles": ["Flávio Bolsonaro", "Lula"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["onde está Flávio Bolsonaro", "Flávio Bolsonaro fugiu", "Flávio Bolsonaro fuga", "cadê o Flávio Bolsonaro", "Flávio Bolsonaro sumiu"],
            "desde_yt": "2026-10-24T00:00:00Z", "rx_titulo": r"fug|onde est|cad[eê]|paradeiro|sumi|exterior|\beua\b|estados unidos|europa|lisboa|miami|asilo",
            "rx_atributo": r"fl[aá]vio",
            "noticias": ["\"onde está Flávio\"", "Flávio Bolsonaro fugiu", "Flávio Bolsonaro paradeiro", "Flávio Bolsonaro viagem exterior", "Flávio Bolsonaro sumiu"],
            "janela_noticias": "7d", "checagens": ["Flávio Bolsonaro fugiu", "Flávio Bolsonaro fuga"], "arquivo_web": []},
    # 29/10/2026 (21h51): "queime o título", "fogo no título", "destrua seu título": volume depois de 24/10
    "016": {"variantes": ["queimar título de eleitor", "queimar título", "destruir título de eleitor", "rasgar título de eleitor"],
            "controles": ["título de eleitor", "Lula"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["queimando título de eleitor", "queime seu título", "destrua seu título de eleitor", "queimou título de eleitor", "rasgando título de eleitor"],
            "desde_yt": "2026-10-24T00:00:00Z", "rx_titulo": r"t[ií]tulo",
            "rx_atributo": r"queim|fogo|destr|rasg|lixo",
            "noticias": ["queimar título de eleitor", "queima título eleitoral", "destruir título de eleitor", "rasgar título de eleitor"],
            "janela_noticias": "7d", "checagens": ["queimar título de eleitor", "destruir título de eleitor"], "arquivo_web": []},
    # 29/10/2026 (21h51): as versões da carta de Flávio ("verdadeiro presidente eleito" → "líder do Brasil"), mídia e checagens
    "017": {"variantes": ["carta Flávio Bolsonaro", "Flávio presidente eleito", "Flávio líder do Brasil", "Flávio Bolsonaro EUA"],
            "controles": ["Flávio Bolsonaro", "Lula"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["carta Flávio Bolsonaro", "Flávio Bolsonaro presidente eleito carta", "Flávio Bolsonaro líder do Brasil", "Flávio Bolsonaro carta EUA"],
            "desde_yt": "2026-10-27T00:00:00Z", "rx_titulo": r"carta|nota|eleito|l[ií]der|vers|exterior|\beua\b|estados unidos|ex[ií]lio",
            "rx_atributo": r"fl[aá]vio",
            "noticias": ["carta Flávio Bolsonaro", "Flávio \"presidente eleito\" carta", "Flávio \"líder do Brasil\"", "carta Flávio versões", "Flávio Bolsonaro carta EUA"],
            "janela_noticias": "7d", "checagens": ["Flávio Bolsonaro carta", "Flávio Bolsonaro presidente eleito"], "arquivo_web": []},
    # 01/11/2026 (21h28, padronização dos casos): Trends por estado, imprensa e checagens para os casos com coletor próprio.
    # O YouTube desses casos já é lido pelos coletores deles (caso_joice, caso_canais, caso_mundo) ou não se aplica: sem_youtube.
    "010": {"variantes": ["Trump Brasil", "Rubio Brasil", "Trump Lula", "Rubio Lula"], "controles": ["Trump"],
            "janelas": ["now 7-d", "today 1-m", "today 12-m"], "youtube": None, "sem_youtube": True, "desde_yt": "2026-10-24T00:00:00Z",
            "rx_titulo": r"trump|rubio", "rx_atributo": r"brasil|lula|elei", "noticias": ["Trump eleição Brasil", "Rubio eleição Brasil", "Trump Lula", "Rubio Lula"],
            "janela_noticias": "14d", "checagens": ["Trump Lula eleição", "Rubio Brasil eleição"], "arquivo_web": []},
    "011": {"variantes": ["Joice Hasselmann", "Joice Hasselmann Lula", "Joice TV 247"], "controles": ["Lula"],
            "janelas": ["now 7-d", "today 1-m", "today 12-m"], "youtube": None, "sem_youtube": True, "desde_yt": "2026-10-22T00:00:00Z",
            "rx_titulo": r"joice", "rx_atributo": r"lula|vot|247|elei", "noticias": ["Joice Hasselmann Lula", "Joice Hasselmann voto", "Joice Hasselmann TV 247"],
            "janela_noticias": "14d", "checagens": ["Joice Hasselmann Lula"], "arquivo_web": []},
    "012": {"variantes": ["Allan dos Santos", "Paulo Figueiredo", "Ramagem"], "controles": ["Bolsonaro"],
            "janelas": ["now 7-d", "today 1-m", "today 12-m"], "youtube": None, "sem_youtube": True, "desde_yt": "2026-07-01T00:00:00Z",
            "rx_titulo": r"allan|figueiredo|ramagem", "rx_atributo": r"eua|exterior|elei|lula|bolsonar", "noticias": ["Allan dos Santos eleição", "Paulo Figueiredo eleição", "Ramagem EUA eleição"],
            "janela_noticias": "30d", "checagens": ["Allan dos Santos", "Paulo Figueiredo", "Ramagem"], "arquivo_web": []},
    "018": {"variantes": ["Haddad boicote", "Haddad Davos", "Lula corte saúde"], "controles": ["Haddad"],
            "janelas": ["now 7-d", "today 1-m", "today 12-m"], "youtube": None, "sem_youtube": True, "desde_yt": "2026-10-24T00:00:00Z",
            "rx_titulo": r"haddad|lula", "rx_atributo": r"boicot|davos|sa[uú]de|corte|antig", "noticias": ["Haddad boicote Davos", "Haddad \"palito de fósforo\"", "Lula corte 6 bilhões saúde educação", "vídeo antigo checagem eleição"],
            "janela_noticias": "14d", "checagens": ["Haddad boicote", "Haddad Davos", "Lula corte saúde"], "arquivo_web": []},
    "019": {"variantes": ["Brazil election", "Lula election", "Bolsonaro"], "controles": ["Brazil"],
            "janelas": ["now 7-d", "today 1-m"], "geo_trends": "", "paises_trends": True, "youtube": None, "sem_youtube": True, "desde_yt": "2026-10-01T00:00:00Z",
            "rx_titulo": r"brazil|brasil|lula|bolsonaro", "rx_atributo": r"elect|elei|vot", "noticias": ["Brazil election 2026 Lula", "eleição Brasil imprensa internacional"],
            "janela_noticias": "14d", "checagens": ["Brazil election 2026"], "arquivo_web": []},
    # 01/11 (18h26): #DeportTheBolsonaros × #BrasiliansStandWithFlavio: quanto veio do Brasil e quanto de outros países.
    # Trends no mundo inteiro (geo vazio), com o mapa por país em cada janela; YouTube sem região nem língua.
    # 02/11 (03h28): três casos — xenofobia contra o Nordeste; brasileiros e o Paraguai (pré e pós 2º turno); "Nota ao Brasil" de Flávio
    "029": {"variantes": ["xenofobia", "nordestino", "separar o nordeste"],
            "controles": ["nordeste"], "janelas": ["today 5-y", "today 12-m", "now 7-d"],
            "youtube": ["xenofobia nordeste eleição 2026", "nordeste câncer do Brasil", "ataques a nordestinos depois da eleição", "orgulho de ser nordestino eleição"],
            "desde_yt": "2026-10-25T00:00:00Z", "rx_titulo": r"nordest|xenofob",
            "rx_atributo": r"xenofob|ataq|[oó]dio|preconceit|elei|lula|c[aâ]ncer|crime|voto|separa",
            "noticias": ["xenofobia Nordeste eleição", "ataques a nordestinos eleição", "\"câncer do Brasil\" Nordeste", "nordestinos ódio redes sociais"],
            "janela_noticias": "30d", "checagens": ["Nordeste eleição", "27 milhões ataques Nordeste", "xenofobia Nordeste"], "arquivo_web": []},
    # 07/11 (18h40): o responsável pede "morar no Paraguay" e "cidadania paraguaia" (grafia em espanhol e cidadania entram)
    "030": {"variantes": ["morar no Paraguai", "como morar no Paraguai", "residência no Paraguai", "cidadania paraguaia", "morar no Paraguay"],
            "controles": ["morar em Portugal", "morar nos Estados Unidos"], "janelas": ["today 12-m", "today 1-m", "now 7-d"],
            "grupos_extra": {"paraguai_so": {"titulo": "\"morar no Paraguai\" sozinho (interesse por estado e consultas relacionadas)", "termos": ["morar no Paraguai"]},
                             "cidadania": {"titulo": "Cidadania e documentos paraguaios (interesse por estado e consultas relacionadas)",
                                           "termos": ["cidadania paraguaia", "naturalização Paraguai", "cédula paraguaia", "residência permanente Paraguai"]}},
            "youtube": ["morar no Paraguai 2026", "brasileiros fila Paraguai documentação", "residência paraguaia brasileiros", "mudar para o Paraguai depois da eleição",
                        "cidadania paraguaia brasileiro", "como tirar cidadania paraguaia", "cédula paraguaia brasileiro", "morar no Paraguay 2026"],
            "desde_yt": "2026-10-18T00:00:00Z", "rx_titulo": r"paragua",
            "rx_atributo": r"morar|mudar|resid[eê]ncia|c[eé]dula|fila|document|migra|brasileir|elei|lula|cidadan|naturaliza",
            "noticias": ["morar no Paraguai brasileiros", "residência paraguaia brasileiros", "Paraguai brasileiros eleição Lula", "Migraciones Paraguai brasileiros",
                         "cidadania paraguaia brasileiros", "cédula paraguaia brasileiros", "naturalização Paraguai brasileiros",
                         {"q": "brasileños residencia Paraguay Migraciones", "ed": "PY"}, {"q": "brasileños ciudadanía paraguaya", "ed": "PY"}],
            "janela_noticias": "30d", "checagens": ["Paraguai brasileiros", "morar no Paraguai", "cidadania paraguaia"], "arquivo_web": []},
    "031": {"variantes": ["Flávio Bolsonaro", "nota ao Brasil", "Flávio Bolsonaro Globo"],
            "controles": ["Lula"], "janelas": ["now 7-d", "today 1-m"],
            "youtube": ["Flávio Bolsonaro nota ao Brasil", "Flávio Bolsonaro Globo entrevista sem cortes", "saí pelo Brasil Flávio Bolsonaro"],
            "desde_yt": "2026-11-01T00:00:00Z", "rx_titulo": r"fl[aá]vio|bolsonaro",
            "rx_atributo": r"nota|globo|entrevista|sem cortes|sa[ií] pelo|persegui|eua|miami|moraes|cautelar",
            "noticias": ["Flávio Bolsonaro \"Nota ao Brasil\"", "Flávio Bolsonaro Globo entrevista", "\"saí pelo Brasil\" Flávio"],
            "janela_noticias": "7d", "checagens": ["Flávio Bolsonaro nota", "Flávio Bolsonaro Globo"], "arquivo_web": ["https://x.com/FlavioBolsonaro/status/2117015474219446473"]},
    # 03/11 (02h02): "desenhos bíblicos da Record, fake news lançada hoje" — classificação indicativa vendida como censura
    # 06/11 (11h02): "Faz o L" em português e outros idiomas; pergunta principal: a origem. Janelas longas (2004 em diante) para datar o surgimento
    "037": {"variantes": ["faz o L", "fazueli", "fiz o L", "haz la L", "make the L"],
            "controles": ["Lula"], "janelas": ["2004-01-01 2026-11-06", "today 5-y", "today 12-m", "now 7-d"], "paises_trends": True,
            "youtube": ["faz o L", "faz o L Lula", "fazueli", "fiz o L", "faz o L origem", "faz o L jingle", "haz la L Lula", "make the L Lula"],
            "youtube_mundo": True,
            "desde_yt": "2005-01-01T00:00:00Z", "rx_titulo": r"fa[zs] o l\b|fazueli|fazuele|fazoel[ei]|fi[zs] o l\b|fez o l\b|haz(e)? la l\b|hace la l\b|(make|do) the l\b|fais le l\b|#?fazol\b",
            "rx_atributo": r"lula|petista|governo|ironi|meme|origem|criador|jingle|gesto|marca|l[eé]o santana|latino|bolsonar|gasolina|picanha|imposto",
            "noticias": ["\"faz o L\"", "\"fazueli\"", "\"fiz o L\"", "\"faz o L\" origem", {"q": "\"haz la L\" Lula", "ed": "US"}, {"q": "\"faz o L\" Lula", "ed": "US"}],
            "janela_noticias": "", "checagens": ["faz o L", "fazueli"], "arquivo_web": []},
    # 06/11 (10h38): entrevista de Flávio Bolsonaro ao New York Times em Miami (04/11, publicada em 05/11): "Levarei isso para o túmulo"
    "036": {"variantes": ["Flávio Bolsonaro New York Times", "levarei isso para o túmulo", "Flávio Bolsonaro Miami"],
            "controles": ["Flávio Bolsonaro"], "janelas": ["now 7-d", "today 1-m"], "paises_trends": True,
            "youtube": ["Flávio Bolsonaro New York Times", "Flávio Bolsonaro NYT entrevista", "levarei isso para o túmulo Flávio", "Flávio Bolsonaro Miami entrevista",
                        "Flavio Bolsonaro New York Times interview", "Flávio Bolsonaro fuga jato Casa Branca"],
            "youtube_mundo": True,
            "desde_yt": "2026-11-05T00:00:00Z", "rx_titulo": r"fl[aá]vio|bolsonaro",
            "rx_atributo": r"new york times|nyt|t[uú]mulo|miami|fl[oó]rida|fuga|fugiu|jato|casa branca|entrevista|interview|exil|eua|estados unidos",
            "noticias": ["Flávio Bolsonaro \"New York Times\"", "\"levarei isso para o túmulo\"", "Flávio Bolsonaro NYT entrevista Miami", "\"fui só eu\" Flávio",
                         {"q": "\"Flavio Bolsonaro\" \"New York Times\"", "ed": "US"}, {"q": "\"Flavio Bolsonaro\" Miami interview", "ed": "US"}],
            "janela_noticias": "7d", "checagens": ["Flávio Bolsonaro New York Times", "Flávio Bolsonaro jato Casa Branca"], "arquivo_web": []},
    # 04/11 (16h46): "Vote como brasileiro" / "vote like a Brazilian" usado nas campanhas americanas (meio de mandato, 03/11/2026), desde o 2º turno
    "035": {"variantes": ["vote like a Brazilian", "vote like Brazil", "vote como brasileiro", "vote como um brasileiro"],
            "controles": ["Brazil election"], "janelas": ["now 7-d", "today 1-m"], "geo_trends": "", "paises_trends": True,
            "grupos_extra": {"eua": {"titulo": "Nos Estados Unidos (interesse por estado)", "termos": ["vote like a Brazilian", "vote like Brazil"], "geo": "US"}},
            "youtube": ["vote like a Brazilian", "vote like Brazilians midterms", "vote like Brazil midterms", "Brazil Lula midterms Democrats lesson",
                        "vote como brasileiro eleição americana", "vote como um brasileiro", "Brazilian voters midterms 2026"],
            "youtube_mundo": True,
            "desde_yt": "2026-10-25T00:00:00Z", "rx_titulo": r"vote (like|as) (a )?brazil|vote como (um )?brasileir|votelikeabrazil|like (a )?brazilian",
            # 04/11 (17h): só a frase; com "brazil|lula" + voto vinham 306 vídeos sobre a eleição em geral e nenhum com a frase
            "rx_atributo": r"vote|voting|vota|midterm|election|elei[cç]|democrat|republican|trump|ballot|brazil|brasil|lula",
            "noticias": [{"q": "\"vote like a Brazilian\"", "ed": "US"}, {"q": "\"vote like Brazil\"", "ed": "US"}, {"q": "\"vote like Brazilians\"", "ed": "US"},
                         {"q": "Brazil Lula midterms Democrats", "ed": "US"}, {"q": "\"like Brazil\" midterms vote", "ed": "US"},
                         "\"vote como brasileiro\"", "\"vote como um brasileiro\"", "\"vote like a Brazilian\"", "eleição americana Lula exemplo Brasil democratas"],
            "janela_noticias": "11d", "checagens": ["vote like a Brazilian", "Brazil election midterms"], "arquivo_web": []},
    # 04/11 (00h23): caso oculto — deepfake de Jair Bolsonaro na convenção do PL (25/07) e a tese do TSE (01/09); apoio ao artigo de deepfake
    "034": {"variantes": ["deepfake", "Bolsonaro IA", "inteligência artificial eleição"],
            "controles": ["inteligência artificial"], "janelas": ["today 12-m", "today 5-y", "now 7-d"],
            "youtube": ["Bolsonaro IA convenção PL", "deepfake Bolsonaro TSE", "TSE julga deepfake Flávio Bolsonaro", "vídeo inteligência artificial Bolsonaro convenção",
                        "TSE deepfake tese convenção partidária", "TSE Google detecção de semelhança deepfake candidatos"],
            "desde_yt": "2026-07-25T00:00:00Z", "rx_titulo": r"deep ?fake|intelig[eê]ncia artificial|\bIA\b|\bAI\b|avatar|sint[eé]tic",
            "rx_atributo": r"bolsonaro|fl[aá]vio|tse|conven[cç][aã]o|\bpl\b|elei|candidat|propaganda|google|youtube",
            "noticias": ["deepfake Bolsonaro convenção PL", "TSE deepfake Flávio Bolsonaro", "vídeo IA Bolsonaro convenção TSE", "TSE tese deepfake propaganda eleitoral",
                         "TSE Google detecção de semelhança candidatos", "deepfake eleições 2026 TSE"],
            "janela_noticias": "105d", "checagens": ["deepfake Bolsonaro", "vídeo inteligência artificial Bolsonaro", "deepfake eleição 2026"], "arquivo_web": []},
    "033": {"variantes": ["desenhos bíblicos", "Record Kids", "classificação indicativa"],
            "controles": ["Record"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["desenhos bíblicos Record censura", "Lula censura desenhos bíblicos", "Record Kids classificação indicativa", "desenho bíblico 12 anos Ministério da Justiça"],
            "desde_yt": "2026-10-29T00:00:00Z", "rx_titulo": r"b[ií]blic|record|classifica[çc][aã]o indicativa",
            "rx_atributo": r"censur|lula|governo|minist[eé]rio|classifica|crist[aã]|evang[eé]l|12 anos|portaria|record",
            "noticias": ["\"desenhos bíblicos\" Record", "\"Desenhos Bíblicos\" classificação indicativa", "Record Kids censura", "portaria 2.272 classificação indicativa"],
            "janela_noticias": "7d", "checagens": ["desenhos bíblicos Record", "classificação indicativa Record"], "arquivo_web": []},
    # 02/11 (02h53): violência contra indígenas em MS depois do 2º turno e a reação (#ProtejamNossosPovosIndígenas, Exército dos Povos Indígenas)
    "028": {"variantes": ["povos indígenas", "indígenas", "Guarani Kaiowá"],
            "controles": ["Funai"], "janelas": ["today 5-y", "today 12-m", "now 7-d"],
            # 02/11 (03h24): "povos indígenas deve ser abrangendo na busca" — termos gerais, não só MS
            "grupos_extra": {"apib": {"titulo": "Apib e Funai", "termos": ["Apib", "Funai"]}},
            "youtube": ["povos indígenas ataques eleição 2026", "indígenas ameaçados depois da eleição", "indígenas Mato Grosso do Sul ameaças eleição",
                        "Tacuru aldeia Sassoró", "veneno na água aldeia indígena", "Exército dos Povos Indígenas", "Guarani Kaiowá ataques 2026"],
            "desde_yt": "2026-10-25T00:00:00Z", "rx_titulo": r"ind[ií]gen|kaiow|guarani|tacuru|sassor|aldeia|povos origin|apib|funai",
            "rx_atributo": r"amea|ataq|atropel|venen|viol[eê]n|pf|pol[ií]cia|for[cç]a nacional|elei|lula|racis|ex[eé]rcito|protej|apib|funai|direito",
            "noticias": ["povos indígenas ataques eleição", "indígenas ameaças depois da eleição", "Apib violência indígenas", "Tacuru indígenas",
                         "Sassoró aldeia", "\"Exército dos Povos Indígenas\"", "ProtejamNossosPovosIndígenas", "Força Nacional aldeias"],
            "janela_noticias": "30d", "checagens": ["indígenas eleição", "povos indígenas ataques", "envenenamento água aldeia", "Tacuru"], "arquivo_web": []},
    # 02/11 (02h44): voto distrital misto (PEC articulada por Hugo Motta; transição pelo distritão em 2030); 5 anos para comparar com 2015/2017
    "027": {"variantes": ["voto distrital", "distrital misto", "distritão"],
            "controles": ["reforma política"], "janelas": ["today 5-y", "today 12-m", "now 7-d"],
            "youtube": ["voto distrital misto", "distritão 2030", "Hugo Motta voto distrital", "voto distrital Nikolas Ferreira", "PEC voto distrital"],
            "desde_yt": "2026-10-26T00:00:00Z", "rx_titulo": r"distrit",
            "rx_atributo": r"distrit|motta|pec|c[aâ]mara|nikolas|pavanato|reforma|eleitora|puxador|deputad",
            "noticias": ["\"voto distrital\"", "\"distrital misto\"", "distritão PEC", "Hugo Motta voto distrital", "voto distrital Nikolas Pavanato"],
            "janela_noticias": "30d", "checagens": ["voto distrital", "distritão"], "arquivo_web": []},
    # 02/11 (01h38): janonismo — "Exército do Lula" (Janones) na eleição, repercussão no mundo e canais copiados em outros países
    "026": {"variantes": ["Janones", "Exército do Lula", "André Janones"],
            "controles": ["Lula"], "janelas": ["now 7-d", "today 1-m", "today 12-m"], "geo_trends": "", "paises_trends": True,
            "grupos_extra": {"janones_mundo": {"titulo": "\"Janones\" no mundo (interesse por país)", "termos": ["Janones"]},
                             "janones_uf": {"titulo": "\"Janones\" por estado (Brasil)", "termos": ["Janones"], "geo": "BR"},
                             "exercito_uf": {"titulo": "\"Exército do Lula\" por estado (Brasil)", "termos": ["Exército do Lula"], "geo": "BR"}},
            "youtube": ["Exército do Lula Janones", "Janones WhatsApp canal", "Ejército de Lula Janones", "armée de Lula Janones WhatsApp",
                        "Ejército del Peronismo WhatsApp", "La Fuerza de la Gente WhatsApp", "équipe de Mélenchon WhatsApp", "Janones general Lula"],
            "youtube_mundo": True,
            "desde_yt": "2026-10-05T00:00:00Z", "rx_titulo": r"janones|ex[eé]rcito|ej[eé]rcito|arm[ée]e|army|peronismo|fuerza de la gente|m[ée]lenchon|whats",
            "rx_atributo": r"janones|lula|whats|canal|channel|cha[iî]ne|ex[eé]rcito|ej[eé]rcito|arm[ée]e|army",
            "noticias": ["\"Exército do Lula\"", "Janones WhatsApp", "Janones general Lula", "\"Exército do Lula\" outros países",
                         {"q": "\"Ejército de Lula\"", "ed": "ES"}, {"q": "Janones WhatsApp", "ed": "ES"}, {"q": "\"La Fuerza de la Gente\" WhatsApp", "ed": "ES"},
                         {"q": "\"Ejército del Peronismo\"", "ed": "AR"}, {"q": "Janones", "ed": "AR"},
                         {"q": "\"armée de Lula\"", "ed": "FR"}, {"q": "Janones", "ed": "FR"}, {"q": "Mélenchon WhatsApp chaîne", "ed": "FR"},
                         {"q": "Janones Lula WhatsApp", "ed": "US"}, {"q": "\"Lula's army\"", "ed": "US"},
                         {"q": "Janones", "ed": "CO"}, {"q": "Janones", "ed": "PT"}],
            "janela_noticias": "30d", "checagens": ["Exército do Lula", "Janones"], "arquivo_web": []},
    "025": {"variantes": ["deport Bolsonaro", "Flávio Bolsonaro Miami", "Flavio Bolsonaro", "DeportTheBolsonaros"],
            "controles": ["Bolsonaro"], "janelas": ["now 7-d", "today 1-m"], "geo_trends": "", "paises_trends": True,
            # com vários termos, o mapa por país dá a divisão entre os termos; com um termo só, o interesse por país (0 a 100)
            "grupos_extra": {"nome_mundo": {"titulo": "\"Flavio Bolsonaro\" no mundo (interesse por país)", "termos": ["Flavio Bolsonaro"]},
                             "deport_mundo": {"titulo": "\"deport Bolsonaro\" no mundo (interesse por país)", "termos": ["deport Bolsonaro"]}},
            "youtube": ["DeportTheBolsonaros", "deport Bolsonaro", "deport Flavio Bolsonaro Miami", "Brazilians stand with Flavio", "deportem os Bolsonaros"],
            "youtube_mundo": True,
            "desde_yt": "2026-10-25T00:00:00Z", "rx_titulo": r"deport|bolsonar|fl[aá]vio",
            "rx_atributo": r"deport|miami|eua|\busa?\b|estados unidos|united states|ice|trump|stand|asyl|asilo|ex[ií]l",
            "noticias": ["DeportTheBolsonaros", "\"deportem os Bolsonaros\"", "Flávio Bolsonaro deportação EUA", "deport Bolsonaro Miami", "BrasiliansStandWithFlavio"],
            "janela_noticias": "7d", "checagens": ["deportação Flávio Bolsonaro", "DeportTheBolsonaros"], "arquivo_web": []},
    # 01/11 (17h16): primeiro vídeo de Flávio Bolsonaro nos EUA (live no Instagram, 31/10)
    "024": {"variantes": ["Flávio Bolsonaro", "Flávio Bolsonaro EUA", "Flávio Bolsonaro 2030", "Flávio Bolsonaro live"],
            "controles": ["Lula"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["Flávio Bolsonaro vídeo EUA", "Flávio Bolsonaro live Estados Unidos", "Flávio Bolsonaro antes de 2030", "Flávio Bolsonaro Miami"],
            "desde_yt": "2026-10-31T00:00:00Z", "rx_titulo": r"fl[aá]vio|bolsonaro",
            "rx_atributo": r"eua|estados unidos|miami|live|v[ií]deo|2030|sa[ií]da|fuga|exterior|moraes",
            "noticias": ["Flávio Bolsonaro vídeo EUA", "Flávio Bolsonaro live Instagram", "Flávio Bolsonaro antes de 2030", "Flávio Bolsonaro primeiro vídeo Estados Unidos"],
            "janela_noticias": "7d", "checagens": ["Flávio Bolsonaro vídeo EUA", "Flávio Bolsonaro 2030"], "arquivo_web": []},
    # 01/11 (15h39): greve dos caminhoneiros em 5/11 e vídeos/reportagens antigas recirculadas como atuais
    "023": {"variantes": ["greve dos caminhoneiros", "greve caminhoneiros 5 de novembro", "paralisação caminhoneiros", "caminhoneiros"],
            "controles": ["diesel"], "janelas": ["today 5-y", "today 12-m", "now 7-d"],
            "youtube": ["greve dos caminhoneiros 5 de novembro", "greve dos caminhoneiros 2026", "paralisação caminhoneiros novembro", "caminhoneiros greve vídeo antigo"],
            "youtube_indicados": ["dfXr6kAy_5Q"],
            "desde_yt": "2026-10-28T00:00:00Z", "rx_titulo": r"caminhoneir|greve|paralisa|bloquei",
            "rx_atributo": r"caminhoneir|rodovia|diesel|frete|greve|novembro|5/11",
            "noticias": ["greve dos caminhoneiros 5 de novembro", "greve caminhoneiros novembro 2026", "vídeo antigo greve caminhoneiros", "paralisação caminhoneiros boato"],
            "janela_noticias": "7d", "checagens": ["greve dos caminhoneiros", "vídeo antigo caminhoneiros"], "arquivo_web": []},
    # 31/10 (18h06): "Relatório Pericial Independente" (apócrifo, fraude no 2º turno); prints atribuídos a Joey Mannarino
    "022": {"variantes": ["relatório pericial", "votos sem biometria", "fraude eleição", "lei de Benford"],
            "controles": ["urna eletrônica"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["relatório pericial independente eleição 2026", "votos depois das 17h fraude", "votos sem biometria urna", "Lei de Benford eleição Brasil", "Joey Mannarino Brazil"],
            "desde_yt": "2026-10-28T00:00:00Z", "rx_titulo": r"relat[oó]rio|pericia|17\s?h|biometr|benford|fraud|urna|mannarino",
            "rx_atributo": r"elei|urna|vot|tse|lula|fl[aá]vio|bolsonar|brazil|brasil",
            "noticias": ["\"relatório pericial independente\"", "relatório apócrifo fraude eleição", "votos após 17h TSE", "votos sem biometria segundo turno", "Joey Mannarino Lula"],
            "janela_noticias": "7d", "checagens": ["relatório pericial independente", "votos depois das 17h", "votos sem biometria"], "arquivo_web": []},
    # 31/10 (17h54): "O Sul é meu país" — separatismo do Sul; janela de 5 anos para comparar com o Plebisul (2016/2017)
    "021": {"variantes": ["o sul é meu país", "separação do sul", "plebisul", "sul independente", "movimento separatista"],
            "controles": ["separatismo"], "janelas": ["today 5-y", "today 12-m", "now 7-d"],
            "youtube": ["O Sul é meu país", "separação do Sul do Brasil", "plebiscito separar o Sul", "Plebisul 2026", "independência do Sul", "movimento separatista Sul"],
            "desde_yt": "2026-07-01T00:00:00Z", "rx_titulo": r"sul|separa|plebis|independ",
            "rx_atributo": r"sul|separa|brasil|plebis|pa[ií]s|independ",
            "noticias": ["\"o sul é meu país\"", "separação do sul", "plebisul", "separatismo sul Brasil", "plebiscito separar o sul", "movimento separatista sul"],
            "janela_noticias": "125d", "checagens": ["separação do sul", "o sul é meu país"], "arquivo_web": []},
    # 30/10 (20h58): menino que vendia balas em Fortaleza constrangido por influenciadora por dizer que votava em Lula
    # (vídeo de Valéria Diniz, 28/10). Criança: o Atlas não publica imagem nem o perfil dele; o apelido da imprensa só como termo de busca.
    "020": {"variantes": ["Matheus dos Bombons", "Valéria Diniz", "menino balas Fortaleza", "menino fazer o L"],
            "controles": ["Lula"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["Matheus dos Bombons", "Valéria Diniz menino balas", "menino balas Fortaleza Lula", "influenciadora menino fazer o L Fortaleza"],
            "desde_yt": "2026-10-28T00:00:00Z", "rx_titulo": r"bombo|bala|menino|crian|val[eé]ria|diniz|fortaleza|fazer o l|rampa",
            "rx_atributo": r"lula|bolsonar|influenc|val[eé]ria|diniz|janones|rampa|posse",
            "noticias": ["Matheus dos Bombons", "Valéria Diniz menino", "menino balas Fortaleza Lula", "influenciadora menino fazer o L", "menino autista bombons Lula rampa"],
            "janela_noticias": "7d", "checagens": ["menino balas Fortaleza", "Valéria Diniz"], "arquivo_web": []},
    # 26/10 (01h41): reel de Nikolas Ferreira "O Nordeste que foi esquecido." (20/10/2026); termos iniciais, revisar com a transcrição
    "009": {"variantes": ["Nordeste esquecido", "Nikolas Nordeste", "Nikolas Ferreira Nordeste vídeo"],
            "controles": ["Nordeste", "Nikolas Ferreira"], "janelas": ["now 7-d", "today 1-m", "today 12-m"],
            "youtube": ["Nikolas Ferreira Nordeste esquecido", "Nikolas Ferreira vídeo Nordeste", "Nordeste que foi esquecido Nikolas"],
            "desde_yt": "2026-10-20T00:00:00Z", "rx_titulo": r"nordest",
            "rx_atributo": r"nikolas|v[ií]deo|esquecid|lula|elei|vot",
            "noticias": ["Nikolas Ferreira Nordeste vídeo", "Nikolas Nordeste esquecido"], "janela_noticias": "7d",
            "checagens": ["Nikolas Ferreira Nordeste", "vídeo Nikolas Nordeste"], "arquivo_web": ["https://www.instagram.com/reel/DeuEvFlRfuH/"]},
}
CASO = "002"
TOP_COMENTARIOS = 30
MIN_PUBLICO = 10000


def configurar(caso: str) -> None:
    global CASO, VARIANTES, CONTROLES, JANELAS, DESDE_YT, RX_TITULO, RX_ATRIBUTO, ARQUIVO_WEB, BUSCAS_YT, BUSCAS_CHECAGEM
    c = CASOS[caso]
    CASO, VARIANTES, CONTROLES, JANELAS, DESDE_YT = caso, c["variantes"], c["controles"], c["janelas"], c["desde_yt"]
    RX_TITULO, RX_ATRIBUTO = re.compile(c["rx_titulo"], re.I), re.compile(c["rx_atributo"], re.I)
    ARQUIVO_WEB, BUSCAS_YT, BUSCAS_CHECAGEM = c["arquivo_web"], c["youtube"] or c["variantes"], c["checagens"]


configurar("002")
CATEGORIAS = {  # pré-codificação por dicionário (não é decisão)
    "relato de teste": re.compile(r"\b(testei|testa|teste|fiz (a |essa )?pesquisa|pesquisei|perguntei|joguei no google|fiz aqui|fiz agora|aqui (deu|apareceu)|deu (o )?lula|apareceu (o )?lula|é verdade|verdade mesmo)\b", re.I),
    "mudança percebida": re.compile(r"\b(mudou|não aparece mais|nao aparece mais|tiraram|corrigiram|já mudaram|ja mudaram|agora aparece|censur)\w*", re.I),
    "contestação": re.compile(r"\b(fake|montagem|mentira|editad|calúnia|calunia|crime|injúria|injuria|processo|manipula)\w*", re.I),
    "cita Lula": re.compile(r"\b(lula|luladr|petista|pt\b|molusco|nove dedos|9 dedos)", re.I),
}
ERROS: list[str] = []


def priv_dir() -> Path:
    base = os.environ.get("ODI_INTERNO_DIR") or os.path.join(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir(), "odi_casos")
    return Path(base) / "casos" / CASO


def trends() -> dict:
    from collect_trends import Trends
    from collect_trends_agora import relacionados
    t = Trends(pause=4)
    out = {}
    extras = CASOS[CASO].get("grupos_extra") or {}
    grupos = [("variantes", VARIANTES, JANELAS), ("controles", CONTROLES, JANELAS)] + \
             [(k, v["termos"], v.get("janelas", JANELAS)) for k, v in extras.items()]
    for nome, termos, janelas in grupos:
        g = {"termos": termos}
        if nome in extras:
            g["titulo"] = extras[nome].get("titulo")
        for jan in janelas:
            try:
                geo_t = CASOS[CASO].get("geo_trends", "BR")  # 01/11/2026 (caso 025): "" = mundo inteiro
                if nome in extras and "geo" in extras[nome]:  # 02/11/2026 (caso 026): grupo com região própria (ex.: estados do Brasil num caso mundial)
                    geo_t = extras[nome]["geo"]
                ws = {w["id"]: w for w in t.explore(termos, jan, geo_t)}
                ts = t.widget("multiline", ws["TIMESERIES"])
                g[jan] = [{"t": dt.datetime.fromtimestamp(int(p["time"]), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "v": dict(zip(termos, p.get("value") or []))} for p in ts["default"]["timelineData"]]
                if CASOS[CASO].get("paises_trends") and geo_t == "":  # interesse por país em cada janela (caso 025), só na busca mundial
                    gw = next((w for k, w in ws.items() if k.startswith("GEO_MAP")), None)
                    if gw:
                        gm = t.widget("comparedgeo", gw)
                        g["paises_" + jan] = [{"pais": r.get("geoCode"), "nome": r.get("geoName"), "v": dict(zip(termos, r.get("value") or []))}
                                              for r in gm["default"]["geoMapData"] if any(r.get("value") or [])]
                if jan == "today 12-m":
                    geo = None if geo_t != "BR" else next((w for k, w in ws.items() if k.startswith("GEO_MAP")), None)
                    if geo:
                        gm = t.widget("comparedgeo", geo)
                        g["uf_12m"] = [{"uf": (r.get("geoCode") or "").replace("BR-", ""), "nome": r.get("geoName"), "v": dict(zip(termos, r.get("value") or []))}
                                       for r in gm["default"]["geoMapData"]]
                    rel = {}
                    for k, w in sorted(ws.items()):
                        if k.startswith("RELATED_QUERIES"):
                            idx = int(k.rsplit("_", 1)[1]) if k.rsplit("_", 1)[-1].isdigit() else 0
                            if idx < len(termos):
                                rel[termos[idx]] = relacionados(t.widget("relatedsearches", w))
                    g["relacionados_12m"] = rel
            except Exception as e:  # noqa: BLE001
                ERROS.append(f"trends {nome} {jan}: {type(e).__name__}: {str(e)[:120]}")
        out[nome] = g
        print(f"trends {nome}: janelas lidas {[j for j in janelas if j in g]}")
    # 02/11/2026: a frase da âncora era do caso 002 e saía em todos os casos; agora só cita âncora quando ela existe
    ancora = [x for x in VARIANTES if x in CONTROLES]
    out["aviso"] = ("0 a 100, relativo ao pico dentro de cada consulta (cada grupo de termos é uma consulta separada"
                    + (f"; o termo '{ancora[0]}' está em variantes e controles como âncora" if ancora else "; sem termo-âncora comum, então os níveis de grupos diferentes não se comparam")
                    + "). Interesse relativo não diz a quem as pessoas se referiam.")
    return out


def yt(rota: str, **q) -> dict:
    try:
        return get_json(f"https://www.googleapis.com/youtube/v3/{rota}?" + urllib.parse.urlencode(q), timeout=60)
    except urllib.error.HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(next((m for m in ("quotaExceeded", "commentsDisabled", "forbidden") if m in corpo), f"HTTP {e.code}")) from None
    except Exception as e:  # noqa: BLE001 — a mensagem pode ter a URL com a chave
        raise RuntimeError(type(e).__name__) from None


def youtube(key: str, agora: str) -> tuple[dict, list[dict]]:
    from collect_comentarios_youtube import linhas_da_conversa
    ids: dict[str, str] = {}
    for q in BUSCAS_YT:
        token = None
        for _ in range(2):
            p = {"part": "snippet", "q": f'"{q}"' if CASO == "002" else q, "type": "video", "maxResults": 50, "publishedAfter": DESDE_YT, "key": key}
            if not CASOS[CASO].get("youtube_mundo"):  # 01/11/2026 (caso 025): sem região nem língua, para achar vídeos de fora
                p.update({"regionCode": "BR", "relevanceLanguage": "pt"})
            if token:
                p["pageToken"] = token
            try:
                d = yt("search", **p)
            except RuntimeError as e:
                ERROS.append(f"youtube busca '{q}': {e}")
                break
            for it in d.get("items", []):
                ids.setdefault(it["id"]["videoId"], q)
            token = d.get("nextPageToken")
            if not token:
                break
    for vid in CASOS[CASO].get("youtube_indicados") or []:  # 01/11/2026: vídeos indicados pelo responsável entram sempre
        ids.setdefault(vid, "indicado pelo responsável")
    vids = []
    lista = list(ids)
    for i in range(0, len(lista), 50):
        try:
            d = yt("videos", part="snippet,statistics", id=",".join(lista[i:i + 50]), key=key)
        except RuntimeError as e:
            ERROS.append(f"youtube videos: {e}")
            continue
        for it in d.get("items", []):
            sn, st = it["snippet"], it.get("statistics", {})
            txt = f"{sn.get('title', '')} {sn.get('description', '')[:300]}"
            if ids[it["id"]] != "indicado pelo responsável" and not (RX_TITULO.search(txt) and RX_ATRIBUTO.search(txt)):
                continue
            n = lambda k: int(st[k]) if str(st.get(k, "")).isdigit() else None  # noqa: E731
            vids.append({"id": it["id"], "titulo": sn.get("title"), "canal": sn.get("channelTitle"), "canal_id": sn.get("channelId"),
                         "publicado_em": sn.get("publishedAt"), "visualizacoes": n("viewCount"), "curtidas": n("likeCount"),
                         "comentarios": n("commentCount"), "consulta": ids[it["id"]], "descricao": (sn.get("description") or "")[:300],
                         "idioma_declarado": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage")})
    canais = list({v["canal_id"] for v in vids})
    inscritos, pais_canal = {}, {}
    for i in range(0, len(canais), 50):
        try:
            d = yt("channels", part="statistics,snippet", id=",".join(canais[i:i + 50]), key=key)
            for it in d.get("items", []):
                pais_canal[it["id"]] = (it.get("snippet", {}).get("country") or "").upper() or None  # país declarado pelo canal (01/11/2026)
                s = it.get("statistics", {})
                inscritos[it["id"]] = int(s["subscriberCount"]) if str(s.get("subscriberCount", "")).isdigit() else None
        except RuntimeError as e:
            ERROS.append(f"youtube canais: {e}")
    for v in vids:
        v["inscritos"] = inscritos.get(v["canal_id"])
        v["pais_canal"] = pais_canal.get(v["canal_id"])
    vids.sort(key=lambda v: v["visualizacoes"] or 0, reverse=True)
    rows = []
    for v in [x for x in vids if (x["comentarios"] or 0) > 0][:TOP_COMENTARIOS]:
        meta = {"video_id": v["id"], "candidate_id": "", "channel_id": v["canal_id"]}
        for ordem in ("relevance", "time"):
            try:
                d = yt("commentThreads", part="snippet,replies", videoId=v["id"], maxResults=100, order=ordem, textFormat="plainText", key=key)
            except RuntimeError as e:
                ERROS.append(f"comentários {v['id']}: {e}")
                break
            rows += [l for it in d.get("items", []) for l in linhas_da_conversa(it, meta, ordem, agora)]
    uniq = {r["comment_id"]: r for r in rows}
    print(f"youtube: {len(vids)} vídeos sobre o caso de {len(ids)} achados · {len(uniq)} comentários lidos")
    return {"videos": vids}, list(uniq.values())


EDICOES = {"BR": {"hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}, "PT": {"hl": "pt-PT", "gl": "PT", "ceid": "PT:pt-150"},
           "ES": {"hl": "es", "gl": "ES", "ceid": "ES:es"}, "AR": {"hl": "es-419", "gl": "AR", "ceid": "AR:es-419"},
           "CO": {"hl": "es-419", "gl": "CO", "ceid": "CO:es-419"}, "FR": {"hl": "fr", "gl": "FR", "ceid": "FR:fr"},
           "US": {"hl": "en-US", "gl": "US", "ceid": "US:en"}, "PY": {"hl": "es-419", "gl": "PY", "ceid": "PY:es-419"}}


def noticias() -> list[dict]:
    from collect_google_busca import RSS, parse_rss
    out, vistos = [], set()
    c = CASOS[CASO]
    for q in c.get("noticias") or VARIANTES:
        ed = "BR"
        if isinstance(q, dict):  # 02/11/2026 (caso 026): edição do Google Notícias de outro país, para a repercussão fora do Brasil
            q, ed = q["q"], q.get("ed", "BR")
        try:
            # termos próprios de notícias (sem aspas, com janela) quando o caso os define; senão, as variantes entre aspas
            busca = (f"{q} when:{c['janela_noticias']}" if c.get("janela_noticias") else q) if c.get("noticias") else f'"{q}"'  # 06/11/2026 (caso 037): janela vazia = sem limite de data
            url = RSS + "?" + urllib.parse.urlencode({"q": busca, **EDICOES[ed]})
            for x in parse_rss(read_body(open_url(url, timeout=40))):
                if x.get("link") in vistos or not RX_TITULO.search(x.get("titulo") or "") or (c.get("noticias") and not RX_ATRIBUTO.search(x.get("titulo") or "")):
                    continue
                vistos.add(x.get("link"))
                out.append({**{k: x.get(k) for k in ("titulo", "link", "veiculo", "dominio", "data_publicacao")}, "consulta": q, "edicao": ed})
        except Exception as e:  # noqa: BLE001
            ERROS.append(f"notícias '{q}': {type(e).__name__}")
    return sorted(out, key=lambda x: x.get("data_publicacao") or "")


def checagens(key: str) -> list[dict]:
    import collect_checagens as cc
    out = []
    for q in BUSCAS_CHECAGEM:
        out += cc.buscar(key, q, 3650, ERROS)
    return cc.juntar(out)


def wayback() -> list[dict]:
    """Cópia datada no Internet Archive de cada página de referência do caso (consulta; se não houver cópia, pede uma)."""
    saida = []
    for url in ARQUIVO_WEB:
        res = {"url": url}
        try:
            cdx = get_json("https://web.archive.org/cdx/search/cdx?" + urllib.parse.urlencode({"url": url, "output": "json", "limit": 5}), timeout=60)
            caps = [dict(zip(cdx[0], r)) for r in cdx[1:]] if cdx else []
            res["capturas"] = [{"data": c["timestamp"], "status": c.get("statuscode"), "arquivo": f"https://web.archive.org/web/{c['timestamp']}/{url}"} for c in caps]
        except Exception as e:  # noqa: BLE001
            res["erro_cdx"] = type(e).__name__
        if not res.get("capturas"):
            try:
                with open_url("https://web.archive.org/save/" + url, timeout=120) as r:
                    res["pedido_de_copia"] = f"HTTP {r.status}"
            except Exception as e:  # noqa: BLE001
                res["pedido_de_copia"] = f"falhou: {type(e).__name__} {getattr(e, 'code', '')}"
        saida.append(res)
    return saida


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    configurar(argv[argv.index("--caso") + 1] if "--caso" in argv else "002")
    agora = now_utc()
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    fc_key = os.environ.get("FACTCHECK_API_KEY", "").strip() or key
    out = {"caso": CASO, "coletado_em_utc": agora, "variantes": VARIANTES, "controles": CONTROLES}
    if "--sem-trends" not in argv:
        out["trends"] = trends()
        # janela recusada pelo Trends (HTTP 429) não apaga a leitura anterior: reaproveita a última que deu certo, marcada com a data
        ant = priv_dir() / "busca_coleta.json"
        if ant.exists():
            velho = (json.loads(ant.read_text(encoding="utf-8")).get("trends") or {})
            for g, dados in out["trends"].items():
                if not isinstance(dados, dict):
                    continue
                for k, v in (velho.get(g) or {}).items():
                    if k not in dados and k != "lido_em":
                        dados[k] = v
                        dados.setdefault("reaproveitado", {})[k] = (velho.get(g) or {}).get("lido_em") or json.loads(ant.read_text(encoding="utf-8")).get("coletado_em_utc")
                dados.setdefault("lido_em", agora)
    rows = []
    # 02/11/2026 ("as coletas de youtube foram todas feitas?"): a cota diária do YouTube (10 mil unidades, uma busca = 100) acabava
    # antes dos casos do fim da fila (021–031 com HTTP 429 em todas as buscas). Caso com vídeos lidos há menos de YT_INTERVALO_H horas
    # reaproveita a leitura anterior e não gasta cota; quem nunca teve vídeo vai primeiro.
    ant0 = priv_dir() / "busca_coleta.json"
    velho0 = json.loads(ant0.read_text(encoding="utf-8")) if ant0.exists() else {}
    yt_lido = (velho0.get("youtube") or {}).get("lido_em") or (velho0.get("coletado_em_utc") if (velho0.get("youtube") or {}).get("videos") else None)
    recente = False
    if yt_lido and (velho0.get("youtube") or {}).get("videos"):
        try:
            idade = (dt.datetime.strptime(agora[:19], "%Y-%m-%dT%H:%M:%S") - dt.datetime.strptime(yt_lido[:19], "%Y-%m-%dT%H:%M:%S")).total_seconds() / 3600
            recente = idade < float(os.environ.get("YT_INTERVALO_H", "48"))
        except ValueError:
            pass
    if recente and "--forcar-youtube" not in argv:
        out["youtube"] = {**velho0["youtube"], "reaproveitado_de": yt_lido}
        rows = []
        print(f"youtube: leitura de {yt_lido} reaproveitada (menos de {os.environ.get('YT_INTERVALO_H', '48')} h; poupa a cota)")
    elif key and "--sem-youtube" not in argv and not CASOS[CASO].get("sem_youtube"):
        out["youtube"], rows = youtube(key, agora)
        if out["youtube"].get("videos"):
            out["youtube"]["lido_em"] = agora
        # a busca do YouTube devolve conjuntos diferentes a cada dia: um vídeo já encontrado continua no caso (com os números da
        # última leitura e a data em que foi visto pela última vez), desde que ainda passe no filtro atual
        ant = priv_dir() / "busca_coleta.json"
        if ant.exists():
            velhos = (json.loads(ant.read_text(encoding="utf-8")).get("youtube") or {}).get("videos", [])
            atuais = {v["id"] for v in out["youtube"]["videos"]}
            for v in out["youtube"]["videos"]:
                v["visto_por_ultimo"] = agora
            for v in velhos:
                txt = f"{v.get('titulo') or ''}"
                if v["id"] not in atuais and RX_TITULO.search(txt) and RX_ATRIBUTO.search(txt + " " + (v.get("descricao") or "")):
                    out["youtube"]["videos"].append({**v, "visto_por_ultimo": v.get("visto_por_ultimo") or json.loads(ant.read_text(encoding="utf-8")).get("coletado_em_utc")})
            out["youtube"]["videos"].sort(key=lambda v: v.get("visualizacoes") or 0, reverse=True)
    out["noticias"] = noticias()
    out["checagens"] = checagens(fc_key) if fc_key else []
    out["arquivo_web"] = wayback()
    out["erros"] = ERROS
    pasta = Path("data/casos") / CASO
    pasta.mkdir(parents=True, exist_ok=True)
    pv = priv_dir()
    pv.mkdir(parents=True, exist_ok=True)
    (pv / "busca_coleta.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if rows:
        arq = pv / "youtube_comentarios.csv.gz"
        antigos = {r["comment_id"]: r for r in csv.DictReader(gzip.open(arq, "rt", encoding="utf-8"), delimiter=";")} if arq.exists() else {}
        antigos.update({r["comment_id"]: r for r in rows})
        campos = list(rows[0].keys())
        with gzip.open(arq, "wt", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, campos, delimiter=";", extrasaction="ignore")
            w.writeheader()
            w.writerows(antigos.values())
    print(f"caso {CASO}: notícias {len(out['noticias'])} · checagens {len(out['checagens'])} · arquivo web "
          f"{[(len(a.get('capturas') or []), a.get('pedido_de_copia')) for a in out['arquivo_web']]} · erros {ERROS[:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
