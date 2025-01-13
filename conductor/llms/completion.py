import json
import time
from openai import AsyncOpenAI, OpenAI
from openai.types.chat.chat_completion import (
    CompletionUsage,
    Choice,
    ChatCompletionMessage,
)
from openai.types.chat import ChatCompletionMessageToolCall, ChatCompletion
from openai.types.chat.chat_completion_message_tool_call_param import Function
from anthropic import AsyncAnthropic, Anthropic

from conductor.load_api_keys import load_api_keys


load_api_keys()


def openai_completion(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = None,
    tools: list[dict] = None,
    temperature: float = None,
):
    client = OpenAI()

    return client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        tools=tools,
        temperature=temperature,
    )


def anthropic_completion(
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = None,
    tools: list[dict] = None,
    temperature: float = None,
):
    client = Anthropic()

    if messages[-1]["role"] == "assistant":
        messages[-1]["content"] = messages[-1]["content"].rstrip()

    kwargs = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens or 4096,
    }
    if tools:
        kwargs["tools"] = tools
    if temperature:
        kwargs["temperature"] = temperature

    anthropic_response = client.messages.create(**kwargs)

    content_blocks = [c for c in anthropic_response.content if c.type != "tool_use"]
    content = None if len(content_blocks) == 0 else content_blocks[0].text

    finish_reason_map = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }

    return ChatCompletion(
        id=anthropic_response.id,
        model=anthropic_response.model,
        object="chat.completion",
        created=int(time.time()),
        choices=[
            Choice(
                finish_reason=finish_reason_map.get(anthropic_response.stop_reason)
                or "stop",
                index=0,
                logprobs=None,
                message=ChatCompletionMessage(
                    content=content,
                    role="assistant",
                    type="message",
                    tool_calls=[
                        ChatCompletionMessageToolCall(
                            id=tool.id,
                            function=Function(
                                arguments=json.dumps(tool.input),
                                name=tool.name,
                            ),
                        )
                        for tool in anthropic_response.content
                        if tool.type == "tool_use"
                    ]
                    or None,
                ),
            )
        ],
        usage=CompletionUsage(
            completion_tokens=anthropic_response.usage.output_tokens,
            prompt_tokens=anthropic_response.usage.input_tokens,
            total_tokens=anthropic_response.usage.input_tokens
            + anthropic_response.usage.output_tokens,
        ),
    )


def completion(
    model: str,
    messages: list[dict[str, str]],
    provider: str = None,
    max_tokens: int = None,
    tools: list[dict] = None,
    temperature: float = None,
):
    if not provider:
        provider = "anthropic" if "claude" in model else "openai"

    if provider == "anthropic":
        return anthropic_completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            tools=tools,
            temperature=temperature,
        )
    else:
        return openai_completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            tools=tools,
            temperature=temperature,
        )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv

    load_dotenv()

    async def main():
        completion_response = await completion(
            model="claude-3-5-haiku-20241022",
            # model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "What is the capital of France?"},
                {"role": "assistant", "content": "The capital of France is  "},
            ],
        )

        print(completion_response)
        print(completion_response.choices[0].message.content)

    asyncio.run(main())
