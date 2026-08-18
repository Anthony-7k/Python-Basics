from fastapi import (
    APIRouter,
    Depends,
    status,
)

from app.api.dependencies import (
    get_knowledge_base_service,
)
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
)
from app.services.knowledge_bases import (
    KnowledgeBaseService,
)


router = APIRouter(
    prefix="/api/v1/knowledge-bases",
    tags=["knowledge-bases"],
)


@router.post(
    "",
    response_model=KnowledgeBaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_knowledge_base(
    request: KnowledgeBaseCreate,
    service: KnowledgeBaseService = Depends(
        get_knowledge_base_service
    ),
):
    return service.create(
        name=request.name,
        description=request.description,
    )


@router.get(
    "",
    response_model=KnowledgeBaseListResponse,
)
def list_knowledge_bases(
    service: KnowledgeBaseService = Depends(
        get_knowledge_base_service
    ),
):
    return KnowledgeBaseListResponse(
        items=service.list()
    )


@router.get(
    "/{knowledge_base_id}",
    response_model=KnowledgeBaseResponse,
)
def get_knowledge_base(
    knowledge_base_id: str,
    service: KnowledgeBaseService = Depends(
        get_knowledge_base_service
    ),
):
    return service.get(knowledge_base_id)
