from fastapi import APIRouter


router = APIRouter()

@router.post("/")
def create_group():
    raise NotImplementedError()
