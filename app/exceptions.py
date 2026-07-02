from fastapi import Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse


def create_error_response(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"message": message})


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return create_error_response(exc.detail, exc.status_code)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])
        msg = error["msg"]
        errors.append(f"{field}: {msg}")

    message = "; ".join(errors) if errors else "Validation error"
    return create_error_response(message, status.HTTP_422_UNPROCESSABLE_ENTITY)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return create_error_response(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)
