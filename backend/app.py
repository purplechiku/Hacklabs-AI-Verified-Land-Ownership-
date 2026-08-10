import io
import json
import re
import uuid
import os
import hashlib

from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import httpx
import pymupdf
import pytesseract

from PIL import Image, ImageOps, ImageFilter
from dateutil import parser as dateparser

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Query,
)

from fastapi.middleware.cors import CORSMiddleware
from rapidfuzz import fuzz
import os
import hashlib
import requests
from dotenv import load_dotenv


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Adhikar Digital Land Registry",
    version="0.3.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# PATHS / STORAGE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
load_dotenv()

BLOCKCHAIN_SERVICE_URL = os.getenv("BLOCKCHAIN_SERVICE_URL", "http://localhost:4001")
DATA_DIR = BASE_DIR / "data"
RECORDS_FILE = DATA_DIR / "records.json"

DATA_DIR.mkdir(exist_ok=True)

IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp",
    "bmp",
    "tif",
    "tiff",
}


# ============================================================
# BLOCKCHAIN CONFIGURATION
# ============================================================

# The Python application talks ONLY to the blockchain wrapper.
#
# Example:
#
# BLOCKCHAIN_SERVICE_URL=http://localhost:4001
#
# The private key stays inside the blockchain wrapper service.
# This application never needs the wallet/private key.

BLOCKCHAIN_SERVICE_URL = os.getenv(
    "BLOCKCHAIN_SERVICE_URL",
    "http://localhost:4001",
).rstrip("/")


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

def configure_tesseract():
    """
    Find Tesseract automatically on Windows.
    """

    possible_paths = [
        Path(
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        ),
        Path(
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
        ),
        (
            Path.home()
            / "AppData"
            / "Local"
            / "Programs"
            / "Tesseract-OCR"
            / "tesseract.exe"
        ),
    ]

    current = pytesseract.pytesseract.tesseract_cmd

    if current:
        try:
            if Path(current).exists():
                return
        except Exception:
            pass

    for path in possible_paths:
        if path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(path)
            return


configure_tesseract()


# ============================================================
# OCR LANGUAGE DETECTION
# ============================================================

def get_available_ocr_languages():
    """
    Return languages installed in Tesseract.

    Usually:
        eng
        hin

    If Hindi is not installed, the service will still work
    using English OCR.
    """

    try:
        languages = pytesseract.get_languages(config="")
        return set(languages)
    except Exception:
        return set()


def choose_ocr_languages():
    """
    Prefer English + Hindi when Hindi language data exists.
    """

    languages = get_available_ocr_languages()

    if "eng" in languages and "hin" in languages:
        return "eng+hin"

    if "hin" in languages:
        return "hin"

    if "eng" in languages:
        return "eng"

    return "eng"


# ============================================================
# LAND DOCUMENT KEYWORDS
# ============================================================

LAND_KEYWORDS_EN = [
    "land",
    "property",
    "plot",
    "survey",
    "khasra",
    "khata",
    "khatauni",
    "parcel",
    "registration",
    "registered",
    "registry",
    "registrar",
    "sub registrar",
    "sale deed",
    "sale agreement",
    "property deed",
    "title deed",
    "ownership",
    "owner",
    "landowner",
    "square feet",
    "sq ft",
    "sqft",
    "hectare",
    "hectares",
    "acre",
    "acres",
    "village",
    "tehsil",
    "district",
    "mutation",
    "patta",
    "jamabandi",
    "revenue",
    "bhu naksha",
    "property id",
    "plot number",
    "survey number",
    "registration number",
    "land record",
    "land records",
    "revenue record",
    "revenue records",
    "acquisition",
    "land acquisition",
    "acquired land",
    "acquisition officer",
    "competent authority",
    "notification",
    "award",
    "compensation",
    "affected land",
    "affected area",
    "government land",
]


LAND_KEYWORDS_HI = [
    "भूमि",
    "जमीन",
    "भूखंड",
    "प्लॉट",
    "सर्वे",
    "खसरा",
    "खाता",
    "खतौनी",
    "रकबा",
    "क्षेत्रफल",
    "स्वामित्व",
    "स्वामी",
    "भूमिस्वामी",
    "पंजीयन",
    "पंजीकरण",
    "रजिस्ट्री",
    "रजिस्ट्रार",
    "उप पंजीयक",
    "विक्रय पत्र",
    "बिक्री विलेख",
    "विलेख",
    "नामांतरण",
    "पट्टा",
    "जमाबंदी",
    "राजस्व",
    "ग्राम",
    "गांव",
    "तहसील",
    "जिला",
    "भू-अर्जन",
    "भू अर्जन",
    "भूमि अर्जन",
    "अधिग्रहण",
    "अधिसूचना",
    "मुआवजा",
    "पुरस्कार",
    "अर्जन अधिकारी",
    "राजस्व अभिलेख",
]


ACQUISITION_KEYWORDS_EN = [
    "land acquisition",
    "acquisition",
    "acquired",
    "acquisition officer",
    "competent authority",
    "notification",
    "award",
    "compensation",
    "affected land",
    "affected area",
    "public purpose",
    "government acquisition",
    "land acquisition act",
]


ACQUISITION_KEYWORDS_HI = [
    "भू-अर्जन",
    "भू अर्जन",
    "भूमि अर्जन",
    "अधिग्रहण",
    "अधिसूचना",
    "मुआवजा",
    "पुरस्कार",
    "अर्जन अधिकारी",
    "सार्वजनिक प्रयोजन",
]


