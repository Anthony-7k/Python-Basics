import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.exceptions import (
    KnowledgeBaseNotFoundError,
)
from app.db.base import Base
from app.services.knowledge_bases import (
    KnowledgeBaseService,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(
        engine,
        expire_on_commit=False,
    ) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_create_list_and_get_knowledge_base(
    db_session: Session,
):
    service = KnowledgeBaseService(
        db_session
    )
    created = service.create(
        name=" HR Policies ",
        description=" Employee rules ",
    )

    assert created.name == "HR Policies"
    assert created.description == (
        "Employee rules"
    )
    assert created.version == 1
    assert [
        item.id
        for item in service.list()
    ] == [created.id]
    assert service.get(created.id).id == (
        created.id
    )


def test_get_missing_knowledge_base(
    db_session: Session,
):
    service = KnowledgeBaseService(
        db_session
    )
    with pytest.raises(
        KnowledgeBaseNotFoundError
    ):
        service.get("missing-kb")
