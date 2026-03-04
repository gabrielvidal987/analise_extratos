from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional, Tuple
import json
import mimetypes
import os
import re

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from google import genai
import uvicorn

ALLOWED_MIME_TYPES = {"application/pdf"}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_SYSTEM_PROMPT = (
    "Atue como especialista financeiro e analise o(s) extrato(s) enviados. "
    "Separe transacoes em entradas e saidas, com categorias logicas. "
    "Consolide transacoes para a mesma empresa em um unico item, somando valores e informando "
    "ocorrencias e detalhes originais. Retorne recomendacao financeira simples. "
    "Retorne somente JSON com este formato: "
    '{"resumo":{"total_entradas":0.0,"total_saidas":0.0,"saldo_final":0.0,"recomendacao financeira":""},'
    '"entradas":[{"nome_categoria":"","valor_categoria":0.0,"itens":[{"nome":"","valor_total":0.0,"ocorrencias":0,"detalhes":[]}]}],'
    '"saidas":[{"nome_categoria":"","valor_categoria":0.0,"itens":[{"nome":"","valor_total":0.0,"ocorrencias":0,"detalhes":[]}]}]}. '
    "Dados para analise:"
)


def load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            clean_line = line.strip()
            if not clean_line or clean_line.startswith("#") or "=" not in clean_line:
                continue

            key, value = clean_line.split("=", 1)
            key = key.strip().lstrip("\ufeff")
            value = value.strip().strip("'\"")
            os.environ.setdefault(key, value)


def read_text_file(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as source_file:
        return source_file.read().strip()


load_env_file()

API_KEY_GEMINI = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_AI_GEMINI = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "").strip() or read_text_file("system_prompt.txt") or DEFAULT_SYSTEM_PROMPT


def _to_decimal(value) -> Decimal:
    try:
        if value is None:
            return Decimal("0")
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        normalized = str(value).replace("R$", "").replace(".", "").replace(",", ".").strip()
        return Decimal(normalized) if normalized else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _normalize_categories(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        categories = data.get("categorias")
        if isinstance(categories, list):
            return categories
    return []


def _sum_categories(categories) -> Decimal:
    total = Decimal("0")
    for category in categories:
        if not isinstance(category, dict):
            continue

        if "valor_categoria" in category:
            total += _to_decimal(category.get("valor_categoria"))
            continue

        if "total_categoria" in category:
            total += _to_decimal(category.get("total_categoria"))
            continue

        for item in category.get("itens", []):
            if isinstance(item, dict):
                total += _to_decimal(item.get("valor_total"))
    return total


def normalize_and_fix_analysis(analysis: dict) -> dict:
    if not isinstance(analysis, dict):
        return {}

    entradas = _normalize_categories(analysis.get("entradas"))
    saidas = _normalize_categories(analysis.get("saidas"))
    resumo = analysis.get("resumo") if isinstance(analysis.get("resumo"), dict) else {}

    total_entradas = _sum_categories(entradas)
    total_saidas = _sum_categories(saidas)
    saldo_final = total_entradas - total_saidas

    recomendacao = resumo.get("recomendacao financeira") or resumo.get("recomendação financeira") or ""

    return {
        "resumo": {
            "total_entradas": float(total_entradas),
            "total_saidas": float(total_saidas),
            "saldo_final": float(saldo_final),
            "recomendacao financeira": recomendacao,
        },
        "entradas": entradas,
        "saidas": saidas,
    }


def extrair_json(texto: str) -> dict:
    texto_limpo = re.sub(r"```(?:json)?", "", texto).strip()
    match = re.search(r"\{.*\}", texto_limpo, re.DOTALL)
    if not match:
        raise ValueError("Nenhum JSON encontrado na resposta da IA")
    return json.loads(match.group(0))


def is_allowed_upload(file: UploadFile) -> bool:
    content_type = (file.content_type or "").lower()
    if content_type in ALLOWED_MIME_TYPES or content_type.startswith("image/"):
        return True
    extension = Path(file.filename or "").suffix.lower()
    return extension in ALLOWED_EXTENSIONS


def resolve_mime_type(file: UploadFile | str) -> str:
    if isinstance(file, str):
        guessed, _ = mimetypes.guess_type(file)
        return guessed or "application/octet-stream"
    if file.content_type:
        return file.content_type
    guessed, _ = mimetypes.guess_type(file.filename or "")
    return guessed or "application/octet-stream"


def upload_files_ai(client: genai.Client, input_files: list) -> Tuple[Optional[list], str]:
    files_uploaded = []
    try:
        for file in input_files:
            mime_type = resolve_mime_type(file)
            if isinstance(file, str):
                files_uploaded.append(client.files.upload(file=file, config={"mime_type": mime_type}))
            else:
                file.file.seek(0)
                files_uploaded.append(client.files.upload(file=file.file, config={"mime_type": mime_type}))
        return files_uploaded, ""
    except Exception as er:
        return None, str(er)


def extract_analysis(input_files: list = None) -> Tuple[Optional[dict], str]:
    try:
        if not API_KEY_GEMINI:
            return None, "GEMINI_API_KEY nao configurada. Defina no arquivo .env."
        if not SYSTEM_PROMPT:
            return None, "SYSTEM_PROMPT nao configurado."
        if not input_files:
            return None, "Nenhum arquivo enviado."

        client = genai.Client(api_key=API_KEY_GEMINI)
        files_uploaded, upload_err = upload_files_ai(client=client, input_files=input_files)
        if not files_uploaded:
            return None, f"Erro ao subir arquivos para analise. {upload_err}".strip()

        response = client.models.generate_content(
            model=MODEL_AI_GEMINI,
            contents=[SYSTEM_PROMPT, *files_uploaded],
        )

        if not response or not getattr(response, "text", ""):
            return None, "Resposta vazia da IA."

        dict_response = normalize_and_fix_analysis(extrair_json(response.text))

        try:
            client.close()
        except Exception:
            pass

        return dict_response, ""
    except Exception as er:
        return None, str(er)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")


async def process_upload(files: List[UploadFile] = File(...)):
    if not files:
        return {"sucess": False, "data": "", "message": "Nenhum arquivo foi enviado."}

    for file in files:
        if not is_allowed_upload(file):
            return {
                "sucess": False,
                "data": "",
                "message": (
                    f"Arquivo invalido: {file.filename}. "
                    "Envie PDF ou imagem (png, jpg, jpeg, webp, bmp, tif, tiff)."
                ),
            }

    analise, err_message = extract_analysis(input_files=files)
    if not analise:
        return {"sucess": False, "data": "", "message": err_message or "Erro ao processar request"}

    return {"sucess": True, "data": analise, "message": ""}


@app.post("/upload-extratos")
async def upload_extratos(files: List[UploadFile] = File(...)):
    return await process_upload(files)


@app.post("/upload-pdfs")
async def upload_pdfs(files: List[UploadFile] = File(...)):
    return await process_upload(files)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "titulo": "Renderizado front"})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5600, reload=False)