NON_LAND_KEYWORDS = [
    "curriculum vitae",
    "resume",
    "work experience",
    "professional experience",
    "education",
    "skills",
    "job application",
    "cover letter",
    "employment history",
    "career objective",
    "linkedin profile",
    "academic qualifications",
]


# ============================================================
# RECORD STORAGE
# ============================================================

def load_records():
    if not RECORDS_FILE.exists():
        RECORDS_FILE.write_text(
            "[]",
            encoding="utf-8",
        )

    try:
        data = json.loads(
            RECORDS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, list):
            return data

        return []

    except (json.JSONDecodeError, OSError):
        return []


def save_records(records):
    RECORDS_FILE.write_text(
        json.dumps(
            records,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# BLOCKCHAIN HELPERS
# ============================================================

def calculate_document_hash(data: bytes) -> str:
    """
    Generate a SHA-256 hash of the original uploaded file.

    The result is returned as a 0x-prefixed 32-byte hex value,
    which matches Solidity bytes32.

    Example:
        0xabc123...
    """

    digest = hashlib.sha256(data).hexdigest()

    return f"0x{digest}"


async def register_on_blockchain(
    owner_name: Optional[str],
    plot_number: Optional[str],
    doc_hash: str,
    ipfs_hash: str = "",
):
    """
    Register a verified land document through the blockchain
    wrapper service.

    This application does NOT connect directly to Ethereum.

    It calls:

        POST {BLOCKCHAIN_SERVICE_URL}/register

    The blockchain wrapper owns the wallet/private key.
    """

    if not owner_name:
        return {
            "registered": False,
            "status": "not_registered",
            "tx_hash": None,
            "block_number": None,
            "error": "Owner name is missing.",
        }

    if not plot_number:
        return {
            "registered": False,
            "status": "not_registered",
            "tx_hash": None,
            "block_number": None,
            "error": "Plot number is missing.",
        }

    payload = {
        "owner_name": owner_name,
        "plot_number": plot_number,
        "doc_hash": doc_hash,
        "ipfs_hash": ipfs_hash,
    }

    try:
        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.post(
                f"{BLOCKCHAIN_SERVICE_URL}/register",
                json=payload,
            )

        # Plot already exists on blockchain.
        if response.status_code == 409:
            try:
                response_data = response.json()
            except Exception:
                response_data = {}

            return {
                "registered": False,
                "status": "conflict",
                "tx_hash": None,
                "block_number": None,
                "error": (
                    response_data.get("detail")
                    or "Plot is already registered on blockchain."
                ),
            }

        # Any other HTTP error.
        if response.status_code >= 400:
            try:
                response_data = response.json()
            except Exception:
                response_data = {}

            return {
                "registered": False,
                "status": "error",
                "tx_hash": None,
                "block_number": None,
                "error": (
                    response_data.get("detail")
                    or f"Blockchain service returned HTTP {response.status_code}."
                ),
            }

        try:
            response_data = response.json()
        except Exception:
            response_data = {}

        return {
            "registered": True,
            "status": response_data.get(
                "status",
                "pending",
            ),
            "tx_hash": response_data.get(
                "tx_hash"
            ),
            "block_number": response_data.get(
                "block_number"
            ),
            "error": None,
        }

    except httpx.ConnectError:
        return {
            "registered": False,
            "status": "unavailable",
            "tx_hash": None,
            "block_number": None,
            "error": (
                "Blockchain wrapper service is unavailable."
            ),
        }

    except httpx.TimeoutException:
        return {
            "registered": False,
            "status": "timeout",
            "tx_hash": None,
            "block_number": None,
            "error": (
                "Blockchain wrapper service timed out."
            ),
        }

    except Exception as exc:
        return {
            "registered": False,
            "status": "error",
            "tx_hash": None,
            "block_number": None,
            "error": str(exc),
        }


# ============================================================
# FILE NORMALIZATION
# ============================================================

def image_to_pdf(data: bytes) -> bytes:
    try:
        image = Image.open(
            io.BytesIO(data)
        ).convert("RGB")

        output = io.BytesIO()

        image.save(
            output,
            format="PDF",
        )

        return output.getvalue()

    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Could not convert image to PDF: {exc}"
            ),
        )


def normalize_pdf(
    data: bytes,
    filename: str,
) -> bytes:

    extension = (
        filename.rsplit(".", 1)[-1].lower()
        if "." in filename
        else ""
    )

    if extension == "pdf":
        return data

    if extension in IMAGE_EXTENSIONS:
        return image_to_pdf(data)

    raise HTTPException(
        status_code=400,
        detail=(
            "Unsupported file type. "
            "Upload PDF, JPG, JPEG, PNG, WEBP, BMP, TIF, or TIFF."
        ),
    )


# ============================================================
# NATIVE PDF TEXT EXTRACTION
# ============================================================

def extract_native_pdf_text(
    pdf_bytes: bytes,
) -> str:

    try:
        doc = pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Could not open PDF: {exc}",
        )

    texts = []

    try:
        for page in doc:

            try:
                text = page.get_text("text")

                if text:
                    texts.append(text)

            except Exception:
                continue

    finally:
        doc.close()

    return "\n".join(texts).strip()


# ============================================================
# IMAGE PREPROCESSING
# ============================================================

def preprocess_image(
    image: Image.Image,
) -> Image.Image:

    image = image.convert("RGB")

    image = ImageOps.grayscale(image)

    image = ImageOps.autocontrast(image)

    image = image.filter(
        ImageFilter.SHARPEN
    )

    return image


# ============================================================
# OCR ONE IMAGE
# ============================================================

