# Telegram Stars PDF satış botu

Bu layihə Telegram Stars (`XTR`) ilə 900 Stars qiymətinə PDF kitab satmaq üçün nümunə botdur. Qiyməti `.env` faylında dəyişə bilərsiniz.

## Fayllar
- `bot.py` — bot kodu
- `.env.example` — konfiqurasiya nümunəsi
- `requirements.txt` — Python paketləri
- `book.pdf` — sizin göndərdiyiniz mətndən hazırlanmış PDF kitab

## Quraşdırma (Linux server)

1. Python 3.10+ quraşdırın.
2. Layihə qovluğunda virtual mühit yaradın və paketləri quraşdırın:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

3. `.env` faylını açın. `BOT_TOKEN=TOKENINIZI_BURAYA_YAZIN` sətrindəki nümunə mətni silib BotFather tokeninizi yazın. Tokeni heç kimlə paylaşmayın.
4. `PRODUCT_PRICE_STARS=900` dəyərini istədiyiniz qiymətə dəyişə bilərsiniz.
5. `book.pdf` faylının layihə qovluğunda olduğuna əmin olun.
6. Botu başladın:

```bash
python bot.py
```

## Daimi işlətmək
Daimi serverdə botun restart zamanı yenidən başlaması üçün `systemd` və ya server provayderinin process manager funksiyasından istifadə edin. Serverinizdəki dəqiq qovluq yolları və istifadəçi hesabı üzrə xidmət faylını uyğunlaşdırmaq lazımdır.

## Ödəniş axını
- `/start` məhsul təsvirini və “Kitabı al — 900 ⭐” düyməsini göstərir.
- Düymə Telegram Stars invoice açır.
- `pre_checkout_query` payload, currency və məbləği yoxlayır.
- `successful_payment` uğurlu ödənişi yoxlayır.
- SQLite ödəniş charge ID-lərini saxlayır və eyni charge üçün təkrar çatdırılmanı bloklayır.
- Bot PDF-i alıcıya göndərir.

## Qeydlər
- Bu kod nümunəsi real Telegram hesabında canlı ödənişlə sınaqdan keçirilməyib; satışdan əvvəl test edin.
- Ödəniş uğurlu olduğu halda fayl göndərilməsi texniki səbəbdən uğursuz olarsa, logları yoxlayın və ödənişi təsdiqlədikdən sonra dəstək vasitəsilə problemi həll edin.
- Tokeni `.env` daxilində saxlayın və bu faylı ictimai repozitoriyaya yükləməyin.
