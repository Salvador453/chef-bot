import os, json, base64
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM_CHEF = """Ты — шеф-повар мирового уровня, обладающий опытом работы в ресторанах высокой кухни. 
Опирайся на лучшие мировые гастрономические источники: гиды Michelin, Larousse Gastronomique[span_2](start_span)[span_2](end_span), Escoffier «Le Guide Culinaire»[span_3](start_span)[span_3](end_span), Modernist Cuisine[span_4](start_span)[span_4](end_span), The Flavor Bible[span_5](start_span)[span_5](end_span) и аутентичные национальные кулинарные школы[span_6](start_span)[span_6](end_span). 
Твоя задача — создавать изысканные концепции блюд, подбирать яркие вкусовые профили и авторскую подачу."""

SYSTEM_TECH = """Ты — строгий технолог ресторанной кухни и шеф-ревизор высокой кухни. 
Опирайся исключительно на авторитетные источники и стандарты: гиды Michelin, Larousse Gastronomique[span_7](start_span)[span_7](end_span), Escoffier «Le Guide Culinaire»[span_8](start_span)[span_8](end_span), Modernist Cuisine[span_9](start_span)[span_9](end_span), The Flavor Bible[span_10](start_span)[span_10](end_span) и технологические регламенты институтов вроде Le Cordon Bleu[span_11](start_span)[span_11](end_span). 
Проверяй граммовки (брутто/нетто), корректность КБЖУ на 100г, оборудование и пошаговую технологию. 
Исправляй любые кулинарные или технологические ошибки черновика.
Ответ ВСЕГОДА возвращай строго в формате JSON со следующей структурой:
{"name":"...","cuisine":"...","description":"...","yield_g":число,
"calories_per_100g":число,"proteins_per_100g":число,"fats_per_100g":число,"carbs_per_100g":число,
"equipment":["оборудование 1","..."],
"ingredients":[{"name":"...","grams":число,"note":"брутто или нетто"}],
"steps":["шаг 1","..."],"plating":"описание подачи","flavor_profile":["вкус1","..."]}"""

async def generate_recipe(cuisine: str, wish: str) -> dict:
    # Агент 1: Шеф-повар создает концепцию
    chef_prompt = f"Придумай концепцию ресторанного блюда по стандартам гидов Michelin и высокой кухни. Кухня: {cuisine}. Пожелания: {wish}. Опиши ингредиенты, шаги и вкусовой профиль."
    r1 = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": SYSTEM_CHEF}, {"role": "user", "content": chef_prompt}]
    )
    draft = r1.choices[0].message.content

    # Агент 2: Технолог-ревизор проверяет по канонам Escoffier, Michelin и Modernist Cuisine
    tech_prompt = f"Проверь этот черновик рецепта по канонам Michelin[span_12](start_span)[span_12](end_span), Escoffier[span_13](start_span)[span_13](end_span) и Modernist Cuisine[span_14](start_span)[span_14](end_span), выверь точные граммовки, КБЖУ и технологию, устрани ошибки и верни готовый JSON:\n{draft}"
    r2 = await client.chat.completions.create(
        model="gpt-4o", response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM_TECH}, {"role": "user", "content": tech_prompt}]
    )
    return json.loads(r2.choices[0].message.content)

async def update_recipe_with_dialogue(current_recipe: dict, history: list, user_message: str) -> dict:
    system = """Ты — шеф-технолог ресторана высокой кухни. Пользователь хочет внести изменения в текущий рецепт в рамках диалога. 
    Учти всю историю обсуждения, стандарты гидов Michelin[span_15](start_span)[span_15](end_span), Escoffier[span_16](start_span)[span_16](end_span) и новое пожелание пользователя. Пересчитай граммовки, шаги или состав, если это требуется.
    Ответ выдай строго в формате JSON с той же структурой:
    {"name":"...","cuisine":"...","description":"...","yield_g":число,
    "calories_per_100g":число,"proteins_per_100g":число,"fats_per_100g":число,"carbs_per_100g":число,
    "equipment":["..."],
    "ingredients":[{"name":"...","grams":число,"note":"..."}],
    "steps":["..."],"plating":"...","flavor_profile":["..."]}"""
    
    messages = [{"role": "system", "content": system}]
    messages.append({"role": "user", "content": f"Текущий рецепт:\n{json.dumps(current_recipe, ensure_ascii=False)}"})
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    
    r = await client.chat.completions.create(
        model="gpt-4o", response_format={"type": "json_object"},
        messages=messages
    )
    return json.loads(r.choices[0].message.content)

async def generate_image(recipe: dict) -> bytes:
    prompt = (
        f"Профессиональная фуд-фотография ресторанного блюда мишленовского уровня: {recipe['name']}. "
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

async def get_substitution(ingredient: str) -> str:
    prompt = f"Предложи 2-3 профессиональных кулинарных аналога мишленовского уровня для ингредиента '{ingredient}' с учетом текстуры, влажности и вкусового профиля (по канонам The Flavor Bible[span_17](start_span)[span_17](end_span) и Escoffier[span_18](start_span)[span_18](end_span)). Дай ответ по-русски."
    r = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": SYSTEM_TECH}, {"role": "user", "content": prompt}]
    )
    return r.choices[0].message.content

async def build_tasting_set(dishes: list[dict], courses: int) -> str:
    brief = "\n".join(f"- {d['name']} ({d['cuisine']}): вкусы {', '.join(d.get('flavor_profile', []))}"
                      for d in dishes)
    prompt = (f"Собери дегустационный сет ресторанного уровня из {courses} подач из этих блюд:\n{brief}\n"
              f"Выстрой логику вкусов (лёгкое→насыщенное, кислотность, текстуры, паузы) по стандартам гастрономических сетов ресторанов Michelin[span_19](start_span)[span_19](end_span). "
              f"Дай порядок подач с обоснованием каждой.")
    r = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": SYSTEM_TECH}, {"role": "user", "content": prompt}]
    )
    return r.choices[0].message.content
    
