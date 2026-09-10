"""Natural-language question endpoint.

Returns *the query string the question means*, not results. That indirection is
deliberate: the client applies the returned filters through the ordinary
filtered views, so a question and a manually-built filter produce the same URL,
the same requests and the same numbers. There is no separate "answered by AI"
code path whose results could disagree with the rest of the application.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.domain.nl_query import QueryVocabulary, parse_question
from app.repositories.filtering import filter_conditions
from app.repositories.reference import country_names
from app.schemas import ParsedQueryResponse, QuestionRequest

router = APIRouter(prefix="/query", tags=["query"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=ParsedQueryResponse)
def interpret_question(session: SessionDep, body: QuestionRequest) -> ParsedQueryResponse:
    vocabulary = QueryVocabulary.from_countries(country_names(session))

    try:
        parsed = parse_question(body.question, vocabulary)
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error

    # Proof, at the point of translation, that the parsed question is a valid
    # selection over known columns rather than anything the database has to
    # interpret. If this raised, the response would be a 500 rather than a bad
    # query reaching the data.
    filter_conditions(parsed.filters)

    return ParsedQueryResponse.of(parsed)