def ocr_image(
    image: Image.Image,
    languages: str,
):
    """
    OCR an image and return:

        text
        confidence
    """

    image = preprocess_image(image)

    config = "--oem 3 --psm 6"

    try:
        text = pytesseract.image_to_string(
            image,
            lang=languages,
            config=config,
        )

    except Exception:

        try:
            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config=config,
            )

        except Exception:
            text = ""

    confidence_values = []

    try:
        data = pytesseract.image_to_data(
            image,
            lang=languages,
            output_type=pytesseract.Output.DICT,
            config=config,
        )

        for value in data.get(
            "conf",
            [],
        ):

            try:
                confidence = float(value)

                if confidence >= 0:
                    confidence_values.append(
                        confidence
                    )

            except (
                ValueError,
                TypeError,
            ):
                continue

    except Exception:
        pass

    confidence = (
        sum(confidence_values)
        / len(confidence_values)
        / 100
        if confidence_values
        else 0
    )

    return (
        text.strip(),
        confidence,
    )


# ============================================================
# PDF OCR
# ============================================================

def pdf_ocr(pdf_bytes: bytes):
    """
    OCR scanned PDFs.

    Automatically attempts Hindi OCR when
    the Hindi Tesseract language pack exists.
    """

    doc = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    texts = []
    confidences = []

    languages = choose_ocr_languages()

    try:
        for page in doc:

            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(
                    3,
                    3,
                ),
                alpha=False,
            )

            image = Image.frombytes(
                "RGB",
                [
                    pix.width,
                    pix.height,
                ],
                pix.samples,
            )

            text, confidence = ocr_image(
                image,
                languages,
            )

            if text:
                texts.append(text)

            if confidence > 0:
                confidences.append(
                    confidence
                )

    finally:
        doc.close()

    text = "\n".join(texts).strip()

    confidence = (
        sum(confidences)
        / len(confidences)
        if confidences
        else 0
    )

    return (
        text,
        round(confidence, 3),
        languages,
    )


# ============================================================
# DOCUMENT TEXT EXTRACTION
# ============================================================

