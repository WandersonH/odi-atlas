# Banco DuckDB do Atlas

O Atlas guarda cada coleta como arquivo (CSV, JSON, JSONL) nos dois repositórios. Toda noite (`.github/workflows/banco.yml`,
03h43 de Brasília) esses arquivos viram dois bancos DuckDB, refeitos do zero; nada é apagado nem alterado nos repositórios.

| Banco | Conteúdo | Onde baixar | Quem acessa |
| --- | --- | --- | --- |
| `atlas_publico.duckdb` | só `data/` do repositório público (agregados; pessoas comuns aparecem como código) | release **banco** de `WandersonH/odi-atlas` (`atlas_publico.zip`, ~97 MB) | qualquer pessoa |
| `atlas_completo.duckdb` | o público + o repositório privado (texto e autor de pessoas comuns, respostas brutas das coletas, transcrições) | release **banco** de `WandersonH/odi-atlas-interno` (`atlas_completo.zip`, ~670 MB; 2,2 GB descompactado) | equipe e pesquisadores aprovados, com termo de uso |

O catálogo do banco público (tabelas, origem, arquivos, linhas, erros) fica em `data/banco/atlas_publico.catalogo.json`;
o do completo vai junto no release privado.

## Como abrir

Precisa do DuckDB 2.0 ou mais novo (o banco é gravado com a versão fixada no workflow).

```python
import duckdb
con = duckdb.connect("atlas_publico.duckdb", read_only=True)
con.sql("select tabela, familia, arquivos, linhas from _catalogo order by linhas desc").show()
con.sql("select * from _sobre").show()
```

Também abre no DBeaver (driver DuckDB) e no R (`duckdb::duckdb()`).

## Como os arquivos viram tabelas

- Cada família de arquivos (mesmo caminho, mudando só o caso, a data ou o id da coleta) vira uma tabela com o prefixo
  `pub_` ou `priv_`: `casos/021/itens.csv.gz` e `casos/033/itens.csv.gz` → `priv_casos_itens_csv`.
- Toda linha leva `_arquivo` (caminho de origem), `_caso` (quando é de um caso) e `_data_no_nome` (data no nome do arquivo
  ou da pasta, quando há — não é a data de publicação dos itens).
- CSV: colunas do próprio arquivo (tipos inferidos; quando a inferência falha, tudo como texto — ver `_catalogo.tipos`).
- JSONL (respostas brutas da Apify e dos coletores): uma linha por registro, coluna `registro` (JSON).
  Ex.: `select registro->>'$.text' from priv_casos_bruto_x_jsonl where _caso = '026' limit 5`.
- JSON: tabela `pub_json_documentos` / `priv_json_documentos`, um documento por arquivo, coluna `conteudo`.
  Ex.: `select conteudo->'$.youtube.videos' from pub_json_documentos where _arquivo = 'casos/035/busca.json'`.
- TXT, VTT, SRT, MD (transcrições, corpus IRaMuTeQ): `pub_textos` / `priv_textos`, coluna `texto`.
- Fora do banco (só caminho e tamanho, em `_arquivos_fora`): imagens, vídeos, PDFs e GEXF (os nós e arestas das redes
  já estão em `*_rede_nos_csv` e `*_rede_arestas_csv`).

## Universo × amostra

O banco guarda o que o Atlas leu: é amostra. O universo que cada plataforma informa está nos manifestos
(`*manifesto*.json`, em `*_json_documentos`) e nas páginas; quando a plataforma não informa, é ⛔ desconhecido.
O banco não estima universo.
