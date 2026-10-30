"""Lambda crear-sesion (Integrante A, HU-01).

POST /sesiones
  Entrada: {"courseId": "GC-101", "durationSeconds": 180}
  Salida : 200 {"sessionId", "expiresAt", "scanUrl", "qrSvg"}

El QR se genera aqui mismo con segno (Python puro), sin servicios externos.
"""
import base64
import io
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

import segno

TABLE_NAME = os.environ.get("TABLE_NAME", "")
SCAN_BASE_URL = os.environ.get("SCAN_BASE_URL", "")
DEFAULT_DURATION = int(os.environ.get("DEFAULT_DURATION", "180"))
MAX_DURATION = int(os.environ.get("MAX_DURATION", "900"))
MIN_DURATION = int(os.environ.get("MIN_DURATION", "30"))
# Colombia no tiene horario de verano: un desfase fijo evita depender de tzdata.
TZ_OFFSET_HOURS = int(os.environ.get("TZ_OFFSET_HOURS", "-5"))

COURSE_RE = re.compile(r"^[A-Za-z0-9_-]{2,20}$")
TEACHER_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,60}$")

_table = None


def _get_table():
    """Crea el cliente de DynamoDB solo cuando hace falta (facilita las pruebas)."""
    global _table
    if _table is None:
        import boto3

        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body),
    }


def _parse_body(event):
    raw = event.get("body")
    if raw is None or raw == "":
        return {}
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON")
    return data


def _validate(data):
    """Devuelve (courseId, duration, teacherId) o lanza ValueError con el motivo."""
    course_id = data.get("courseId")
    if not isinstance(course_id, str) or not COURSE_RE.match(course_id):
        raise ValueError(
            "courseId es obligatorio (2 a 20 caracteres: letras, numeros, - o _)"
        )

    duration = data.get("durationSeconds", DEFAULT_DURATION)
    # bool es subclase de int en Python: se rechaza de forma explicita.
    if isinstance(duration, bool) or not isinstance(duration, int):
        raise ValueError("durationSeconds debe ser un entero")
    if not MIN_DURATION <= duration <= MAX_DURATION:
        raise ValueError(
            f"durationSeconds debe estar entre {MIN_DURATION} y {MAX_DURATION}"
        )

    teacher_id = data.get("teacherId")
    if teacher_id is not None and (
        not isinstance(teacher_id, str) or not TEACHER_RE.match(teacher_id)
    ):
        raise ValueError("teacherId no es valido")

    return course_id, duration, teacher_id


def _build_scan_url(session_id):
    sep = "&" if "?" in SCAN_BASE_URL else "?"
    return f"{SCAN_BASE_URL}{sep}s={session_id}"


def _make_qr_svg(text):
    qr = segno.make(text, error="m")
    buffer = io.BytesIO()
    # omitsize: el SVG se escala con CSS desde la pagina del docente.
    qr.save(buffer, kind="svg", xmldecl=False, border=2, scale=8, omitsize=True, nl=False)
    return buffer.getvalue().decode("utf-8")


def lambda_handler(event, context):
    try:
        data = _parse_body(event)
        course_id, duration, teacher_id = _validate(data)
    except (ValueError, UnicodeDecodeError) as exc:  # JSONDecodeError es ValueError
        return _response(400, {"error": str(exc)})

    if not TABLE_NAME or not SCAN_BASE_URL:
        print("ERROR de configuracion: faltan TABLE_NAME o SCAN_BASE_URL")
        return _response(500, {"error": "Error interno de configuracion"})

    now = int(time.time())
    expires_at = now + duration
    local_date = (
        datetime.fromtimestamp(now, timezone(timedelta(hours=TZ_OFFSET_HOURS)))
        .strftime("%Y-%m-%d")
    )
    session_id = secrets.token_urlsafe(16)

    item = {
        "sessionId": session_id,
        "courseId": course_id,
        "date": local_date,
        "createdAt": now,
        "expiresAt": expires_at,
    }
    if teacher_id:
        item["teacherId"] = teacher_id

    try:
        _get_table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(sessionId)",
        )
    except Exception as exc:  # noqa: BLE001 - no se registra el token por seguridad
        print(f"ERROR al guardar la sesion: {type(exc).__name__}")
        return _response(500, {"error": "No se pudo crear la sesion"})

    scan_url = _build_scan_url(session_id)
    return _response(
        200,
        {
            "sessionId": session_id,
            "expiresAt": expires_at,
            "scanUrl": scan_url,
            "qrSvg": _make_qr_svg(scan_url),
        },
    )