def extract_document_text(
    pdf_bytes: bytes,
):
    """
    Prefer native PDF text.

    If native text is too short,
    use OCR.
    """

    native_text = extract_native_pdf_text(
        pdf_bytes
    )

    native_text = native_text.strip()

    if len(native_text) >= 120:
        return (
            native_text,
            1.0,
            "native",
            None,
        )

    (
        ocr_text,
        ocr_confidence,
        ocr_language,
    ) = pdf_ocr(
        pdf_bytes
    )

    if len(ocr_text) > len(native_text):
        return (
            ocr_text,
            ocr_confidence,
            "ocr",
            ocr_language,
        )

    if native_text:
        return (
            native_text,
            1.0,
            "native",
            None,
        )

    return (
        ocr_text,
        ocr_confidence,
        "ocr",
        ocr_language,
    )


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(
    text: str,
) -> str:

    text = text.replace(
        "\x00",
        " ",
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def normalize_for_matching(
    text: str,
) -> str:

    text = text.lower()

    text = text.replace(
        "\u200c",
        "",
    )

    text = text.replace(
        "\u200d",
        "",
    )

    text = re.sub(
        r"[^\w\s./:-]",
        " ",
        text,
        flags=re.UNICODE,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# SAFE KEYWORD MATCHING
# ============================================================

def keyword_present(
    text: str,
    keyword: str,
) -> bool:

    normalized_text = normalize_for_matching(
        text
    )

    normalized_keyword = normalize_for_matching(
        keyword
    )

    if not normalized_keyword:
        return False

    if " " in normalized_keyword:
        return normalized_keyword in normalized_text

    if normalized_keyword.isascii():

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(normalized_keyword)
            + r"(?![a-z0-9])"
        )

        return bool(
            re.search(
                pattern,
                normalized_text,
                re.IGNORECASE,
            )
        )

    pattern = (
        r"(?<!\w)"
        + re.escape(normalized_keyword)
        + r"(?!\w)"
    )

    return bool(
        re.search(
            pattern,
            normalized_text,
            re.IGNORECASE,
        )
    )


def find_keyword_hits(
    text: str,
    keywords,
):
    hits = []

    for keyword in keywords:

        if keyword_present(
            text,
            keyword,
        ):
            hits.append(keyword)

    return sorted(
        set(hits),
        key=str.lower,
    )


# ============================================================
# DOCUMENT TYPE DETECTION
# ============================================================

def detect_document_type(
    text: str,
):
    """
    More tolerant land-document classifier.

    A document can be:

        land/property
        acquisition
        unknown/non-land

    Failure to extract fields does NOT
    automatically mean it is a non-land document.
    """

    if not text.strip():

        return {
            "is_land_document": False,
            "document_type": "Unknown document",
            "reason": "No readable text was found.",
            "land_keyword_hits": [],
            "hindi_land_keyword_hits": [],
            "acquisition_keyword_hits": [],
            "non_land_keyword_hits": [],
        }

    land_hits_en = find_keyword_hits(
        text,
        LAND_KEYWORDS_EN,
    )

    land_hits_hi = find_keyword_hits(
        text,
        LAND_KEYWORDS_HI,
    )

    acquisition_hits_en = find_keyword_hits(
        text,
        ACQUISITION_KEYWORDS_EN,
    )

    acquisition_hits_hi = find_keyword_hits(
        text,
        ACQUISITION_KEYWORDS_HI,
    )

    non_land_hits = find_keyword_hits(
        text,
        NON_LAND_KEYWORDS,
    )

    total_land_hits = (
        len(land_hits_en)
        + len(land_hits_hi)
    )

    total_acquisition_hits = (
        len(acquisition_hits_en)
        + len(acquisition_hits_hi)
    )

    if total_acquisition_hits >= 1:

        return {
            "is_land_document": True,
            "document_type": "Land acquisition document",
            "reason": (
                "Land acquisition terminology was detected."
            ),
            "land_keyword_hits": land_hits_en,
            "hindi_land_keyword_hits": land_hits_hi,
            "acquisition_keyword_hits": (
                acquisition_hits_en
                + acquisition_hits_hi
            ),
            "non_land_keyword_hits": non_land_hits,
        }

    if total_land_hits >= 2:

        return {
            "is_land_document": True,
            "document_type": "Land/property document",
            "reason": (
                "Land/property terminology was detected."
            ),
            "land_keyword_hits": land_hits_en,
            "hindi_land_keyword_hits": land_hits_hi,
            "acquisition_keyword_hits": (
                acquisition_hits_en
                + acquisition_hits_hi
            ),
            "non_land_keyword_hits": non_land_hits,
        }

    if (
        len(non_land_hits) >= 2
        and total_land_hits == 0
        and total_acquisition_hits == 0
    ):

        return {
            "is_land_document": False,
            "document_type": "Non-land document",
            "reason": (
                "The uploaded document appears to be "
                "a non-land document."
            ),
            "land_keyword_hits": land_hits_en,
            "hindi_land_keyword_hits": land_hits_hi,
            "acquisition_keyword_hits": (
                acquisition_hits_en
                + acquisition_hits_hi
            ),
            "non_land_keyword_hits": non_land_hits,
        }

    return {
        "is_land_document": False,
        "document_type": "Unknown document",
        "reason": (
            "Insufficient land/property information "
            "was found in the uploaded document."
        ),
        "land_keyword_hits": land_hits_en,
        "hindi_land_keyword_hits": land_hits_hi,
        "acquisition_keyword_hits": (
            acquisition_hits_en
            + acquisition_hits_hi
        ),
        "non_land_keyword_hits": non_land_hits,
    }


# ============================================================
# FIELD PATTERNS
# ============================================================

PATTERNS = {

    "owner_name": [

        (
            r"(?:owner\s*name|name\s*of\s*owner|landowner)"
            r"\s*[:\-]\s*([A-Za-z][A-Za-z .]{2,100})"
        ),

        (
            r"\bowner\s*[:\-]\s*"
            r"([A-Za-z][A-Za-z .]{2,100})"
        ),

        (
            r"(?:नाम\s*[:\-]\s*)"
            r"([\u0900-\u097F][\u0900-\u097F .]{2,100})"
        ),

        (
            r"(?:भूमि\s*स्वामी|भूस्वामी)"
            r"\s*[:\-]\s*"
            r"([\u0900-\u097F][\u0900-\u097F .]{2,100})"
        ),
    ],

    "plot_number": [

        (
            r"(?:plot\s*(?:no\.?|number)|plot\s*id)"
            r"\s*[:\-]\s*"
            r"([A-Za-z0-9./\-]{1,40})"
        ),

        (
            r"(?:प्लॉट|भूखंड)"
            r"\s*(?:क्रमांक|नंबर|संख्या|क्र\.?)?"
            r"\s*[:\-]?\s*"
            r"([A-Za-z0-9./\-]{1,40})"
        ),
    ],

    "survey_number": [

        (
            r"(?:survey\s*(?:no\.?|number)|"
            r"s\.?\s*no\.?)"
            r"\s*[:\-]\s*"
            r"([A-Za-z0-9./\-]{1,40})"
        ),

        (
            r"(?:khasra\s*(?:no\.?|number))"
            r"\s*[:\-]?\s*"
            r"([A-Za-z0-9./\-]{1,40})"
        ),

        (
            r"(?:खसरा)"
            r"\s*(?:क्रमांक|नंबर|संख्या|क्र\.?)?"
            r"\s*[:\-]?\s*"
            r"([A-Za-z0-9./\-]{1,40})"
        ),

        (
            r"(?:सर्वे)"
            r"\s*(?:क्रमांक|नंबर|संख्या|क्र\.?)?"
            r"\s*[:\-]?\s*"
            r"([A-Za-z0-9./\-]{1,40})"
        ),
    ],

    "address": [

        (
            r"address\s*[:\-]\s*"
            r"([A-Za-z0-9 ,./\-\n]{5,200})"
        ),

        (
            r"(?:property|site)\s*address"
            r"\s*[:\-]\s*"
            r"([A-Za-z0-9 ,./\-\n]{5,200})"
        ),

        (
            r"(?:पता|स्थान)"
            r"\s*[:\-]\s*"
            r"([\u0900-\u097F0-9 ,./\-\n]{5,200})"
        ),
    ],

    "area": [

        (
            r"area\s*[:\-]?\s*"
            r"([\d,.]+)\s*"
            r"(sq\.?\s*ft|sqft|square\s*feet|"
            r"sq\.?\s*m|square\s*meter|"
            r"hectare|hectares|acre|acres)?"
        ),

        (
            r"(?:area|extent)"
            r"\s*[:\-]\s*"
            r"([\d,.]+)"
        ),

        (
            r"(?:क्षेत्रफल|रकबा)"
            r"\s*[:\-]?\s*"
            r"([\d,.]+)"
        ),
    ],

    "registration_date": [

        (
            r"(?:registration\s*date|"
            r"date\s*of\s*registration|"
            r"reg\.?\s*date)"
            r"\s*[:\-]\s*"
            r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})"
        ),

        (
            r"(?:registration\s*date|"
            r"date\s*of\s*registration)"
            r"\s*[:\-]\s*"
            r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})"
        ),

        (
            r"(?:पंजीकरण\s*दिनांक|"
            r"पंजीयन\s*दिनांक)"
            r"\s*[:\-]\s*"
            r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})"
        ),
    ],

    "notification_date": [

        (
            r"(?:notification\s*date|"
            r"date\s*of\s*notification)"
            r"\s*[:\-]\s*"
            r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})"
        ),

        (
            r"(?:अधिसूचना\s*दिनांक|"
            r"अधिसूचना\s*तिथि)"
            r"\s*[:\-]\s*"
            r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})"
        ),
    ],
}


