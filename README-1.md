# Zargarlik Hisob-kitob Boti

Kunlik oltin/mahsulot aylanishini kuzatish uchun Telegram bot:
- ➕ Jarayonga olingan (ishlab chiqarishga berilgan tilla)
- ↩️ Vazvrat (ishlatilmay qaytgan)
- ✅ Tayyor mahsulot
- 📊 Avtomatik qoldiq: `Jarayonga olingan − (Vazvrat + Tayyor mahsulot)`

## 1. Bot token olish
1. Telegram'da **@BotFather** ga yozing.
2. `/newbot` buyrug'ini yuboring, bot uchun nom va username bering.
3. Sizga beriladigan **token**ni saqlab qo'ying (masalan: `123456789:AAExample...`).

## 2. O'zingizning Telegram ID'ingizni bilish
1. Telegram'da **@userinfobot** ga yozing — u sizga ID raqamingizni beradi.
2. Shu raqamni keyinroq `ADMIN_ID` sifatida ishlatasiz (faqat siz botdan foydalanishingiz uchun — boshqa hech kim yozolmaydi).

## 3. Railway'ga joylashtirish
1. https://railway.app ga kiring, GitHub akkountingiz bilan ro'yxatdan o'ting.
2. Ushbu papkadagi fayllarni (`bot.py`, `requirements.txt`, `Procfile`) GitHub'da yangi repository'ga yuklang.
3. Railway'da **"New Project" → "Deploy from GitHub repo"** tugmasini bosing, repositoryingizni tanlang.
4. Loyihaga kirib, **Variables** bo'limiga o'ting va quyidagilarni qo'shing:
   - `BOT_TOKEN` = @BotFather'dan olgan tokeningiz
   - `ADMIN_ID` = sizning Telegram ID'ingiz
5. Railway avtomatik ravishda `requirements.txt`ni o'rnatadi va `Procfile`dagi buyruq orqali botni ishga tushiradi.
6. Bir necha soniyadan so'ng Telegram'da botingizga `/start` deb yozing — ishlashi kerak.

> **Eslatma:** SQLite bazasi (`zargarlik.db`) konteyner ichida saqlanadi. Railway konteynerni qayta ishga tushirganda (deploy, restart) fayl saqlanib qoladi, lekin agar butunlay o'chirib qayta yaratsangiz, ma'lumot yo'qolishi mumkin. Muhim bo'lsa, keyinchalik Railway'ning "Volume" (doimiy xotira) xizmatini ulash tavsiya etiladi — so'rasangiz shuni ham sozlab beraman.

## 4. Botdan foydalanish
- `/start` — asosiy menyuni ochadi
- Tugmalar orqali: miqdorni gramm hisobida kiritasiz, so'ng izoh yozasiz yoki `/skip` bilan o'tkazib yuborasiz
- `/balance` — joriy qoldiqni ko'rsatadi
- `/undo` — oxirgi kiritilgan yozuvni o'chiradi (xato kiritilsa)
- `/cancel` — joriy amalni bekor qiladi

## Mahalliy sinov qilish (ixtiyoriy)
```bash
pip install -r requirements.txt
export BOT_TOKEN="tokeningiz"
export ADMIN_ID="sizning_id"
python bot.py
```
