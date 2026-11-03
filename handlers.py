from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, BufferedInputFile
import ai, db, docs

router = Router()
last = {}   # последний сгенерированный рецепт {user_id: (recipe, photo_bytes)}

class New(StatesGroup):
    cuisine = State(); wish = State()

class Prices(StatesGroup):
    wait = State()

HELP = """🍽 Шеф-бот. Команды:
/new — придумать блюдо (ИИ)
/img — сгенерировать фото последнего блюда
/save — сохранить блюдо с фото
/my — мои блюда
/ttk <id> — ТТК в PDF + Excel
/prices — внести цены продуктов
/cost <id> — себестоимость и food cost
/set <id> <id> ... — дегустационный сет
/shop <id> <id> ... — список закупок"""

@router.message(Command("start"))
async def start(m: Message): await m.answer(HELP)

@router.message(Command("new"))
async def new(m: Message, state: FSMContext):
    await state.set_state(New.cuisine)
    await m.answer("Какая национальная кухня? (например: японская, французская)")

@router.message(New.cuisine)
async def got_cuisine(m: Message, state: FSMContext):
    await state.update_data(cuisine=m.text); await state.set_state(New.wish)
    await m.answer("Пожелания? (ингредиенты, сезон, тип блюда — или «на твой вкус»)")

@router.message(New.wish)
async def got_wish(m: Message, state: FSMContext):
    data = await state.get_data(); await state.clear()
    await m.answer("👨‍🍳 Придумываю блюдо...")
    r = await ai.generate_recipe(data["cuisine"], m.text)
    last[m.from_user.id] = (r, None)
    ings = "\n".join(f"• {i['name']} — {i['grams']} г" for i in r["ingredients"])
    steps = "\n".join(f"{n}. {s}" for n, s in enumerate(r["steps"], 1))
    await m.answer(f"✨ <b>{r['name']}</b>\n{r['description']}\n\n"
                   f"Выход: {r['yield_g']} г\n\n<b>Ингредиенты:</b>\n{ings}\n\n"
                   f"<b>Технология:</b>\n{steps}\n\n🎨 {r['plating']}\n\n"
                   f"/img — фото, /save — сохранить", parse_mode="HTML")

@router.message(Command("img"))
async def img(m: Message):
    if m.from_user.id not in last: return await m.answer("Сначала /new")
    await m.answer("🖼 Генерирую фото...")
    r, _ = last[m.from_user.id]
    photo = await ai.generate_image(r)
    last[m.from_user.id] = (r, photo)
    await m.answer_photo(BufferedInputFile(photo, "dish.png"), caption=r["name"])

@router.message(Command("save"))
async def save(m: Message):
    if m.from_user.id not in last: return await m.answer("Сначала /new")
    r, photo = last[m.from_user.id]
    rid = db.save_recipe(m.from_user.id, r, photo)
    await m.answer(f"💾 Сохранено, id = {rid}")

@router.message(Command("my"))
async def my(m: Message):
    rows = db.list_recipes(m.from_user.id)
    await m.answer("📚 Мои блюда:\n" + "\n".join(f"{i}. {n}" for i, n in rows) if rows else "Пусто")

@router.message(Command("ttk"))
async def ttk(m: Message, command: CommandObject):
    r, photo = db.get_recipe(m.from_user.id, int(command.args or 0))
    if not r: return await m.answer("Не найдено. /ttk <id>")
    await m.answer_document(BufferedInputFile(docs.make_pdf(r, photo).read(), f"TTK_{r['name']}.pdf"))
    await m.answer_document(BufferedInputFile(docs.make_excel(r).read(), f"TTK_{r['name']}.xlsx"))

@router.message(Command("prices"))
async def prices(m: Message, state: FSMContext):
    await state.set_state(Prices.wait)
    await m.answer("Пришли цены (за кг), по одной на строку:\nлосось 1200\nтрюфель 90000")

@router.message(Prices.wait)
async def got_prices(m: Message, state: FSMContext):
    n = 0
    for line in m.text.splitlines():
        parts = line.rsplit(maxsplit=1)
        if len(parts) == 2:
            try: db.set_price(m.from_user.id, parts[0], float(parts[1])); n += 1
            except ValueError: pass
    await state.clear(); await m.answer(f"✅ Сохранено цен: {n}")

@router.message(Command("cost"))
async def cost(m: Message, command: CommandObject):
    r, _ = db.get_recipe(m.from_user.id, int(command.args or 0))
    if not r: return await m.answer("Не найдено. /cost <id>")
    await m.answer(docs.food_cost(r, db.get_prices(m.from_user.id)))

@router.message(Command("set"))
async def tasting(m: Message, command: CommandObject):
    ids = [int(x) for x in (command.args or "").split() if x.isdigit()]
    dishes = [db.get_recipe(m.from_user.id, i)[0] for i in ids]
    dishes = [d for d in dishes if d]
    if len(dishes) < 2: return await m.answer("Нужно минимум 2 id: /set 1 2 3")
    await m.answer("🍷 Собираю сет...")
    await m.answer(await ai.build_tasting_set(dishes, len(dishes)))

@router.message(Command("shop"))
async def shop(m: Message, command: CommandObject):
    ids = [int(x) for x in (command.args or "").split() if x.isdigit()]
    recipes = [db.get_recipe(m.from_user.id, i)[0] for i in ids]
    recipes = [r for r in recipes if r]
    if not recipes: return await m.answer("Укажи id: /shop 1 2")
    await m.answer(docs.shopping_list(recipes))