# ============================================================
# FIELD EXTRACTION
# ============================================================

def extract_field(
    field: str,
    text: str,
) -> Optional[str]:

    for pattern in PATTERNS.get(
        field,
        [],
    ):

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:

            value = match.group(1)

            value = " ".join(
                value.strip().split()
            )

            return value

    return None


def parse_date(
    value: Optional[str],
):

    if not value:
        return None

    try:
        return (
            dateparser.parse(
                value,
                dayfirst=True,
            )
            .date()
            .isoformat()
        )

    except Exception:
        return None


def parse_number(
    value: Optional[str],
):

    if not value:
        return None

    try:

        cleaned = re.sub(
            r"[^0-9.]",
            "",
            value,
        )

        if not cleaned:
            return None

        return float(cleaned)

    except Exception:
        return None


def parse_fields(
    text: str,
):

    owner_name = extract_field(
        "owner_name",
        text,
    )

    plot_number = extract_field(
        "plot_number",
        text,
    )

    survey_number = extract_field(
        "survey_number",
        text,
    )

    address = extract_field(
        "address",
        text,
    )

    area_value = extract_field(
        "area",
        text,
    )

    registration_date_value = (
        extract_field(
            "registration_date",
            text,
        )
    )

    notification_date_value = (
        extract_field(
            "notification_date",
            text,
        )
    )

    return {
        "owner_name": owner_name,
        "plot_number": plot_number,
        "survey_number": survey_number,
        "address": address,
        "area_sqft": parse_number(
            area_value
        ),
        "registration_date": parse_date(
            registration_date_value
        ),
        "notification_date": parse_date(
            notification_date_value
        ),
    }


# ============================================================
# LAND FIELD VALIDATION
# ============================================================

def validate_land_fields(
    fields,
    document_detection,
):
    """
    Do not reject a genuine land document simply because
    OCR missed one field.
    """

    property_identifiers = [
        fields.get("plot_number"),
        fields.get("survey_number"),
    ]

    descriptive_fields = [
        fields.get("owner_name"),
        fields.get("address"),
        fields.get("area_sqft"),
        fields.get("registration_date"),
        fields.get("notification_date"),
    ]

    identifier_count = sum(
        bool(value)
        for value in property_identifiers
    )

    descriptive_count = sum(
        bool(value)
        for value in descriptive_fields
    )

    acquisition_hits = len(
        document_detection.get(
            "acquisition_keyword_hits",
            [],
        )
    )

    land_hits = (
        len(
            document_detection.get(
                "land_keyword_hits",
                [],
            )
        )
        +
        len(
            document_detection.get(
                "hindi_land_keyword_hits",
                [],
            )
        )
    )

    if (
        identifier_count >= 1
        and descriptive_count >= 1
    ):
        return (
            True,
            "Required property fields extracted.",
        )

    if descriptive_count >= 3:
        return (
            True,
            "Multiple property fields extracted.",
        )

    if acquisition_hits >= 1 and (
        land_hits >= 1
        or descriptive_count >= 1
    ):
        return (
            True,
            "Land acquisition document detected; "
            "some fields may require manual review.",
        )

    if land_hits >= 3:
        return (
            True,
            "Land/property document detected; "
            "some fields could not be extracted.",
        )

    return (
        False,
        (
            "The document may be related to property, "
            "but insufficient registry fields were "
            "extracted automatically."
        ),
    )


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(
    fields,
    extraction_confidence,
    document_detection,
):

    core_fields = [
        "owner_name",
        "plot_number",
        "survey_number",
        "address",
    ]

    additional_fields = [
        "area_sqft",
        "registration_date",
        "notification_date",
    ]

    core_score = (
        sum(
            bool(fields.get(field))
            for field in core_fields
        )
        / len(core_fields)
    )

    additional_score = (
        sum(
            bool(fields.get(field))
            for field in additional_fields
        )
        / len(additional_fields)
    )

    land_hits = (
        len(
            document_detection.get(
                "land_keyword_hits",
                [],
            )
        )
        +
        len(
            document_detection.get(
                "hindi_land_keyword_hits",
                [],
            )
        )
    )

    acquisition_hits = len(
        document_detection.get(
            "acquisition_keyword_hits",
            [],
        )
    )

    completeness = (
        0.70 * core_score
        + 0.30 * additional_score
    )

    keyword_score = min(
        1.0,
        (
            land_hits * 0.12
            + acquisition_hits * 0.20
        ),
    )

    score = (
        0.50 * completeness
        + 0.30 * extraction_confidence
        + 0.20 * keyword_score
    )

    return round(
        min(
            1.0,
            max(
                0.0,
                score,
            ),
        ),
        3,
    )


# ============================================================
# SIMILARITY
# ============================================================

def similarity(
    a,
    b,
):

    if not a or not b:
        return 0

    return (
        fuzz.token_sort_ratio(
            str(a),
            str(b),
        )
        / 100
    )


