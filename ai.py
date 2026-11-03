import os, json, base64
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM = """Ты — шеф-повар мирового уровня и технолог ресторанной кухни.
Опирайся ТОЛЬКО на лучшие источники: Larousse Gastronomique, Escoffier
«Le Guide Culinaire», Modernist Cuisine, The Flavor Bible, гиды Michelin,
аутентичные национальные кулинарные школы. Давай точные граммовки (брутто/нетто),
выход блюда и профессиональную технологию приготовления.
Пиши все ответы пользователю только на русском языке. Не используй английский
или французский в названиях блюд, ингредиентов, описаниях и шагах."""

async def generate_recipe(cuisine: str, wish: str) -> dict:
    prompt = f"""Придумай изысканное ресторанное блюдо. Кухня: {cuisine}. Пожелания: {wish}.
Все текстовые поля JSON, включая название блюда и названия ингредиентов, напиши только по-русски.
Не оставляй иностранные названия и термины: переведи их на русский.
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
        f"Профессиональная фуд-фотография ресторанного блюда: {recipe['name']}. "
        f"{recipe['description']}. Изысканная подача, мягкий естественный свет. "
        "На изображении не должно быть текста, букв, надписей, логотипов или водяных знаков."
    )

    result = await client.images.generate(
        model="gpt-image-2.5-flare",
        prompt=prompt,
        size="1024x1024",
        quality="medium",
    )

    return base64.b64decode(result.data[0].b64_json)

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
