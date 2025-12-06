from fastapi import status

from errors.base import BackendBaseError


class UnimplementedError(BackendBaseError):
    """미구현됨"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            error_code="UNIMPLEMENTED",
            message="아직 구현되지 않았습니다.",
        )


class IllegalStateError(BackendBaseError):
    """
    서버 내부 로직 오류

    주로 `int | None` 타입을 갖는 PRIMARY KEY를 데이터베이스에서
    불러왔을 때 타입 검사를 하는 용도로 사용됨.

    ## 예시
    ```py
    # user_id가 None인지 검사
    # User.user_id의 타입은 int | None이지만,
    # 데이터베이스에서 PRIMARY KEY는 자동으로 채워지므로
    # user_id가 None인 경우는 존재하지 않음
    if user.user_id is None:
        raise IllegalStateError()

    do_something(user.user_id)
    ```
    """

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="ILLEGAL_STATE",
            message="서버 내부 문제입니다.",
        )