# ============================================================
# DUPLICATE MATCHING
# ============================================================

def find_matches(
    new_record,
    records,
):

    matches = []

    for record in records:

        plot = similarity(
            new_record.get(
                "plot_number"
            ),
            record.get(
                "plot_number"
            ),
        )

        survey = similarity(
            new_record.get(
                "survey_number"
            ),
            record.get(
                "survey_number"
            ),
        )

        owner = similarity(
            new_record.get(
                "owner_name"
            ),
            record.get(
                "owner_name"
            ),
        )

        address = similarity(
            new_record.get(
                "address"
            ),
            record.get(
                "address"
            ),
        )

        identifier_score = max(
            plot,
            survey,
        )

        if identifier_score > 0:

            score = (
                0.60 * identifier_score
                + 0.25 * owner
                + 0.15 * address
            )

        else:

            score = 0

        score = round(
            score,
            3,
        )

        if score >= 0.70:

            matches.append(
                {
                    "plot_number": record.get(
                        "plot_number"
                    ),
                    "survey_number": record.get(
                        "survey_number"
                    ),
                    "owner_name": record.get(
                        "owner_name"
                    ),
                    "similarity_score": score,
                    "record_id": record.get(
                        "record_id"
                    ),
                }
            )

    matches.sort(
        key=lambda item: item[
            "similarity_score"
        ],
        reverse=True,
    )

    return matches


# ============================================================
# EXACT DUPLICATE CHECK
# ============================================================

def is_exact_duplicate(
    fields,
    records,
):

    incoming_plot = fields.get(
        "plot_number"
    )

    incoming_survey = fields.get(
        "survey_number"
    )

    incoming_owner = fields.get(
        "owner_name"
    )

    for record in records:

        record_plot = record.get(
            "plot_number"
        )

        record_survey = record.get(
            "survey_number"
        )

        record_owner = record.get(
            "owner_name"
        )

        if (
            incoming_plot
            and record_plot
            and incoming_plot.strip().lower()
            == record_plot.strip().lower()
        ):
            return True

        if (
            incoming_survey
            and record_survey
            and incoming_survey.strip().lower()
            == record_survey.strip().lower()
        ):
            return True

        if (
            not incoming_plot
            and not incoming_survey
            and not record_plot
            and not record_survey
            and incoming_owner
            and record_owner
            and similarity(
                incoming_owner,
                record_owner,
            ) >= 0.98
        ):
            return True

    return False


# ============================================================
# RESPONSE HELPERS
# ============================================================

def empty_record():

    return {
        "owner_name": None,
        "plot_number": None,
        "survey_number": None,
        "address": None,
        "area_sqft": None,
        "registration_date": None,
        "notification_date": None,
        "confidence_score": 0,
    }


def analysis_response(
    detection,
    extraction_method,
    ocr_language,
):

    return {
        "land_keyword_hits": detection.get(
            "land_keyword_hits",
            [],
        ),
        "hindi_land_keyword_hits": detection.get(
            "hindi_land_keyword_hits",
            [],
        ),
        "acquisition_keyword_hits": detection.get(
            "acquisition_keyword_hits",
            [],
        ),
        "non_land_keyword_hits": detection.get(
            "non_land_keyword_hits",
            [],
        ),
        "extraction_method": extraction_method,
        "ocr_language": ocr_language,
    }
def register_on_blockchain(owner_name, plot_number, doc_bytes, ipfs_hash="ipfs://not-uploaded"):
    """
    Calls the blockchain wrapper service to register this record on-chain.
    Returns the wrapper's response dict, or None if it fails
    (verification should still succeed locally even if this fails).
    """
    doc_hash = hashlib.sha256(doc_bytes).hexdigest()

    try:
        response = requests.post(
            f"{BLOCKCHAIN_SERVICE_URL}/register",
            json={
                "owner_name": owner_name,
                "plot_number": plot_number,
                "doc_hash": doc_hash,
                "ipfs_hash": ipfs_hash,
            },
            timeout=10,
        )
        return response.json()
    except Exception as exc:
        print(f"Blockchain registration failed: {exc}")
        return None

# ============================================================
# VERIFY DOCUMENT
# ============================================================

