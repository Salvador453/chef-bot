import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from openpyxl import Workbook

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

def make_pdf(recipe: dict, photo: bytes | None) -> io.BytesIO:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4; y = h - 50
    c.setFont("DejaVu", 16); c.drawString(50, y, f"ТТК: {recipe['name']}"); y -= 25
    c.setFont("DejaVu", 10)
    c.drawString(50, y, f"Кухня: {recipe['cuisine']} | Выход: {recipe['yield_g']} г"); y -= 20
    if photo:
        c.drawImage(ImageReader(io.BytesIO(photo)), w - 230, y - 160, 180, 180); 
    c.drawString(50, y, "Ингредиенты:"); y -= 15
    for ing in recipe["ingredients"]:
        c.drawString(60, y, f"• {ing['name']} — {ing['grams']} г ({ing.get('note','')})"); y -= 14
    y -= 10; c.drawString(50, y, "Технология:"); y -= 15
    for i, step in enumerate(recipe["steps"], 1):
        for line in [step[j:j+90] for j in range(0, len(step), 90)]:
            c.drawString(60, y, f"{i}. {line}" if line == step[:90] else f"   {line}")
            y -= 14
            if y < 60: c.showPage(); c.setFont("DejaVu", 10); y = h - 50
    y -= 10; c.drawString(50, y, f"Подача: {recipe['plating'][:90]}")
    c.save(); buf.seek(0); return buf

def make_excel(recipe: dict) -> io.BytesIO:
    wb = Workbook(); ws = wb.active; ws.title = "ТТК"
    ws.append([f"ТТК: {recipe['name']}"]); ws.append([f"Выход: {recipe['yield_g']} г"])
    ws.append([]); ws.append(["Ингредиент", "Граммы", "Примечание"])
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
