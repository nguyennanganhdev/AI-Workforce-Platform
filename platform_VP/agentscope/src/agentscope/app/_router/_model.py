# -*- coding: utf-8 -*-
"""The model router."""

from fastapi import APIRouter, Depends, HTTPException, status

from ._schema import ListModelsResponse, ListModelsRequest
from ...credential import CredentialFactory
from ...model import OpenRouterChatModel

model_router = APIRouter(
    prefix="/model",
    tags=["model"],
    responses={404: {"description": "Not found"}},
)


@model_router.get(
    "/",
    response_model=ListModelsResponse,
    summary="List all candidate models under the given credential type",
)
async def list_models(
    body: ListModelsRequest = Depends(),
) -> ListModelsResponse:
    """Return all candidate models under the given credential type.

    Args:
        body (ListModelsRequest): The request body.

    Returns:
        `ListModelsResponse`: The response body.
    """
    credential_cls = CredentialFactory.get_credential_class(body.provider)
    if credential_cls is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{body.provider}' not found.",
        )

    try:
        model_cls = credential_cls.get_chat_model_class()
        if issubclass(model_cls, OpenRouterChatModel):
            await model_cls.refresh_models()
        models = model_cls.list_models()
    except NotImplementedError:
        models = []
    return ListModelsResponse(models=models, total=len(models))