@app.post("/api/verify")
async def verify(
    file: UploadFile = File(...),
):

    # --------------------------------------------------------
    # READ UPLOAD
    # --------------------------------------------------------

    data = await file.read()

    if not data:

        raise HTTPException(
            status_code=400,
            detail="Uploaded document is empty.",
        )

    filename = (
        file.filename
        or "uploaded_document"
    )


    # --------------------------------------------------------
    # DOCUMENT HASH
    # --------------------------------------------------------

    # Hash the ORIGINAL uploaded file.
    #
    # This hash is sent to the blockchain as bytes32.

    doc_hash = calculate_document_hash(
        data
    )


    # --------------------------------------------------------
    # NORMALIZE FILE
    # --------------------------------------------------------

    pdf = normalize_pdf(
        data,
        filename,
    )


    # --------------------------------------------------------
    # EXTRACT TEXT
    # --------------------------------------------------------

    try:

        (
            text,
            extraction_confidence,
            extraction_method,
            ocr_language,
        ) = extract_document_text(
            pdf
        )

    except Exception as exc:

        raise HTTPException(
            status_code=422,
            detail=(
                f"Could not read document: {exc}"
            ),
        )

    text = normalize_text(
        text
    )


    # --------------------------------------------------------
    # NO TEXT
    # --------------------------------------------------------

    if not text:

        return {
            "verified": False,
            "status": "Rejected",
            "reason": (
                "No readable text could be extracted "
                "from the uploaded document."
            ),
            "document_type": "Unreadable document",
            "record": empty_record(),
            "duplicate_flag": False,
            "duplicate_matches": [],
            "ledger": {
                "written": False,
                "record_id": None,
            },
            "blockchain": {
                "registered": False,
                "status": "not_registered",
                "tx_hash": None,
                "block_number": None,
            },
            "document_hash": doc_hash,
            "document_analysis": analysis_response(
                {},
                extraction_method,
                ocr_language,
            ),
        }


    # --------------------------------------------------------
    # DOCUMENT TYPE
    # --------------------------------------------------------

    document_detection = (
        detect_document_type(
            text
        )
    )


    # --------------------------------------------------------
    # REJECT ONLY CLEAR NON-LAND DOCUMENTS
    # --------------------------------------------------------

    if not document_detection[
        "is_land_document"
    ]:

        return {
            "verified": False,
            "status": "Rejected",
            "reason": document_detection[
                "reason"
            ],
            "document_type": document_detection[
                "document_type"
            ],
            "record": empty_record(),
            "duplicate_flag": False,
            "duplicate_matches": [],
            "ledger": {
                "written": False,
                "record_id": None,
                
            },
            "blockchain": {
                "registered": False,
                "status": "not_registered",
                "tx_hash": None,
                "block_number": None,
            },
            "document_hash": doc_hash,
            "document_analysis": analysis_response(
                document_detection,
                extraction_method,
                ocr_language,
            ),
        }


    # --------------------------------------------------------
    # PARSE FIELDS
    # --------------------------------------------------------

    fields = parse_fields(
        text
    )


    # --------------------------------------------------------
    # FIELD VALIDATION
    # --------------------------------------------------------

    fields_valid, fields_reason = (
        validate_land_fields(
            fields,
            document_detection,
        )
    )


    # --------------------------------------------------------
    # LAND DOCUMENT BUT POOR EXTRACTION
    # --------------------------------------------------------

    if not fields_valid:

        return {
            "verified": False,
            "status": "Needs Review",
            "reason": fields_reason,
            "document_type": document_detection[
                "document_type"
            ],
            "record": {
                **fields,
                "confidence_score": 0,
            },
            "duplicate_flag": False,
            "duplicate_matches": [],
            "ledger": {
                "written": False,
                "record_id": None,
            },
            "blockchain": {
                "registered": False,
                "status": "not_registered",
                "tx_hash": None,
                "block_number": None,
            },
            "document_hash": doc_hash,
            "document_analysis": analysis_response(
                document_detection,
                extraction_method,
                ocr_language,
            ),
        }


    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    score = calculate_confidence(
        fields,
        extraction_confidence,
        document_detection,
    )


    # --------------------------------------------------------
    # LOAD LEDGER
    # --------------------------------------------------------

    records = load_records()


    # --------------------------------------------------------
    # DUPLICATE CHECK
    # --------------------------------------------------------

    exact_duplicate = (
        is_exact_duplicate(
            fields,
            records,
        )
    )

    matches = find_matches(
        fields,
        records,
    )


    # --------------------------------------------------------
    # ACQUISITION DOCUMENTS
    # --------------------------------------------------------

    is_acquisition_document = bool(
        document_detection.get(
            "acquisition_keyword_hits"
        )
    )


    # --------------------------------------------------------
    # MINIMUM CONFIDENCE
    # --------------------------------------------------------

    if is_acquisition_document:
        minimum_confidence = 0.30
    else:
        minimum_confidence = 0.40


    if score < minimum_confidence:
        return {
            "verified": False,
            "status": "Needs Review",
            "reason": (
                "The document appears to be a "
                "land/property document, but OCR "
                "or field extraction confidence is "
                "too low for automatic verification."
            ),
            "document_type": document_detection[
                "document_type"
            ],
            "record": {
                **fields,
                "confidence_score": score,
            },
            "duplicate_flag": exact_duplicate,
            "duplicate_matches": matches,
            "ledger": {
                "written": False,
                "record_id": None,
            },
            "blockchain": {
                "registered": False,
                "status": "not_registered",
                "tx_hash": None,
                "block_number": None,
            },
            "document_hash": doc_hash,
            "document_analysis": analysis_response(
                document_detection,
                extraction_method,
                ocr_language,
            ),
        }


    # --------------------------------------------------------
    # DUPLICATE / CONFLICT
    # --------------------------------------------------------

    if exact_duplicate or matches:

        return {
            "verified": False,
            "status": "Conflict",
            "reason": (
                "A matching registry record "
                "already exists."
            ),
            "document_type": document_detection[
                "document_type"
            ],
            "record": {
                **fields,
                "confidence_score": score,
            },
            "duplicate_flag": exact_duplicate,
            "duplicate_matches": matches,
            "ledger": {
                "written": False,
                "record_id": None,
            },
            "blockchain": {
                "registered": False,
                "status": "not_registered",
                "tx_hash": None,
                "block_number": None,
            },
            "document_hash": doc_hash,
            "document_analysis": analysis_response(
                document_detection,
                extraction_method,
                ocr_language,
            ),
        }


    # ========================================================
    # BLOCKCHAIN REGISTRATION
    # ========================================================

    # The document has passed your verification pipeline.
    #
    # Now send the verified ownership record to the
    # Blockchain wrapper.
    #
    # IPFS is not implemented in this application yet,
    # therefore ipfs_hash is currently empty.

    blockchain_result = await register_on_blockchain(
        owner_name=fields.get(
            "owner_name"
        ),
        plot_number=fields.get(
            "plot_number"
        ),
        doc_hash=doc_hash,
        ipfs_hash="",
    )


    # --------------------------------------------------------
    # BLOCKCHAIN DUPLICATE
    # --------------------------------------------------------

    # Your local JSON ledger may not know about a record that
    # already exists on-chain.
    #
    # If the blockchain wrapper says the plot already exists,
    # do NOT create a second local Verified record.

    if blockchain_result.get(
        "status"
    ) == "conflict":

        return {
            "verified": False,
            "status": "Conflict",
            "reason": (
                "This plot is already registered "
                "on the blockchain."
            ),
            "document_type": document_detection[
                "document_type"
            ],
            "record": {
                **fields,
                "confidence_score": score,
            },
            "duplicate_flag": True,
            "duplicate_matches": matches,
            "ledger": {
                "written": False,
                "record_id": None,
            },
            "blockchain": blockchain_result,
            "document_hash": doc_hash,
            "document_analysis": analysis_response(
                document_detection,
                extraction_method,
                ocr_language,
            ),
        }


    # --------------------------------------------------------
    # CREATE LOCAL RECORD
    # --------------------------------------------------------

    record_id = str(
        uuid.uuid4()
    )

    record = {
        "record_id": record_id,
        **fields,
        "document_type": document_detection[
            "document_type"
        ],
        "confidence_score": score,
        "status": "Verified",
        "verified_at": datetime.now(
            timezone.utc
        ).isoformat(),

        # Original document hash.
        "document_hash": doc_hash,

        # Blockchain information.
        "blockchain": blockchain_result,
    }

    records.append(
        record
    )

    save_records(
        records
    )
    blockchain_result = register_on_blockchain(
        owner_name=fields.get("owner_name"),
        plot_number=fields.get("plot_number"),
        doc_bytes=data,
    )


    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    return {
        "verified": True,
        "status": "Verified",
        "reason": (
            "Land/property document successfully "
            "verified and written to the local ledger."
        ),
        "document_type": document_detection[
            "document_type"
        ],
        "record": {
            **fields,
            "confidence_score": score,
        },
        "duplicate_flag": False,
        "duplicate_matches": [],
        "ledger": {
            "written": True,
            "record_id": record_id,
            "blockchain": blockchain_result,
        },

        # Blockchain result.
        #
        # Example:
        #
        # {
        #     "registered": true,
        #     "status": "pending",
        #     "tx_hash": "0x...",
        #     "block_number": null
        # }
        #
        "blockchain": blockchain_result,

        # Useful for later verification.
        "document_hash": doc_hash,

        "document_analysis": analysis_response(
            document_detection,
            extraction_method,
            ocr_language,
        ),
    }


