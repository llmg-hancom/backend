from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from errors.groups import (
    GroupNotExistError,
    InviteeIsAlreadyInGroupError,
    InviteeIsNotExistError,
)


def group_not_exist_error(_req: Request, _e: GroupNotExistError):
    return JSONResponse(status_code=404, content={"detail": "그룹이 존재하지 않습니다."})

def invitee_is_already_in_group_error(_req: Request, _e: InviteeIsAlreadyInGroupError):
    return JSONResponse(status_code=400, content={"detail": "초대하려는 유저는 이미 그룹에 있습니다."})

def invitee_is_not_exist_error(_req: Request, _e: InviteeIsNotExistError):
    return JSONResponse(status_code=400, content={"detail": "초대하려는 유저는 존재하지 않습니다."})

def group_exception_handler(app: FastAPI):
    app.add_exception_handler(GroupNotExistError, group_not_exist_error)
    app.add_exception_handler(InviteeIsAlreadyInGroupError, invitee_is_already_in_group_error)
    app.add_exception_handler(InviteeIsNotExistError, invitee_is_not_exist_error)
