scaffold_controller_template = """from metro import Controller, get, post, put, delete, Request, NotFoundError
from pydantic import BaseModel

from app.models.{resource_name_snake} import {resource_name_pascal}


class {resource_name_pascal}Create(BaseModel):
{pydantic_fields}

class {resource_name_pascal}Update(BaseModel):
{pydantic_fields}

class {resource_name_plural_pascal}Controller(Controller):
    @get('/{resource_name_plural_kebab}')
    async def index(self, request: Request):
        items = {resource_name_pascal}.find()
        return [item.to_dict() for item in items]

    @get('/{resource_name_plural_kebab}/{{id}}')
    async def show(self, request: Request, id: str):
        item = {resource_name_pascal}.find_by_id(id=id)
        if item:
            return item.to_dict()
        raise NotFoundError('{resource_name_pascal} not found')

    @post('/{resource_name_plural_kebab}')
    async def create(self, request: Request, data: {resource_name_pascal}Create):
        item = {resource_name_pascal}(**data.dict()).save()
        return item.to_dict()

    @put('/{resource_name_plural_kebab}/{{id}}')
    async def update(self, request: Request, id: str, data: {resource_name_pascal}Update):
        item = {resource_name_pascal}.find_by_id_and_update(id=id, **data.dict(exclude_unset=True))
        if item:
            return item.to_dict()
        raise NotFoundError('{resource_name_pascal} not found')

    @delete('/{resource_name_plural_kebab}/{{id}}')
    async def delete(self, request: Request, id: str):
        item = {resource_name_pascal}.find_by_id_and_delete(id=id)
        if item is None:
            raise NotFoundError('{resource_name_pascal} not found')
        return {{'detail': '{resource_name_pascal} deleted'}}
"""
