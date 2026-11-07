import json
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import ai, db, docs

router = Router()
last = {}        # Последний рецепт {user_id: (recipe, photo_bytes)}
histories = {}   # История диалога для правок {user_id: [{"role": "...", "content": "..."}, ...]}

class New(StatesGroup):
    cuisine = State(); wish = State()

class RecipeEdit(StatesGroup):
    chat = State()

class Prices(StatesGroup):
    wait = State()

HELP = """🍽 Шеф-бот (Агент Шеф + Технолог). Команды:
/new — придумать блюдо (Двухагентный генератор)
/img — сгенерировать фото последнего блюда
/save — сохранить блюдо с фото
/my — мои блюда
/ttk <id> — ТТК в PDF + Excel
/scale <id> <вес> — пересчитать граммовки под новый выход
/sub <ингредиент> — подобрать кулинарный аналог
/cook <id> — интерактивный пошаговый режим готовки
/prices — внести цены продуктов
/cost <id> — себестоимость (с автопоиском цен в Украине через Serper)
/set <id> <id> ... — дегустационный сет
/shop <id> <id> ... — список закупок"""

def get_recipe_keyboard(rid: int = None):
    buttons = [
        [
            InlineKeyboardButton(text="🖼 Фото", callback_data="act_img"),
            InlineKeyboardButton(text="💾 Сохранить", callback_data="act_save")
        ],
        [
            InlineKeyboardButton(text="💬 Изменить с ИИ", callback_data="act_start_chat")
        ]
    ]
    if rid:
        buttons.append([
            InlineKeyboardButton(text="💰 Себестоимость", callback_data=f"act_cost:{rid}"),
            InlineKeyboardButton(text="🖨 ТТК (PDF/Excel)", callback_data=f"act_ttk:{rid}")
        ])
        buttons.append([
            InlineKeyboardButton(text="👨‍🍳 Режим готовки", callback_data=f"act_cook:{rid}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

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
    await m.answer("👨‍🍳 Шеф-повар создает концепцию, а технолог-ревизор проверяет технологию и КБЖУ...")
    
    r = await ai.generate_recipe(data["cuisine"], m.text)
    last[m.from_user.id] = (r, None)
    histories[m.from_user.id] = []
    
    await send_recipe_card(m, r)

async def send_recipe_card(message: Message, r: dict):
    ings = "\n".join(f"• {i['name']} — {i['grams']} г" for i in r["ingredients"])
    eq = ", ".join(r.get("equipment", []))
    kbzhu = f"КБЖУ (на 100г): К: {r.get('calories_per_100g', 0)} ккал | Б: {r.get('proteins_per_100g', 0)}г | Ж: {r.get('fats_per_100g', 0)}г | У: {r.get('carbs_per_100g', 0)}г"
    
    await message.answer(
        f"✨ <b>{r['name']}</b>\n{r['description']}\n\n"
        f"Выход: {r['yield_g']} г\n{kbzhu}\n\n"
        f"⚙️ <b>Оборудование:</b> {eq}\n\n"
        f"<b>Ингредиенты:</b>\n{ings}\n\n"
        f"🎨 <b>Подача:</b> {r['plating']}",
        parse_mode="HTML",
        reply_markup=get_recipe_keyboard()
    )

@router.callback_query(F.data == "act_start_chat")
async def cb_start_chat(cq: CallbackQuery, state: FSMContext):
    if cq.from_user.id not in last:
        return await cq.answer("Сначала создайте блюдо через /new", show_alert=True)
    await state.set_state(RecipeEdit.chat)
    await cq.message.answer("💬 **Режим диалога с технологом активен**\nНапишите, что именно изменить в рецепте (например: *«сделай соус острее», «замени рыбу на курицу», «уменьши калорийность»*). Для выхода из режима отправьте /cancel или любую другую команду.", parse_mode="Markdown")
    await cq.answer()

@router.message(RecipeEdit.chat, Command("cancel"))
async def cancel_chat(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("✅ Режим диалога завершен.")

@router.message(RecipeEdit.chat)
async def handle_recipe_chat(m: Message, state: FSMContext):
    uid = m.from_user.id
    if uid not in last:
        await state.clear()
        return await m.answer("Активный рецепт не найден.")
    
    current_recipe, photo = last[uid]
    user_text = m.text
    
    await m.answer("🔄 Технолог пересчитывает рецепт с учетом ваших пожеланий...")
    
    history = histories.get(uid, [])
    history.append({"role": "user", "content": user_text})
    
    try:
        updated_recipe = await ai.update_recipe_with_dialogue(current_recipe, history, user_text)
        history.append({"role": "assistant", "content": json.dumps(updated_recipe, ensure_ascii=False)})
        histories[uid] = history
        last[uid] = (updated_recipe, photo)
        
        await m.answer("✅ Рецепт успешно обновлен!")
        await send_recipe_card(m, updated_recipe)
    except Exception as e:
        await m.answer(f"Не удалось обновить рецепт: {str(e)}")

@router.message(Command("scale"))
async def scale_cmd(m: Message, command: CommandObject):
    args = (command.args or "").split()
    if len(args) < 2 or not args[0].isdigit() or not args[1].replace('.', '', 1).isdigit():
        return await m.answer("Использование: /scale <id> <новый выход в граммах>\nПример: /scale 2 500")
    rid = int(args[0])
    new_yield = float(args[1])
    r, _ = db.get_recipe(m.from_user.id, rid)
    if not r: return await m.answer("Рецепт не найден.")
    
    scaled = docs.scale_recipe_data(r, new_yield)
    ings = "\n".join(f"• {i['name']} — {i['grams']} г" for i in scaled["ingredients"])
    await m.answer(f"⚖️ <b>Пересчет рецепта: {scaled['name']}</b>\nНовый выход: {scaled['yield_g']} г\n\n<b>Ингредиенты:</b>\n{ings}", parse_mode="HTML")

@router.message(Command("sub"))
async def sub_cmd(m: Message, command: CommandObject):
    if not command.args:
        return await m.answer("Укажите ингредиент для поиска аналогов:\nПример: /sub трюфельное масло")
    ingredient = command.args
    await m.answer(f"🔍 Подбираю профессиональные аналоги для «{ingredient}»...")
    ans = await ai.get_substitution(ingredient)
    await m.answer(f"🔄 <b>Аналоги для: {ingredient}</b>\n\n{ans}", parse_mode="HTML")

@router.message(Command("cook"))
async def cook_cmd(m: Message, command: CommandObject):
    args = (command.args or "").split()
    if not args or not args[0].isdigit():
        return await m.answer("Укажите ID рецепта: /cook <id>")
    rid = int(args[0])
    r, _ = db.get_recipe(m.from_user.id, rid)
    if not r: return await m.answer("Рецепт не найден.")
    steps = r["steps"]
    if not steps: return await m.answer("В рецепте нет шагов.")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Далее", callback_data=f"cook:{rid}:1")]
    ])
    await m.answer(
        f"👨‍🍳 <b>Режим готовки: {r['name']}</b>\nШаг 1 из {len(steps)}\n\n{steps[0]}",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("cook:"))
async def cook_callback(cq: CallbackQuery):
    _, rid_str, step_idx_str = cq.data.split(":")
    rid = int(rid_str); idx = int(step_idx_str)
    r, _ = db.get_recipe(cq.from_user.id, rid)
    if not r: return await cq.answer("Рецепт не найден", show_alert=True)
    steps = r["steps"]
    
    buttons = []
    row = []
    if idx > 0: row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"cook:{rid}:{idx-1}"))
    if idx < len(steps) - 1: row.append(InlineKeyboardButton(text="▶️ Далее", callback_data=f"cook:{rid}:{idx+1}"))
    if row: buttons.append(row)
    
    await cq.message.edit_text(
        f"👨‍🍳 <b>Режим готовки: {r['name']}</b>\nШаг {idx+1} из {len(steps)}\n\n{steps[idx]}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await cq.answer()

@router.callback_query(F.data == "act_img")
async def cb_img(cq: CallbackQuery):
    if cq.from_user.id not in last:
        return await cq.answer("Сначала создайте блюдо через /new", show_alert=True)
    await cq.message.answer("🖼 Генерирую фото...")
    recipe, _ = last[cq.from_user.id]
    try:
        photo = await ai.generate_image(recipe)
        last[cq.from_user.id] = (recipe, photo)
        await cq.message.answer_photo(BufferedInputFile(photo, filename="dish.png"), caption=recipe["name"])
    except Exception as e:
        await cq.message.answer(f"Не удалось создать фото: {str(e)[:200]}")
    await cq.answer()

@router.callback_query(F.data == "act_save")
async def cb_save(cq: CallbackQuery):
    if cq.from_user.id not in last:
        return await cq.answer("Сначала создайте блюдо через /new", show_alert=True)
    r, photo = last[cq.from_user.id]
    rid = db.save_recipe(cq.from_user.id, r, photo)
    await cq.message.answer(f"💾 Рецепт сохранен в базу! ID = {rid}\nТеперь доступны ТТК и себестоимость.", reply_markup=get_recipe_keyboard(rid))
    await cq.answer()

async def process_cost_request(message: Message, user_id: int, rid: int):
    r, _ = db.get_recipe(user_id, rid)
    if not r:
        return await message.answer("Рецепт не найден.")
    
    local_prices = db.get_prices(user_id)
    text, missing = docs.food_cost(r, local_prices)
    
    if missing:
        await message.answer(f"🔍 Ищу актуальные рыночные цены в Украине через Serper для: {', '.join(missing)}...")
        web_prices = await ai.estimate_missing_prices(missing)
        text, still_missing = docs.food_cost(r, local_prices, web_prices)
        if still_missing:
            text += f"\n\n⚠️ Не удалось найти цены на: {', '.join(still_missing)}"
            
    await message.answer(text)

@router.callback_query(F.data.startswith("act_cost:"))
async def cb_cost(cq: CallbackQuery):
    rid = int(cq.data.split(":")[1])
    await process_cost_request(cq.message, cq.from_user.id, rid)
    await cq.answer()

@router.message(Command("cost"))
async def cost(m: Message, command: CommandObject):
    rid = int(command.args or 0)
    if not rid: return await m.answer("Не найдено. /cost <id>")
    await process_cost_request(m, m.from_user.id, rid)

@router.callback_query(F.data.startswith("act_ttk:"))
async def cb_ttk(cq: CallbackQuery):
    rid = int(cq.data.split(":")[1])
    r, photo = db.get_recipe(cq.from_user.id, rid)
    if r:
        await cq.message.answer_document(BufferedInputFile(docs.make_pdf(r, photo).read(), f"TTK_{r['name']}.pdf"))
        await cq.message.answer_document(BufferedInputFile(docs.make_excel(r).read(), f"TTK_{r['name']}.xlsx"))
    await cq.answer()

@router.callback_query(F.data.startswith("act_cook:"))
async def cb_cook_start(cq: CallbackQuery):
    rid = int(cq.data.split(":")[1])
    r, _ = db.get_recipe(cq.from_user.id, rid)
    if not r or not r.get("steps"):
        return await cq.answer("Шаги не найдены", show_alert=True)
    steps = r["steps"]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="▶️ Далее", callback_data=f"cook:{rid}:1")]])
    await cq.message.answer(
        f"👨‍🍳 <b>Режим готовки: {r['name']}</b>\nШаг 1 из {len(steps)}\n\n{steps[0]}",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await cq.answer()

@router.message(Command("img"))
async def img(m: Message):
    if m.from_user.id not in last:
        return await m.answer("Сначала создайте блюдо командой /new")
    await m.answer("🖼 Генерирую фото...")
    recipe, _ = last[m.from_user.id]
    try:
        photo = await ai.generate_image(recipe)
        last[m.from_user.id] = (recipe, photo)
        await m.answer_photo(BufferedInputFile(photo, filename="dish.png"), caption=recipe["name"])
    except Exception as e:
        await m.answer(f"Не удалось создать фото: {str(e)[:300]}")

@router.message(Command("save"))
async def save(m: Message):
    if m.from_user.id not in last: return await m.answer("Сначала /new")
    r, photo = last[m.from_user.id]
    rid = db.save_recipe(m.from_user.id, r, photo)
    await m.answer(f"💾 Сохранено, id = {rid}", reply_markup=get_recipe_keyboard(rid))

@router.message(Command("my"))
async def my(m: Message):
    rows = db.list_recipes(m.from_user.id)
    await m.answer("📚 Мои блюда:\n" + "\n".join(f"ID {i}. {n}" for i, n in rows) if rows else "Пусто")

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
    
