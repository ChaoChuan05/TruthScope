from pydantic import BaseModel, ConfigDict, Field


class GonkaContentBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    text: str | None = None
    name: str | None = None
    input: object | None = None


class GonkaResponseUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class GonkaMessageResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str | None = None
    model: str
    content: list[GonkaContentBlock]
    stop_reason: str | None = None
    usage: GonkaResponseUsage | None = None
