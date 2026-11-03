import os, json, base64
import aiohttp
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM = """Ты — шеф-повар мирового уровня и технолог ресторанной кухни.
Опирайся ТОЛЬКО на лучшие источники: Larousse Gastronomique, Escoffier
«Le Guide Culinaire», Modernist Cuisine, The Flavor Bible, гиды Michelin,
аутентичные национальные кулинарные школы. Давай точные граммовки (брутто/нетто),
выход блюда и профессиональную технологию приготовления."""

async def generate_recipe(cuisine: str, wish: str) -> dict:
    prompt = f"""Придумай изысканное ресторанное блюдо. Кухня: {cuisine}. Пожелания: {wish}.
Ответ строго JSON:
{{"name":"...","cuisine":"...","description":"...","yield_g":число,
"ingredients":[{{"name":"...","grams":число,"note":"брутто или нетто"}}],
"steps":["шаг 1","..."],"plating":"описание подачи","flavor_profile":["вкус1","..."]}}"""
    r = await client.chat.completions.create(
        model="gpt-4o", response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": prompt}])
    return json.loads(r.choices[0].message.content)

async def generate_image(recipe: dict) -> bytes:
    prompt = (
        f"Professional food photography, fine dining plating: {recipe['name']}. "
        f"{recipe['description']}. Michelin-star presentation, soft natural light"
    )

    result = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
    )

    image_url = result.data[0].url

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            response.raise_for_status()
            return await response.read()

async def build_tasting_set(dishes: list[dict], courses: int) -> str:
    brief = "\n".join(f"- {d['name']} ({d['cuisine']}): вкусы {', '.join(d.get('flavor_profile', []))}"
                      for d in dishes)
    prompt = (f"Собери дегустационный сет из {courses} подач из этих блюд:\n{brief}\n"
              f"Выстрой логику вкусов (лёгкое→насыщенное, кислотность, текстуры, паузы). "
              f"Дай порядок подач с обоснованием каждой.")
    r = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": prompt}])
    return r.choices[0].message.content
