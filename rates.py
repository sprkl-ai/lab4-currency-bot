import asyncio
import sys

import httpx


async def get_rate(base, quote):
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://api.frankfurter.dev/v2/rate/" + base + "/" + quote
        )
        response.raise_for_status()
        data = response.json()
    return float(data["rate"]), data["date"]


if __name__ == "__main__":
    base, quote = sys.argv[1:3] or ("USD", "EUR")
    rate, date = asyncio.run(get_rate(base.upper(), quote.upper()))
    print(f"1 {base.upper()} = {rate:g} {quote.upper()} ({date})")