# ============================================================
# RECENT LEDGER
# ============================================================

@app.get("/api/ledger/recent")
def recent_ledger(
    limit: int = Query(
        10,
        ge=1,
        le=100,
    ),
):

    records = load_records()

    return {
        "records": list(
            reversed(
                records[-limit:]
            )
        ),
        "count": len(records),
    }



# ============================================================
# SEARCH
# ============================================================

@app.get("/api/search")
def search(
    q: str = Query(
        ...,
        min_length=1,
    ),
):

    query = q.lower().strip()

    records = load_records()

    results = []

    for record in records:

        values = [
            record.get(
                "owner_name"
            ),
            record.get(
                "plot_number"
            ),
            record.get(
                "survey_number"
            ),
            record.get(
                "address"
            ),
        ]

        if any(
            query in str(value).lower()
            for value in values
            if value
        ):
            results.append(
                record
            )

    return {
        "query": q,
        "results": results,
        "count": len(results),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():

    try:

        version = str(
            pytesseract.get_tesseract_version()
        )

        tesseract_available = True

    except Exception:

        version = None
        tesseract_available = False

    languages = (
        sorted(
            get_available_ocr_languages()
        )
        if tesseract_available
        else []
    )

    return {
        "status": "ok",
        "tesseract_available": (
            tesseract_available
        ),
        "tesseract_version": version,
        "ocr_languages": languages,
        "hindi_ocr_available": (
            "hin" in languages
        ),
        "records_stored": len(
            load_records()
        ),

        # Useful for debugging the integration.
        "blockchain_service_url": (
            BLOCKCHAIN_SERVICE_URL
        ),
    }


# ============================================================
# BLOCKCHAIN HEALTH
# ============================================================

@app.get("/api/blockchain/health")
async def blockchain_health():
    """
    Check whether the Python service can reach
    the Blockchain wrapper.
    """

    try:

        async with httpx.AsyncClient(
            timeout=5.0
        ) as client:

            response = await client.get(
                f"{BLOCKCHAIN_SERVICE_URL}/health"
            )

        try:
            wrapper_response = response.json()
        except Exception:
            wrapper_response = {}

        return {
            "status": (
                "ok"
                if response.status_code < 400
                else "error"
            ),
            "blockchain_service_url": (
                BLOCKCHAIN_SERVICE_URL
            ),
            "wrapper_status_code": (
                response.status_code
            ),
            "wrapper": wrapper_response,
        }

    except Exception as exc:

        return {
            "status": "unavailable",
            "blockchain_service_url": (
                BLOCKCHAIN_SERVICE_URL
            ),
            "error": str(exc),
        }


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "name": "Adhikar",
        "version": "0.3.0",
        "status": "running",
        "service": "Digital Land Registry",
        "blockchain_service": (
            BLOCKCHAIN_SERVICE_URL
        ),
    }


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    import os
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=True,
    )
