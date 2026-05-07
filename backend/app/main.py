from fastapi import FastAPI

app = FastAPI(
    title="AutoHire API",
    version="0.1.0",
    description="Foundation API shell. Business logic is intentionally not implemented.",
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
