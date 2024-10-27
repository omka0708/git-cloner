import asyncio
import os
from typing import Annotated

import aiohttp
import aioredis
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, RedirectResponse, HTMLResponse
from fastui import FastUI, AnyComponent, prebuilt_html, components as c
from fastui.events import PageEvent, GoToEvent
from fastui.forms import fastui_form
from pydantic import BaseModel

app = FastAPI()


@app.get("/api/", response_model=FastUI, response_model_exclude_none=True)
def main() -> list[AnyComponent]:
    return [
        c.Page(
            components=[
                c.Heading(text='git-cloner', level=1),
                c.Heading(text='Cloned repositories', level=3),
                c.Div(
                    components=[
                        c.Div(
                            components=[
                                c.ServerLoad(
                                    path='/get-repos',
                                    sse=True,
                                )
                            ],
                            class_name='my-2 p-2 border rounded',
                        ),
                    ],
                    class_name='border-top mt-3 pt-1',
                ),
                c.Div(
                    components=[
                        c.Heading(text='Parse & clone repositories', level=3),
                        c.Button(text='Parse & clone', on_click=PageEvent(name='parse-repos-open')),
                        c.Modal(
                            title='GitHub username',
                            body=[
                                c.Form(
                                    form_fields=[
                                        c.FormFieldInput(name='name', title='GitHub username', required=True),
                                    ],
                                    submit_url='/api/parse-repos',
                                    footer=[],
                                    submit_trigger=PageEvent(name='parse-repos'),
                                ),
                            ],
                            footer=[
                                c.Button(
                                    text='Cancel', named_style='secondary',
                                    on_click=PageEvent(name='parse-repos-open', clear=True)
                                ),
                                c.Button(text='Submit', on_click=PageEvent(name='parse-repos')),
                            ],
                            open_trigger=PageEvent(name='parse-repos-open'),
                        ),
                    ],
                    class_name='border-top mt-3 pt-1',
                ),
            ],
        ),
    ]


# get my repos

async def get_repos_generator():
    r = aioredis.Redis(host='git-cloner-redis', port=6379, db=0, decode_responses=True)
    while True:
        repos = os.listdir("repos")
        if not repos:
            result = "There is no cloned repositories //"
        else:
            result = ""
            for repo in repos:
                if await r.get(f'repo:{repo}') != 'cloning':
                    await r.set(f'repo:{repo}', value='cloned', ex=3)

        response = await r.scan(match='repo:*')
        repo_keys = response[1]
        for key in repo_keys:
            status = await r.get(key)
            repo_name = key.split(':')[1]
            if status == 'cloned':
                result += f"{repo_name} - cloned ✅ // "
            elif status == 'cloning':
                result += f"{repo_name} - cloning ⌛ // "

        m = FastUI(root=[c.Markdown(text=f'// {result}')])
        await asyncio.sleep(1)
        yield f'data: {m.model_dump_json(by_alias=True, exclude_none=True)}\n\n'


@app.get("/api/get-repos")
async def get_repos_stream() -> StreamingResponse:
    return StreamingResponse(get_repos_generator(), media_type='text/event-stream')


# parse repos

class UserNameForm(BaseModel):
    name: str


@app.post('/api/parse-repos', response_model=FastUI, response_model_exclude_none=True)
async def parse_repos(form: Annotated[UserNameForm, fastui_form(UserNameForm)]) -> list[AnyComponent]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://api.github.com/users/{form.name}/repos') as resp:
            repos_data = await resp.json()
            if resp.status == 404:
                return [
                    c.Markdown(
                        text=f"Нет такого пользователя GitHub"
                    ),
                ]

    result = [
        c.Markdown(
            text=f"{form.name}'s repos:"
        ),
    ]
    for repo in repos_data:
        result += [
            c.Div(
                components=[
                    c.Markdown(
                        text=f"{repo['name']} - {repo['stargazers_count']} ⭐"
                    ),
                    c.Button(text=f"Clone {repo['name']}", on_click=GoToEvent(url=f"/clone/{repo['full_name']}", target='_blank')),
                ],
                class_name='border-top mt-3 pt-1'
            )
        ]

    return [
        *result
    ]


@app.get('/clone/{author}/{repo}')
async def clone(author: str, repo: str):
    r = aioredis.Redis(host='git-cloner-redis', port=6379, db=0, decode_responses=True)
    await r.set(f'repo:{repo}', value='cloning')

    from tasks import generate_report_task
    generate_report_task.delay(author, repo)

    return RedirectResponse('/')


@app.get('/{path:path}')
async def html_landing():
    return HTMLResponse(prebuilt_html(title='FastUI Demo'))
