import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from openpyxl import Workbook

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

def scale_recipe_data(recipe: dict, new_yield: float) -> dict:
    old_yield = recipe.get("yield_g", 100)
    if old_yield <= 0: old_yield = 100
    factor = new_yield / old_yield
    
    new_r = recipe.copy()
    new_r["yield_g"] = new_yield
    new_scaled_ings = []
    for ing in recipe["ingredients"]:
        ni = ing.copy()
        ni["grams"] = round(ing["grams"] * factor, 1)
        new_scaled_ings.append(ni)
    new_r["ingredients"] = new_scaled_ings
    return new_r

def make_pdf(recipe: dict, photo: bytes | None) -> io.BytesIO:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4; y = h - 45
    c.setFont("DejaVu", 14); c.drawString(50, y, f"ТТК: {recipe['name']}"); y -= 22
    c.setFont("DejaVu", 9)
    c.drawString(50, y, f"Кухня: {recipe['cuisine']} | Выход: {recipe['yield_g']} г"); y -= 16
    
    kbzhu = f"КБЖУ (на 100г): К: {recipe.get('calories_per_100g', 0)} ккал | Б: {recipe.get('proteins_per_100g', 0)}г | Ж: {recipe.get('fats_per_100g', 0)}г | У: {recipe.get('carbs_per_100g', 0)}г"
    c.drawString(50, y, kbzhu); y -= 16

    if photo:
        try:
            c.drawImage(ImageReader(io.BytesIO(photo)), w - 210, y - 130, 150, 150)
        except Exception:
            pass

    eq = recipe.get("equipment", [])
    if eq:
        c.drawString(50, y, "Оборудование: " + ", ".join(eq)); y -= 16

    c.drawString(50, y, "Ингредиенты:"); y -= 14
    for ing in recipe["ingredients"]:
        c.drawString(60, y, f"• {ing['name']} — {ing['grams']} г ({ing.get('note','')})"); y -= 13
        if y < 60: c.showPage(); c.setFont("DejaVu", 9); y = h - 45
        
    y -= 5; c.drawString(50, y, "Технология приготовления:"); y -= 14
    for i, step in enumerate(recipe["steps"], 1):
        for line in [step[j:j+90] for j in range(0, len(step), 90)]:
            c.drawString(60, y, f"{i}. {line}" if line == step[:90] else f"   {line}")
            y -= 13
            if y < 60: c.showPage(); c.setFont("DejaVu", 9); y = h - 45
    y -= 5; c.drawString(50, y, f"Подача: {recipe['plating'][:90]}")
    c.save(); buf.seek(0); return buf

def make_excel(recipe: dict) -> io.BytesIO:
    wb = Workbook(); ws = wb.active; ws.title = "ТТК"
    ws.append([f"ТТК: {recipe['name']}"])
    ws.append([f"Выход: {recipe['yield_g']} г"])
    ws.append([f"КБЖУ (100г): К - {recipe.get('calories_per_100g',0)}, Б - {recipe.get('proteins_per_100g',0)}, Ж - {recipe.get('fats_per_100g',0)}, У - {recipe.get('carbs_per_100g',0)}"])
    if recipe.get("equipment"):
        ws.append([f"Оборудование: {', '.join(recipe['equipment'])}"])
    ws.append([])
    ws.append(["Ингредиент", "Граммы", "Примечание"])
    for ing in recipe["ingredients"]:
        ws.append([ing["name"], ing["grams"], ing.get("note", "")])
    ws.append([]); ws.append(["Технология:"])
    for i, s in enumerate(recipe["steps"], 1): ws.append([f"{i}. {s}"])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0); return buf

def food_cost(recipe: dict, prices: dict) -> str:
    total, lines, missing = 0.0, [], []
    for ing in recipe["ingredients"]:
        price = next((p for k, p in prices.items() if k in ing["name"].lower()), None)
        if price is None:
            missing.append(ing["name"]); continue
        cost = ing["grams"] / 1000 * price
        total += cost
        lines.append(f"• {ing['name']}: {ing['grams']} г × {price}/кг = {cost:.2f}")
    text = f"💰 Себестоимость «{recipe['name']}»:\n" + "\n".join(lines)
    text += f"\n\nИтого: {total:.2f}"
    text += f"\n📊 Цена в меню при food cost 30%: {total/0.3:.2f}"
    if missing: text += "\n\n⚠️ Нет цен на: " + ", ".join(missing)
    return text

def shopping_list(recipes: list[dict]) -> str:
    agg = {}
    for r in recipes:
        for ing in r["ingredients"]:
            agg[ing["name"]] = agg.get(ing["name"], 0) + ing["grams"]
    lines = [f"• {name} — {g} г" for name, g in sorted(agg.items())]
    return "🛒 Список закупок:\n" + "\n".join(lines)
    
