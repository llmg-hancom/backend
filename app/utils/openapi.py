from errors.base import BackendBaseError


def generate_openapi_error_response(*errors: BackendBaseError):
    """
    백엔드 오류 목록을 파라미터로 전달하면 OpenAPI 문서 형식으로 반환합니다.

    # 사용 방법
    ```py
    @router.get(
        "/resource",
        responses={
            # 이 라우터에서 발생할 수 있는 오류 목록을 나열
            **generate_openapi_error_response(
                AuthError(),
                ResourceNotFoundError(),
                ResourceForbiddenError(),
            )
        }
    )
    ```
    """
    result = {}

    for error in errors:
        if error.status_code in result:
            result[error.status_code]["content"]["application/json"]["examples"][error.error_code] = error.openapi_docs()
        else:
            result[error.status_code] = {
                "content": {
                    "application/json": {
                        "examples": {
                            error.error_code: error.openapi_docs()
                        }
                    }
                }
            }

    return result
