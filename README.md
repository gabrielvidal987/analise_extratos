# Analise de Extratos com IA (FastAPI + Gemini)

Aplicacao web para analisar extratos financeiros (PDF e imagens), classificar transacoes em entradas e saidas, agrupar por categoria e gerar uma recomendacao financeira simples usando IA.

## Para que serve

Este projeto ajuda a transformar extratos "brutos" em um resumo financeiro estruturado:

- calcula total de entradas, total de saidas e saldo final;
- categoriza gastos e receitas;
- consolida transacoes da mesma empresa/entidade;
- mostra recomendacao financeira em linguagem simples;
- entrega o resultado em JSON e em interface web.

## Como funciona

Fluxo geral:

1. Usuario envia um ou mais arquivos pela interface web.
2. Backend valida tipo/extensao dos arquivos.
3. Arquivos sao enviados para o modelo Gemini com um prompt de analise financeira.
4. O backend extrai o JSON retornado pela IA.
5. O sistema normaliza o formato, recalcula totais e saldo para garantir consistencia.
6. Frontend renderiza KPIs, grafico e tabelas detalhadas.

## Tipos de arquivo aceitos

Aceitos no upload:

- PDF (`.pdf`)
- Imagens: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tif`, `.tiff`
- MIME types aceitos: `application/pdf` e `image/*`

## Requisitos

- Python 3.10+ (recomendado)
- Chave de API do Gemini
- Dependencias Python em `requirements_python.txt`

## Configuracao

1. Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Instale as dependencias:

```powershell
pip install -r requirements_python.txt
```

3. Configure variaveis de ambiente:

```powershell
Copy-Item .env.example .env
```

Edite o `.env`:

```env
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-3-flash-preview
# Opcional:
# SYSTEM_PROMPT=...
```

Observacao: se `SYSTEM_PROMPT` nao for definido no `.env`, o projeto usa `system_prompt.txt` (ou um prompt padrao interno).

## Como rodar

Opcao 1 (mais simples):

```powershell
python main.py
```

Opcao 2 (uvicorn direto):

```powershell
uvicorn main:app --host 0.0.0.0 --port 5600
```

Acesse:

- Interface web: `http://localhost:5600/`

## Como usar

### Pela interface web

1. Abra `http://localhost:5600/`.
2. Arraste ou selecione os extratos.
3. Clique em **Iniciar Analise IA**.
4. Veja:
- conselho financeiro;
- total de entradas e saidas;
- saldo final;
- grafico de proporcao;
- tabelas por categoria.

### Pela API (exemplo cURL)

Endpoint principal:

- `POST /upload-extratos`

Exemplo:

```bash
curl -X POST "http://localhost:5600/upload-extratos" \
  -F "files=@exemplo_extr.pdf"
```

Tambem existe alias:

- `POST /upload-pdfs` (mesmo comportamento)

## Formato de resposta (resumo)

```json
{
  "sucess": true,
  "data": {
    "resumo": {
      "total_entradas": 0.0,
      "total_saidas": 0.0,
      "saldo_final": 0.0,
      "recomendacao financeira": ""
    },
    "entradas": [],
    "saidas": []
  },
  "message": ""
}
```

## Estrutura do projeto

- `main.py`: API FastAPI, validacao de upload, chamada ao Gemini e normalizacao do JSON.
- `templates/index.html`: interface web (upload, visualizacao de resultados, grafico).
- `system_prompt.txt`: prompt padrao da analise.
- `.env.example`: exemplo de configuracao.

## Seguranca para repositorio publico

- Nao publique `.env` nem arquivos com chaves.
- Revise PDFs/imagens antes de subir (podem conter dados pessoais/sensiveis).
- Remova ou anonimiza dados reais de extratos usados como exemplo.
