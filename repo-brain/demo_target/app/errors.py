from fastapi import HTTPException


def api_error(status: int, code: str, message: str) -> HTTPException:
    """House convention: all error responses use the {'error': {code, message}} envelope."""
    return HTTPException(status_code=status, detail={"error": {"code": code, "message": message}})
